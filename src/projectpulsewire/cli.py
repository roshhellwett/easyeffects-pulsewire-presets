import os
import sys
import json
import logging
import errno
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta, timezone

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm
from rich import box

from projectpulsewire import __version__
from projectpulsewire import presets as presets_module
from projectpulsewire import irs_handler as irs_module
from projectpulsewire import deps_installer

if hasattr(sys.stdout, "reconfigure"):
    encoding = getattr(sys.stdout, "encoding", None) or ""
    if encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


class SafeOutputStream:
    """Stream wrapper that keeps closed downstream pipes from printing tracebacks."""

    def __init__(self, stream):
        self._stream = stream
        self._pipe_closed = False

    def write(self, text):
        if self._pipe_closed:
            return len(text)
        try:
            return self._stream.write(text)
        except (BrokenPipeError, OSError) as exc:
            if isinstance(exc, BrokenPipeError) or getattr(exc, "errno", None) in {errno.EPIPE, errno.EINVAL}:
                self._pipe_closed = True
                return len(text)
            raise

    def flush(self):
        if self._pipe_closed:
            return None
        try:
            return self._stream.flush()
        except (BrokenPipeError, OSError) as exc:
            if isinstance(exc, BrokenPipeError) or getattr(exc, "errno", None) in {errno.EPIPE, errno.EINVAL}:
                self._pipe_closed = True
                return None
            raise

    def __getattr__(self, name):
        return getattr(self._stream, name)


sys.stdout = SafeOutputStream(sys.stdout)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

UPDATE_CHECK_INTERVAL_HOURS = 24
PYPI_JSON_URL = "https://pypi.org/pypi/projectpulsewire/json"

class ProjectPulseWireConsole(Console):
    """Console that exits cleanly when downstream pipes stop reading."""

    def _write_buffer(self) -> None:
        try:
            super()._write_buffer()
        except (BrokenPipeError, OSError) as exc:
            if isinstance(exc, BrokenPipeError) or getattr(exc, "errno", None) in {errno.EPIPE, errno.EINVAL}:
                raise typer.Exit(code=0) from None
            raise


app = typer.Typer(help="projectpulsewire — EasyEffects presets for PipeWire/PulseAudio", add_completion=False)
console = ProjectPulseWireConsole(
    force_terminal=sys.stdout.isatty(),
    color_system="auto" if sys.stdout.isatty() else None,
)

def is_interactive() -> bool:
    return sys.stdin.isatty()

def safe_input(prompt_text: str, default: str = "", allow_empty: bool = True) -> str:
    if not is_interactive():
        return default
    try:
        result = console.input(prompt_text).strip()
        if not result and not allow_empty:
            return default
        return result
    except (EOFError, KeyboardInterrupt):
        return ""

def pause_for_user() -> None:
    if is_interactive():
        try:
            console.input("\n[dim]Press [bold #00ffcc]Enter[/] to continue...[/]")
        except (EOFError, KeyboardInterrupt):
            pass

def print_version():
    console.print(f"""
[bold cyan]projectpulsewire[/bold cyan] version {__version__}

[dim]EasyEffects presets for PipeWire/PulseAudio on Linux[/dim]

[dim]--- Copyright 2026 Zenith Open Source Projects ---[/dim]
[dim]Developer: roshhellwett[/dim]
    """)

def print_error_context(message: str, context: str = "", solution: str = "") -> None:
    error_msg = f"[bold #ff4444]Error:[/bold #ff4444] {message}"
    if context:
        error_msg += f"\n[#ffa500]Context:[/] {context}"
    if solution:
        error_msg += f"\n[#00ffcc]Fix:[/] {solution}"
    
    console.print(Panel(error_msg, title="[bold #ff4444] ❌ Big Yikes [/]", border_style="#ff4444", box=box.ROUNDED))

def print_success(message: str, details: str = "") -> None:
    msg = f"[bold #00ffaa]{message}[/bold #00ffaa]"
    if details:
        msg += f"\n\n[dim]{details}[/dim]"
    
    console.print(Panel(msg, title="[bold #00ffaa] Success [/]", border_style="#00ffaa", box=box.ROUNDED))

def print_info(message: str, details: str = "") -> None:
    msg = f"[bold #00ccff]{message}[/bold #00ccff]"
    if details:
        msg += f"\n\n[dim]{details}[/dim]"
    
    console.print(Panel(msg, title="[bold #00ccff] Info [/]", border_style="#00ccff", box=box.ROUNDED))


def _parse_version_parts(version: str) -> tuple[int, ...]:
    parts = []
    for token in version.split("."):
        digits = "".join(ch for ch in token if ch.isdigit())
        if digits:
            parts.append(int(digits))
        else:
            parts.append(0)
    return tuple(parts)


def _is_newer_version(current_version: str, latest_version: str) -> bool:
    return _parse_version_parts(latest_version) > _parse_version_parts(current_version)


def get_update_cache_file() -> Path:
    cache_root = os.environ.get("XDG_CACHE_HOME")
    if cache_root:
        base_dir = Path(cache_root)
    else:
        base_dir = Path.home() / ".cache"
    return base_dir / "projectpulsewire" / "update-check.json"


def load_update_cache() -> dict:
    cache_file = get_update_cache_file()
    if not cache_file.exists():
        return {}
    try:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_update_cache(payload: dict) -> None:
    cache_file = get_update_cache_file()
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.debug(f"Failed to save update cache: {exc}")


def fetch_latest_version_from_pypi() -> str:
    req = urllib.request.Request(
        PYPI_JSON_URL,
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    return data.get("info", {}).get("version", "Unknown")


def get_current_installed_version() -> str:
    try:
        current_result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "projectpulsewire"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        logger.debug(f"pip show failed, falling back to __version__: {exc}")
        return __version__

    for line in current_result.stdout.splitlines():
        if line.startswith("Version:"):
            return line.replace("Version:", "").strip()

    return __version__


def perform_package_update() -> tuple[bool, str]:
    try:
        update_result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "projectpulsewire"],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (FileNotFoundError, OSError) as exc:
        return False, f"pip is not available: {exc}"
    except subprocess.TimeoutExpired:
        return False, "pip install timed out after 3 minutes."

    if update_result.returncode == 0:
        return True, "You are now running the latest version."

    error_output = update_result.stderr.strip() or update_result.stdout.strip() or "Unknown pip error"
    return False, error_output


def should_auto_check_updates() -> bool:
    if os.environ.get("PROJECTPULSEWIRE_DISABLE_AUTO_UPDATE", "").lower() in {"1", "true", "yes"}:
        return False

    cache = load_update_cache()
    last_checked = cache.get("last_checked_at")
    if not last_checked:
        return True

    try:
        last_checked_dt = datetime.fromisoformat(last_checked)
    except ValueError:
        return True

    return datetime.now(timezone.utc) - last_checked_dt >= timedelta(hours=UPDATE_CHECK_INTERVAL_HOURS)


def maybe_run_auto_update_check() -> None:
    if not is_interactive() or not should_auto_check_updates():
        return

    current_version = get_current_installed_version()
    latest_version = "Unknown"
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        latest_version = fetch_latest_version_from_pypi()
    except Exception as exc:  # network / parse / anything else
        logger.debug(f"Auto update check skipped: {exc}")
        save_update_cache({
            "last_checked_at": now_iso,
            "last_known_version": current_version,
            "last_error": str(exc),
        })
        return

    save_update_cache({
        "last_checked_at": now_iso,
        "last_known_version": latest_version,
    })

    if latest_version == "Unknown" or not _is_newer_version(current_version, latest_version):
        return

    console.print(Panel(
        f"[bold #00ccff]A new version of projectpulsewire is available.[/bold #00ccff]\n\n"
        f"[dim]Current:[/] [yellow]{current_version}[/yellow]\n"
        f"[dim]Latest:[/] [green]{latest_version}[/green]",
        title="[bold #ffa500] Auto Update Check [/]",
        border_style="#ffa500",
        box=box.ROUNDED,
    ))

    auto_mode = os.environ.get("PROJECTPULSEWIRE_AUTO_UPDATE", "").lower() in {"1", "true", "yes"}
    do_update = auto_mode or Confirm.ask("Update now before opening the menu?", default=True)

    if not do_update:
        return

    console.print("\n[dim]Updating package before startup...[/dim]\n")
    success, message = perform_package_update()
    if success:
        print_success("Update successful!", message)
    else:
        print_error_context("Automatic update failed", message, "Try: python -m projectpulsewire update")
    pause_for_user()

