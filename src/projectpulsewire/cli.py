import os
import sys
import logging
from pathlib import Path
from datetime import datetime

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.prompt import Prompt, Confirm

from projectpulsewire import __version__
from projectpulsewire import presets as presets_module
from projectpulsewire import irs_handler as irs_module

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = typer.Typer(help="projectpulsewire — EasyEffects presets for PipeWire/PulseAudio", add_completion=False)
console = Console()

def is_interactive() -> bool:
    return sys.stdin.isatty()

def safe_input(prompt_text: str, default: str = "", allow_empty: bool = True) -> str:
    if not is_interactive():
        return default
    try:
        result = input(prompt_text).strip()
        if not result and not allow_empty:
            return default
        return result
    except (EOFError, KeyboardInterrupt):
        return ""

def pause_for_user() -> None:
    if is_interactive():
        try:
            input("\nPress Enter to continue...")
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
    error_msg = f"[red]Error:[/red] {message}"
    if context:
        error_msg += f"\n[yellow]Context:[/yellow] {context}"
    if solution:
        error_msg += f"\n[green]Solution:[/green] {solution}"
    
    console.print(Panel(error_msg, title="Something went wrong", border_style="red"))

def print_success(message: str, details: str = "") -> None:
    msg = f"[green]{message}[/green]"
    if details:
        msg += f"\n\n{details}"
    
    console.print(Panel(msg, title="Success", border_style="green"))

def print_info(message: str, details: str = "") -> None:
    msg = f"[cyan]{message}[/cyan]"
    if details:
        msg += f"\n\n{details}"
    
    console.print(Panel(msg, title="Info", border_style="cyan"))

def show_main_menu() -> str:
    console.clear()
    all_presets = presets_module.get_all_presets()
    installed_presets = presets_module.get_installed_presets()
    ee_dir = presets_module.get_easyeffects_presets_dir()
    ee_dir_display = str(ee_dir) if ee_dir else "Not detected"
    
    all_irs = irs_module.get_all_irs()
    installed_irs = irs_module.get_installed_irs()
    convolver_dir = irs_module.get_easyeffects_convolver_dir()
    convolver_dir_display = str(convolver_dir) if convolver_dir else "Not detected"
    
    console.print(Panel(f"""
[bold cyan]Welcome to projectpulsewire[/bold cyan]
[dim]EasyEffects presets for PipeWire/PulseAudio[/dim]

[bold]---[/bold] [yellow]Quick Info[/yellow] [bold]---[/bold]
  Available Presets: {len(all_presets)}  |  Installed Presets: {len(installed_presets)}
  Available IRS: {len(all_irs)}  |  Installed IRS: {len(installed_irs)}
  Output Presets Folder: {ee_dir_display}
  Convolver Folder: {convolver_dir_display}

[bold]---[/bold] [yellow]Menu Options[/yellow] [bold]---[/bold]

  [green]1[/green]  Browse & Preview Presets (EQ)
  [green]2[/green]  Browse & Preview IRS (Convolution)
  [green]3[/green]  Install Preset(s)
  [green]4[/green]  Install IRS(s)
  [green]5[/green]  View Installed (Presets + IRS)
  [green]6[/green]  Remove Preset(s)/IRS(s)
  [green]7[/green]  Update projectpulsewire
  [green]8[/green]  Help & Commands
  [green]9[/green]  Exit
    """, title="[bold cyan]projectpulsewire Menu[/bold cyan]", border_style="cyan", padding=(1, 2)))
    console.print("[dim]--- Copyright 2026 Zenith Open Source Projects | Developer: roshhellwett ---[/dim]")
    
    choice = safe_input("\n>> Enter your choice (1-9): ", allow_empty=False)
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
        console.print("\n[bold cyan]--- Browse Presets ---[/bold cyan]\n")
        
        console.print("[bold]Categories:[/bold]")
        for i, cat in enumerate(cat_list, 1):
            count = len(categories[cat])
            console.print(f"  [cyan]{i}[/cyan]  {cat} ({count} presets)")
        console.print(f"  [cyan]A[/cyan]  All Presets ({len(all_presets)})")
        console.print(f"  [cyan]I[/cyan]  Installed Only ({len(installed)})")
        console.print("  [cyan]B[/cyan]  Back to main menu")
        
        choice = safe_input("\n>> Select category (number/A/I/B): ").strip().lower()
        
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
            console.print("\n[yellow]No presets in this category.[/red]")
            safe_input("Press Enter to continue...")
            continue
        
        while True:
            console.clear()
            console.print(f"\n[bold cyan]--- {title} ---[/bold cyan]\n")
            
            table = Table(show_header=True, header_style="bold magenta", box=None)
            table.add_column("#", style="dim", width=5)
            table.add_column("Preset Name", style="cyan")
            table.add_column("Status", style="yellow", width=12)
            
            for i, preset in enumerate(selected_presets, 1):
                status = "[green]Installed[/green]" if preset["name"] in installed else "[dim]Not installed[/dim]"
                table.add_row(f"[cyan]{i}[/cyan]", f"[green]{preset['name']}[/green]", status)
            
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
            
            try:
                idx = int(choice) - 1
                if idx < 0 or idx >= len(selected_presets):
                    console.print(f"\n[red]Invalid choice. Please enter 1-{len(selected_presets)}.[/red]")
                    safe_input("Press Enter to continue...")
                    continue
            except ValueError:
                console.print("\n[red]Invalid input.[/red]")
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
[bold cyan]{name}[/bold cyan]

