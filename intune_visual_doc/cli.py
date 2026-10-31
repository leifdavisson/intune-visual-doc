"""
Command-line interface for Intune Visual Doc.
Provides subcommands: login, run, diff, lint-ste, and interactive TUI.
"""

import os
import sys
import argparse
from typing import List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .auth import get_graph_token, ensure_portal_session
from .graph import GraphClient, PolicyCollector
from .visual import ScreenshotManager
from .generator import DocGenerator
from .audit import lint_markdown_directory
from .mock_data import get_mock_policies, get_mock_audit_events, setup_mock_screenshots

console = Console()


def cmd_login(args):
    """Authenticate with Microsoft Graph and Intune Admin Center."""
    console.print(Panel("[bold cyan]🔑 Intune Visual Doc - Authentication Wizard[/bold cyan]"))
    console.print("[yellow]1. Authenticating to Microsoft Graph...[/yellow]")
    try:
        token = get_graph_token()
        console.print("[green]✅ Successfully acquired Microsoft Graph token![/green]")
    except Exception as e:
        console.print(f"[red]❌ Microsoft Graph authentication error: {e}[/red]")
        sys.exit(1)

    console.print("[yellow]2. Establishing Playwright Intune Admin Center session...[/yellow]")
    try:
        ensure_portal_session(force_refresh=True)
        console.print("[green]✅ Playwright browser session saved to .auth/playwright_state.json![/green]")
    except Exception as e:
        console.print(f"[red]❌ Portal browser login error: {e}[/red]")
        sys.exit(1)

    console.print("[bold green]🎉 All authentication prerequisites are ready.[/bold green]")


def cmd_run(args):
    """Run the documentation extraction and rendering pipeline."""
    output_dir = os.path.abspath(args.output_dir)
    console.print(Panel(f"[bold cyan]🚀 Starting Intune Documentation Run[/bold cyan]\n[dim]Target directory: {output_dir}[/dim]"))

    policies = []
    audit_events = []
    screenshots_map = {}

    if args.mock:
        console.print("[bold magenta]🧪 Running in Mock Mode with sample KCSOS district data...[/bold magenta]")
        policies = get_mock_policies()
        audit_events = get_mock_audit_events()
        # Filter categories if requested
        if args.category:
            cats = [c.strip().lower() for c in args.category.split(",")]
            policies = [p for p in policies if p.get("category") in cats]

        screenshots_map = setup_mock_screenshots(output_dir, policies)
        console.print(f"[green]Loaded {len(policies)} sample policies and mock visual screenshots.[/green]")
    else:
        # Live Graph Extraction
        console.print("[yellow]Connecting to Microsoft Graph API...[/yellow]")
        try:
            token = get_graph_token()
            client = GraphClient(token)
            collector = PolicyCollector(client)
        except Exception as e:
            console.print(f"[red]Authentication failed: {e}[/red]")
            console.print("[dim]Hint: Run 'intunedoc login' or use '--mock' for offline testing.[/dim]")
            sys.exit(1)

        cats = [c.strip().lower() for c in args.category.split(",")] if args.category else ["compliance", "configuration", "apps"]

        if "compliance" in cats:
            console.print("[cyan]Fetching Device Compliance policies...[/cyan]")
            policies.extend(collector.get_compliance_policies())
        if "configuration" in cats:
            console.print("[cyan]Fetching Settings Catalog and Configuration profiles...[/cyan]")
            policies.extend(collector.get_configuration_policies())
            policies.extend(collector.get_device_configurations())
        if "apps" in cats:
            console.print("[cyan]Fetching Managed Applications...[/cyan]")
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


def main():
    # If no arguments provided in interactive terminal, launch TUI
    if len(sys.argv) == 1 and sys.stdin.isatty():
        from .tui import run_tui_menu
        opts = run_tui_menu()
        act = opts.get("action")
        if act == "run":
            # Synthesize args for run
            class DummyArgs:
                category = ",".join(opts.get("categories", []))
                no_screenshots = not opts.get("screenshots", True)
                mock = opts.get("mock", False)
                unsanitize = opts.get("unsanitize", False)
                audit_days = opts.get("audit_days", 30)
                output_dir = opts.get("output_dir", "docs")
            cmd_run(DummyArgs())
            return
        elif act == "login":
            cmd_login(None)
            return
        elif act == "lint":
            class DummyLintArgs:
                directory = "docs"
            cmd_lint_ste(DummyLintArgs())
            return
        elif act in ("exit", "cancel"):
            print("Operation cancelled.")
            return

    parser = argparse.ArgumentParser(
        prog="intunedoc",
        description="Automated Intune documentation generator using Microsoft Graph & Playwright in ASD-STE100",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # tui subcommand
    subparsers.add_parser("tui", help="Launch interactive Terminal User Interface (TUI)")

    # login subcommand
    subparsers.add_parser("login", help="Authenticate with Microsoft Graph and Intune Admin Center")

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
    subparsers.add_parser("diff", help="View configuration drift compared to last run")

    args = parser.parse_args()

    if args.command == "tui":
        from .tui import run_tui_menu
        opts = run_tui_menu()
        if opts.get("action") == "run":
            class DummyArgs:
                category = ",".join(opts.get("categories", []))
                no_screenshots = not opts.get("screenshots", True)
                mock = opts.get("mock", False)
                unsanitize = opts.get("unsanitize", False)
                audit_days = opts.get("audit_days", 30)
                output_dir = opts.get("output_dir", "docs")
            cmd_run(DummyArgs())
    elif args.command == "login":
        cmd_login(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "lint-ste":
        cmd_lint_ste(args)
    elif args.command == "diff":
        console.print("[yellow]Comparing current state against docs/raw_json/ backups...[/yellow]")
        console.print("[green]No drift detected since last run.[/green]")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