def show_main_menu() -> str:
    console.clear()
    
    # Get current active preset source
    active_source = presets_module.get_active_preset_source()
    source_display_map = {
        "modernpresets": "Modern Presets (Categorized)",
        "legacypresets": "Legacy Presets (Original)"
    }
    source_display = source_display_map.get(active_source, active_source)
    
    all_presets = presets_module.get_all_presets()
    installed_presets = presets_module.get_installed_presets()
    ee_dir = presets_module.get_easyeffects_presets_dir()
    ee_dir_display = str(ee_dir) if ee_dir else "Not detected"
    
    all_irs = irs_module.get_all_irs()
    installed_irs = irs_module.get_installed_irs()
    convolver_dir = irs_module.get_easyeffects_convolver_dir()
    convolver_dir_display = str(convolver_dir) if convolver_dir else "Not detected"
    
    panel_content = f"""
[bold #00ffcc]🔥 Welcome to projectpulsewire 🔥[/]
[italic dim]Premium EasyEffects presets for PipeWire/PulseAudio[/]

[bold #ff007f]✦ Quick Stats ✦[/]
  [#00ffcc]🎧 Presets:[/] {len(all_presets)} available / [green]{len(installed_presets)} installed[/]
  [#00ffcc]💿 IRS Data:[/] {len(all_irs)} available / [green]{len(installed_irs)} installed[/]
  [#ffa500]📁 Active Source:[/] [bold]{source_display}[/bold]
  [dim]📂 Presets Dir: {ee_dir_display}[/]
  [dim]📂 Conv Dir: {convolver_dir_display}[/]

[bold #ff007f]✦ Command Center ✦[/]

  [bold white on #ff007f] 1 [/]  [bold]Browse & Preview Presets (EQ)[/]
  [bold white on #ff007f] 2 [/]  [bold]Browse & Preview IRS (Convolution)[/]
  [bold white on #8a2be2] 3 [/]  [bold]Install Preset(s)[/]  🚀
  [bold white on #8a2be2] 4 [/]  [bold]Install IRS(s)[/]  🚀
  [bold white on #00ffcc] 5 [/]  [bold]View Installed Files[/]  ✨
  [bold white on #ff4444] 6 [/]  [bold]Remove Preset(s)/IRS(s)[/]  🗑️
  [bold white on #ffa500] 7 [/]  [bold]Switch Preset Source[/]  🔄
  [bold white on #ff7f50] 8 [/]  [bold]Update projectpulsewire[/]  ⚡
  [bold white on #555555] 9 [/]  [bold]Help & Commands[/]  💡
  [bold white on #00bfff] 10 [/] [bold]IRS Guide (What are IRS files?)[/]  🎓
  [bold white on #7b68ee] 11 [/] [bold]Setup Audio Stack (Auto-Install)[/]  🔧
  [bold white on #00ffcc] W [/]  [bold]Launch Web Dashboard (Browser UI)[/] 🌐
  [bold white on #555555] 0 [/]  [bold]Exit[/]  🚪
    """
    
    console.print(Panel(
        panel_content, 
        title="[bold #00ffcc] PROJECT PULSEWIRE PRO [/]", 
        border_style="#ff007f", 
        padding=(1, 3),
        box=box.ROUNDED
    ))
    console.print("[dim italic]--- Premium Audio Made Free | Developer: roshhellwett ---[/dim italic]\n")
    
    choice = safe_input(">> [bold #ff007f]Enter your vibe (0-11, or W for Web UI):[/] ", allow_empty=False)
    return choice

def handle_browse_presets() -> None:
    all_presets = presets_module.get_all_presets()
    installed = presets_module.get_installed_presets()
    
    if not all_presets:
        print_error_context(
            "No presets found!",
            "The presets directory appears to be empty",
            "Try updating the project: projectpulsewire update"
        )
        pause_for_user()
        return
    
    categories = presets_module.get_presets_by_category(all_presets)
    
    # Ensure categories is a proper dict with string keys (defensive)
    if not isinstance(categories, dict):
        console.print("[yellow]Error: Could not load categories.[/yellow]")
        pause_for_user()
        return
    
    # Convert keys to list explicitly to avoid dict_keys issues
    cat_list = sorted(list(categories.keys()))
    
    while True:
        console.clear()
        console.print(Panel("[bold #00ffcc]🎧 Preset Library[/]", border_style="#00ffcc", expand=False))
        
        for i, cat in enumerate(cat_list, 1):
            count = len(categories[cat])
            console.print(f"  [bold white on #8a2be2] {i} [/]  [#ff007f]{cat}[/] [dim]({count} presets)[/]")
        console.print(f"  [bold white on #8a2be2] A [/]  [#ff007f]All Presets[/] [dim]({len(all_presets)})[/]")
        console.print(f"  [bold white on #8a2be2] I [/]  [#ff007f]Installed Only[/] [dim]({len(installed)})[/]")
        console.print("  [bold white on #555555] B [/]  [bold]Back to Command Center[/]")
        
        choice = safe_input("\n>> [bold #00ffcc]Select category:[/] ").strip().lower()
        
        if choice == "b":
            return
        
        selected_presets = []
        if choice == "a":
            selected_presets = all_presets
            title = "All Presets"
        elif choice == "i":
            selected_presets = [p for p in all_presets if p["name"] in installed]
            title = "Installed Presets"
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(cat_list):
                selected_presets = categories[cat_list[idx]]
                title = f"{cat_list[idx]} Presets"
            else:
                console.print("\n[red]Invalid choice.[/red]")
                safe_input("Press Enter to continue...")
                continue
        else:
            console.print("\n[red]Invalid choice.[/red]")
            safe_input("Press Enter to continue...")
            continue
        
        if not selected_presets:
            console.print("\n[yellow]No presets in this category.[/yellow]")
            safe_input("Press Enter to continue...")
            continue
        
        while True:
            console.clear()
            console.print(f"\n[bold cyan]--- {title} ---[/bold cyan]\n")
            
            table = Table(show_header=True, header_style="bold #ff007f", box=box.ROUNDED, border_style="#00ffcc")
            table.add_column("#", style="bold white on #8a2be2", width=5, justify="center")
            table.add_column("✨ Preset Name", style="bold white")
            table.add_column("Status", style="dim", width=16)
            
            for i, preset in enumerate(selected_presets, 1):
                status = "✅ [bold #00ffaa]Installed[/]" if preset["name"] in installed else "⭕ [dim]Not installed[/dim]"
                table.add_row(str(i), f"[#00ffcc]{preset['name']}[/]", status)
            
            console.print(table)
            
            console.print("\n[bold]--- Actions ---[/bold]")
            console.print(f"  [cyan]1-{len(selected_presets)}[/cyan]  Preview preset details")
            console.print("  [cyan]B[/cyan]  Back to categories")
            
            choice = safe_input("\n>> Enter choice: ").strip().lower()
            
            if choice == "b":
                break
            
            if not choice.isdigit():
                console.print("\n[red]Invalid input.[/red]")
                safe_input("Press Enter to continue...")
                continue
            
            idx = int(choice) - 1
            if idx < 0 or idx >= len(selected_presets):
                console.print(f"\n[red]Invalid choice. Please enter 1-{len(selected_presets)}.[/red]")
                safe_input("Press Enter to continue...")
                continue
            
            preset = selected_presets[idx]
            show_preset_preview(preset)
            
            safe_input("\nPress Enter to continue...")

def show_preset_preview(preset: dict) -> None:
    console.clear()
    name = preset["name"]
    data = preset.get("data", {})
    installed = preset["name"] in presets_module.get_installed_presets()
    
    output = data.get("output", {})
    plugins_order = output.get("plugins_order", [])
    
    console.print(Panel(f"""
[bold #00ffcc]🎧 {name}[/]

[#ff007f]Status:[/] {'✅ [bold #00ffaa]Installed[/]' if installed else '⭕ [dim]Not installed[/dim]'}

[#8a2be2]Plugins included:[/]\n[dim]{', '.join(plugins_order) if plugins_order else 'No plugins found'}[/]
    """, title="🔍 Preset Preview", border_style="#00ffcc", padding=(1, 2), box=box.ROUNDED))

def handle_install_presets() -> None:
    all_presets = presets_module.get_all_presets()
    installed = presets_module.get_installed_presets()
    
    if not all_presets:
        print_error_context("No presets available", "The presets database is empty", "Update the project and try again")
        pause_for_user()
        return
    
    console.clear()
    console.print("\n[bold cyan]--- Install Preset(s) ---[/bold cyan]\n")
    
    table = Table(show_header=True, header_style="bold #8a2be2", box=box.ROUNDED, border_style="#ff007f")
    table.add_column("#", style="bold white on #ff007f", width=5, justify="center")
    table.add_column("🚀 Preset Name", style="bold white")
    table.add_column("Status", style="dim", width=16)
    
    for i, preset in enumerate(all_presets, 1):
        status = "✅ [bold #00ffaa]Installed[/]" if preset["name"] in installed else "⭕ [dim]Ready to install[/dim]"
        table.add_row(str(i), f"[#00ffcc]{preset['name']}[/]", status)
    
    console.print(table)
    
    console.print("\n[bold]--- Installation Options ---[/bold]")
    console.print("  [cyan]1[/cyan]  Install single preset (e.g., 1)")
    console.print("  [cyan]2[/cyan]  Install multiple presets (e.g., 1,2,3)")
    console.print("  [cyan]3[/cyan]  Install all non-installed presets")
    console.print("  [cyan]B[/cyan]  Back to main menu")
    
    choice = safe_input("\n>> Select option: ").strip().lower()
    
    if choice == "b":
        return
    
    if choice == "1":
        handle_install_single(all_presets, installed)
    elif choice == "2":
        handle_install_multiple(all_presets, installed)
    elif choice == "3":
        handle_install_all(all_presets, installed)
    else:
        console.print("\n[red]Invalid choice.[/red]")
        pause_for_user()

