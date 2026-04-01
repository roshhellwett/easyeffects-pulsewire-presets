import json
import os
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Optional
from functools import lru_cache

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_presets_cache = None
_installed_cache = None

def _find_package_data_dir() -> Path:
    """Find the presets directory (works both in dev and installed mode)."""
    package_dir = Path(__file__).parent
    presets_dir = package_dir / "presets"
    
    if presets_dir.exists() and any(presets_dir.glob("*.json")):
        return presets_dir
    
    dev_presets = package_dir.parent.parent / "presets"
    if dev_presets.exists() and any(dev_presets.glob("*.json")):
        return dev_presets
    
    logger.warning(f"Presets directory not found. Searched: {presets_dir}, {dev_presets}")
    return presets_dir

def _clear_cache() -> None:
    """Clear all caches - call this when presets are installed/removed."""
    global _presets_cache, _installed_cache
    _presets_cache = None
    _installed_cache = None

def get_presets_dir() -> Path:
    return _find_package_data_dir()

def get_easyeffects_presets_dir() -> Optional[Path]:
    xdg_config = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    ee_dir = Path(xdg_config) / "easyeffects" / "presets"
    return ee_dir

def get_all_presets(force_refresh: bool = False) -> List[Dict]:
    global _presets_cache
    
    if force_refresh:
        _clear_cache()
    
    if _presets_cache is not None:
        return _presets_cache
    
    presets_dir = get_presets_dir()
    presets = []
    
    if not presets_dir.exists():
        logger.warning(f"Presets directory not found: {presets_dir}")
        return presets
    
    for file in presets_dir.glob("*.json"):
        if file.name == "credit.txt":
            continue
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                preset_info = {
                    "name": file.stem,
                    "filename": file.name,
                    "path": str(file),
                    "data": data,
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
    categories = {}
    
    category_keywords = {
        "Bass": ["bass", "hb-", "heavy"],
        "Loudness": ["loudness", "dynamics", "autogain", "boost", "advanced"],
        "Music Genre": ["rock", "lofi", "edm", "indie", "kpop", "classical", "hifi"],
        "Device": ["sony", "bose"],
        "Voice": ["dialogue", "clarity", "gentle"],
        "Video": ["video"],
    }
    
    for preset in presets:
        categorized = False
        preset_name_lower = preset["name"].lower()
        
        for category, keywords in category_keywords.items():
            if category not in categories:
                categories[category] = []
            for kw in keywords:
                if kw in preset_name_lower:
                    categories[category].append(preset)
                    categorized = True
                    break
        
        if not categorized:
            if "Other" not in categories:
                categories["Other"] = []
            categories["Other"].append(preset)
    
    return categories

def get_installed_presets(force_refresh: bool = False) -> List[str]:
    global _installed_cache
    
    if force_refresh:
        _clear_cache()
    
    if _installed_cache is not None:
        return _installed_cache
    
    ee_dir = get_easyeffects_presets_dir()
    if not ee_dir or not ee_dir.exists():
        _installed_cache = []
        return _installed_cache
    
    installed = []
    for file in ee_dir.glob("*.json"):
        installed.append(file.stem)
    
    _installed_cache = sorted(installed)
    return _installed_cache

def is_preset_installed(preset_name: str) -> bool:
    installed = get_installed_presets()
    return preset_name in installed

def install_preset(preset: Dict) -> tuple[bool, str]:
    if not preset or not preset.get("path"):
        return False, "Invalid preset data: missing path"
    
    ee_dir = get_easyeffects_presets_dir()
    
    if not ee_dir:
        return False, "Could not determine EasyEffects presets directory. Please set XDG_CONFIG_HOME."
    
    src_path = Path(preset["path"])
    if not src_path.exists():
        return False, f"Preset file not found: {preset['name']}"
    
    try:
        ee_dir.mkdir(parents=True, exist_ok=True)
        
        dest_path = ee_dir / preset["filename"]
        shutil.copy2(src_path, dest_path)
        
        _clear_cache()
        
        return True, str(dest_path)
    except PermissionError:
        return False, f"Permission denied. Cannot write to {ee_dir}. Check folder permissions."
    except Exception as e:
        logger.error(f"Failed to install preset: {e}")
        return False, f"Installation failed: {str(e)}"

def install_multiple_presets(presets: List[Dict]) -> tuple[bool, str]:
    if not presets:
        return True, "No presets selected for installation"
    
    ee_dir = get_easyeffects_presets_dir()
    
    if not ee_dir:
        return False, "Could not determine EasyEffects presets directory. Please set XDG_CONFIG_HOME."
    
    try:
        ee_dir.mkdir(parents=True, exist_ok=True)
        
        installed = []
        failed = []
        
        for preset in presets:
            try:
                src_path = Path(preset["path"])
                if not src_path.exists():
                    failed.append(f"{preset['name']}: file not found")
                    continue
                    
                dest_path = ee_dir / preset["filename"]
                shutil.copy2(src_path, dest_path)
                installed.append(preset["name"])
            except Exception as e:
                failed.append(f"{preset['name']}: {str(e)}")
        
        _clear_cache()
        
        if failed and not installed:
            return False, f"All installations failed. Errors: {', '.join(failed)}"
        
        if failed:
            return True, f"Installed: {', '.join(installed)}. Failed: {', '.join(failed)}"
        
        return True, f"Successfully installed {len(installed)} preset(s): {', '.join(installed)}"
    except Exception as e:
        logger.error(f"Failed to install presets: {e}")
        return False, f"Installation failed: {str(e)}"

def remove_preset(preset_name: str) -> tuple[bool, str]:
    if not preset_name:
        return False, "Preset name cannot be empty"
    
    ee_dir = get_easyeffects_presets_dir()
    
    if not ee_dir or not ee_dir.exists():
        return False, "EasyEffects presets directory not found. Is EasyEffects installed?"
    
    preset_file = None
    for file in ee_dir.glob("*.json"):
        if file.stem.lower() == preset_name.lower():
            preset_file = file
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
    
    ee_dir = get_easyeffects_presets_dir()
    
    if not ee_dir or not ee_dir.exists():
        return False, "EasyEffects presets directory not found. Is EasyEffects installed?"
    
    removed = []
    failed = []
    
    for preset_name in preset_names:
        found = False
        for file in ee_dir.glob("*.json"):
            if file.stem.lower() == preset_name.lower():
                try:
                    file.unlink()
                    removed.append(file.stem)
                    found = True
                except Exception as e:
                    failed.append(f"{preset_name}: {str(e)}")
                break
        if not found:
            failed.append(f"{preset_name}: not found")
    
    _clear_cache()
    
    if failed and not removed:
        return False, f"All removals failed. Errors: {', '.join(failed)}"
    
    if failed:
        return True, f"Removed: {', '.join(removed)}. Failed: {', '.join(failed)}"
    
    return True, f"Successfully removed {len(removed)} preset(s): {', '.join(removed)}"
