import os
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_irs_cache = None
_installed_irs_cache = None

def _find_package_data_dir() -> Path:
    """Find the IRS directory (works both in dev and installed mode)."""
    package_dir = Path(__file__).parent
    irs_dir = package_dir / "irs"
    
    if irs_dir.exists() and any(irs_dir.glob("*.irs")):
        return irs_dir
    
    dev_irs = package_dir.parent.parent / "irs"
    if dev_irs.exists() and any(dev_irs.glob("*.irs")):
        return dev_irs
    
    logger.warning(f"IRS directory not found. Searched: {irs_dir}, {dev_irs}")
    return irs_dir

def _clear_cache() -> None:
    """Clear all caches - call this when IRS are installed/removed."""
    global _irs_cache, _installed_irs_cache
    _irs_cache = None
    _installed_irs_cache = None

def get_irs_dir() -> Path:
    return _find_package_data_dir()

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


def get_easyeffects_convolver_dir() -> Optional[Path]:
    """Get the EasyEffects convolver/IRS directory.
    
    Checks both native and Flatpak paths, preferring native.
    """
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if not xdg_config or (os.environ.get("SUDO_USER") and xdg_config.startswith("/root")):
        xdg_config = str(_get_real_home() / ".config")
        
    native_dir = Path(xdg_config) / "easyeffects" / "irs"
    
    if native_dir.exists() or native_dir.parent.exists():
        return native_dir
    
    flatpak_config = _get_flatpak_config()
    if flatpak_config:
        return flatpak_config / "irs"
    
    return native_dir


def get_all_convolver_dirs() -> List[Path]:
    """Get ALL convolver directories (native + Flatpak)."""
    dirs = []
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if not xdg_config or (os.environ.get("SUDO_USER") and xdg_config.startswith("/root")):
        xdg_config = str(_get_real_home() / ".config")
    
    native_dir = Path(xdg_config) / "easyeffects" / "irs"
    dirs.append(native_dir)
    
    flatpak_config = _get_flatpak_config()
    if flatpak_config:
        flatpak_dir = flatpak_config / "irs"
        if flatpak_dir not in dirs:
            dirs.append(flatpak_dir)
    
    return dirs


# ============================================================
# IRS Education / Description System
# ============================================================

IRS_CATEGORY_DESCRIPTIONS = {
    "Dolby": "Dolby surround & headphone virtualization — makes stereo headphones sound like a surround system. Great for movies and immersive music.",
    "DFX": "DFX audio enhancement profiles — general purpose audio improvement with bass boost, clarity, and spatial enhancement.",
    "Creative": "Creative Sound Blaster profiles — gaming-oriented 3D audio and crystal clear sound enhancement.",
    "Bass": "Bass enhancement & subwoofer simulation — adds deep, thumping low-end to any speakers or headphones.",
    "Clarity": "Clarity & detail enhancement — makes every instrument and vocal crisp and well-defined.",
    "Ambience": "Ambience & hall simulation — adds room reverb and concert hall atmosphere to your audio.",
    "Headphone": "Headphone optimization — 3D soundstage and enhanced imaging specifically tuned for headphone listening.",
    "Music Genre": "Genre-specific tuning — optimized frequency responses for specific music genres like jazz, rock, classical, etc.",
    "Device": "Device-specific correction — frequency response correction for specific headphone/speaker models.",
    "Room Correction": "Room acoustic correction — compensates for room resonances and speaker placement issues.",
    "Other": "General audio enhancement — various audio profiles for different listening scenarios.",
}


def get_irs_category_description(category: str) -> str:
    """Get a human-friendly description for an IRS category."""
    return IRS_CATEGORY_DESCRIPTIONS.get(category, "Audio enhancement impulse response files.")