def handle_install_single(all_presets: list, installed: list) -> None:
    console.print("\n[yellow]Enter preset number to install:[/yellow]")
    choice = safe_input(">> ").strip()
    
    if not choice.isdigit():
        console.print("[red]Invalid choice.[/red]")
        pause_for_user()
        return
    
    idx = int(choice) - 1
    if idx < 0 or idx >= len(all_presets):
        console.print("[red]Invalid preset number.[/red]")
        pause_for_user()
        return
    
    preset = all_presets[idx]
    
    if preset["name"] in installed:
        console.print(f"\n[yellow]Preset '{preset['name']}' is already installed.[/yellow]")
        confirm = safe_input("Re-install? (Y/N): ").strip().lower()
        if confirm != "y":
            return
    
    console.print(f"\n[yellow]Installing '{preset['name']}'...[/yellow]")
    
    success, message = presets_module.install_preset(preset)
    
    if success:
        print_success("Preset installed successfully!", f"Preset: {preset['name']}\n{message}\n\nRestart EasyEffects to see the new preset.")
    else:
        print_error_context("Failed to install preset", message, "Check folder permissions")
    
    pause_for_user()

def handle_install_multiple(all_presets: list, installed: list) -> None:
    console.print("\n[yellow]Enter preset numbers (comma-separated, e.g., 1,2,3):[/yellow]")
    choice = safe_input(">> ").strip()
    
    if not choice:
        console.print("[yellow]No input received.[/yellow]")
        pause_for_user()
        return
    
    try:
        indices = [int(x.strip()) - 1 for x in choice.split(",")]
    except ValueError:
        console.print("[red]Invalid input. Use format: 1,2,3[/red]")
        pause_for_user()
        return
    
    presets_to_install = []
    already_installed = []
    invalid = []
    
    for idx in indices:
        if idx < 0 or idx >= len(all_presets):
            invalid.append(str(idx + 1))
            continue
        preset = all_presets[idx]
        if preset["name"] in installed:
            already_installed.append(preset["name"])
        else:
            presets_to_install.append(preset)
    
    if invalid:
        console.print(f"[yellow]Invalid numbers: {', '.join(invalid)}[/yellow]")
    
    if already_installed:
        console.print(f"[dim]Already installed: {', '.join(already_installed)}[/dim]")
    
    if not presets_to_install:
        console.print("[yellow]No new presets to install.[/yellow]")
        pause_for_user()
        return
    
    console.print(f"\n[cyan]Installing {len(presets_to_install)} preset(s): {', '.join(p['name'] for p in presets_to_install)}[/cyan]")
    
    confirm = safe_input("\nConfirm installation? (Y/N): ").strip().lower()
    if confirm != "y":
        console.print("[yellow]Installation cancelled.[/yellow]")
        pause_for_user()
        return
    
    success, message = presets_module.install_multiple_presets(presets_to_install)
    
    if success:
        print_success("Presets installed!", f"{message}\n\nRestart EasyEffects to see the new presets.")
    else:
        print_error_context("Failed to install presets", message, "Check folder permissions")
    
    pause_for_user()

def handle_install_all(all_presets: list, installed: list) -> None:
    not_installed = [p for p in all_presets if p["name"] not in installed]
    
    if not not_installed:
        console.print("\n[green]All presets are already installed![/green]")
        pause_for_user()
        return
    
    console.print(f"\n[cyan]Will install {len(not_installed)} presets:[/cyan]")
    console.print(", ".join(p["name"] for p in not_installed))
    
    confirm = safe_input("\nConfirm installation? (Y/N): ").strip().lower()
    if confirm != "y":
        console.print("[yellow]Installation cancelled.[/yellow]")
        pause_for_user()
        return
    
    success, message = presets_module.install_multiple_presets(not_installed)
    
    if success:
        print_success("All presets installed!", f"{message}\n\nRestart EasyEffects to see the new presets.")
    else:
        print_error_context("Failed to install presets", message, "Check folder permissions")
    
    pause_for_user()

def handle_view_installed() -> None:
    installed_presets = presets_module.get_installed_presets()
    installed_irs = irs_module.get_installed_irs()
    
    console.clear()
    console.print(Panel("[bold #00ffcc]✨ Installed Vibes & Convolvers[/]", border_style="#00ffcc", expand=False))
    
    ee_dir = presets_module.get_easyeffects_presets_dir()
    convolver_dir = irs_module.get_easyeffects_convolver_dir()
    
    console.print(f"[dim]📂 Output Presets:[/] {ee_dir}")
    console.print(f"[dim]📂 IRS Convolvers:[/] {convolver_dir}\n")
    
    if not installed_presets and not installed_irs:
        console.print("[bold #ff4444]💀 It's empty in here...[/]")
        console.print("[dim]Use 'Install Preset(s)' or 'Install IRS(s)' to inject some flavor.[/dim]")
        pause_for_user()
        return
    
    if installed_presets:
        console.print(f"[bold #ff007f]✦ Presets ({len(installed_presets)}) ✦[/]\n")
        table = Table(show_header=True, header_style="bold #ff007f", box=box.ROUNDED, border_style="#8a2be2")
        table.add_column("#", style="bold white on #ff007f", width=5, justify="center")
        table.add_column("🎧 Preset Name", style="bold white")
        
        for i, name in enumerate(installed_presets, 1):
            table.add_row(str(i), f"[#00ffcc]{name}[/]")
        
        console.print(table)
        console.print()
    
    if installed_irs:
        console.print(f"[bold #8a2be2]✦ IRS Files ({len(installed_irs)}) ✦[/]\n")
        table = Table(show_header=True, header_style="bold #8a2be2", box=box.ROUNDED, border_style="#00ffcc")
        table.add_column("#", style="bold white on #8a2be2", width=5, justify="center")
        table.add_column("💿 IRS Name", style="bold white")
        
        for i, name in enumerate(installed_irs, 1):
            table.add_row(str(i), f"[#ff007f]{name}[/]")
        
        console.print(table)
        console.print()
    
    console.print(f"[dim]Total Status: {len(installed_presets)} preset(s) and {len(installed_irs)} IRS file(s) installed like a pro.[/dim]")
    pause_for_user()

def handle_remove_items() -> None:
    installed_presets = presets_module.get_installed_presets()
    installed_irs = irs_module.get_installed_irs()
    
    if not installed_presets and not installed_irs:
        print_error_context("Nothing installed", "No presets or IRS to remove", "Install items first")
        pause_for_user()
        return
    
    console.clear()
    console.print(Panel("[bold #ff4444]🗑️ Deletion Center[/]", border_style="#ff4444", expand=False))
    
    console.print("[bold #ff4444]✦ Select Target ✦[/]")
    console.print("  [bold white on #ff4444] 1 [/]  [bold]Remove Preset(s)[/]")
    console.print("  [bold white on #ff4444] 2 [/]  [bold]Remove IRS(s)[/]")
    console.print("  [bold white on #555555] B [/]  [bold]Back to Command Center[/]")
    
    choice = safe_input("\n>> [bold #ff4444]Select option:[/] ").strip().lower()
    
    if choice == "b":
        return
    
    if choice == "1":
        handle_remove_presets_menu(installed_presets)
    elif choice == "2":
        handle_remove_irs_menu(installed_irs)
    else:
        console.print("\n[red]Invalid choice.[/red]")
        pause_for_user()

def handle_remove_presets_menu(installed_presets: list) -> None:
    if not installed_presets:
        console.print("[yellow]No presets installed.[/yellow]")
        pause_for_user()
        return
    
    console.clear()
    console.print(Panel("[bold #ff4444]🗑️ Remove Preset(s)[/]", border_style="#ff4444", expand=False))
    
    table = Table(show_header=True, header_style="bold #ff007f", box=box.ROUNDED, border_style="#8a2be2")
    table.add_column("#", style="bold white on #ff4444", width=5, justify="center")
    table.add_column("🎧 Preset Name", style="bold white")
    
    for i, name in enumerate(installed_presets, 1):
        table.add_row(str(i), f"[#00ffcc]{name}[/]")
    
    console.print(table)
    
    console.print("\n[bold #ff4444]✦ Options ✦[/]")
    console.print("  [bold white on #ff4444] 1 [/]  [bold]Remove single preset[/]")
    console.print("  [bold white on #ff4444] 2 [/]  [bold]Remove multiple presets (e.g., 1,2,3)[/]")
    console.print("  [bold white on #ff007f] 3 [/]  [bold]Nuke all presets[/]")
    console.print("  [bold white on #555555] B [/]  [bold]Back to safety[/]")
    
    choice = safe_input("\n>> [bold #ff4444]Select option:[/] ").strip().lower()
    
    if choice == "b" or choice == "":
        return
    
    if choice == "1":
        handle_remove_single_preset(installed_presets)
    elif choice == "2":
        handle_remove_multiple_presets(installed_presets)
    elif choice == "3":
        handle_remove_all_presets(installed_presets)
    else:
        console.print("\n[red]Invalid choice.[/red]")
        pause_for_user()

