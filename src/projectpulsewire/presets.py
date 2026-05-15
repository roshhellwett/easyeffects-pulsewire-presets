import json
import os
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

_presets_cache = None
_installed_cache = None
_selected_preset_source = "modernpresets"  # Default preset source

# Map for preset folder names
PRESET_SOURCES = {
    "modern": "modernpresets",
    "legacy": "legacypresets",
}

def _find_package_data_dir(preset_source: str = None) -> Path:
    """Find the presets directory (works both in dev and installed mode).
    
    Args:
        preset_source: Either 'modernpresets' or 'legacypresets'. 
                      Defaults to the currently selected source.
    """
    if preset_source is None:
        preset_source = _selected_preset_source
    
    package_dir = Path(__file__).parent
    presets_dir = package_dir / preset_source
    
    if presets_dir.exists() and any(presets_dir.glob("*.json")):
        return presets_dir
    
    dev_presets = package_dir.parent.parent / preset_source
    if dev_presets.exists() and any(dev_presets.glob("*.json")):
        return dev_presets
    
    logger.warning(f"Presets directory not found for source '{preset_source}'. Searched: {presets_dir}, {dev_presets}")
    return presets_dir

def _clear_cache() -> None:
    """Clear all caches - call this when presets are installed/removed."""
    global _presets_cache, _installed_cache
    _presets_cache = None
    _installed_cache = None

def get_available_preset_sources() -> List[str]:
    """Get list of available preset sources."""
    sources = []
    package_dir = Path(__file__).parent
    for source_name in PRESET_SOURCES.values():
        source_dir = package_dir / source_name
        if source_dir.exists() and any(source_dir.glob("*.json")):
            sources.append(source_name)
    return sorted(sources)

def set_active_preset_source(source: str) -> bool:
    """Set the active preset source.
    
    Args:
        source: Either 'modernpresets' or 'legacypresets'
        
    Returns:
        True if source was set successfully, False if source doesn't exist
    """
    global _selected_preset_source
    
    source_path = Path(__file__).parent / source
    if not source_path.exists() or not any(source_path.glob("*.json")):
        logger.error(f"Preset source '{source}' not found or empty")
        return False
    
    _selected_preset_source = source
    _clear_cache()
    return True

def get_active_preset_source() -> str:
    """Get the currently active preset source."""
    return _selected_preset_source

def get_presets_dir(preset_source: str = None) -> Path:
    """Get the presets directory path.
    
    Args:
        preset_source: Optional specific preset source. If None, uses the active source.
        
    Returns:
        Path to the presets directory
    """
    return _find_package_data_dir(preset_source)

def _get_real_home() -> Path:
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        try:
            import pwd
            return Path(pwd.getpwnam(sudo_user).pw_dir)
        except (ImportError, KeyError):
            pass
    return Path.home()

def _get_flatpak_config() -> Optional[Path]:
    """Get the Flatpak EasyEffects config directory if it exists."""
    home = _get_real_home()
    flatpak_dir = home / ".var" / "app" / "com.github.wwmm.easyeffects" / "config" / "easyeffects"
    if flatpak_dir.exists():
        return flatpak_dir
    return None


def get_easyeffects_presets_dir(preset_type: str = "output") -> Optional[Path]:
    """Get the EasyEffects presets directory.
    
    Checks both native (~/.config/easyeffects/) and Flatpak
    (~/.var/app/com.github.wwmm.easyeffects/config/easyeffects/) paths.
    Returns whichever exists, preferring native.
    
    Args:
        preset_type: Either 'output' (speakers/headphones) or 'input' (microphone).
                     Defaults to 'output'.
    """
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if not xdg_config or (os.environ.get("SUDO_USER") and xdg_config.startswith("/root")):
        xdg_config = str(_get_real_home() / ".config")
        
    native_dir = Path(xdg_config) / "easyeffects" / preset_type
    
    # Check if native path exists or its parent exists
    if native_dir.exists() or native_dir.parent.exists():
        return native_dir
    
    # Fallback to Flatpak path
    flatpak_config = _get_flatpak_config()
    if flatpak_config:
        return flatpak_config / preset_type
    
    # Default to native (will be created on install)
    return native_dir


