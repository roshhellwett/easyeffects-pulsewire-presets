"""
Audio Stack Dependency Installer for ProjectPulsewire.

Detects the Linux distribution and checks/installs essential audio packages:
- PipeWire (audio server)
- EasyEffects (audio effects processor)
- LSP Plugins, Calf, ZAM, MDA (audio effect plugins)
- WirePlumber (session manager)

Supports: Ubuntu/Debian, Fedora, Arch, openSUSE, and Flatpak.
"""

import os
import subprocess
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# Package definitions per distro
# ============================================================

PACKAGES = [
    {
        "name": "PipeWire",
        "description": "Modern audio/video server (replaces PulseAudio)",
        "critical": True,
        "check_cmd": "pipewire",
        "ubuntu": "pipewire",
        "fedora": "pipewire",
        "arch": "pipewire",
        "opensuse": "pipewire",
    },
    {
        "name": "PipeWire PulseAudio",
        "description": "PulseAudio compatibility layer for PipeWire",
        "critical": True,
        "check_cmd": None,
        "ubuntu": "pipewire-pulse",
        "fedora": "pipewire-pulseaudio",
        "arch": "pipewire-pulse",
        "opensuse": "pipewire-pulseaudio",
    },
    {
        "name": "PipeWire ALSA",
        "description": "ALSA compatibility layer for PipeWire",
        "critical": True,
        "check_cmd": None,
        "ubuntu": "pipewire-alsa",
        "fedora": "pipewire-alsa",
        "arch": "pipewire-alsa",
        "opensuse": "pipewire-alsa",
    },
    {
        "name": "WirePlumber",
        "description": "Session manager for PipeWire",
        "critical": True,
        "check_cmd": "wireplumber",
        "ubuntu": "wireplumber",
        "fedora": "wireplumber",
        "arch": "wireplumber",
        "opensuse": "wireplumber",
    },
    {
        "name": "EasyEffects",
        "description": "Audio effects processor (EQ, compressor, etc.)",
        "critical": True,
        "check_cmd": "easyeffects",
        "ubuntu": "easyeffects",
        "fedora": "easyeffects",
        "arch": "easyeffects",
        "opensuse": "easyeffects",
        "flatpak": "com.github.wwmm.easyeffects",
    },
    {
        "name": "LSP Plugins",
        "description": "High-quality audio plugins (EQ, compressor, limiter)",
        "critical": True,
        "check_cmd": None,
        "ubuntu": "lsp-plugins",
        "fedora": "lsp-plugins",
        "arch": "lsp-plugins",
        "opensuse": "lsp-plugins",
    },
    {
        "name": "Calf Plugins",
        "description": "Audio effects plugins (reverb, compression, etc.)",
        "critical": False,
        "check_cmd": None,
        "ubuntu": "calf-plugins",
        "fedora": "calf-plugins",
        "arch": "calf",
        "opensuse": "calf-plugins",
    },
    {
        "name": "ZAM Plugins",
        "description": "Maximizer and audio utility plugins",
        "critical": False,
        "check_cmd": None,
        "ubuntu": "zam-plugins",
        "fedora": "zam-plugins",
        "arch": "zam-plugins",
        "opensuse": "zam-plugins",
    },
    {
        "name": "MDA LV2 Plugins",
        "description": "Classic lightweight audio plugins",
        "critical": False,
        "check_cmd": None,
        "ubuntu": "mda-lv2",
        "fedora": "mda-lv2-plugins",
        "arch": "mda.lv2",
        "opensuse": "mda-lv2",
    },
]


# ============================================================
# Distro detection
# ============================================================

