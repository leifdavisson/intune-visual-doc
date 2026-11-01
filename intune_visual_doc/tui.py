"""
Interactive Terminal User Interface (TUI) for Intune Visual Doc.
Always audits system prerequisites, browser profiles, and dependencies by default.
Features intelligent workflow gates and live CLI command previews.
"""

import sys
from InquirerPy import inquirer
from InquirerPy.separator import Separator
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


def interactive_audit_wizard(target_dir: str = "deliverables") -> dict:
    """
    Unified interactive posture audit wizard.
    Enforces safe harbor legal acknowledgment, backup workload detection,
    and profile/domain selection.
    """
    from .audit.posture import detect_backup_scope
    from .audit.rules import get_legal_disclaimer_text

    scope = detect_backup_scope(target_dir)
    if not scope["is_valid"]:
        console.print(f"\n[bold yellow]⚠️  Missing Backup Dependency:[/bold yellow] No configuration backup found in {target_dir}.")
        do_backup = inquirer.confirm(
            message="Would you like to run Step 5 (Export Backup) now before auditing?",
            default=True,
            style=TUI_STYLE,
        ).execute()
        if do_backup:
            return {"action": "backup", "categories": ["all"], "mock": False, "unsanitize": True, "output_dir": "deliverables"}
        return {"action": "cancel"}

    # Legal safe harbor notice gate
    console.print(
        Panel(
            get_legal_disclaimer_text(),
            title="🛡️ Safe Harbor Acknowledgment",
            border_style="yellow",
        )
    )
    ack = inquirer.confirm(message="Acknowledge legal advisory notice and proceed?", default=True, style=TUI_STYLE).execute()
    if not ack:
        return {"action": "cancel"}

    detected = sorted(list(scope["detected_categories"]))
    console.print(f"\n[cyan]Detected backup workloads:[/cyan] {', '.join(detected) if detected else 'All'}")

    domain_choices = [
        {"name": "Endpoint Encryption (BitLocker / FileVault)", "value": "endpoint_encryption", "enabled": True},
        {"name": "Antivirus & EDR (Microsoft Defender)", "value": "antivirus_edr", "enabled": True},
        {"name": "Host Firewall (Domain, Private, Public)", "value": "host_firewall", "enabled": True},
        {"name": "Windows Update Cadence (WUfB Rings)", "value": "update_cadence", "enabled": "configuration" in scope["detected_categories"] or not scope["detected_categories"]},
        {"name": "Identity & Credential Hygiene (LAPS, Screen Lock)", "value": "identity_credentials", "enabled": True},
        {"name": "Policy Hygiene & Lifecycle (Dormant Policies)", "value": "policy_hygiene", "enabled": True},
    ]

    selected_domains = inquirer.checkbox(
        message="Select audit baseline domains to evaluate (pre-checked by detected scope):",
        choices=domain_choices,
        style=TUI_STYLE,
    ).execute()

    if not selected_domains:
        console.print("[yellow]No domains selected for evaluation. Audit cancelled.[/yellow]\n")
        return {"action": "cancel"}

    profile = inquirer.select(
        message="Select security audit baseline profile:",
        choices=[
            {"name": "🛡️  Balanced Baseline (CIS Intune Level 1 + MS Baseline + NIST 800-63B) [Recommended]", "value": "balanced"},
            {"name": "🔒 Strict STIG Profile (DoD DISA STIG + ASR Block Enforcement)", "value": "strict-stig"},
        ],
        default="balanced",
        style=TUI_STYLE,
    ).execute()

    report_format = inquirer.select(
        message="Select audit deliverable format:",
        choices=[
            {"name": "📦 All Formats (Console, Markdown, HTML, and Executive PDF) [Recommended]", "value": "both"},
            {"name": "📄 Executive Vector PDF Packet (Printable for Board / Insurance)", "value": "pdf"},
            {"name": "🌐 Standalone HTML Packet (Single-file offline presentation)", "value": "html"},
            {"name": "📝 Markdown Technical Runbook (AUDIT_RECOMMENDATIONS.md)", "value": "markdown"},
            {"name": "🖥️  Terminal Scorecard Only", "value": "console"},
        ],
        default="both",
        style=TUI_STYLE,
    ).execute()

    cmd_preview = f"intunedoc audit {scope['run_dir']} --profile {profile} --format {report_format}"
    console.print(
        Panel(
            f"[bold yellow]👉 Equivalent CLI Command:[/bold yellow]\n\n"
            f"[bold green]{cmd_preview}[/bold green]\n\n"
            f"[dim]Tip: Fast offline analysis against raw JSON backups.[/dim]",
            title="Command Preview",
            border_style="yellow",
        )
    )

    proceed = inquirer.confirm(message="Ready to execute posture audit?", default=True, style=TUI_STYLE).execute()
    return {
        "action": "audit" if proceed else "cancel",
        "target_dir": scope["run_dir"],
        "profile": profile,
        "selected_domains": selected_domains,
        "format": report_format,
        "mock": False,
    }