def get_all_easyeffects_presets_dirs(preset_type: str = "output") -> List[Path]:
    """Get ALL EasyEffects presets directories (native + Flatpak).
    
    Used during installation to install presets to all detected locations.
    """
    dirs = []
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if not xdg_config or (os.environ.get("SUDO_USER") and xdg_config.startswith("/root")):
        xdg_config = str(_get_real_home() / ".config")
    
    native_dir = Path(xdg_config) / "easyeffects" / preset_type
    dirs.append(native_dir)
    
    flatpak_config = _get_flatpak_config()
    if flatpak_config:
        flatpak_dir = flatpak_config / preset_type
        if flatpak_dir not in dirs:
            dirs.append(flatpak_dir)
    
    return dirs

def get_all_presets(force_refresh: bool = False, preset_source: str = None) -> List[Dict]:
    """Get all presets from the specified or active preset source.
    
    Args:
        force_refresh: Whether to bypass cache and reload
        preset_source: Optional specific preset source. If None, uses the active source.
        
    Returns:
        List of preset dictionaries
    """
    global _presets_cache
    
    if force_refresh:
        _clear_cache()
    
    if _presets_cache is not None:
        return _presets_cache
    
    presets_dir = get_presets_dir(preset_source)
    presets = []
    
    if not presets_dir.exists():
        logger.warning(f"Presets directory not found: {presets_dir}")
        return presets
    
    for file in presets_dir.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                preset_info = {
                    "name": file.stem,
                    "filename": file.name,
                    "path": str(file),
                    "data": data,
                    "source": get_active_preset_source(),
                }
                presets.append(preset_info)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading preset {file.name}: {e}")
    
    _presets_cache = sorted(presets, key=lambda x: x["name"].lower())
    return _presets_cache

def get_preset_by_name(name: str) -> Optional[Dict]:
    all_presets = get_all_presets()
    name_lower = name.lower()
    for preset in all_presets:
        if preset["name"].lower() == name_lower:
            return preset
    return None

def get_presets_by_category(presets: List[Dict]) -> Dict[str, List[Dict]]:
    categories: Dict[str, List[Dict]] = {}
    category_order = ["Bass", "Genre", "Voice", "Brand", "Dynamics", "Other"]
    alias_map = {
        "music genre": "Genre",
        "genre": "Genre",
        "voice": "Voice",
        "media": "Voice",
        "device": "Brand",
        "brand": "Brand",
        "loudness": "Dynamics",
        "dynamics": "Dynamics",
    }

    for preset in presets:
        name = preset["name"]
        category = "Other"

        if " - " in name:
            prefix = name.split(" - ", 1)[0].strip().lower()
            category = alias_map.get(prefix, name.split(" - ", 1)[0].strip())
        else:
            preset_name_lower = name.lower()
            fallback_keywords = {
                "Bass": ["bass", "sub", "kick", "v-shape"],
                "Genre": ["edm", "rock", "classical", "lo-fi", "indie", "k-pop", "hi-fi"],
                "Voice": ["dialogue", "podcast", "vocal", "gaming", "video", "live"],
                "Brand": ["bose", "jbl", "harman", "sony"],
                "Dynamics": ["loudness", "auto gain", "crystal", "soft volume", "late night"],
            }
            for fallback_category, keywords in fallback_keywords.items():
                if any(keyword in preset_name_lower for keyword in keywords):
                    category = fallback_category
                    break

        categories.setdefault(category, []).append(preset)

    ordered_categories: Dict[str, List[Dict]] = {}
    for category in category_order:
        if category in categories:
            ordered_categories[category] = categories[category]

    for category in sorted(k for k in categories.keys() if k not in ordered_categories):
        ordered_categories[str(category)] = categories[category]

    return ordered_categories

def get_installed_presets(force_refresh: bool = False) -> List[str]:
    global _installed_cache
    
    if force_refresh:
        _clear_cache()
    
    if _installed_cache is not None:
        return _installed_cache
    
    installed = []
    for preset_type in ("output", "input"):
        ee_dir = get_easyeffects_presets_dir(preset_type)
        if ee_dir and ee_dir.exists():
            for file in ee_dir.glob("*.json"):
                installed.append(file.stem)
    
    _installed_cache = sorted(list(set(installed)))
    return _installed_cache

def is_preset_installed(preset_name: str) -> bool:
    installed = get_installed_presets()
    return preset_name in installed