[yellow]Status:[/yellow] {'[green]Installed[/green]' if installed else '[dim]Not installed[/dim]'}

[yellow]Plugins in this preset:[/yellow]
{', '.join(plugins_order) if plugins_order else 'No plugins found'}
    """, title="Preset Preview", border_style="cyan", padding=(1, 2)))

def handle_install_presets() -> None:
    all_presets = presets_module.get_all_presets()
    installed = presets_module.get_installed_presets()
    
    if not all_presets:
        print_error_context("No presets available", "The presets database is empty", "Update the project and try again")
        pause_for_user()
        return
    
    console.clear()
    console.print("\n[bold cyan]--- Install Preset(s) ---[/bold cyan]\n")
    
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("#", style="dim", width=5)
    table.add_column("Preset Name", style="cyan")
    table.add_column("Status", style="yellow", width=15)
    
    for i, preset in enumerate(all_presets, 1):
        status = "[green]Installed[/green]" if preset["name"] in installed else "[dim]Not installed[/dim]"
        table.add_row(f"[cyan]{i}[/cyan]", f"[green]{preset['name']}[/green]", status)
    
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
    console.print("\n[bold cyan]--- Installed Items ---[/bold cyan]\n")
    
    ee_dir = presets_module.get_easyeffects_presets_dir()
    convolver_dir = irs_module.get_easyeffects_convolver_dir()
    
    console.print(f"[dim]Output Presets Folder: {ee_dir}[/dim]")
    console.print(f"[dim]Convolver Folder: {convolver_dir}[/dim]\n")
    
    if not installed_presets and not installed_irs:
        console.print("[yellow]No presets or IRS files installed yet.[/yellow]")
        console.print("[dim]Use 'Install Preset(s)' or 'Install IRS(s)' to add files to EasyEffects.[/dim]")
        pause_for_user()
        return
    
    if installed_presets:
        console.print(f"[bold magenta]--- Presets ({len(installed_presets)}) ---[/bold magenta]\n")
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("#", style="dim", width=5)
        table.add_column("Preset Name", style="cyan")
        
        for i, name in enumerate(installed_presets, 1):
            table.add_row(f"[cyan]{i}[/cyan]", f"[green]{name}[/green]")
        
        console.print(table)
        console.print()
    
    if installed_irs:
        console.print(f"[bold magenta]--- IRS Files ({len(installed_irs)}) ---[/bold magenta]\n")
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("#", style="dim", width=5)
        table.add_column("IRS Name", style="cyan")
        
        for i, name in enumerate(installed_irs, 1):
            table.add_row(f"[cyan]{i}[/cyan]", f"[green]{name}[/green]")
        
        console.print(table)
        console.print()
    
    console.print(f"[dim]Total: {len(installed_presets)} preset(s), {len(installed_irs)} IRS file(s) installed[/dim]")
    pause_for_user()

def handle_remove_items() -> None:
    installed_presets = presets_module.get_installed_presets()
    installed_irs = irs_module.get_installed_irs()
    
    if not installed_presets and not installed_irs:
        print_error_context("Nothing installed", "No presets or IRS to remove", "Install items first")
        pause_for_user()
        return
    
    console.clear()
    console.print("\n[bold cyan]--- Remove Preset(s) or IRS(s) ---[/bold cyan]\n")
    
    console.print("[bold]--- Select Type ---[/bold]")
    console.print("  [cyan]1[/cyan]  Remove Preset(s)")
    console.print("  [cyan]2[/cyan]  Remove IRS(s)")
    console.print("  [cyan]B[/cyan]  Back to main menu")
    
    choice = safe_input("\n>> Select option: ").strip().lower()
    
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
    console.print("\n[bold cyan]--- Remove Preset(s) ---[/bold cyan]\n")
    
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("#", style="dim", width=5)
    table.add_column("Preset Name", style="cyan")
    
    for i, name in enumerate(installed_presets, 1):
        table.add_row(f"[cyan]{i}[/cyan]", f"[green]{name}[/green]")
    
    console.print(table)
    
    console.print("\n[bold]--- Removal Options ---[/bold]")
    console.print("  [cyan]1[/cyan]  Remove single preset")
    console.print("  [cyan]2[/cyan]  Remove multiple presets (e.g., 1,2,3)")
    console.print("  [cyan]3[/cyan]  Remove all presets")
    console.print("  [cyan]B[/cyan]  Back")
    
    choice = safe_input("\n>> Select option: ").strip().lower()
    
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
    console.print("\n[bold cyan]--- Remove IRS(s) ---[/bold cyan]\n")
    
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("#", style="dim", width=5)
    table.add_column("IRS Name", style="cyan")
    
    for i, name in enumerate(installed_irs, 1):
        table.add_row(f"[cyan]{i}[/cyan]", f"[green]{name}[/green]")
    
    console.print(table)
    
    console.print("\n[bold]--- Removal Options ---[/bold]")
    console.print("  [cyan]1[/cyan]  Remove single IRS")
    console.print("  [cyan]2[/cyan]  Remove multiple IRS (e.g., 1,2,3)")
    console.print("  [cyan]3[/cyan]  Remove all IRS")
    console.print("  [cyan]B[/cyan]  Back")
    
    choice = safe_input("\n>> Select option: ").strip().lower()
    
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
    
    console.print("\n[bold]--- Removal Options ---[/bold]")
    console.print("  [cyan]1[/cyan]  Remove single preset")
    console.print("  [cyan]2[/cyan]  Remove multiple presets (e.g., 1,2,3)")
    console.print("  [cyan]3[/cyan]  Remove all installed presets")
    console.print("  [cyan]B[/cyan]  Back to main menu")
    
    choice = safe_input("\n>> Select option: ").strip().lower()
    
    if choice == "b":
        return
    
    if choice == "1":
        handle_remove_single(installed)
    elif choice == "2":
        handle_remove_multiple(installed)
    elif choice == "3":
        handle_remove_all(installed)
    else:
        console.print("\n[red]Invalid choice.[/red]")
        pause_for_user()

def handle_remove_single(installed: list) -> None:
    choice = safe_input("\n>> Enter preset number to remove: ").strip()
    
    if not choice.isdigit():
        console.print("[red]Invalid choice.[/red]")
        pause_for_user()
        return
    
    idx = int(choice) - 1
    if idx < 0 or idx >= len(installed):
        console.print("[red]Invalid preset number.[/red]")
        pause_for_user()
        return
    
    preset_name = installed[idx]
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

def handle_remove_multiple(installed: list) -> None:
    choice = safe_input("\n>> Enter preset numbers (comma-separated, e.g., 1,2,3): ").strip()
    
    try:
        indices = [int(x.strip()) - 1 for x in choice.split(",")]
    except ValueError:
        console.print("[red]Invalid input. Use format: 1,2,3[/red]")
        pause_for_user()
        return
    
    presets_to_remove = []
    invalid = []
    
    for idx in indices:
        if idx < 0 or idx >= len(installed):
            invalid.append(str(idx + 1))
            continue
        presets_to_remove.append(installed[idx])
    
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

def handle_remove_all(installed: list) -> None:
    console.print(f"\n[red]WARNING: This will remove ALL {len(installed)} installed presets![/red]")
    confirm = safe_input("Are you sure? (Y/N): ").strip().lower()
    
    if confirm != "y":
        console.print("[yellow]Removal cancelled.[/yellow]")
        pause_for_user()
        return
    
    success, message = presets_module.remove_multiple_presets(installed)
    
    if success:
        print_success("All presets removed!", message)
    else:
        print_error_context("Failed to remove presets", message, "Check folder permissions")
    
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
        console.print("\n[bold cyan]--- Browse IRS Files ---[/bold cyan]\n")
        
        console.print("[bold]Categories:[/bold]")
        for i, cat in enumerate(cat_list, 1):
            count = len(categories[cat])
            console.print(f"  [cyan]{i}[/cyan]  {cat} ({count} IRS)")
        console.print(f"  [cyan]A[/cyan]  All IRS ({len(all_irs)})")
        console.print(f"  [cyan]I[/cyan]  Installed Only ({len(installed_irs)})")
        console.print("  [cyan]B[/cyan]  Back to main menu")
        
        choice = safe_input("\n>> Select category (number/A/I/B): ").strip().lower()
        
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
            
            table = Table(show_header=True, header_style="bold magenta", box=None)
            table.add_column("#", style="dim", width=5)
            table.add_column("IRS Name", style="cyan")
            table.add_column("Status", style="yellow", width=15)
            table.add_column("Size", style="dim", width=10)
            
            for i, irs in enumerate(selected_irs, 1):
                status = "[green]Installed[/green]" if irs["name"] in installed_irs else "[dim]Not installed[/dim]"
                size_kb = irs.get("size", 0) // 1024
                size_str = f"{size_kb} KB" if size_kb > 0 else "Unknown"
                table.add_row(f"[cyan]{i}[/cyan]", f"[green]{irs['name']}[/green]", status, size_str)
            
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
            
            try:
                idx = int(choice) - 1
                if idx < 0 or idx >= len(selected_irs):
                    console.print(f"\n[red]Invalid choice. Please enter 1-{len(selected_irs)}.[/red]")
                    safe_input("Press Enter to continue...")
                    continue
            except ValueError:
                console.print("\n[red]Invalid input.[/red]")
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
    
    console.print(Panel(f"""