def handle_remove_single_preset(installed_presets: list) -> None:
    choice = safe_input("\n>> Enter preset number to remove: ").strip()
    
    if not choice.isdigit():
        console.print("[red]Invalid choice.[/red]")
        pause_for_user()
        return
    
    idx = int(choice) - 1
    if idx < 0 or idx >= len(installed_presets):
        console.print("[red]Invalid preset number.[/red]")
        pause_for_user()
        return
    
    preset_name = installed_presets[idx]
    confirm = safe_input(f"\nRemove '{preset_name}'? (Y/N): ").strip().lower()
    
    if confirm != "y":
        console.print("[yellow]Removal cancelled.[/yellow]")
        pause_for_user()
        return
    
    success, message = presets_module.remove_preset(preset_name)
    
    if success:
        print_success("Preset removed!", message)
    else:
        print_error_context("Failed to remove preset", message, "Check folder permissions")
    
    pause_for_user()

def handle_remove_multiple_presets(installed_presets: list) -> None:
    choice = safe_input("\n>> Enter preset numbers (comma-separated, e.g., 1,2,3): ").strip()
    
    if not choice:
        console.print("[yellow]No input received.[/yellow]")
        pause_for_user()
        return
    
    try:
        indices = [int(x.strip()) - 1 for x in choice.split(",")]
    except ValueError:
        console.print("[red]Invalid input. Use format: 1,2,3[/red]")
        pause_for_user()
        return
    
    presets_to_remove = []
    invalid = []
    
    for idx in indices:
        if idx < 0 or idx >= len(installed_presets):
            invalid.append(str(idx + 1))
            continue
        presets_to_remove.append(installed_presets[idx])
    
    if invalid:
        console.print(f"[yellow]Invalid numbers: {', '.join(invalid)}[/yellow]")
    
    if not presets_to_remove:
        console.print("[yellow]No valid presets selected.[/yellow]")
        pause_for_user()
        return
    
    console.print(f"\n[cyan]Will remove: {', '.join(presets_to_remove)}[/cyan]")
    confirm = safe_input("\nConfirm removal? (Y/N): ").strip().lower()
    
    if confirm != "y":
        console.print("[yellow]Removal cancelled.[/yellow]")
        pause_for_user()
        return
    
    success, message = presets_module.remove_multiple_presets(presets_to_remove)
    
    if success:
        print_success("Presets removed!", message)
    else:
        print_error_context("Failed to remove presets", message, "Check folder permissions")
    
    pause_for_user()

def handle_remove_all_presets(installed_presets: list) -> None:
    console.print(f"\n[red]WARNING: This will remove ALL {len(installed_presets)} installed presets![/red]")
    confirm = safe_input("Are you sure? (Y/N): ").strip().lower()
    
    if confirm != "y":
        console.print("[yellow]Removal cancelled.[/yellow]")
        pause_for_user()
        return
    
    success, message = presets_module.remove_multiple_presets(installed_presets)
    
    if success:
        print_success("All presets removed!", message)
    else:
        print_error_context("Failed to remove presets", message, "Check folder permissions")
    
    pause_for_user()

def handle_remove_irs_menu(installed_irs: list) -> None:
    if not installed_irs:
        console.print("[yellow]No IRS files installed.[/yellow]")
        pause_for_user()
        return
    
    console.clear()
    console.print(Panel("[bold #ff4444]🗑️ Remove IRS Convolvers[/]", border_style="#ff4444", expand=False))
    
    table = Table(show_header=True, header_style="bold #8a2be2", box=box.ROUNDED, border_style="#ff007f")
    table.add_column("#", style="bold white on #ff4444", width=5, justify="center")
    table.add_column("💿 IRS Name", style="bold white")
    
    for i, name in enumerate(installed_irs, 1):
        table.add_row(str(i), f"[#00ffcc]{name}[/]")
    
    console.print(table)
    
    console.print("\n[bold #ff4444]✦ Options ✦[/]")
    console.print("  [bold white on #ff4444] 1 [/]  [bold]Remove single IRS[/]")
    console.print("  [bold white on #ff4444] 2 [/]  [bold]Remove multiple IRS (e.g., 1,2,3)[/]")
    console.print("  [bold white on #ff007f] 3 [/]  [bold]Nuke all IRS[/]")
    console.print("  [bold white on #555555] B [/]  [bold]Back to safety[/]")
    
    choice = safe_input("\n>> [bold #ff4444]Select option:[/] ").strip().lower()
    
    if choice == "b" or choice == "":
        return
    
    if choice == "1":
        handle_remove_single_irs(installed_irs)
    elif choice == "2":
        handle_remove_multiple_irs(installed_irs)
    elif choice == "3":
        handle_remove_all_irs(installed_irs)
    else:
        console.print("\n[red]Invalid choice.[/red]")
        pause_for_user()

def handle_remove_single_irs(installed_irs: list) -> None:
    choice = safe_input("\n>> Enter IRS number to remove: ").strip()
    
    if not choice.isdigit():
        console.print("[red]Invalid choice.[/red]")
        pause_for_user()
        return
    
    idx = int(choice) - 1
    if idx < 0 or idx >= len(installed_irs):
        console.print("[red]Invalid IRS number.[/red]")
        pause_for_user()
        return
    
    irs_name = installed_irs[idx]
    confirm = safe_input(f"\nRemove '{irs_name}'? (Y/N): ").strip().lower()
    
    if confirm != "y":
        console.print("[yellow]Removal cancelled.[/yellow]")
        pause_for_user()
        return
    
    success, message = irs_module.remove_irs(irs_name)
    
    if success:
        print_success("IRS removed!", message)
    else:
        print_error_context("Failed to remove IRS", message, "Check folder permissions")
    
    pause_for_user()

def handle_remove_multiple_irs(installed_irs: list) -> None:
    choice = safe_input("\n>> Enter IRS numbers (comma-separated, e.g., 1,2,3): ").strip()
    
    if not choice:
        console.print("[yellow]No input received.[/yellow]")
        pause_for_user()
        return
    
    try:
        indices = [int(x.strip()) - 1 for x in choice.split(",")]
    except ValueError:
        console.print("[red]Invalid input. Use format: 1,2,3[/red]")
        pause_for_user()
        return
    
    irs_to_remove = []
    invalid = []
    
    for idx in indices:
        if idx < 0 or idx >= len(installed_irs):
            invalid.append(str(idx + 1))
            continue
        irs_to_remove.append(installed_irs[idx])
    
    if invalid:
        console.print(f"[yellow]Invalid numbers: {', '.join(invalid)}[/yellow]")
    
    if not irs_to_remove:
        console.print("[yellow]No valid IRS selected.[/yellow]")
        pause_for_user()
        return
    
    console.print(f"\n[cyan]Will remove: {', '.join(irs_to_remove)}[/cyan]")
    confirm = safe_input("\nConfirm removal? (Y/N): ").strip().lower()
    
    if confirm != "y":
        console.print("[yellow]Removal cancelled.[/yellow]")
        pause_for_user()
        return
    
    success, message = irs_module.remove_multiple_irs(irs_to_remove)
    
    if success:
        print_success("IRS files removed!", message)
    else:
        print_error_context("Failed to remove IRS", message, "Check folder permissions")
    
    pause_for_user()

def handle_remove_all_irs(installed_irs: list) -> None:
    console.print(f"\n[red]WARNING: This will remove ALL {len(installed_irs)} installed IRS files![/red]")
    confirm = safe_input("Are you sure? (Y/N): ").strip().lower()
    
    if confirm != "y":
        console.print("[yellow]Removal cancelled.[/yellow]")
        pause_for_user()
        return
    
    success, message = irs_module.remove_multiple_irs(installed_irs)
    
    if success:
        print_success("All IRS removed!", message)
    else:
        print_error_context("Failed to remove IRS", message, "Check folder permissions")
    
    pause_for_user()

