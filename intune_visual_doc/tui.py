"""
Interactive Terminal User Interface (TUI) for Intune Visual Doc.
Features system prerequisites checking, interactive browser/profile picker, and live CLI command previews.
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
    wipe_all_credentials,
)
from .auth.portal_auth import authenticate_via_browser_hook

console = Console()


def render_banner():
    cfg = load_config()
    b_label = cfg.get("browser_label", "Microsoft Edge")
    p_label = cfg.get("profile_label", "Profile 1")
    acc = cfg.get("account_email", "ledavisson@kern.org")

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


def interactive_pick_browser_and_profile():
    """Interactive wizard to select browser and profile with clear defaults."""
    console.print(Panel("[bold cyan]🛠️  Browser & Profile Selection[/bold cyan]"))
    browsers = scan_installed_browsers()

    if not browsers:
        console.print("[red]❌ No supported Chromium-based browsers (Edge or Chrome) detected on your system.[/red]")
        return None

    cfg = load_config()
    active_b_id = cfg.get("browser_id", "msedge")
    active_p_dir = cfg.get("profile_dir", "Default")

    # Step 1: Select Browser
    browser_choices = []
    default_browser_choice = browsers[0]
    for b in browsers:
        choice = {"name": f"{b['name']} ({b['binary']})", "value": b}
        browser_choices.append(choice)
        if b["id"] == active_b_id:
            default_browser_choice = b

    selected_browser = inquirer.select(
        message="Select browser to use for Intune portal and network hooking:",
        choices=browser_choices,
        default=default_browser_choice,
    ).execute()

    # Step 2: Select Profile
    profile_choices = []
    default_profile_choice = selected_browser["profiles"][0]
    for p in selected_browser["profiles"]:
        label = f"{p['name']} [{p['directory']}]"
        if p["email"]:
            label += f" - {p['email']}"
        choice = {"name": label, "value": p}
        profile_choices.append(choice)
        if p["directory"] == active_p_dir:
            default_profile_choice = p

    selected_profile = inquirer.select(
        message=f"Select user profile in {selected_browser['name']}:",
        choices=profile_choices,
        default=default_profile_choice,
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

    action = inquirer.select(
        message="Select action to execute:",
        choices=[
            {"name": "🚀 1. Run Documentation Generator", "value": "run"},
            {"name": "🔑 2. Login & Authenticate (Graph + Playwright)", "value": "login"},
            {"name": "🛠️  3. Prerequisites & Change Browser / Profile", "value": "prereqs"},
            {"name": "📝 4. Run ASD-STE100 Linter on Documents", "value": "lint"},
            {"name": "🔍 5. View Configuration Drift (Diff)", "value": "diff"},
            {"name": "🗑️  6. Logout (Wipe Stored Credentials)", "value": "logout"},
            {"name": "❌ 7. Exit", "value": "exit"},
        ],
        default="run",
    ).execute()

    if action == "logout":
        confirm = inquirer.confirm(message="Are you sure you want to wipe all cached credentials?", default=False).execute()
        if confirm:
            wipe_all_credentials()
            console.print("[bold green]✅ Stored credentials wiped successfully.[/bold green]\n")
        return {"action": "logout_done"}
        display_prerequisites_table()
        change = inquirer.confirm(message="Would you like to select your browser and profile?", default=True).execute()
        if change:
            interactive_pick_browser_and_profile()
        return {"action": "prereqs_done"}

    if action == "login":
        # Ask user if they'd like to verify or change browser/profile before launching
        cfg = load_config()
        p_label = cfg.get("profile_label", "Profile 1")
        acc = cfg.get("account_email", "ledavisson@kern.org")
        b_label = cfg.get("browser_label", "Microsoft Edge")

        console.print(f"\n[cyan]Target:[/cyan] {b_label} with {p_label} ({acc})")
        change = inquirer.confirm(message="Do you want to change the browser or profile for this login?", default=False).execute()
        if change:
            interactive_pick_browser_and_profile()

        # Run login and catch cancellations cleanly
        res = authenticate_via_browser_hook(force_refresh=True)
        if not res or res.get("status") == "cancelled":
            console.print("\n[yellow]⚠️  Browser closed without completing login. Authentication cancelled gracefully.[/yellow]\n")
        elif res.get("status") == "success":
            console.print("\n[bold green]🎉 Live Microsoft Graph Bearer token and Intune Portal session acquired successfully![/bold green]\n")
        else:
            console.print(f"\n[red]Login notice: {res.get('message', 'Authentication incomplete')}[/red]\n")
        return {"action": "login_done"}

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
        mock=False,
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
        "mock": False,
        "unsanitize": not sanitize,
        "audit_days": int(audit_days),
        "output_dir": output_dir,
    }