[bold cyan]{name}[/bold cyan]

[yellow]Status:[/yellow] {'[green]Installed[/green]' if installed else '[dim]Not installed[/dim]'}
[yellow]File Size:[/yellow] {size_str}

[dim]This is an Impulse Response file for EasyEffects Convolver plugin.[/dim]
[dim]IRS files create reverb effects and room correction.[/dim]
    """, title="IRS Preview", border_style="cyan", padding=(1, 2)))

def handle_install_irs() -> None:
    all_irs = irs_module.get_all_irs()
    installed_irs = irs_module.get_installed_irs()
    
    if not all_irs:
        print_error_context("No IRS available", "The IRS database is empty", "Update the project and try again")
        pause_for_user()
        return
    
    console.clear()
    console.print("\n[bold cyan]--- Install IRS(s) ---[/bold cyan]\n")
    
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("#", style="dim", width=5)
    table.add_column("IRS Name", style="cyan")
    table.add_column("Status", style="yellow", width=15)
    table.add_column("Size", style="dim", width=10)
    
    for i, irs in enumerate(all_irs, 1):
        status = "[green]Installed[/green]" if irs["name"] in installed_irs else "[dim]Not installed[/dim]"
        size_kb = irs.get("size", 0) // 1024
        size_str = f"{size_kb} KB" if size_kb > 0 else "Unknown"
        table.add_row(f"[cyan]{i}[/cyan]", f"[green]{irs['name']}[/green]", status, size_str)
    
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

def handle_update() -> None:
    import subprocess
    
    console.clear()
    console.print("\n[bold cyan]--- Update projectpulsewire ---[/bold cyan]\n")
    console.print("[dim]Checking for updates from PyPI...[/dim]\n")
    
    try:
        result = subprocess.run(
            ["pip", "index", "versions", "projectpulsewire"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            available_versions = []
            for line in lines:
                if "Available versions:" in line:
                    available_versions = line.replace("Available versions:", "").strip().split(", ")
                    break
            
            current_result = subprocess.run(
                ["pip", "show", "projectpulsewire"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            current_version = "Unknown"
            for line in current_result.stdout.split("\n"):
                if line.startswith("Version:"):
                    current_version = line.replace("Version:", "").strip()
                    break
            
            latest_version = available_versions[-1] if available_versions else "Unknown"
            
            console.print(f"  [dim]Current version:[/dim] [yellow]{current_version}[/yellow]")
            console.print(f"  [dim]Latest version:[/dim]  [green]{latest_version}[/green]\n")
            
            if current_version != latest_version and latest_version != "Unknown":
                console.print("[bold yellow]A new version is available![/bold yellow]\n")
                
                do_update = Confirm.ask("Do you want to update now?", default=True)
                
                if do_update:
                    console.print("\n[dim]Updating package...[/dim]\n")
                    
                    update_result = subprocess.run(
                        ["pip", "install", "--upgrade", "projectpulsewire"],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    
                    if update_result.returncode == 0:
                        print_success("Update successful!", "You are now running the latest version.")
                    else:
                        print_error_context("Update failed", update_result.stderr, "Try: pip install --upgrade projectpulsewire")
            else:
                print_info("You're up to date!", f"No updates available. Current version: {current_version}")
        else:
            print_error_context("Could not check for updates", result.stderr, "Check internet connection")
            
    except subprocess.TimeoutExpired:
        print_error_context("Update check timed out", "Request took too long", "Check internet connection")
    except FileNotFoundError:
        print_error_context("pip not found", "Python pip not in PATH", "Ensure Python is properly installed")
    except Exception as e:
        logger.error(f"Update error: {e}")
        print_error_context("Unexpected error", str(e), "Try again later")
    
    console.print("\n[dim]--- Copyright 2026 Zenith Open Source Projects ---[/dim]")
    pause_for_user()

def handle_help() -> None:
    console.print(f"""