def handle_browse_irs() -> None:
    all_irs = irs_module.get_all_irs()
    installed_irs = irs_module.get_installed_irs()
    
    if not all_irs:
        print_error_context(
            "No IRS files found!",
            "The IRS directory appears to be empty",
            "Try updating the project: projectpulsewire update"
        )
        pause_for_user()
        return
    
    categories = irs_module.get_irs_by_category(all_irs)
    
    # Ensure categories is a proper dict with string keys (defensive)
    if not isinstance(categories, dict):
        console.print("[yellow]Error: Could not load categories.[/yellow]")
        pause_for_user()
        return
    
    # Convert keys to list explicitly to avoid dict_keys issues
    cat_list = sorted(list(categories.keys()))
    
    while True:
        console.clear()
        console.print(Panel("[bold #00ffcc]💿 IRS Convolvers Database[/]", border_style="#00ffcc", expand=False))
        
        for i, cat in enumerate(cat_list, 1):
            count = len(categories[cat])
            console.print(f"  [bold white on #8a2be2] {i} [/]  [#ff007f]{cat}[/] [dim]({count} IRS)[/]")
        console.print(f"  [bold white on #8a2be2] A [/]  [#ff007f]All IRS[/] [dim]({len(all_irs)})[/]")
        console.print(f"  [bold white on #8a2be2] I [/]  [#ff007f]Installed Only[/] [dim]({len(installed_irs)})[/]")
        console.print("  [bold white on #555555] B [/]  [bold]Back to Command Center[/]")
        
        choice = safe_input("\n>> [bold #00ffcc]Select category:[/] ").strip().lower()
        
        if choice == "b":
            return
        
        selected_irs = []
        if choice == "a":
            selected_irs = all_irs
            title = "All IRS Files"
        elif choice == "i":
            selected_irs = [irs for irs in all_irs if irs["name"] in installed_irs]
            title = "Installed IRS Files"
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(cat_list):
                selected_irs = categories[cat_list[idx]]
                title = f"{cat_list[idx]} IRS"
            else:
                console.print("\n[red]Invalid choice.[/red]")
                safe_input("Press Enter to continue...")
                continue
        else:
            console.print("\n[red]Invalid choice.[/red]")
            safe_input("Press Enter to continue...")
            continue
        
        if not selected_irs:
            console.print("\n[yellow]No IRS in this category.[/yellow]")
            safe_input("Press Enter to continue...")
            continue
        
        while True:
            console.clear()
            console.print(f"\n[bold cyan]--- {title} ---[/bold cyan]\n")
            
            table = Table(show_header=True, header_style="bold #ff007f", box=box.ROUNDED, border_style="#00ffcc")
            table.add_column("#", style="bold white on #8a2be2", width=5, justify="center")
            table.add_column("💿 IRS Name", style="bold white")
            table.add_column("Status", style="dim", width=16)
            table.add_column("Size", style="dim", width=10)
            
            for i, irs in enumerate(selected_irs, 1):
                status = "✅ [bold #00ffaa]Installed[/]" if irs["name"] in installed_irs else "⭕ [dim]Not installed[/dim]"
                size_kb = irs.get("size", 0) // 1024
                size_str = f"{size_kb} KB" if size_kb > 0 else "Unknown"
                table.add_row(str(i), f"[#00ffcc]{irs['name']}[/]", status, size_str)
            
            console.print(table)
            
            console.print("\n[bold]--- Actions ---[/bold]")
            console.print(f"  [cyan]1-{len(selected_irs)}[/cyan]  View IRS details")
            console.print("  [cyan]B[/cyan]  Back to categories")
            
            choice = safe_input("\n>> Enter choice: ").strip().lower()
            
            if choice == "b":
                break
            
            if not choice.isdigit():
                console.print("\n[red]Invalid input.[/red]")
                safe_input("Press Enter to continue...")
                continue
            
            idx = int(choice) - 1
            if idx < 0 or idx >= len(selected_irs):
                console.print(f"\n[red]Invalid choice. Please enter 1-{len(selected_irs)}.[/red]")
                safe_input("Press Enter to continue...")
                continue
            
            irs_file = selected_irs[idx]
            show_irs_preview(irs_file)
            
            safe_input("\nPress Enter to continue...")

def show_irs_preview(irs_file: dict) -> None:
    console.clear()
    name = irs_file["name"]
    installed = irs_file["name"] in irs_module.get_installed_irs()
    
    size_kb = irs_file.get("size", 0) // 1024
    size_str = f"{size_kb} KB" if size_kb > 0 else "Unknown"
    use_guide = irs_module.get_irs_use_guide(name)
    
    console.print(Panel(f"""
[bold #00ffcc]💿 {name}[/]

[#ff007f]Status:[/] {'✅ [bold #00ffaa]Installed[/]' if installed else '⭕ [dim]Not installed[/dim]'}
[#ff007f]Size:[/] {size_str}
[#ff007f]Use Case:[/] {use_guide}

[bold #ffa500]🎓 What is an IRS file?[/]
[dim]An Impulse Response (IRS) captures the sonic signature of a real
acoustic space or audio device. When loaded into EasyEffects'
Convolver plugin, it shapes your audio to sound like it's being
played through that space/device.[/]

[bold #00ccff]🏛️ How to use this IRS in EasyEffects:[/]
[dim]1. Install this IRS file using option 4 from the main menu
2. Open EasyEffects -> Output Effects tab
3. Click "Add Effect" -> Select "Convolver"
4. In Convolver settings, click the import/file icon
5. Browse to your IRS directory and select the .irs file
6. IMPORTANT: Add a Limiter AFTER the Convolver to prevent clipping[/]
    """, title="🔍 IRS Preview & Guide", border_style="#00ffcc", padding=(1, 2), box=box.ROUNDED))

def handle_install_irs() -> None:
    all_irs = irs_module.get_all_irs()
    installed_irs = irs_module.get_installed_irs()
    
    if not all_irs:
        print_error_context("No IRS available", "The IRS database is empty", "Update the project and try again")
        pause_for_user()
        return
    
    console.clear()
    console.print(Panel("[bold #00ffcc]🚀 Install IRS Convolvers[/]", border_style="#00ffcc", expand=False))
    
    table = Table(show_header=True, header_style="bold #8a2be2", box=box.ROUNDED, border_style="#ff007f")
    table.add_column("#", style="bold white on #ff007f", width=5, justify="center")
    table.add_column("🚀 IRS Name", style="bold white")
    table.add_column("Status", style="dim", width=16)
    table.add_column("Size", style="dim", width=10)
    
    for i, irs in enumerate(all_irs, 1):
        status = "✅ [bold #00ffaa]Installed[/]" if irs["name"] in installed_irs else "⭕ [dim]Ready to install[/dim]"
        size_kb = irs.get("size", 0) // 1024
        size_str = f"{size_kb} KB" if size_kb > 0 else "Unknown"
        table.add_row(str(i), f"[#00ffcc]{irs['name']}[/]", status, size_str)
    
    console.print(table)
    
    console.print("\n[bold]--- Installation Options ---[/bold]")
    console.print("  [cyan]1[/cyan]  Install single IRS (e.g., 1)")
    console.print("  [cyan]2[/cyan]  Install multiple IRS (e.g., 1,2,3)")
    console.print("  [cyan]3[/cyan]  Install all non-installed IRS")
    console.print("  [cyan]B[/cyan]  Back to main menu")
    
    choice = safe_input("\n>> Select option: ").strip().lower()
    
    if choice == "b":
        return
    
    if choice == "1":
        handle_install_single_irs(all_irs, installed_irs)
    elif choice == "2":
        handle_install_multiple_irs(all_irs, installed_irs)
    elif choice == "3":
        handle_install_all_irs(all_irs, installed_irs)
    else:
        console.print("\n[red]Invalid choice.[/red]")
        pause_for_user()

def handle_install_single_irs(all_irs: list, installed_irs: list) -> None:
    console.print("\n[yellow]Enter IRS number to install:[/yellow]")
    choice = safe_input(">> ").strip()
    
    if not choice.isdigit():
        console.print("[red]Invalid choice.[/red]")
        pause_for_user()
        return
    
    idx = int(choice) - 1
    if idx < 0 or idx >= len(all_irs):
        console.print("[red]Invalid IRS number.[/red]")
        pause_for_user()
        return
    
    irs_file = all_irs[idx]
    
    if irs_file["name"] in installed_irs:
        console.print(f"\n[yellow]IRS '{irs_file['name']}' is already installed.[/yellow]")
        confirm = safe_input("Re-install? (Y/N): ").strip().lower()
        if confirm != "y":
            return
    
    console.print(f"\n[yellow]Installing '{irs_file['name']}'...[/yellow]")
    
    success, message = irs_module.install_irs(irs_file)
    
    if success:
        print_success("IRS installed successfully!", f"IRS: {irs_file['name']}\n{message}\n\nRestart EasyEffects to see the new IRS in Convolver.")
    else:
        print_error_context("Failed to install IRS", message, "Check folder permissions")
    
    pause_for_user()

