"""
Command-line interface for Intune Visual Doc.
Provides subcommands: login, run, diff, lint-ste, check-prereqs, and interactive TUI.
"""

import os
import sys
import signal
import argparse
from typing import List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .auth import get_graph_token, ensure_portal_session
from .auth.portal_auth import authenticate_via_browser_hook
from .graph import GraphClient, PolicyCollector
from .visual import ScreenshotManager
from .generator import DocGenerator
from .audit import lint_markdown_directory, compare_with_backups
from .prerequisites import display_prerequisites_table, wipe_all_credentials
from .mock_data import get_mock_policies, get_mock_audit_events, setup_mock_screenshots

console = Console()


def setup_graceful_interrupt():
    """Trap SIGINT (Ctrl-C) to exit cleanly without python stack trace."""
    def handler(sig, frame):
        console.print("\n[yellow]⚠️  Process interrupted by user. Exiting cleanly...[/yellow]")
        sys.exit(0)
    signal.signal(signal.SIGINT, handler)


def cmd_logout(args):
    """Purge all stored tokens and sessions from .auth/."""
    try:
        wipe_all_credentials()
        console.print("[bold green]✅ All cached credentials, tokens, and browser sessions purged successfully.[/bold green]")
    except Exception as e:
        console.print(f"[red]❌ Error purging credentials: {e}[/red]")


def cmd_login(args):
    """Authenticate with Microsoft Graph and Intune Admin Center via browser hook."""
    console.print(Panel("[bold cyan]🔑 Intune Visual Doc - Authentication Wizard[/bold cyan]"))
    try:
        res = authenticate_via_browser_hook(force_refresh=True)
        if not res or res.get("status") == "cancelled":
            console.print("\n[yellow]⚠️  Browser closed without completing login. Authentication cancelled gracefully.[/yellow]\n")
            return
        elif res.get("status") == "success":
            console.print("[bold green]🎉 Live Microsoft Graph Bearer token and Intune Portal session acquired successfully![/bold green]")
            console.print("[dim]Token and session saved in .auth/ for subsequent automated runs.[/dim]\n")
        else:
            console.print(f"[yellow]Authentication status: {res.get('message', 'Incomplete')}[/yellow]\n")
    except Exception as e:
        console.print(f"[red]❌ Authentication note: {e}[/red]")


