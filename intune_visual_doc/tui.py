"""
Interactive Terminal User Interface (TUI) for Intune Visual Doc.
Features system prerequisites checking, browser profile selection, and live CLI command previews.
"""

import sys
from InquirerPy import inquirer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .prerequisites import (
    scan_installed_browsers,
    load_config,
    save_config,
    display_prerequisites_table,
)

console = Console()


def render_banner():
    cfg = load_config()
    b_label = cfg.get("browser_label", "Auto / Not Selected")
    p_label = cfg.get("profile_label", "Default")
    acc = cfg.get("account_email", "")

    status_str = f"Active Browser: [bold green]{b_label}[/bold green] | Profile: [bold green]{p_label}[/bold green]"
    if acc:
        status_str += f" ([cyan]{acc}[/cyan])"

    console.print(
        Panel.fit(
            "[bold cyan]🛡️  Intune Visual Doc[/bold cyan]\n"
            "[dim]Automated Intune Settings Documentation with Microsoft Graph & Playwright Screenshots[/dim]\n"
            "[green]Standards: ASD-STE100 | License: GNU AGPLv3[/green]\n\n"
            f"{status_str}",
            border_style="cyan",
        )
    )


def configure_browser_and_profile():
    """Interactive wizard to detect and select browser and profile."""
    console.print(Panel("[bold cyan]🛠️  Prerequisites & Browser Profile Selection[/bold cyan]"))
    browsers = scan_installed_browsers()

    if not browsers:
        console.print("[red]❌ No supported Chromium-based browsers (Edge or Chrome) detected on your system.[/red]")
        return None

    # Step 1: Select Browser
    browser_choices = [
        {"name": f"{b['name']} ({b['binary']})", "value": b}
        for b in browsers
    ]

    selected_browser = inquirer.select(
        message="Select browser to use for Intune portal and network hooking:",
        choices=browser_choices,
        default=browser_choices[0]["value"],
    ).execute()

    # Step 2: Select Profile
    profile_choices = []
    for p in selected_browser["profiles"]:
        label = f"{p['name']} [{p['directory']}]"
        if p["email"]:
            label += f" - {p['email']}"
        profile_choices.append({
            "name": label,
            "value": p,
        })

    selected_profile = inquirer.select(
        message=f"Select user profile in {selected_browser['name']}:",
        choices=profile_choices,
        default=profile_choices[0]["value"],
    ).execute()

    # Save to config
    new_cfg = {
        "browser_id": selected_browser["id"],
        "browser_label": selected_browser["name"],
        "browser_binary": selected_browser["binary"],
        "profile_dir": selected_profile["directory"],
        "profile_label": selected_profile["name"],
        "account_email": selected_profile["email"],
    }
    save_config(new_cfg)

    console.print(
        f"[bold green]✅ Configured active browser to {selected_browser['name']} using profile '{selected_profile['name']}' ({selected_profile['email'] or 'Local'})[/bold green]\n"
    )
    return new_cfg


def build_cli_command(categories, screenshots, mock, unsanitize, audit_days, output_dir):
    parts = ["intunedoc", "run"]
    if categories and len(categories) < 3:
        parts.extend(["--category", ",".join(categories)])
    if not screenshots:
        parts.append("--no-screenshots")
    if mock:
        parts.append("--mock")
    if unsanitize:
        parts.append("--unsanitize")
    if audit_days != 30:
        parts.extend(["--audit-days", str(audit_days)])
    if output_dir != "docs":
        parts.extend(["--output-dir", output_dir])
    return " ".join(parts)


def run_tui_menu() -> dict:
    """Launch interactive prompt session and return chosen options."""
    render_banner()

    cfg = load_config()
    if not cfg.get("browser_id"):
        console.print("[yellow]Notice: Initial setup required. Please select your browser and profile.[/yellow]")
        cfg = configure_browser_and_profile()

    action = inquirer.select(
        message="Select action to execute:",
        choices=[
            {"name": "🚀 1. Run Documentation Generator", "value": "run"},
            {"name": "🔑 2. Login & Authenticate (Graph + Playwright)", "value": "login"},
            {"name": "🛠️  3. Prerequisites & Select Browser / Profile", "value": "prereqs"},
            {"name": "📝 4. Run ASD-STE100 Linter on Documents", "value": "lint"},
            {"name": "🔍 5. View Configuration Drift (Diff)", "value": "diff"},
            {"name": "❌ 6. Exit", "value": "exit"},
        ],
        default="run",
    ).execute()

    if action == "prereqs":
        display_prerequisites_table()
        change = inquirer.confirm(message="Would you like to change your browser/profile selection?", default=False).execute()
        if change:
            configure_browser_and_profile()
        return {"action": "prereqs_done"}

    if action != "run":
        return {"action": action}

    # Configuration for Run
    categories = inquirer.checkbox(
        message="Select policy categories to document:",
        choices=[
            {"name": "Device Compliance Policies", "value": "compliance", "enabled": True},
            {"name": "Configuration Profiles & Settings Catalog", "value": "configuration", "enabled": True},
            {"name": "Mobile & Managed Applications", "value": "apps", "enabled": True},
        ],
    ).execute()

    use_mock = False  # User explicitly requested real tenant documentation

    screenshots = inquirer.confirm(
        message="Capture automated Playwright visual screenshots?",
        default=True,
    ).execute()

    sanitize = inquirer.confirm(
        message="Sanitize sensitive credentials, SSIDs, and keys by default?",
        default=True,
    ).execute()

    audit_days = inquirer.number(
        message="Number of days for Admin Audit Events:",
        default=30,
        min_allowed=1,
        max_allowed=180,
    ).execute()

    output_dir = "docs"

    cmd_preview = build_cli_command(
        categories=categories,
        screenshots=screenshots,
        mock=use_mock,
        unsanitize=not sanitize,
        audit_days=audit_days,
        output_dir=output_dir,
    )

    console.print(
        Panel(
            f"[bold yellow]👉 Equivalent CLI Command:[/bold yellow]\n\n"
            f"[bold green]{cmd_preview}[/bold green]\n\n"
            f"[dim]Tip: You can run this exact command directly in your shell or CI/CD pipelines.[/dim]",
            title="Command Preview",
            border_style="yellow",
        )
    )

    proceed = inquirer.confirm(message="Ready to execute documentation run?", default=True).execute()

    return {
        "action": "run" if proceed else "cancel",
        "categories": categories,
        "screenshots": screenshots,
        "mock": use_mock,
        "unsanitize": not sanitize,
        "audit_days": int(audit_days),
        "output_dir": output_dir,
    }