[bold cyan]--- Help & Commands ---[/bold cyan]

[bold yellow]Quick Commands:[/bold yellow]
  [green]python -m projectpulsewire start[/green]         Start interactive menu mode
  [green]python -m projectpulsewire list[/green]          List all available presets
  [green]python -m projectpulsewire list-irs[/green]     List all available IRS files
  [green]python -m projectpulsewire install <name>[/green]  Install a preset by name
  [green]python -m projectpulsewire install-irs <name>[/green] Install an IRS by name
  [green]python -m projectpulsewire installed[/green]    List installed presets & IRS
  [green]python -m projectpulsewire remove <name>[/green]  Remove a preset
  [green]python -m projectpulsewire remove-irs <name>[/green] Remove an IRS
  [green]python -m projectpulsewire update[/green]        Check for updates
  [green]python -m projectpulsewire --help[/green]         Show all options
  [green]python -m projectpulsewire --version[/green]      Show version

[bold yellow]Installation:[/bold yellow]
  [green]pip install projectpulsewire[/green]

[bold yellow]How It Works:[/bold yellow]
  [dim]• Output Presets → ~/.config/easyeffects/output/ (speakers/headphones)[/dim]
  [dim]• Input Presets → ~/.config/easyeffects/input/ (microphone)[/dim]
  [dim]• IRS Files → ~/.config/easyeffects/irs/ (Convolver impulse responses)[/dim]
  [dim]• Restart EasyEffects after installing new items[/dim]
  [dim]• Find presets in EasyEffects preset manager[/dim]
  [dim]• Find IRS in EasyEffects Convolver plugin[/dim]