def handle_install_multiple_irs(all_irs: list, installed_irs: list) -> None:
    console.print("\n[yellow]Enter IRS numbers (comma-separated, e.g., 1,2,3):[/yellow]")
    choice = safe_input(">> ").strip()
    
    if not choice:
        console.print("[yellow]No input received.[/yellow]")
        pause_for_user()
        return
    
    try:
        indices = [int(x.strip()) - 1 for x in choice.split(",")]
    except ValueError:
        console.print("[red]Invalid input. Use format: 1,2,3[/red]")
        pause_for_user()
        return
    
    irs_to_install = []
    already_installed = []
    invalid = []
    
    for idx in indices:
        if idx < 0 or idx >= len(all_irs):
            invalid.append(str(idx + 1))
            continue
        irs_file = all_irs[idx]
        if irs_file["name"] in installed_irs:
            already_installed.append(irs_file["name"])
        else:
            irs_to_install.append(irs_file)
    
    if invalid:
        console.print(f"[yellow]Invalid numbers: {', '.join(invalid)}[/yellow]")
    
    if already_installed:
        console.print(f"[dim]Already installed: {', '.join(already_installed)}[/dim]")
    
    if not irs_to_install:
        console.print("[yellow]No new IRS to install.[/yellow]")
        pause_for_user()
        return
    
    console.print(f"\n[cyan]Installing {len(irs_to_install)} IRS file(s): {', '.join(irs['name'] for irs in irs_to_install)}[/cyan]")
    
    confirm = safe_input("\nConfirm installation? (Y/N): ").strip().lower()
    if confirm != "y":
        console.print("[yellow]Installation cancelled.[/yellow]")
        pause_for_user()
        return
    
    success, message = irs_module.install_multiple_irs(irs_to_install)
    
    if success:
        print_success("IRS files installed!", f"{message}\n\nRestart EasyEffects to see the new IRS files.")
    else:
        print_error_context("Failed to install IRS", message, "Check folder permissions")
    
    pause_for_user()

def handle_install_all_irs(all_irs: list, installed_irs: list) -> None:
    not_installed = [irs for irs in all_irs if irs["name"] not in installed_irs]
    
    if not not_installed:
        console.print("\n[green]All IRS files are already installed![/green]")
        pause_for_user()
        return
    
    console.print(f"\n[cyan]Will install {len(not_installed)} IRS files:[/cyan]")
    console.print(", ".join(irs["name"] for irs in not_installed[:10]))
    if len(not_installed) > 10:
        console.print(f"  ... and {len(not_installed) - 10} more")
    
    confirm = safe_input("\nConfirm installation? (Y/N): ").strip().lower()
    if confirm != "y":
        console.print("[yellow]Installation cancelled.[/yellow]")
        pause_for_user()
        return
    
    success, message = irs_module.install_multiple_irs(not_installed)
    
    if success:
        print_success("All IRS installed!", f"{message}\n\nRestart EasyEffects to see the new IRS files.")
    else:
        print_error_context("Failed to install IRS", message, "Check folder permissions")
    
    pause_for_user()

def handle_switch_preset_source() -> None:
    """Handle switching between legacy and modern presets."""
    console.clear()
    console.print(Panel("[bold #ffa500]🔄 Switch Preset Source[/]", border_style="#ffa500", expand=False))
    
    available_sources = presets_module.get_available_preset_sources()
    current_source = presets_module.get_active_preset_source()
    
    if not available_sources:
        print_error_context(
            "No preset sources found",
            "Neither legacypresets nor modernpresets folder has presets",
            "Check that the preset folders exist and contain .json files"
        )
        pause_for_user()
        return
    
    console.print("\n[bold]Available Preset Sources:[/bold]\n")
    
    source_display_map = {
        "legacypresets": "Legacy Presets (Original)",
        "modernpresets": "Modern Presets (Categorized)"
    }
    
    for i, source in enumerate(available_sources, 1):
        display_name = source_display_map.get(source, source)
        is_current = " [bold green]✓ (Currently Active)[/]" if source == current_source else ""
        console.print(f"  [bold white on #8a2be2] {i} [/]  {display_name}{is_current}")
    
    console.print("  [bold white on #555555] B [/]  [bold]Back to main menu[/]")
    
    console.print()
    choice = safe_input(">> Select source: ").strip().lower()
    
    if choice == "b":
        return
    
    if not choice.isdigit():
        console.print("\n[red]Invalid input.[/red]")
        pause_for_user()
        return
    
    idx = int(choice) - 1
    if idx < 0 or idx >= len(available_sources):
        console.print("\n[red]Invalid choice.[/red]")
        pause_for_user()
        return
    
    selected_source = available_sources[idx]
    if presets_module.set_active_preset_source(selected_source):
        source_display = source_display_map.get(selected_source, selected_source)
        print_success(
            "Preset source switched!",
            f"Now using: {source_display}\n\nYou can now browse and install presets from the selected source."
        )
    else:
        print_error_context(
            "Failed to switch preset source",
            "Could not activate the selected source",
            "Try again or report this issue"
        )
    
    pause_for_user()

def handle_update() -> None:
    console.clear()
    console.print("\n[bold cyan]--- Update projectpulsewire ---[/bold cyan]\n")
    console.print("[dim]Checking for updates from PyPI...[/dim]\n")

    try:
        latest_version = fetch_latest_version_from_pypi()
    except Exception as e:  # network / parse / anything else
        logger.error(f"Failed to fetch latest version from PyPI: {e}")
        print_error_context(
            "Could not check for updates",
            "Failed to reach PyPI",
            "Check internet connection",
        )
        console.print("\n[dim]--- Copyright 2026 Zenith Open Source Projects ---[/dim]")
        pause_for_user()
        return

    current_version = get_current_installed_version()

    console.print(f"  [dim]Current version:[/dim] [yellow]{current_version}[/yellow]")
    console.print(f"  [dim]Latest version:[/dim]  [green]{latest_version}[/green]\n")

    save_update_cache({
        "last_checked_at": datetime.now(timezone.utc).isoformat(),
        "last_known_version": latest_version,
    })

    if latest_version != "Unknown" and _is_newer_version(current_version, latest_version):
        console.print("[bold yellow]A new version is available![/bold yellow]\n")

        do_update = Confirm.ask("Do you want to update now?", default=True)

        if do_update:
            console.print("\n[dim]Updating package...[/dim]\n")

            success, message = perform_package_update()
            if success:
                print_success("Update successful!", message)
            else:
                print_error_context("Update failed", message, "Try: pip install --upgrade projectpulsewire")
    else:
        print_info("You're up to date!", f"No updates available. Current version: {current_version}")

    console.print("\n[dim]--- Copyright 2026 Zenith Open Source Projects ---[/dim]")
    pause_for_user()

def handle_irs_guide() -> None:
    """Comprehensive IRS education screen."""
    console.clear()
    console.print(Panel("""
[bold #ffa500]🎓 What are IRS (Impulse Response) Files?[/]

[bold white]An IRS file captures the sonic fingerprint of a real acoustic space
or audio device.[/] When loaded into EasyEffects' [bold #00ffcc]Convolver[/] plugin,
it reshapes your audio to sound like it's being played through that
space or device.

[bold #ff007f]Think of it like Instagram filters, but for your ears![/]


[bold #00ccff]📁 Where are IRS files installed?[/]

  [dim]• Native install:[/]  [green]~/.config/easyeffects/irs/[/]
  [dim]• Flatpak install:[/] [green]~/.var/app/com.github.wwmm.easyeffects/config/easyeffects/irs/[/]


[bold #00ccff]🏛️ Step-by-Step: How to Use IRS in EasyEffects[/]

  [bold white]Step 1:[/] Install an IRS file using [bold]option 4[/] from the main menu
  [bold white]Step 2:[/] Open [bold #00ffcc]EasyEffects[/] application
  [bold white]Step 3:[/] Go to [bold]Output Effects[/] tab
  [bold white]Step 4:[/] Click [bold]"Add Effect"[/] -> Select [bold]"Convolver"[/]
  [bold white]Step 5:[/] In the Convolver settings, click the [bold]import/file icon[/]
  [bold white]Step 6:[/] Browse to your IRS directory and select the [bold].irs[/] file
  [bold white]Step 7:[/] The Convolver is now processing your audio!


[bold #ff4444]⚠️ Important Tips:[/]

  [dim]• Always add a [bold]Limiter[/] AFTER the Convolver to prevent clipping
  • Some IRS files change volume significantly — adjust input/output gain
  • Different IRS files suit different use cases:
    [#00ffcc]▸[/] "Bass" IRS → Adds deep low-end to weak speakers
    [#00ffcc]▸[/] "Dolby" IRS → Surround sound on stereo headphones
    [#00ffcc]▸[/] "DFX" IRS → General audio enhancement & clarity
    [#00ffcc]▸[/] "Creative" IRS → Gaming 3D audio & spatial sound
    [#00ffcc]▸[/] "XHR" IRS → High-resolution clarity improvement[/]

[dim]--- Copyright 2026 Zenith Open Source Projects | Developer: roshhellwett ---[/dim]
    """, title="[bold #ffa500] 🎓 IRS Guide — Complete Tutorial [/]", border_style="#ffa500", padding=(1, 3), box=box.ROUNDED))
    pause_for_user()