def install_preset(preset: Dict) -> tuple[bool, str]:
    if not preset or not preset.get("path"):
        return False, "Invalid preset data: missing path"

    ee_dirs = get_all_easyeffects_presets_dirs()
    if not ee_dirs:
        return False, "Could not determine EasyEffects presets directory. Please set XDG_CONFIG_HOME."

    src_path = Path(preset["path"])
    if not src_path.exists():
        return False, f"Preset file not found: {preset['name']}"

    written_paths: List[str] = []
    failures: List[str] = []
    for ee_dir in ee_dirs:
        try:
            ee_dir.mkdir(parents=True, exist_ok=True)
            dest_path = ee_dir / preset["filename"]
            shutil.copy2(src_path, dest_path)
            written_paths.append(str(dest_path))
        except PermissionError:
            failures.append(f"{ee_dir}: permission denied")
        except Exception as e:
            logger.error(f"Failed to install preset to {ee_dir}: {e}")
            failures.append(f"{ee_dir}: {e}")

    _clear_cache()

    if written_paths:
        msg = " + ".join(written_paths)
        if failures:
            msg += f" (warnings: {'; '.join(failures)})"
        return True, msg

    return False, "; ".join(failures) or "Installation failed for all detected directories"

def install_multiple_presets(presets: List[Dict]) -> tuple[bool, str]:
    if not presets:
        return True, "No presets selected for installation"

    ee_dirs = get_all_easyeffects_presets_dirs()
    if not ee_dirs:
        return False, "Could not determine EasyEffects presets directory. Please set XDG_CONFIG_HOME."

    # Best-effort mkdir up front; per-preset writes still tolerate per-dir failures.
    for ee_dir in ee_dirs:
        try:
            ee_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create {ee_dir}: {e}")

    installed: List[str] = []
    failed: List[str] = []

    for preset in presets:
        src_path = Path(preset["path"])
        if not src_path.exists():
            failed.append(f"{preset['name']}: file not found")
            continue

        any_written = False
        per_preset_errors: List[str] = []
        for ee_dir in ee_dirs:
            try:
                dest_path = ee_dir / preset["filename"]
                shutil.copy2(src_path, dest_path)
                any_written = True
            except Exception as e:
                per_preset_errors.append(f"{ee_dir}: {e}")

        if any_written:
            installed.append(preset["name"])
        else:
            failed.append(f"{preset['name']}: {'; '.join(per_preset_errors)}")

    _clear_cache()

    if failed and not installed:
        return False, f"All installations failed. Errors: {', '.join(failed)}"

    if failed:
        return True, f"Installed: {', '.join(installed)}. Failed: {', '.join(failed)}"

    return True, f"Successfully installed {len(installed)} preset(s): {', '.join(installed)}"

def remove_preset(preset_name: str) -> tuple[bool, str]:
    if not preset_name:
        return False, "Preset name cannot be empty"
    
    preset_file = None
    for preset_type in ("output", "input"):
        ee_dir = get_easyeffects_presets_dir(preset_type)
        if not ee_dir or not ee_dir.exists():
            continue
        for file in ee_dir.glob("*.json"):
            if file.stem.lower() == preset_name.lower():
                preset_file = file
                break
        if preset_file:
            break
    
    if not preset_file:
        return False, f"Preset '{preset_name}' not found in EasyEffects presets"
    
    try:
        preset_file.unlink()
        _clear_cache()
        return True, f"Removed preset: {preset_name}"
    except PermissionError:
        return False, f"Permission denied. Cannot remove {preset_name}. Check folder permissions."
    except Exception as e:
        logger.error(f"Failed to remove preset: {e}")
        return False, f"Removal failed: {str(e)}"

def remove_multiple_presets(preset_names: List[str]) -> tuple[bool, str]:
    if not preset_names:
        return True, "No presets selected for removal"
    
    removed = []
    failed = []
    
    for preset_name in preset_names:
        found = False
        for preset_type in ("output", "input"):
            ee_dir = get_easyeffects_presets_dir(preset_type)
            if not ee_dir or not ee_dir.exists():
                continue
            for file in ee_dir.glob("*.json"):
                if file.stem.lower() == preset_name.lower():
                    found = True
                    try:
                        file.unlink()
                        removed.append(file.stem)
                    except Exception as e:
                        failed.append(f"{preset_name}: {str(e)}")
                    break
            if found:
                break
        if not found:
            failed.append(f"{preset_name}: not found")
    
    _clear_cache()
    
    if failed and not removed:
        return False, f"All removals failed. Errors: {', '.join(failed)}"
    
    if failed:
        return True, f"Removed: {', '.join(removed)}. Failed: {', '.join(failed)}"
    
    return True, f"Successfully removed {len(removed)} preset(s): {', '.join(removed)}"