def cmd_run(args):
    """Run the documentation extraction and rendering pipeline."""
    output_dir = os.path.abspath(args.output_dir)
    console.print(Panel(f"[bold cyan]🚀 Starting Intune Documentation Run[/bold cyan]\n[dim]Target directory: {output_dir}[/dim]"))

    policies = []
    audit_events = []
    screenshots_map = {}

    if args.mock:
        console.print("[bold magenta]🧪 Running in Mock Mode with sample school district data...[/bold magenta]")
        policies = get_mock_policies()
        audit_events = get_mock_audit_events()
        if args.category:
            cats = [c.strip().lower() for c in args.category.split(",")]
            policies = [p for p in policies if p.get("category") in cats]

        screenshots_map = setup_mock_screenshots(output_dir, policies)
        console.print(f"[green]Loaded {len(policies)} sample policies and mock visual screenshots.[/green]")
    else:
        # Live Graph Extraction via Browser Network Hook or SPN
        console.print("[yellow]Connecting to Microsoft Graph API...[/yellow]")
        try:
            token = get_graph_token()
            client = GraphClient(token)
            collector = PolicyCollector(client)
        except Exception as e:
            console.print(f"[red]Authentication not ready: {e}[/red]")
            console.print("[dim]Hint: Run 'intunedoc login' to launch the browser and capture session.[/dim]")
            sys.exit(1)

        cats = [c.strip().lower() for c in args.category.split(",")] if args.category else ["all"]
        legacy_config_bundle = "configuration" in cats and not any(k in cats for k in ("endpoint_security", "scripts", "enrollment"))
        fetch_all = "all" in cats or not cats

        if fetch_all or "compliance" in cats:
            console.print("[cyan]Fetching Devices > Compliance policies...[/cyan]")
            policies.extend(collector.get_compliance_policies())

        if fetch_all or "configuration" in cats:
            console.print("[cyan]Fetching Devices > Configuration profiles (Settings Catalog & Templates)...[/cyan]")
            policies.extend(collector.get_configuration_policies())
            policies.extend(collector.get_device_configurations())

        if fetch_all or legacy_config_bundle or "endpoint_security" in cats or "endpoint security" in cats:
            console.print("[cyan]Fetching Endpoint security policies (Disk encryption, Antivirus, Firewall)...[/cyan]")
            policies.extend(collector.get_endpoint_security_policies())

        if fetch_all or legacy_config_bundle or "scripts" in cats:
            console.print("[cyan]Fetching Devices > Scripts (PowerShell & Shell)...[/cyan]")
            policies.extend(collector.get_device_management_scripts())

        if fetch_all or legacy_config_bundle or "enrollment" in cats:
            console.print("[cyan]Fetching Devices > Enrollment configurations (Autopilot)...[/cyan]")
            policies.extend(collector.get_device_enrollment_configurations())

        if fetch_all or "apps" in cats:
            console.print("[cyan]Fetching Apps (Managed applications)...[/cyan]")
            policies.extend(collector.get_managed_apps())

        console.print(f"[cyan]Fetching Admin Audit Events (past {args.audit_days} days)...[/cyan]")
        audit_events = collector.get_audit_logs(days=args.audit_days)

        # Capture Playwright screenshots if not disabled
        if not args.no_screenshots:
            console.print("[yellow]Capturing live Intune Admin Center screenshots via Playwright...[/yellow]")
            manager = ScreenshotManager(output_dir=output_dir, headless=True)

            def progress_cb(current, total, name):
                console.print(f" [dim]({current}/{total}) Snapping Overview and Properties: {name}[/dim]")

            try:
                screenshots_map = manager.capture_policy_screenshots(policies, on_progress=progress_cb)
            except Exception as e:
                console.print(f"[yellow]⚠️ Screenshot capture warning ({e}). Continuing with text docs...[/yellow]")

    # Generate Markdown documentation
    console.print("[yellow]Rendering ASD-STE100 Markdown documentation...[/yellow]")
    generator = DocGenerator(output_dir=output_dir, unsanitize=args.unsanitize)
    summary = generator.render_all(
        policies=policies,
        audit_events=audit_events,
        generator_user="Intune Administrator",
        audit_days=args.audit_days,
        screenshots_map=screenshots_map,
    )

    # Display Rich Summary Table
    table = Table(title="Intune Documentation Run Summary", border_style="cyan")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right", style="green")
    table.add_column("Health / Status", style="yellow")

    table.add_row("Total Policies", str(summary["stats"]["total_policies"]), "Extracted from Graph")
    table.add_row("Assigned", str(summary["stats"]["assigned_policies"]), "🟢 Targeted to devices/users")
    table.add_row("Unassigned / Dormant", str(summary["stats"]["unassigned_policies"]), "🟡 Needs review")
    table.add_row("Security Baselines", str(summary["stats"]["baseline_policies"]), "🛡️ Recommended")
    table.add_row("Secret Sanitization", summary["stats"]["sanitized_status"], "Protected for git")
    table.add_row("Admin Audit Events", str(len(audit_events)), f"Past {args.audit_days} days")

    console.print(table)
    console.print(f"\n[bold green]✅ Documentation generation complete![/bold green]")
    console.print(f"👉 [bold underline]Index Path:[/bold underline] file://{summary['index_path']}\n")


def cmd_lint_ste(args):
    """Run ASD-STE100 linter across documentation."""
    target_dir = os.path.abspath(args.directory)
    console.print(Panel(f"[bold cyan]🔍 Running ASD-STE100 Documentation Linter[/bold cyan]\nTarget: {target_dir}"))

    results = lint_markdown_directory(target_dir)

    table = Table(title="ASD-STE100 Compliance Results", border_style="cyan")
    table.add_column("File", style="cyan")
    table.add_column("Line", justify="right", style="magenta")
    table.add_column("Rule", style="yellow")
    table.add_column("Severity", style="bold")
    table.add_column("Issue Details", style="white")

    for iss in results["issues"][:25]:
        sev_style = "red" if iss["severity"] == "Warning" else "blue"
        table.add_row(
            iss["file"],
            str(iss["line"]),
            iss["rule"],
            f"[{sev_style}]{iss['severity']}[/{sev_style}]",
            iss["message"],
        )

    console.print(table)
    console.print(f"\n[bold]Files Scanned:[/bold] {results['files_scanned']} | [bold]Total Findings:[/bold] {results['total_issues']}")
    if results["total_issues"] == 0:
        console.print("[bold green]🎉 100% ASD-STE100 Compliant! No issues found.[/bold green]\n")