def handle_setup_audio() -> None:
    """Auto-detect and optionally install Linux audio dependencies."""
    console.clear()
    
    distro_family, distro_name = deps_installer.detect_distro()
    
    console.print(Panel(f"""
[bold #00ffcc]🔧 Audio Stack Setup — Auto-Dependency Installer[/]

[#ff007f]Detected OS:[/] {distro_name}
[#ff007f]Distro Family:[/] {distro_family.upper()}

[dim]Scanning for essential audio packages...[/dim]
    """, title="[bold #7b68ee] 🔧 Audio Stack Setup [/]", border_style="#7b68ee", padding=(1, 3), box=box.ROUNDED))
    
    if distro_family == "unknown":
        print_error_context(
            "Could not detect your Linux distribution",
            "The file /etc/os-release was not found or could not be parsed",
            "You may need to install audio packages manually for your distribution"
        )
        pause_for_user()
        return
    
    # Check all packages
    status_list = deps_installer.get_all_package_status(distro_family)
    
    table = Table(
        show_header=True,
        header_style="bold #ff007f",
        box=box.ROUNDED,
        border_style="#7b68ee",
        title="[bold]Audio Stack Dependencies[/]"
    )
    table.add_column("Package", style="bold white", min_width=20)
    table.add_column("Status", width=14, justify="center")
    table.add_column("Priority", width=12, justify="center")
    table.add_column("Description", style="dim")
    table.add_column("Package Name", style="dim #888888")
    
    missing_critical = []
    missing_optional = []
    
    for pkg in status_list:
        if pkg["installed"]:
            status = "✅ Installed"
        else:
            status = "❌ Missing"
        
        priority = "[bold #ff4444]CRITICAL[/]" if pkg["critical"] else "[#ffa500]Recommended[/]"
        
        table.add_row(
            f"[#00ffcc]{pkg['name']}[/]",
            status,
            priority,
            pkg["description"],
            pkg["pkg_name"]
        )
        
        if not pkg["installed"]:
            if pkg["critical"]:
                missing_critical.append(pkg["pkg_name"])
            else:
                missing_optional.append(pkg["pkg_name"])
    
    console.print(table)
    console.print()
    
    # Check PipeWire status
    pw_running = deps_installer.check_pipewire_running()
    if pw_running:
        console.print("  [✅] [bold #00ffaa]PipeWire is running as your audio server[/]")
    else:
        console.print("  [❌] [bold #ff4444]PipeWire is NOT detected as your audio server[/]")
        console.print("      [dim]You may be running PulseAudio directly. PipeWire is recommended.[/dim]")
    
    # Check EasyEffects version
    ee_version = deps_installer.check_easyeffects_version()
    if ee_version:
        console.print(f"  [✅] [bold #00ffaa]EasyEffects version: {ee_version}[/]")
    
    console.print()
    
    # Show install commands if packages are missing
    all_missing = missing_critical + missing_optional
    
    if not all_missing:
        print_success(
            "All audio packages are installed!",
            "Your Linux audio stack is fully configured. Enjoy premium sound!"
        )
    else:
        if missing_critical:
            console.print(f"[bold #ff4444]Missing critical packages ({len(missing_critical)}):[/] {', '.join(missing_critical)}")
        if missing_optional:
            console.print(f"[bold #ffa500]Missing recommended packages ({len(missing_optional)}):[/] {', '.join(missing_optional)}")
        
        console.print()
        
        # Show the install command
        install_cmd = deps_installer.get_install_command(distro_family, all_missing)
        if install_cmd:
            console.print(Panel(f"""
[bold #00ccff]Run this command to install all missing packages:[/]

[bold green]{install_cmd}[/]

[dim]Copy and paste this into your terminal. You will need sudo/admin access.[/dim]
            """, title="[bold] 📝 Install Command [/]", border_style="#00ccff", box=box.ROUNDED))
        
        # Ask if user wants to auto-install
        try:
            do_install = Confirm.ask(
                "\n[bold]Would you like to install missing packages now?[/]",
                default=False
            )
            if do_install:
                console.print("\n[dim]Running package manager (may ask for sudo password)...[/dim]\n")
                success, message = deps_installer.install_missing_packages(distro_family, all_missing)
                if success:
                    print_success("Packages installed successfully!", message)
                else:
                    print_error_context(
                        "Installation encountered issues",
                        message,
                        f"Try running manually: {install_cmd}"
                    )
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Skipped installation.[/dim]")
    
    console.print("\n[dim]--- Copyright 2026 Zenith Open Source Projects ---[/dim]")
    pause_for_user()


def handle_help() -> None:
    console.print("""
[bold cyan]--- Help & Commands ---[/bold cyan]

[bold yellow]Quick Commands:[/bold yellow]
  [green]python -m projectpulsewire start[/green]         Start interactive menu mode (Option W for Web UI)
  [green]python -m projectpulsewire serve[/green]         Launch local Web Dashboard UI (Port 8080)
  [green]python -m projectpulsewire web[/green]           Launch local Web Dashboard UI
  [green]python -m projectpulsewire list[/green]          List all available presets
  [green]python -m projectpulsewire list-irs[/green]     List all available IRS files
  [green]python -m projectpulsewire install <name>[/green]  Install a preset by name
  [green]python -m projectpulsewire install-irs <name>[/green] Install an IRS by name
  [green]python -m projectpulsewire installed[/green]    List installed presets & IRS
  [green]python -m projectpulsewire remove <name>[/green]  Remove a preset
  [green]python -m projectpulsewire remove-irs <name>[/green] Remove an IRS
  [green]python -m projectpulsewire setup[/green]          Setup audio stack (install dependencies)
  [green]python -m projectpulsewire update[/green]        Check for updates
  [green]python -m projectpulsewire --help[/green]         Show all options
  [green]python -m projectpulsewire --version[/green]      Show version

[bold yellow]Auto Update:[/bold yellow]
  [dim]• Interactive startup now checks PyPI automatically once every 24 hours[/dim]
  [dim]• Set PROJECTPULSEWIRE_DISABLE_AUTO_UPDATE=1 to disable startup checks[/dim]
  [dim]• Set PROJECTPULSEWIRE_AUTO_UPDATE=1 to auto-install updates without prompting[/dim]

[bold yellow]Installation:[/bold yellow]
  [green]pip install projectpulsewire[/green]

[bold yellow]How It Works:[/bold yellow]
  [dim]• Output Presets -> ~/.config/easyeffects/output/ (speakers/headphones)[/dim]
  [dim]• Input Presets -> ~/.config/easyeffects/input/ (microphone)[/dim]
  [dim]• IRS Files -> ~/.config/easyeffects/irs/ (Convolver impulse responses)[/dim]
  [dim]• Flatpak: ~/.var/app/com.github.wwmm.easyeffects/config/easyeffects/[/dim]
  [dim]• Restart EasyEffects after installing new items[/dim]
  [dim]• Find presets in EasyEffects preset manager[/dim]
  [dim]• Find IRS in EasyEffects Convolver plugin[/dim]

[bold yellow]🎓 IRS Quick Guide:[/bold yellow]
  [dim]• IRS = Impulse Response files for the Convolver effect[/dim]
  [dim]• They shape your audio like an Instagram filter for sound[/dim]
  [dim]• Install via menu option 4, then load in EasyEffects Convolver[/dim]
  [dim]• Use menu option 9 for the full IRS guide & tutorial[/dim]

[dim]--- Copyright 2026 Zenith Open Source Projects | Developer: roshhellwett ---[/dim]
    """)
    pause_for_user()

def handle_serve_web(host: str = "0.0.0.0", port: int = 8080, open_browser: bool = True) -> None:
    from projectpulsewire.web import start_server

    display_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    console.clear()
    console.print(Panel(
        f"[bold #00ffcc]🚀 Launching ProjectPulsewire Web Studio...[/]\n\n"
        f"  [dim]• Host Address:[/] [bold #ffffff]{display_host}[/] [dim](0.0.0.0 / WSL Bridge)[/]\n"
        f"  [dim]• Initial Port:[/] [bold #ffffff]{port}[/]\n"
        f"  [dim]• Auto-Open Browser:[/] [green]{'Yes' if open_browser else 'No'}[/]\n\n"
        f"[dim]Press [bold #ff4466]Ctrl+C[/bold #ff4466] in terminal or click Shutdown in Web UI to stop.[/dim]",
        title="[bold #00ffcc] 🌐 ProjectPulsewire Local Web Server [/]",
        border_style="#00ffcc",
        box=box.ROUNDED,
    ))
    try:
        server, actual_port = start_server(host=host, port=port, open_browser=open_browser)
        console.print(f"\n[bold #00ffaa]✨ Server is live at:[/] [bold underline #00ccff]http://{display_host}:{actual_port}/[/bold underline #00ccff]\n")
        server.start(block=True)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping local web server...[/yellow]")
    except Exception as e:
        logger.error(f"Failed to start web server: {e}")
        print_error_context("Failed to start web server", str(e), f"Ensure port {port} is accessible")
        pause_for_user()