def detect_distro() -> Tuple[str, str]:
    """
    Detect the Linux distribution from /etc/os-release.
    
    Returns:
        Tuple of (distro_family, distro_name).
        distro_family is one of: ubuntu, fedora, arch, opensuse, unknown
    """
    os_release = Path("/etc/os-release")
    if not os_release.exists():
        return "unknown", "Unknown Linux"
    
    info = {}
    try:
        with open(os_release, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    key, _, value = line.partition("=")
                    info[key] = value.strip('"')
    except Exception:
        return "unknown", "Unknown Linux"
    
    distro_id = info.get("ID", "").lower()
    distro_like = info.get("ID_LIKE", "").lower()
    pretty_name = info.get("PRETTY_NAME", distro_id)
    
    if distro_id in ("ubuntu", "debian", "linuxmint", "pop", "elementary", "zorin", "neon"):
        return "ubuntu", pretty_name
    if "ubuntu" in distro_like or "debian" in distro_like:
        return "ubuntu", pretty_name
    
    if distro_id in ("fedora", "rhel", "centos", "rocky", "almalinux", "nobara"):
        return "fedora", pretty_name
    if "fedora" in distro_like or "rhel" in distro_like:
        return "fedora", pretty_name
    
    if distro_id in ("arch", "manjaro", "endeavouros", "garuda", "artix"):
        return "arch", pretty_name
    if "arch" in distro_like:
        return "arch", pretty_name
    
    if distro_id in ("opensuse-tumbleweed", "opensuse-leap", "sles"):
        return "opensuse", pretty_name
    if "suse" in distro_like:
        return "opensuse", pretty_name
    
    return "unknown", pretty_name


# ============================================================
# Package checking
# ============================================================

def _run_quiet(cmd: List[str], timeout: int = 10) -> Tuple[int, str]:
    """Run a command quietly and return (returncode, stdout)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 1, ""


def is_command_available(cmd: str) -> bool:
    """Check if a command is available in PATH."""
    return shutil.which(cmd) is not None


def check_package_installed(pkg: Dict, distro_family: str) -> bool:
    """
    Check if a package is installed using the distro's package manager.
    """
    # First try the binary check
    if pkg.get("check_cmd") and is_command_available(pkg["check_cmd"]):
        return True
    
    pkg_name = pkg.get(distro_family)
    if not pkg_name:
        return False
    
    if distro_family == "ubuntu":
        rc, _ = _run_quiet(["dpkg", "-s", pkg_name])
        return rc == 0
    elif distro_family == "fedora":
        rc, _ = _run_quiet(["rpm", "-q", pkg_name])
        return rc == 0
    elif distro_family == "arch":
        rc, _ = _run_quiet(["pacman", "-Q", pkg_name])
        return rc == 0
    elif distro_family == "opensuse":
        rc, _ = _run_quiet(["rpm", "-q", pkg_name])
        return rc == 0
    
    return False


def check_flatpak_installed(app_id: str) -> bool:
    """Check if a Flatpak app is installed."""
    if not is_command_available("flatpak"):
        return False
    rc, output = _run_quiet(["flatpak", "list", "--app", "--columns=application"])
    return app_id in output


def check_easyeffects_version() -> Optional[str]:
    """Get the installed EasyEffects version."""
    # Try native
    if is_command_available("easyeffects"):
        rc, output = _run_quiet(["easyeffects", "--version"])
        if rc == 0 and output.strip():
            return output.strip()
    
    # Try Flatpak
    if is_command_available("flatpak"):
        rc, output = _run_quiet(["flatpak", "info", "com.github.wwmm.easyeffects"])
        if rc == 0:
            for line in output.split("\n"):
                if "Version:" in line:
                    return line.split(":", 1)[1].strip()
    
    return None


def check_pipewire_running() -> bool:
    """Check if PipeWire is the active audio server."""
    rc, output = _run_quiet(["pactl", "info"])
    if rc == 0:
        return "PipeWire" in output
    return False


# ============================================================
# Package query
# ============================================================

def get_all_package_status(distro_family: str) -> List[Dict]:
    """
    Check the status of all required packages.
    
    Returns:
        List of dicts with keys: name, description, critical, installed, pkg_name
    """
    results = []
    for pkg in PACKAGES:
        pkg_name = pkg.get(distro_family, "N/A")
        installed = check_package_installed(pkg, distro_family)
        
        # Special check for EasyEffects Flatpak
        if pkg.get("flatpak") and not installed:
            installed = check_flatpak_installed(pkg["flatpak"])
            if installed:
                pkg_name = f"{pkg_name} (Flatpak)"
        
        results.append({
            "name": pkg["name"],
            "description": pkg["description"],
            "critical": pkg["critical"],
            "installed": installed,
            "pkg_name": pkg_name,
        })
    
    return results


def get_install_command(distro_family: str, packages: List[str]) -> Optional[str]:
    """
    Get the install command for the given distro and package list.
    
    Returns:
        The full sudo install command string, or None if distro is unknown.
    """
    if not packages:
        return None
    
    pkg_str = " ".join(packages)
    
    if distro_family == "ubuntu":
        return f"sudo apt install -y {pkg_str}"
    elif distro_family == "fedora":
        return f"sudo dnf install -y {pkg_str}"
    elif distro_family == "arch":
        return f"sudo pacman -S --noconfirm {pkg_str}"
    elif distro_family == "opensuse":
        return f"sudo zypper install -y {pkg_str}"
    
    return None


def get_missing_packages(distro_family: str, critical_only: bool = False) -> List[str]:
    """Get list of missing package names for this distro."""
    missing = []
    for pkg in PACKAGES:
        if critical_only and not pkg["critical"]:
            continue
        pkg_name = pkg.get(distro_family)
        if not pkg_name:
            continue
        if not check_package_installed(pkg, distro_family):
            # Also check Flatpak for EasyEffects
            if pkg.get("flatpak") and check_flatpak_installed(pkg["flatpak"]):
                continue
            missing.append(pkg_name)
    return missing


def install_missing_packages(distro_family: str, packages: List[str]) -> Tuple[bool, str]:
    """
    Install the given packages using the distro's package manager.
    Requires sudo privileges.
    
    Returns:
        Tuple of (success, message)
    """
    cmd = get_install_command(distro_family, packages)
    if not cmd:
        return False, "Unknown distribution. Cannot determine install command."
    
    try:
        result = subprocess.run(
            cmd.split(),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            return True, f"Successfully installed: {', '.join(packages)}"
        else:
            return False, f"Installation failed:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return False, "Installation timed out after 5 minutes."
    except Exception as e:
        return False, f"Installation error: {str(e)}"


def update_easyeffects_flatpak() -> Tuple[bool, str]:
    """Update EasyEffects Flatpak to the latest version."""
    if not is_command_available("flatpak"):
        return False, "Flatpak is not installed."
    
    try:
        result = subprocess.run(
            ["flatpak", "update", "-y", "com.github.wwmm.easyeffects"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            return True, "EasyEffects Flatpak updated to latest version."
        else:
            return False, f"Update failed:\n{result.stderr}"
    except Exception as e:
        return False, f"Update error: {str(e)}"