def cmd_diff(args):
    """Compare live or mock Intune policies against saved docs/raw_json/ backups."""
    output_dir = os.path.abspath(getattr(args, "output_dir", "docs"))
    use_mock = getattr(args, "mock", False)
    console.print(Panel(f"[bold cyan]🔍 Auditing Configuration Drift[/bold cyan]\nBackup Directory: {output_dir}/raw_json"))

    if use_mock:
        policies = get_mock_policies()
    else:
        try:
            token = get_graph_token()
            client = GraphClient(token)
            collector = PolicyCollector(client)
            policies = (
                collector.get_compliance_policies()
                + collector.get_configuration_policies()
                + collector.get_device_configurations()
                + collector.get_endpoint_security_policies()
                + collector.get_device_management_scripts()
                + collector.get_device_enrollment_configurations()
                + collector.get_managed_apps()
            )
        except Exception as e:
            console.print(f"[red]Authentication not ready: {e}[/red]")
            console.print("[dim]Hint: Run 'intunedoc login' first or pass '--mock' for offline verification.[/dim]")
            sys.exit(1)

    findings = compare_with_backups(policies, output_dir=output_dir)
    if not findings:
        console.print("[bold green]✅ No configuration drift detected since last backup.[/bold green]\n")
        return

    table = Table(title="Configuration Drift Report", border_style="yellow")
    table.add_column("Policy", style="cyan")
    table.add_column("Category", style="magenta")
    table.add_column("Drift Status", style="bold yellow")
    table.add_column("Details", style="white")
    for item in findings:
        table.add_row(item["policy"], item["category"], item["status"], item["details"])
    console.print(table)


def cmd_setup(args):
    """Guide or automate creation of read-only SPN and screenshot service account."""
    from .setup_wizard import (
        display_setup_banner,
        interactive_setup_wizard,
        export_setup_scripts,
        verify_spn_credentials,
        generate_spn_bash_script,
        generate_screenshot_user_script,
    )
    from .prerequisites import load_config

    if getattr(args, "export_scripts", False):
        display_setup_banner()
        out_dir = getattr(args, "output_dir", "setup") or "setup"
        files = export_setup_scripts(output_dir=out_dir)
        console.print(f"[bold green]✅ Exported setup scripts to {out_dir}/ successfully:[/bold green]")
        for f in files:
            console.print(f"  • {f}")
        return

    if getattr(args, "test_spn", False):
        display_setup_banner()
        cfg = load_config()
        t_id = os.environ.get("AZURE_TENANT_ID") or cfg.get("azure_tenant_id")
        c_id = os.environ.get("AZURE_CLIENT_ID") or cfg.get("azure_client_id")
        sec = os.environ.get("AZURE_CLIENT_SECRET") or cfg.get("azure_client_secret")
        if not t_id or not c_id or not sec:
            console.print("[red]❌ SPN credentials missing. Run 'intunedoc setup' or set AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET.[/red]")
            return
        console.print("[yellow]Testing configured SPN credentials against Microsoft Graph...[/yellow]")
        res = verify_spn_credentials(t_id, c_id, sec)
        if res.get("success"):
            console.print(f"[bold green]🎉 Verified! Connected to tenant: {res.get('org_name')}[/bold green]")
            console.print("[green]Strict read-only Graph permissions are active.[/green]\n")
        else:
            console.print(f"[red]❌ Verification failed:[/red] {res.get('error')}\n")
        return

    if getattr(args, "spn", False):
        display_setup_banner()
        console.print(generate_spn_bash_script())
        return

    if getattr(args, "screenshot_user", False):
        display_setup_banner()
        console.print(generate_screenshot_user_script())
        return

    interactive_setup_wizard()