def get_irs_use_guide(irs_name: str) -> str:
    """Get a use-case description based on the IRS name patterns."""
    name_lower = irs_name.lower()
    
    if any(kw in name_lower for kw in ["bass", "subwoofer", "bassboom"]):
        return "Best for: Adding deep bass to speakers/headphones that lack low-end punch."
    elif any(kw in name_lower for kw in ["dolby", "atmos", "surround"]):
        return "Best for: Movie watching and immersive audio — simulates surround sound on stereo headphones."
    elif any(kw in name_lower for kw in ["headphone", "3d", "head360"]):
        return "Best for: Headphone users — creates a wider, more natural soundstage."
    elif any(kw in name_lower for kw in ["clarity", "clear", "crystal", "hifi"]):
        return "Best for: Making vocals and instruments sound crisp and detailed."
    elif any(kw in name_lower for kw in ["studio", "master", "prosound"]):
        return "Best for: Mastering-style audio that sounds polished and professional."
    elif any(kw in name_lower for kw in ["theater", "cinema"]):
        return "Best for: Movie and video content — enhanced dialogue and spatial effects."
    elif any(kw in name_lower for kw in ["gaming", "sonic"]):
        return "Best for: Gaming — enhanced footsteps, gunshots, and spatial awareness."
    elif any(kw in name_lower for kw in ["jazz", "blues", "rock", "metal", "classic"]):
        return "Best for: This specific music genre — tuned frequency response for optimal genre presentation."
    elif any(kw in name_lower for kw in ["frc", "correction"]):
        return "Best for: Correcting frequency response of specific headphone models for flat/accurate playback."
    elif any(kw in name_lower for kw in ["loud", "boost", "maximizer"]):
        return "Best for: Making audio louder and more impactful without clipping."
    else:
        return "General audio enhancement — try it to hear the difference!"

def get_all_irs(force_refresh: bool = False) -> List[Dict]:
    global _irs_cache
    
    if force_refresh:
        _clear_cache()
    
    if _irs_cache is not None:
        return _irs_cache
    
    irs_dir = get_irs_dir()
    irs_files = []
    
    if not irs_dir.exists():
        logger.warning(f"IRS directory not found: {irs_dir}")
        return irs_files
    
    for file in irs_dir.glob("*.irs"):
        try:
            irs_info = {
                "name": file.stem,
                "filename": file.name,
                "path": str(file),
                "size": file.stat().st_size,
            }
            irs_files.append(irs_info)
        except OSError as e:
            logger.error(f"Error loading IRS {file.name}: {e}")
    
    _irs_cache = sorted(irs_files, key=lambda x: x["name"].lower())
    return _irs_cache

def get_irs_by_name(name: str) -> Optional[Dict]:
    all_irs = get_all_irs()
    name_lower = name.lower()
    for irs in all_irs:
        if irs["name"].lower() == name_lower:
            return irs
    return None

def get_irs_by_category(irs_list: List[Dict]) -> Dict[str, List[Dict]]:
    categories: Dict[str, List[Dict]] = {}
    
    category_keywords = {
        "Dolby": ["dolby"],
        "DFX": ["dfx"],
        "Creative": ["creative", "x-fi", "cmms"],
        "Bass": ["bass", "basswaves", "bass+"],
        "Clarity": ["clarity", "clear"],
        "Ambience": ["ambience", "hall", "concert"],
        "Headphone": ["headphone", "3d"],
        "Music Genre": ["jazz", "blues", "rock", "metal", "hip", "country", "classic"],
        "Device": ["accudio", "xba", "mdr", "sennheiser"],
        "Room Correction": ["room", "correction"],
    }
    
    for irs in irs_list:
        categorized = False
        irs_name_lower = irs["name"].lower()
        
        for category, keywords in category_keywords.items():
            for kw in keywords:
                if kw in irs_name_lower:
                    categories.setdefault(category, []).append(irs)
                    categorized = True
                    break
            if categorized:
                break
        
        if not categorized:
            categories.setdefault("Other", []).append(irs)
    
    # Ensure all keys are strings (defensive)
    return {str(k): v for k, v in categories.items()}

def get_installed_irs(force_refresh: bool = False) -> List[str]:
    global _installed_irs_cache
    
    if force_refresh:
        _clear_cache()
    
    if _installed_irs_cache is not None:
        return _installed_irs_cache
    
    convolver_dir = get_easyeffects_convolver_dir()
    if not convolver_dir or not convolver_dir.exists():
        _installed_irs_cache = []
        return _installed_irs_cache
    
    installed = []
    for file in convolver_dir.glob("*.irs"):
        installed.append(file.stem)
    
    _installed_irs_cache = sorted(installed)
    return _installed_irs_cache

def is_irs_installed(irs_name: str) -> bool:
    installed = get_installed_irs()
    return irs_name in installed

