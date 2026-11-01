"""
Interactive Terminal User Interface (TUI) for Intune Visual Doc.
Always audits system prerequisites, browser profiles, and dependencies by default.
Features intelligent workflow gates and live CLI command previews.
"""

import sys
from InquirerPy import inquirer
from InquirerPy.utils import get_style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .prerequisites import (
    scan_installed_browsers,
    load_config,
    save_config,
    display_prerequisites_table,
    evaluate_dependencies_and_supersedences,
    wipe_all_credentials,
)
from .auth.portal_auth import authenticate_via_browser_hook
from .setup_wizard import interactive_setup_wizard

console = Console(legacy_windows=False)

# Highlighted menu line styling: BOLD and vibrant cyan for maximum visibility
TUI_STYLE = get_style(
    {
        "questionmark": "bold #00ffff",
        "answer": "bold #00ff7f",
        "input": "#00ffff",
        "question": "bold",
        "instruction": "#abb2bf",
        "pointer": "bold #00ffff",
        "checkbox": "bold #00ff7f",
        "marker": "bold #ffb86c",
    }
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
        style=TUI_STYLE,
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
        style=TUI_STYLE,
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
    if categories and "all" not in categories and len(categories) < 6:
        parts.extend(["--category", ",".join(categories)])
    if not screenshots:
        parts.append("--no-screenshots")
    if mock:
        parts.append("--mock")
    if unsanitize:
        parts.append("--unsanitize")
    if audit_days != 30:
        parts.extend(["--audit-days", str(audit_days)])
    if output_dir != "deliverables":
        parts.extend(["--output-dir", output_dir])
    return " ".join(parts)


def run_tui_menu(skip_prereqs: bool = False) -> dict:
    """
    Launch interactive prompt session.
    ALWAYS runs prerequisites and dependency audit first by default unless --skip-prereqs is passed.
    """
    console.print(
        Panel.fit(
            "[bold cyan]🛡️  Intune Visual Doc[/bold cyan]\n"
            "[dim]Automated Intune Settings Documentation with Microsoft Graph & Playwright Screenshots[/dim]\n"
            "[green]Standards: ASD-STE100 | License: GNU AGPLv3[/green]",
            border_style="cyan",
        )
    )

    # 1. ALWAYS run prerequisites and dependency matrix first by default
    if not skip_prereqs:
        audit = display_prerequisites_table()
    else:
        audit = evaluate_dependencies_and_supersedences()

    if audit.get("can_skip_login"):
        user_hint = audit.get("selected_account") or "Active Session"
        console.print(
            f"[bold green]✨ Fast Track:[/bold green] Active session ready ({user_hint})! "
            "[dim]You can skip Step 2 & 3 and run Step 4 directly.[/dim]\n"
        )

    # 2. Main workflow menu in exact chronological order
    action = inquirer.select(
        message="Select workflow step to execute:",
        choices=[
            {"name": "🛠️  1. Check Prerequisites & Select Browser / Profile", "value": "prereqs"},
            {"name": "⚙️  2. Setup Read-Only SPN & Screenshot Maker (Optional: Server / CI/CD)", "value": "setup"},
            {"name": "🔑 3. Authenticate & Hook Session (Interactive Browser Login)", "value": "login"},
            {"name": "🚀 4. Run Documentation Generator (Extract & Screenshot)", "value": "run"},
            {"name": "📦 5. Export Backup (Raw Configs Only — Fast, No Screenshots)", "value": "backup"},
            {"name": "📝 6. Verify ASD-STE100 Compliance (Linter)", "value": "lint"},
            {"name": "🔍 7. Audit Configuration Drift (Diff)", "value": "diff"},
            {"name": "🗑️  8. Logout (Purge Stored Credentials)", "value": "logout"},
            {"name": "❌ 9. Exit", "value": "exit"},
        ],
        default="prereqs",
        style=TUI_STYLE,
    ).execute()

    if action == "prereqs":
        display_prerequisites_table()
        change = inquirer.confirm(message="Would you like to select your browser and profile?", default=True, style=TUI_STYLE).execute()
        if change:
            interactive_pick_browser_and_profile()
        return {"action": "prereqs_done"}

    if action == "setup":
        interactive_setup_wizard()
        return {"action": "setup_done"}

    if action == "logout":
        confirm = inquirer.confirm(message="Are you sure you want to wipe all cached credentials?", default=False, style=TUI_STYLE).execute()
        if confirm:
            wipe_all_credentials()
            console.print("[bold green]✅ Stored credentials wiped successfully.[/bold green]\n")
        return {"action": "logout_done"}

    if action == "login":
        cfg = load_config()
        p_label = cfg.get("profile_label", "Profile 1")
        acc = cfg.get("account_email", "")
        b_label = cfg.get("browser_label", "Microsoft Edge")

        console.print(f"\n[cyan]Target:[/cyan] {b_label} with {p_label} ({acc or 'Default'})")
        change = inquirer.confirm(message="Do you want to change the browser or profile for this login?", default=False, style=TUI_STYLE).execute()
        if change:
            interactive_pick_browser_and_profile()

        res = authenticate_via_browser_hook(force_refresh=True)
        if not res or res.get("status") == "cancelled":
            console.print(f"\n[yellow]⚠️  {res.get('message', 'Browser closed without completing login.')}[/yellow]\n")
            return {"action": "login_done"}
        elif res.get("status") == "success":
            user_display = res.get("user") or acc or "Intune Admin"
            console.print(f"\n[bold green]🎉 Live Microsoft Graph Bearer token and Intune Portal session acquired successfully for {user_display}![/bold green]\n")
            proceed_now = inquirer.confirm(
                message="Would you like to proceed directly to Step 4 (Run Documentation Generator) now?",
                default=True,
                style=TUI_STYLE,
            ).execute()
            if not proceed_now:
                return {"action": "login_done"}
            action = "run"
        else:
            console.print(f"\n[red]Login notice: {res.get('message', 'Authentication incomplete')}[/red]\n")
            return {"action": "login_done"}

    if action == "backup":
        if not audit["can_skip_login"]:
            console.print("\n[bold yellow]⚠️  Missing Dependency Gate:[/bold yellow] No valid Microsoft Graph authentication token or SPN was found.")
            do_auth = inquirer.confirm(
                message="Would you like to run Step 3 (Authenticate & Hook Session) now before exporting backup?",
                default=True,
                style=TUI_STYLE,
            ).execute()
            if do_auth:
                res = authenticate_via_browser_hook(force_refresh=False)
                if not res or res.get("status") != "success":
                    console.print("[red]Authentication not completed. Cannot proceed with backup.[/red]\n")
                    return {"action": "cancel"}
            else:
                console.print("[yellow]Cannot export tenant data without authentication. Backup cancelled.[/yellow]\n")
                return {"action": "cancel"}

        categories = inquirer.checkbox(
            message="Select Intune policy categories to backup:",
            choices=[
                {"name": "🌟 ALL Categories (Full Tenant Configuration Backup)", "value": "all", "enabled": True},
                {"name": "Devices > Compliance (Device compliance policies)", "value": "compliance", "enabled": True},
                {"name": "Devices > Configuration (Settings catalog & profile templates)", "value": "configuration", "enabled": True},
                {"name": "Endpoint security (Disk encryption, Antivirus, Firewall)", "value": "endpoint_security", "enabled": True},
                {"name": "Devices > Scripts (PowerShell & Shell scripts)", "value": "scripts", "enabled": True},
                {"name": "Devices > Enrollment (Autopilot & enrollment configurations)", "value": "enrollment", "enabled": True},
                {"name": "Apps (Managed desktop, store, and mobile applications)", "value": "apps", "enabled": True},
            ],
            style=TUI_STYLE,
        ).execute()

        if "all" in categories:
            categories = ["all"]

        unsanitize = inquirer.confirm(
            message="Preserve unmasked raw configuration secrets (Recommended for 1-to-1 restore)?",
            default=True,
            style=TUI_STYLE,
        ).execute()

        cmd_preview = f"intunedoc backup{' --category ' + ','.join(categories) if 'all' not in categories else ''}{' --unsanitize' if unsanitize else ''}"
        console.print(
            Panel(
                f"[bold yellow]👉 Equivalent CLI Command:[/bold yellow]\n\n"
                f"[bold green]{cmd_preview}[/bold green]\n\n"
                f"[dim]Tip: Fast raw JSON export. Use 'scripts/intune_restore.py' to restore.[/dim]",
                title="Command Preview",
                border_style="yellow",
            )
        )

        proceed = inquirer.confirm(message="Ready to export configuration backup?", default=True, style=TUI_STYLE).execute()

        return {
            "action": "backup" if proceed else "cancel",
            "categories": categories,
            "mock": False,
            "unsanitize": unsanitize,
            "output_dir": "deliverables",
        }

    if action != "run":
        return {"action": action}

    # Workflow Dependency Gate: Check if token exists before running Step 4
    if not audit["can_skip_login"]:
        console.print("\n[bold yellow]⚠️  Missing Dependency Gate:[/bold yellow] No valid Microsoft Graph authentication token or SPN was found.")
        do_auth = inquirer.confirm(
            message="Would you like to run Step 3 (Authenticate & Hook Session) now before generating docs?",
            default=True,
            style=TUI_STYLE,
        ).execute()
        if do_auth:
            res = authenticate_via_browser_hook(force_refresh=False)
            if not res or res.get("status") != "success":
                console.print("[red]Authentication not completed. Cannot proceed with documentation generation.[/red]\n")
                return {"action": "cancel"}
        else:
            console.print("[yellow]Cannot extract live tenant data without authentication. Run cancelled.[/yellow]\n")
            return {"action": "cancel"}

    # Configuration for Run
    categories = inquirer.checkbox(
        message="Select Intune policy categories to document (matches Intune Admin Center):",
        choices=[
            {"name": "🌟 ALL Categories (Full Tenant Documentation)", "value": "all", "enabled": True},
            {"name": "Devices > Compliance (Device compliance policies)", "value": "compliance", "enabled": True},
            {"name": "Devices > Configuration (Settings catalog & profile templates)", "value": "configuration", "enabled": True},
            {"name": "Endpoint security (Disk encryption, Antivirus, Firewall)", "value": "endpoint_security", "enabled": True},
            {"name": "Devices > Scripts (PowerShell & Shell scripts)", "value": "scripts", "enabled": True},
            {"name": "Devices > Enrollment (Autopilot & enrollment configurations)", "value": "enrollment", "enabled": True},
            {"name": "Apps (Managed desktop, store, and mobile applications)", "value": "apps", "enabled": True},
        ],
        style=TUI_STYLE,
    ).execute()

    if "all" in categories:
        categories = ["all"]

    screenshots = inquirer.confirm(
        message="Capture automated Playwright visual screenshots?",
        default=True,
        style=TUI_STYLE,
    ).execute()

    sanitize = inquirer.confirm(
        message="Sanitize sensitive credentials, SSIDs, and keys by default?",
        default=True,
        style=TUI_STYLE,
    ).execute()

    audit_days = inquirer.number(
        message="Number of days for Admin Audit Events:",
        default=30,
        min_allowed=1,
        max_allowed=180,
        style=TUI_STYLE,
    ).execute()

    output_dir = "deliverables"

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

    proceed = inquirer.confirm(message="Ready to execute documentation run?", default=True, style=TUI_STYLE).execute()

    return {
        "action": "run" if proceed else "cancel",
        "categories": categories,
        "screenshots": screenshots,
        "mock": False,
        "unsanitize": not sanitize,
        "audit_days": int(audit_days),
        "output_dir": output_dir,
    }