def _dispatch_tui(skip_prereqs: bool = False):
    """Launch TUI in an interactive loop. Returns to menu after each selection."""
    from .tui import run_tui_menu

    first_run = True

    while True:
        # Show full prerequisites table on startup; evaluate silently on subsequent menu returns
        opts = run_tui_menu(skip_prereqs=skip_prereqs or (not first_run))
        first_run = False
        act = opts.get("action")

        if act == "run":
            class RunArgs:
                category = ",".join(opts.get("categories", []))
                no_screenshots = not opts.get("screenshots", True)
                mock = opts.get("mock", False)
                unsanitize = opts.get("unsanitize", False)
                audit_days = opts.get("audit_days", 30)
                output_dir = opts.get("output_dir", "docs")
            cmd_run(RunArgs())
            console.print("\n[dim]Press any key or return to main menu...[/dim]\n")
        elif act in ("login_done", "prereqs_done", "logout_done", "setup_done"):
            continue
        elif act == "setup":
            cmd_setup(None)
        elif act == "login":
            cmd_login(None)
        elif act == "lint":
            class LintArgs:
                directory = "docs"
            cmd_lint_ste(LintArgs())
            console.print("\n[dim]Returning to main menu...[/dim]\n")
        elif act == "diff":
            class DiffArgs:
                output_dir = "docs"
                mock = False
            cmd_diff(DiffArgs())
            console.print("\n[dim]Returning to main menu...[/dim]\n")
        elif act in ("exit", "cancel"):
            console.print("[bold cyan]👋 Exiting Intune Visual Doc. Goodbye![/bold cyan]\n")
            break


def main():
    setup_graceful_interrupt()

    # If no arguments provided in interactive terminal, launch TUI
    if len(sys.argv) == 1 and sys.stdin.isatty():
        _dispatch_tui(skip_prereqs=False)
        return

    parser = argparse.ArgumentParser(
        prog="intunedoc",
        description="Automated Intune documentation generator using Microsoft Graph & Playwright in ASD-STE100",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # setup subcommand
    setup_parser = subparsers.add_parser("setup", help="Configure read-only SPN or screenshot maker service account")
    setup_parser.add_argument("--spn", action="store_true", help="Display bash creation script for intunedoc-reader-spn")
    setup_parser.add_argument("--screenshot-user", action="store_true", help="Display PowerShell script for svc-intunedoc-screenshot")
    setup_parser.add_argument("--export-scripts", action="store_true", help="Export setup scripts and documentation to setup/ directory")
    setup_parser.add_argument("--output-dir", type=str, default="setup", help="Target directory for exported setup scripts (default: setup)")
    setup_parser.add_argument("--test-spn", action="store_true", help="Test configured SPN credentials against Microsoft Graph API")

    # tui subcommand
    tui_parser = subparsers.add_parser("tui", help="Launch interactive Terminal User Interface (TUI)")
    tui_parser.add_argument("--skip-prereqs", action="store_true", help="Skip running the prerequisites and dependency matrix on launch")

    # check-prereqs subcommand
    subparsers.add_parser("check-prereqs", help="Display system and browser prerequisites table")

    # login subcommand
    subparsers.add_parser("login", help="Authenticate with Microsoft Graph and Intune Admin Center via browser hook")

    # logout subcommand
    subparsers.add_parser("logout", help="Purge all cached credentials and sessions")

    # run subcommand
    run_parser = subparsers.add_parser("run", help="Extract policies and generate documentation")
    run_parser.add_argument("--category", type=str, default="", help="Comma-separated categories (compliance,configuration,apps)")
    run_parser.add_argument("--no-screenshots", action="store_true", help="Skip capturing Playwright screenshots")
    run_parser.add_argument("--mock", action="store_true", help="Use mock school district sample data")
    run_parser.add_argument("--unsanitize", action="store_true", help="Do not mask sensitive keys and pre-shared secrets")
    run_parser.add_argument("--audit-days", type=int, default=30, help="Days of admin audit logs to include (default: 30)")
    run_parser.add_argument("--output-dir", type=str, default="docs", help="Directory where documentation will be generated (default: docs)")

    # lint-ste subcommand
    lint_parser = subparsers.add_parser("lint-ste", help="Audit markdown files for ASD-STE100 compliance")
    lint_parser.add_argument("--directory", type=str, default="docs", help="Directory of markdown files to audit (default: docs)")

    # diff subcommand
    diff_parser = subparsers.add_parser("diff", help="View configuration drift compared to last run")
    diff_parser.add_argument("--output-dir", type=str, default="docs", help="Documentation directory containing raw_json/ backups")
    diff_parser.add_argument("--mock", action="store_true", help="Compare mock policies against saved backups")

    args = parser.parse_args()

    if args.command == "tui":
        _dispatch_tui(skip_prereqs=args.skip_prereqs)
    elif args.command == "check-prereqs":
        display_prerequisites_table()
    elif args.command == "setup":
        cmd_setup(args)
    elif args.command == "login":
        cmd_login(args)
    elif args.command == "logout":
        cmd_logout(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "lint-ste":
        cmd_lint_ste(args)
    elif args.command == "diff":
        cmd_diff(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