def interactive_diff_wizard(output_dir: str = "deliverables") -> dict:
    """
    Interactive wizard for configuration drift comparison.
    Supports offline comparison between two timestamped backups,
    or comparing the live tenant against the latest backup.
    """
    from .deliverables import list_historical_runs, get_latest_deliverables_dir

    runs = list_historical_runs(output_dir)
    latest_dir = get_latest_deliverables_dir(output_dir)

    console.print(Panel("[bold cyan]🔍 Configuration Drift Comparison Wizard[/bold cyan]"))

    mode_choices = []
    if len(runs) >= 2:
        mode_choices.append({
            "name": f"🔄 Compare Two Historical Runs (Offline) [{len(runs)} backups available]",
            "value": "runs",
        })
    mode_choices.append({
        "name": f"⚡ Compare Live Intune Tenant against Latest Backup ({os.path.basename(latest_dir) if latest_dir else 'None'})",
        "value": "live",
    })

    mode = inquirer.select(
        message="Select drift comparison mode:",
        choices=mode_choices,
        default=mode_choices[0]["value"],
        style=TUI_STYLE,
    ).execute()

    from_run = None
    to_run = None

    if mode == "runs":
        run_choices = [
            {"name": f"{r['name']} ({r['policy_count']} policies)", "value": r["path"]}
            for r in runs
        ]
        from_run = inquirer.select(
            message="Select baseline (older) run:",
            choices=run_choices,
            default=run_choices[min(1, len(run_choices) - 1)]["value"],
            style=TUI_STYLE,
        ).execute()

        to_choices = [c for c in run_choices if c["value"] != from_run]
        to_run = inquirer.select(
            message="Select target (newer) run to compare against baseline:",
            choices=to_choices if to_choices else run_choices,
            default=to_choices[0]["value"] if to_choices else run_choices[0]["value"],
            style=TUI_STYLE,
        ).execute()

    export_html = inquirer.confirm(
        message="Generate interactive Visual Drift HTML report (DRIFT_REPORT.html)?",
        default=True,
        style=TUI_STYLE,
    ).execute()

    cmd_parts = ["intunedoc diff"]
    if from_run:
        cmd_parts.append(f"--from {from_run}")
    if to_run:
        cmd_parts.append(f"--to {to_run}")
    if export_html:
        cmd_parts.append("--html")
    cmd_preview = " ".join(cmd_parts)

    console.print(
        Panel(
            f"[bold yellow]👉 Equivalent CLI Command:[/bold yellow]\n\n"
            f"[bold green]{cmd_preview}[/bold green]\n\n"
            f"[dim]Tip: Fast granular setting drift with screenshot and JSON diffs.[/dim]",
            title="Command Preview",
            border_style="yellow",
        )
    )

    proceed = inquirer.confirm(message="Ready to execute drift diff?", default=True, style=TUI_STYLE).execute()

    return {
        "action": "diff" if proceed else "cancel",
        "output_dir": output_dir,
        "from_run": from_run,
        "to_run": to_run,
        "html": export_html,
        "mock": False,
    }


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

    user_hint = audit.get("selected_account") or ""
    if audit.get("can_skip_login"):
        console.print(
            f"[bold green]✨ Fast Track:[/bold green] Active session ready ({user_hint or 'Active Session'})! "
            "[dim]You can skip Step 2 & 3 and run Step 4 directly.[/dim]\n"
        )

    # 2. Main workflow menu with aligned single-digit numbers and clear section headers
    default_step = "run" if audit.get("can_skip_login") else "prereqs"
    choices = [
        Separator("── Setup ──────────────────────────────────────────"),
        {"name": " 1  Check prerequisites and browser profile", "value": "prereqs"},
        {"name": " 2  Set up read-only identities (CI/CD, optional)", "value": "setup"},
        {"name": f" 3  Sign in to Microsoft Graph{f' ({user_hint})' if user_hint else ''}", "value": "login"},
        Separator("── Collect ────────────────────────────────────────"),
        {"name": " 4  Generate documentation with screenshots", "value": "run"},
        {"name": " 5  Export backup (raw JSON, fast)", "value": "backup"},
        Separator("── Analyze ────────────────────────────────────────"),
        {"name": " 6  Run security posture audit (CIS & MS Baselines)", "value": "audit"},
        {"name": " 7  Verify ASD-STE100 compliance (Linter)", "value": "lint"},
        {"name": " 8  Compare configuration drift (Diff)", "value": "diff"},
        Separator("── Session ────────────────────────────────────────"),
        {"name": " 9  Sign out and purge credentials", "value": "logout"},
        {"name": " 0  Exit", "value": "exit"},
    ]

    action = inquirer.select(
        message="Select workflow step to execute:",
        choices=choices,
        default=default_step,
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

    if action == "audit":
        return interactive_audit_wizard("deliverables")

    if action == "diff":
        return interactive_diff_wizard("deliverables")

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
