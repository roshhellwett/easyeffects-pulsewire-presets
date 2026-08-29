"""
REST API handlers for the ProjectPulsewire local web dashboard.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote

from projectpulsewire import __version__
from projectpulsewire import presets as presets_mod
from projectpulsewire import irs_handler as irs_mod
from projectpulsewire import deps_installer as deps_mod

logger = logging.getLogger(__name__)


def _format_bytes(size_bytes: int) -> str:
    """Format bytes to human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


class ApiHandler:
    """Dispatches API requests to underlying projectpulsewire core modules."""

    @staticmethod
    def get_status() -> Dict[str, Any]:
        """Return system and audio stack overview."""
        active_source = presets_mod.get_active_preset_source()
        available_sources = presets_mod.get_available_preset_sources()
        all_presets = presets_mod.get_all_presets()
        installed_presets = presets_mod.get_installed_presets()
        all_irs = irs_mod.get_all_irs()
        installed_irs = irs_mod.get_installed_irs()

        ee_dir = presets_mod.get_easyeffects_presets_dir()
        convolver_dir = irs_mod.get_easyeffects_convolver_dir()
        distro_family, distro_name = deps_mod.detect_distro()
        pipewire_running = deps_mod.check_pipewire_running()
        ee_version = deps_mod.check_easyeffects_version()

        # Update cache check
        from projectpulsewire import cli as cli_mod
        update_cache = cli_mod.load_update_cache()
        latest_version = update_cache.get("last_known_version", "Unknown")
        has_update = False
        if latest_version != "Unknown":
            has_update = cli_mod._is_newer_version(__version__, latest_version)

        return {
            "version": __version__,
            "latest_version": latest_version,
            "has_update": has_update,
            "active_source": active_source,
            "available_sources": available_sources,
            "presets_total": len(all_presets),
            "presets_installed": len(installed_presets),
            "irs_total": len(all_irs),
            "irs_installed": len(installed_irs),
            "presets_dir": str(ee_dir) if ee_dir else "Not detected",
            "convolver_dir": str(convolver_dir) if convolver_dir else "Not detected",
            "distro_family": distro_family,
            "distro_name": distro_name,
            "pipewire_running": pipewire_running,
            "easyeffects_version": ee_version,
        }

    @staticmethod
    def get_presets(query_params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Return list of presets with optional category/source/search filtering."""
        source_param = query_params.get("source", [None])[0]
        category_param = query_params.get("category", [None])[0]
        installed_only = query_params.get("installed_only", ["false"])[0].lower() in ("true", "1", "yes")
        search_param = query_params.get("search", [""])[0].strip().lower()

        active_source = presets_mod.get_active_preset_source()
        target_source = source_param or active_source

        all_presets = presets_mod.get_all_presets(preset_source=target_source)
        installed = set(presets_mod.get_installed_presets())
        categories_dict = presets_mod.get_presets_by_category(all_presets)

        category_counts = {cat: len(items) for cat, items in categories_dict.items()}

        results = []
        for preset in all_presets:
            p_name = preset["name"]
            is_installed = p_name in installed

            if installed_only and not is_installed:
                continue

            # Identify category
            preset_category = "Other"
            for cat, items in categories_dict.items():
                if any(item["name"] == p_name for item in items):
                    preset_category = cat
                    break

            if category_param and category_param.lower() != "all" and preset_category.lower() != category_param.lower():
                continue

            if search_param and search_param not in p_name.lower():
                continue

            data = preset.get("data", {})
            output = data.get("output", {})
            plugins_order = output.get("plugins_order", [])

            results.append({
                "name": p_name,
                "filename": preset.get("filename", ""),
                "source": preset.get("source", target_source),
                "category": preset_category,
                "installed": is_installed,
                "plugin_count": len(plugins_order),
                "plugins_order": plugins_order,
            })

        return {
            "active_source": active_source,
            "available_sources": presets_mod.get_available_preset_sources(),
            "categories": category_counts,
            "total_count": len(all_presets),
            "installed_count": len(installed),
            "filtered_count": len(results),
            "presets": results,
        }

    @staticmethod
    def get_preset_detail(name: str) -> Optional[Dict[str, Any]]:
        """Return comprehensive preset detail including signal chain data."""
        preset = presets_mod.get_preset_by_name(name)
        if not preset:
            return None

        installed = presets_mod.is_preset_installed(name)
        data = preset.get("data", {})
        output = data.get("output", {})
        plugins_order = output.get("plugins_order", [])

        # Extract details per plugin in the chain
        plugin_details = []
        for plugin_name in plugins_order:
            plugin_cfg = output.get(plugin_name, {})
            plugin_details.append({
                "name": plugin_name,
                "config": plugin_cfg,
            })

        return {
            "name": preset["name"],
            "filename": preset.get("filename"),
            "path": preset.get("path"),
            "source": preset.get("source"),
            "installed": installed,
            "plugins_order": plugins_order,
            "plugin_details": plugin_details,
            "raw_data": data,
        }

    @staticmethod
    def install_presets(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Install single, multiple, or all uninstalled presets."""
        names = payload.get("names") or ([payload["name"]] if payload.get("name") else [])
        all_uninstalled = payload.get("all_uninstalled", False)

        all_presets = presets_mod.get_all_presets()
        installed = set(presets_mod.get_installed_presets())

        if all_uninstalled:
            targets = [p for p in all_presets if p["name"] not in installed]
        elif names:
            name_set = {n.lower() for n in names}
            targets = [p for p in all_presets if p["name"].lower() in name_set]
        else:
            return {"success": False, "message": "No presets specified for installation"}

        if not targets:
            return {"success": True, "message": "No new presets to install"}

        success, message = presets_mod.install_multiple_presets(targets)
        return {
            "success": success,
            "message": message,
            "count": len(targets),
        }

    @staticmethod
    def remove_presets(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Remove single, multiple, or all presets."""
        names = payload.get("names") or ([payload["name"]] if payload.get("name") else [])
        all_presets_flag = payload.get("all", False)

        installed = presets_mod.get_installed_presets()

        if all_presets_flag:
            targets = list(installed)
        elif names:
            targets = [n for n in names if n in installed or presets_mod.is_preset_installed(n)]
        else:
            return {"success": False, "message": "No presets specified for removal"}

        if not targets:
            return {"success": False, "message": "None of the specified presets are currently installed"}

        success, message = presets_mod.remove_multiple_presets(targets)
        return {
            "success": success,
            "message": message,
            "count": len(targets),
        }

    @staticmethod
    def set_preset_source(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Switch active preset source (modernpresets vs legacypresets)."""
        source = payload.get("source", "")
        if not source:
            return {"success": False, "message": "Missing preset source"}

        success = presets_mod.set_active_preset_source(source)
        if success:
            return {
                "success": True,
                "active_source": presets_mod.get_active_preset_source(),
                "message": f"Switched preset source to '{presets_mod.get_active_preset_source()}'",
            }
        else:
            return {
                "success": False,
                "message": f"Invalid preset source '{source}'. Available: {presets_mod.get_available_preset_sources()}",
            }

    @staticmethod
    def get_irs(query_params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Return list of IRS files with optional category/search filtering."""
        category_param = query_params.get("category", [None])[0]
        installed_only = query_params.get("installed_only", ["false"])[0].lower() in ("true", "1", "yes")
        search_param = query_params.get("search", [""])[0].strip().lower()

        all_irs = irs_mod.get_all_irs()
        installed = set(irs_mod.get_installed_irs())
        categories_dict = irs_mod.get_irs_by_category(all_irs)

        category_counts = {cat: len(items) for cat, items in categories_dict.items()}

        results = []
        for irs in all_irs:
            name = irs["name"]
            is_installed = name in installed

            if installed_only and not is_installed:
                continue

            # Identify category
            irs_category = "Other"
            for cat, items in categories_dict.items():
                if any(item["name"] == name for item in items):
                    irs_category = cat
                    break

            if category_param and category_param.lower() != "all" and irs_category.lower() != category_param.lower():
                continue

            if search_param and search_param not in name.lower():
                continue

            size_bytes = irs.get("size", 0)
            results.append({
                "name": name,
                "filename": irs.get("filename", ""),
                "size": size_bytes,
                "size_formatted": _format_bytes(size_bytes),
                "category": irs_category,
                "category_desc": irs_mod.get_irs_category_description(irs_category),
                "use_guide": irs_mod.get_irs_use_guide(name),
                "installed": is_installed,
            })

        return {
            "categories": category_counts,
            "total_count": len(all_irs),
            "installed_count": len(installed),
            "filtered_count": len(results),
            "irs": results,
        }

    @staticmethod
    def get_irs_detail(name: str) -> Optional[Dict[str, Any]]:
        """Return IRS metadata and usage recommendations."""
        irs = irs_mod.get_irs_by_name(name)
        if not irs:
            return None

        installed = irs_mod.is_irs_installed(name)
        categories_dict = irs_mod.get_irs_by_category([irs])
        cat = next(iter(categories_dict.keys()), "Other")

        return {
            "name": irs["name"],
            "filename": irs.get("filename"),
            "path": irs.get("path"),
            "size": irs.get("size", 0),
            "size_formatted": _format_bytes(irs.get("size", 0)),
            "category": cat,
            "category_desc": irs_mod.get_irs_category_description(cat),
            "use_guide": irs_mod.get_irs_use_guide(name),
            "installed": installed,
        }

    @staticmethod
    def install_irs(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Install single, multiple, or all uninstalled IRS files."""
        names = payload.get("names") or ([payload["name"]] if payload.get("name") else [])
        all_uninstalled = payload.get("all_uninstalled", False)

        all_irs = irs_mod.get_all_irs()
        installed = set(irs_mod.get_installed_irs())

        if all_uninstalled:
            targets = [i for i in all_irs if i["name"] not in installed]
        elif names:
            name_set = {n.lower() for n in names}
            targets = [i for i in all_irs if i["name"].lower() in name_set]
        else:
            return {"success": False, "message": "No IRS files specified for installation"}

        if not targets:
            return {"success": True, "message": "No new IRS files to install"}

        success, message = irs_mod.install_multiple_irs(targets)
        return {
            "success": success,
            "message": message,
            "count": len(targets),
        }

    @staticmethod
    def remove_irs(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Remove single, multiple, or all IRS files."""
        names = payload.get("names") or ([payload["name"]] if payload.get("name") else [])
        all_irs_flag = payload.get("all", False)

        installed = irs_mod.get_installed_irs()

        if all_irs_flag:
            targets = list(installed)
        elif names:
            targets = [n for n in names if n in installed or irs_mod.is_irs_installed(n)]
        else:
            return {"success": False, "message": "No IRS files specified for removal"}

        if not targets:
            return {"success": False, "message": "None of the specified IRS files are currently installed"}

        success, message = irs_mod.remove_multiple_irs(targets)
        return {
            "success": success,
            "message": message,
            "count": len(targets),
        }

    @staticmethod
    def get_audio_stack() -> Dict[str, Any]:
        """Return audio stack packages, status, distro detection, and install commands."""
        distro_family, distro_name = deps_mod.detect_distro()
        packages = deps_mod.get_all_package_status(distro_family)
        missing = deps_mod.get_missing_packages(distro_family)
        critical_missing = deps_mod.get_missing_packages(distro_family, critical_only=True)
        install_cmd = deps_mod.get_install_command(distro_family, missing) if missing else None

        pipewire_running = deps_mod.check_pipewire_running()
        ee_version = deps_mod.check_easyeffects_version()

        return {
            "distro_family": distro_family,
            "distro_name": distro_name,
            "pipewire_running": pipewire_running,
            "easyeffects_version": ee_version,
            "packages": packages,
            "missing_packages": missing,
            "critical_missing": critical_missing,
            "install_command": install_cmd,
            "is_complete": len(missing) == 0,
        }

    @staticmethod
    def install_audio_stack(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger dependency installation."""
        distro_family, _ = deps_mod.detect_distro()
        packages = payload.get("packages") or deps_mod.get_missing_packages(distro_family)

        if not packages:
            return {"success": True, "message": "All required audio stack packages are already installed"}

        success, message = deps_mod.install_missing_packages(distro_family, packages)
        return {"success": success, "message": message}

    @staticmethod
    def get_updates() -> Dict[str, Any]:
        """Check PyPI for newer versions."""
        from projectpulsewire import cli as cli_mod
        current_version = cli_mod.get_current_installed_version()
        latest_version = "Unknown"
        error_msg = None

        try:
            latest_version = cli_mod.fetch_latest_version_from_pypi()
        except Exception as e:
            error_msg = str(e)

        has_update = False
        if latest_version != "Unknown":
            has_update = cli_mod._is_newer_version(current_version, latest_version)

        return {
            "current_version": current_version,
            "latest_version": latest_version,
            "has_update": has_update,
            "error": error_msg,
        }

    @staticmethod
    def perform_upgrade() -> Dict[str, Any]:
        """Trigger package upgrade via pip."""
        from projectpulsewire import cli as cli_mod
        success, message = cli_mod.perform_package_update()
        return {"success": success, "message": message}

    @staticmethod
    def get_irs_guide() -> Dict[str, Any]:
        """Return IRS usage tutorial, categories, and setup instructions."""
        categories = []
        for cat, desc in irs_mod.IRS_CATEGORY_DESCRIPTIONS.items():
            categories.append({"name": cat, "description": desc})

        steps = [
            "Install an IRS impulse response file using ProjectPulsewire.",
            "Open EasyEffects → select Output Effects.",
            "Click Add Effect → select Convolver.",
            "In Convolver settings, click the Import / File icon.",
            "Select your installed .irs file from ~/.config/easyeffects/irs/.",
            "Always place a Limiter plugin after the Convolver to prevent digital clipping.",
        ]

        return {
            "title": "IRS (Impulse Response) Convolver Guide",
            "categories": categories,
            "steps": steps,
        }