[dim]--- Copyright 2026 Zenith Open Source Projects | Developer: roshhellwett ---[/dim]
    """)
    pause_for_user()

def main_menu_loop() -> None:
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
                handle_update()
            elif choice == "8":
                handle_help()
            elif choice == "9":
                console.print("\n[cyan]Thank you for using projectpulsewire![/cyan]")
                console.print("[dim]--- Copyright 2026 Zenith Open Source Projects | Developer: roshhellwett ---[/dim]\n")
                break
            else:
                console.print(f"\n[red]Invalid choice '{choice}'. Please enter 1-9.[/red]")
                pause_for_user()
        except KeyboardInterrupt:
            console.print("\n\n[cyan]Goodbye![/cyan]")
            console.print("[dim]--- Copyright 2026 Zenith Open Source Projects | Developer: roshhellwett ---[/dim]\n")
            break
        except Exception as e:
            logger.error(f"Menu error: {e}")
            print_error_context("An error occurred", str(e), "Try restarting the application")
            pause_for_user()

@app.callback()
def main(version: bool = typer.Option(False, "--version", "-V", help="Show version and exit")):
    if version:
        print_version()
        raise typer.Exit()

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
def list_cmd(category: str | None = typer.Option(None, "--category", "-c", help="Filter by category")):
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
def list_irs(category: str | None = typer.Option(None, "--category", "-c", help="Filter by category")):
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

if __name__ == "__main__":
    app()