def install_irs(irs_file: Dict) -> tuple[bool, str]:
    if not irs_file or not irs_file.get("path"):
        return False, "Invalid IRS data: missing path"
    
    convolver_dir = get_easyeffects_convolver_dir()
    
    if not convolver_dir:
        return False, "Could not determine EasyEffects convolver directory. Please set XDG_CONFIG_HOME."
    
    src_path = Path(irs_file["path"])
    if not src_path.exists():
        return False, f"IRS file not found: {irs_file['name']}"
    
    try:
        convolver_dir.mkdir(parents=True, exist_ok=True)
        
        dest_path = convolver_dir / irs_file["filename"]
        shutil.copy2(src_path, dest_path)
        
        _clear_cache()
        
        return True, str(dest_path)
    except PermissionError:
        return False, f"Permission denied. Cannot write to {convolver_dir}. Check folder permissions."
    except Exception as e:
        logger.error(f"Failed to install IRS: {e}")
        return False, f"Installation failed: {str(e)}"

def install_multiple_irs(irs_files: List[Dict]) -> tuple[bool, str]:
    if not irs_files:
        return True, "No IRS files selected for installation"
    
    convolver_dir = get_easyeffects_convolver_dir()
    
    if not convolver_dir:
        return False, "Could not determine EasyEffects convolver directory. Please set XDG_CONFIG_HOME."
    
    try:
        convolver_dir.mkdir(parents=True, exist_ok=True)
        
        installed = []
        failed = []
        
        for irs_file in irs_files:
            try:
                src_path = Path(irs_file["path"])
                if not src_path.exists():
                    failed.append(f"{irs_file['name']}: file not found")
                    continue
                    
                dest_path = convolver_dir / irs_file["filename"]
                shutil.copy2(src_path, dest_path)
                installed.append(irs_file["name"])
            except Exception as e:
                failed.append(f"{irs_file['name']}: {str(e)}")
        
        _clear_cache()
        
        if failed and not installed:
            return False, f"All installations failed. Errors: {', '.join(failed)}"
        
        if failed:
            return True, f"Installed: {', '.join(installed)}. Failed: {', '.join(failed)}"
        
        return True, f"Successfully installed {len(installed)} IRS file(s): {', '.join(installed)}"
    except Exception as e:
        logger.error(f"Failed to install IRS files: {e}")
        return False, f"Installation failed: {str(e)}"

def remove_irs(irs_name: str) -> tuple[bool, str]:
    if not irs_name:
        return False, "IRS name cannot be empty"
    
    convolver_dir = get_easyeffects_convolver_dir()
    
    if not convolver_dir or not convolver_dir.exists():
        return False, "EasyEffects convolver directory not found. Is EasyEffects installed?"
    
    irs_file = None
    for file in convolver_dir.glob("*.irs"):
        if file.stem.lower() == irs_name.lower():
            irs_file = file
            break
    
    if not irs_file:
        return False, f"IRS '{irs_name}' not found in convolver folder"
    
    try:
        irs_file.unlink()
        _clear_cache()
        return True, f"Removed IRS: {irs_name}"
    except PermissionError:
        return False, f"Permission denied. Cannot remove {irs_name}. Check folder permissions."
    except Exception as e:
        logger.error(f"Failed to remove IRS: {e}")
        return False, f"Removal failed: {str(e)}"

def remove_multiple_irs(irs_names: List[str]) -> tuple[bool, str]:
    if not irs_names:
        return True, "No IRS files selected for removal"
    
    convolver_dir = get_easyeffects_convolver_dir()
    
    if not convolver_dir or not convolver_dir.exists():
        return False, "EasyEffects convolver directory not found. Is EasyEffects installed?"
    
    removed = []
    failed = []
    
    for irs_name in irs_names:
        found = False
        for file in convolver_dir.glob("*.irs"):
            if file.stem.lower() == irs_name.lower():
                try:
                    file.unlink()
                    removed.append(file.stem)
                    found = True
                except Exception as e:
                    failed.append(f"{irs_name}: {str(e)}")
                break
        if not found:
            failed.append(f"{irs_name}: not found")
    
    _clear_cache()
    
    if failed and not removed:
        return False, f"All removals failed. Errors: {', '.join(failed)}"
    
    if failed:
        return True, f"Removed: {', '.join(removed)}. Failed: {', '.join(failed)}"
    
    return True, f"Successfully removed {len(removed)} IRS file(s): {', '.join(removed)}"