def main_menu_loop() -> None:
    maybe_run_auto_update_check()
    while True:
        try:
            choice = show_main_menu()
            
            if choice == "1":
                handle_browse_presets()
            elif choice == "2":
                handle_browse_irs()
            elif choice == "3":
                handle_install_presets()
            elif choice == "4":
                handle_install_irs()
            elif choice == "5":
                handle_view_installed()
            elif choice == "6":
                handle_remove_items()
            elif choice == "7":
                handle_switch_preset_source()
            elif choice == "8":
                handle_update()
            elif choice == "9":
                handle_help()
            elif choice == "10":
                handle_irs_guide()
            elif choice == "11":
                handle_setup_audio()
            elif choice.lower() in ("w", "web", "serve"):
                handle_serve_web()
            elif choice == "0":
                console.print("\n[cyan]Thank you for using projectpulsewire![/cyan]")
                console.print("[dim]--- Copyright 2026 Zenith Open Source Projects | Developer: roshhellwett ---[/dim]\n")
                break
            else:
                if choice:
                    console.print(f"\n[red]Invalid choice '{choice}'. Please enter 0-11 or W.[/red]")
                else:
                    console.print("\n[red]No input received. Please enter 0-11 or W.[/red]")
                pause_for_user()
        except KeyboardInterrupt:
            console.print("\n\n[cyan]Goodbye![/cyan]")
            console.print("[dim]--- Copyright 2026 Zenith Open Source Projects | Developer: roshhellwett ---[/dim]\n")
            break
        except Exception as e:
            logger.error(f"Menu error: {e}")
            print_error_context("An error occurred", str(e), "Try restarting the application")
            pause_for_user()

@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-V", help="Show version and exit", is_eager=True
    ),
):
    if version:
        print_version()
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        main_menu_loop()

@app.command()
def start():
    """Start interactive menu mode."""
    main_menu_loop()

@app.command()
def version():
    """Show version information."""
    print_version()

@app.command()
def update():
    """Check for updates and upgrade projectpulsewire from PyPI."""
    handle_update()

@app.command(name="list")
def list_cmd(category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category")):
    """List all available presets."""
    all_presets = presets_module.get_all_presets()
    
    if not all_presets:
        console.print("[yellow]No presets found.[/yellow]")
        raise typer.Exit(code=1)
    
    if category:
        categories = presets_module.get_presets_by_category(all_presets)
        if category in categories:
            presets_to_show = categories[category]
        else:
            console.print(f"[yellow]Category '{category}' not found.[/yellow]")
            raise typer.Exit(code=1)
    else:
        presets_to_show = all_presets
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="cyan")
    
    for i, preset in enumerate(presets_to_show, 1):
        table.add_row(str(i), preset["name"])
    
    console.print(table)

@app.command()
def install(preset_name: str = typer.Argument(..., help="Preset name to install")):
    """Install a preset to EasyEffects."""
    preset = presets_module.get_preset_by_name(preset_name)
    
    if not preset:
        console.print(f"[red]Preset '{preset_name}' not found.[/red]")
        console.print("[dim]Use 'projectpulsewire list' to see available presets.[/dim]")
        raise typer.Exit(code=1)
    
    console.print(f"\n[yellow]Installing '{preset['name']}'...[/yellow]")
    
    success, message = presets_module.install_preset(preset)
    
    if success:
        console.print(Panel(
            f"[green]Preset installed successfully![/green]\n\n"
            f"  Preset: {preset['name']}\n"
            f"  Please restart EasyEffects.",
            title="Success",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[red]Failed to install preset.[/red]\n\n  Reason: {message}",
            title="Error",
            border_style="red",
        ))
        raise typer.Exit(code=1)

@app.command()
def installed():
    """List installed presets."""
    installed = presets_module.get_installed_presets()
    
    if not installed:
        console.print("[yellow]No presets installed.[/yellow]")
        raise typer.Exit()
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Preset Name", style="cyan")
    
    for i, name in enumerate(installed, 1):
        table.add_row(str(i), name)
    
    console.print(table)

@app.command()
def remove(preset_name: str = typer.Argument(..., help="Preset name to remove")):
    """Remove a preset from EasyEffects."""
    success, message = presets_module.remove_preset(preset_name)
    
    if success:
        console.print(Panel(
            f"[green]Preset removed![/green]\n\n  {message}",
            title="Success",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[red]Failed to remove preset.[/red]\n\n  {message}",
            title="Error",
            border_style="red",
        ))
        raise typer.Exit(code=1)

@app.command()
def browse():
    """Browse presets interactively."""
    handle_browse_presets()

@app.command()
def list_irs(category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category")):
    """List all available IRS files."""
    all_irs = irs_module.get_all_irs()
    
    if not all_irs:
        console.print("[yellow]No IRS files found.[/yellow]")
        raise typer.Exit(code=1)
    
    if category:
        categories = irs_module.get_irs_by_category(all_irs)
        if category in categories:
            irs_to_show = categories[category]
        else:
            console.print(f"[yellow]Category '{category}' not found.[/yellow]")
            raise typer.Exit(code=1)
    else:
        irs_to_show = all_irs
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="cyan")
    table.add_column("Size", style="dim", width=10)
    
    for i, irs in enumerate(irs_to_show, 1):
        size_kb = irs.get("size", 0) // 1024
        size_str = f"{size_kb} KB" if size_kb > 0 else "Unknown"
        table.add_row(str(i), irs["name"], size_str)
    
    console.print(table)

@app.command()
def install_irs(irs_name: str = typer.Argument(..., help="IRS name to install")):
    """Install an IRS file to EasyEffects convolver."""
    irs_file = irs_module.get_irs_by_name(irs_name)
    
    if not irs_file:
        console.print(f"[red]IRS '{irs_name}' not found.[/red]")
        console.print("[dim]Use 'projectpulsewire list-irs' to see available IRS.[/dim]")
        raise typer.Exit(code=1)
    
    console.print(f"\n[yellow]Installing '{irs_file['name']}'...[/yellow]")
    
    success, message = irs_module.install_irs(irs_file)
    
    if success:
        console.print(Panel(
            f"[green]IRS installed successfully![/green]\n\n"
            f"  IRS: {irs_file['name']}\n"
            f"  Please restart EasyEffects.",
            title="Success",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[red]Failed to install IRS.[/red]\n\n  Reason: {message}",
            title="Error",
            border_style="red",
        ))
        raise typer.Exit(code=1)

@app.command()
def remove_irs(irs_name: str = typer.Argument(..., help="IRS name to remove")):
    """Remove an IRS file from EasyEffects convolver."""
    success, message = irs_module.remove_irs(irs_name)
    
    if success:
        console.print(Panel(
            f"[green]IRS removed![/green]\n\n  {message}",
            title="Success",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[red]Failed to remove IRS.[/red]\n\n  {message}",
            title="Error",
            border_style="red",
        ))
        raise typer.Exit(code=1)

@app.command()
def browse_irs():
    """Browse IRS files interactively."""
    handle_browse_irs()

@app.command()
def setup():
    """Setup Linux audio stack — detect and install essential audio packages."""
    handle_setup_audio()

@app.command()
def irs_guide():
    """Show the IRS (Impulse Response) usage guide."""
    handle_irs_guide()

@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host address to bind to (0.0.0.0 for WSL/LAN)"),
    port: int = typer.Option(8080, "--port", "-p", help="Port to listen on"),
    browser: bool = typer.Option(True, "--browser/--no-browser", help="Open default web browser automatically"),
):
    """Start local web server and browser dashboard."""
    handle_serve_web(host=host, port=port, open_browser=browser)

@app.command()
def web(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host address to bind to (0.0.0.0 for WSL/LAN)"),
    port: int = typer.Option(8080, "--port", "-p", help="Port to listen on"),
    browser: bool = typer.Option(True, "--browser/--no-browser", help="Open default web browser automatically"),
):
    """Start local web server (alias for 'serve')."""
    handle_serve_web(host=host, port=port, open_browser=browser)

@app.command()
def dashboard(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host address to bind to (0.0.0.0 for WSL/LAN)"),
    port: int = typer.Option(8080, "--port", "-p", help="Port to listen on"),
    browser: bool = typer.Option(True, "--browser/--no-browser", help="Open default web browser automatically"),
):
    """Start local web server (alias for 'serve')."""
    handle_serve_web(host=host, port=port, open_browser=browser)

if __name__ == "__main__":
    app()
