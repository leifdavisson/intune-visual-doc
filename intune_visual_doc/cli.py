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
from .prerequisites import display_prerequisites_table, wipe_all_credentials, load_config, load_dotenv
from .mock_data import get_mock_policies, get_mock_audit_events, setup_mock_screenshots
from .deliverables import (
    create_timestamped_run_dir,
    update_latest_pointer,
    record_run_in_catalog,
    get_latest_deliverables_dir,
)

console = Console(legacy_windows=False)


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
    target_base = getattr(args, "output_dir", "deliverables")
    no_timestamp = getattr(args, "no_timestamp", False)

    # Determine output directory
    is_timestamped = not no_timestamp and target_base in ("deliverables", "docs")
    if is_timestamped:
        base_dir = "deliverables"
        output_dir = create_timestamped_run_dir(base_dir=base_dir)
    else:
        output_dir = os.path.abspath(target_base)
        os.makedirs(output_dir, exist_ok=True)
        base_dir = output_dir

    console.print(Panel(
        f"[bold cyan]🚀 Starting Intune Documentation Run[/bold cyan]\n"
        f"[dim]Target deliverable directory: {output_dir}[/dim]"
    ))

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
            if not (fetch_all or "configuration" in cats):
                policies.extend([
                    p for p in collector.get_configuration_policies()
                    if p.get("category_label") == "Endpoint Security"
                ])

        if fetch_all or legacy_config_bundle or "scripts" in cats:
            console.print("[cyan]Fetching Devices > Scripts (PowerShell & Shell)...[/cyan]")
            policies.extend(collector.get_device_management_scripts())

        if fetch_all or legacy_config_bundle or "enrollment" in cats:
            console.print("[cyan]Fetching Devices > Enrollment configurations (Autopilot)...[/cyan]")
            policies.extend(collector.get_device_enrollment_configurations())

        if fetch_all or "apps" in cats:
            console.print("[cyan]Fetching Apps (Managed applications)...[/cyan]")
            policies.extend(collector.get_managed_apps())

        # Deduplicate policies by ID while preserving extraction order
        seen_ids = set()
        deduped_policies = []
        for p in policies:
            pid = p.get("id")
            if pid and pid in seen_ids:
                continue
            if pid:
                seen_ids.add(pid)
            deduped_policies.append(p)
        policies = deduped_policies

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
    console.print(f"👉 [bold underline]Deliverable Index:[/bold underline] file://{summary['index_path']}")

    if is_timestamped:
        latest_pointer = update_latest_pointer(output_dir, base_dir=base_dir)
        cfg = load_config()
        account_email = cfg.get("account_email", "")
        catalog_path = record_run_in_catalog(
            base_dir=base_dir,
            run_dir=output_dir,
            summary=summary,
            tenant_hint=account_email,
            audit_count=len(audit_events),
        )
        console.print(f"👉 [bold underline]Latest Pointer:[/bold underline] file://{latest_pointer}/README.md")
        console.print(f"👉 [bold underline]Master Catalog:[/bold underline] file://{catalog_path}\n")
    else:
        console.print("")


def cmd_backup(args):
    """Export raw JSON policy configurations for disaster recovery and safe restores."""
    base_dir = getattr(args, "output_dir", "deliverables")
    no_timestamp = getattr(args, "no_timestamp", False)
    use_mock = getattr(args, "mock", False)
    unsanitize = getattr(args, "unsanitize", True)

    if no_timestamp:
        output_dir = os.path.abspath(base_dir)
        os.makedirs(output_dir, exist_ok=True)
        is_timestamped = False
    else:
        output_dir = create_timestamped_run_dir(base_dir=base_dir)
        is_timestamped = True

    fidelity_text = (
        "Unsanitized (Full fidelity for 1-to-1 restore)"
        if unsanitize
        else "Sanitized (Secrets masked)"
    )
    console.print(Panel(
        f"[bold cyan]📦 Exporting Intune Configuration Backup[/bold cyan]\n"
        f"Mode: {'Mock Sample Data' if use_mock else 'Live Microsoft Graph API'}\n"
        f"Restore Fidelity: {fidelity_text}\n"
        f"Target Directory: {output_dir}/raw_json\n\n"
        f"[dim]Tip: Fast export without browser screenshots. Use 'scripts/intune_restore.py' to restore.[/dim]"
    ))

    policies = []
    if use_mock:
        policies = get_mock_policies()
    else:
        try:
            token = get_graph_token()
            client = GraphClient(token)
            collector = PolicyCollector(client)
        except Exception as e:
            console.print(f"[red]Authentication not ready: {e}[/red]")
            console.print("[dim]Hint: Run 'intunedoc login' first or pass '--mock' for offline verification.[/dim]")
            sys.exit(1)

        cats = [c.strip().lower() for c in getattr(args, "category", "").split(",") if c.strip()]
        fetch_all = not cats or "all" in cats

        if fetch_all or "compliance" in cats:
            console.print("[cyan]Backing up Devices > Compliance policies...[/cyan]")
            policies.extend(collector.get_compliance_policies())

        if fetch_all or "configuration" in cats:
            console.print("[cyan]Backing up Devices > Configuration (Settings Catalog & Templates)...[/cyan]")
            policies.extend(collector.get_configuration_policies())
            policies.extend(collector.get_device_configurations())

        if fetch_all or "endpoint_security" in cats:
            console.print("[cyan]Backing up Endpoint security policies...[/cyan]")
            policies.extend(collector.get_endpoint_security_policies())

        if fetch_all or "scripts" in cats:
            console.print("[cyan]Backing up Devices > Scripts (PowerShell & Shell)...[/cyan]")
            policies.extend(collector.get_device_management_scripts())

        if fetch_all or "enrollment" in cats:
            console.print("[cyan]Backing up Devices > Enrollment configurations (Autopilot)...[/cyan]")
            policies.extend(collector.get_device_enrollment_configurations())

        if fetch_all or "apps" in cats:
            console.print("[cyan]Backing up Apps (Managed applications)...[/cyan]")
            policies.extend(collector.get_managed_apps())

        # Deduplicate policies by ID
        seen_ids = set()
        deduped = []
        for p in policies:
            pid = p.get("id")
            if pid and pid in seen_ids:
                continue
            if pid:
                seen_ids.add(pid)
            deduped.append(p)
        policies = deduped

    # Generate backup bundle
    generator = DocGenerator(output_dir=output_dir, unsanitize=unsanitize)
    summary = generator.render_all(
        policies=policies,
        audit_events=[],
        generator_user="Intune Backup Service",
        audit_days=0,
        screenshots_map={},
    )

    # Rich summary
    table = Table(title="Configuration Backup Summary", border_style="cyan")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right", style="green")
    table.add_column("Status", style="yellow")

    table.add_row("Total Policies", str(summary["stats"]["total_policies"]), "Exported to raw_json/")
    table.add_row("Assigned", str(summary["stats"]["assigned_policies"]), "Targeted in tenant")
    table.add_row("Unassigned", str(summary["stats"]["unassigned_policies"]), "Dormant in tenant")
    table.add_row("Restore Readiness", "✅ Valid JSON", "Ready for scripts/intune_restore.py")
    table.add_row("Restore Safety", "🛡️ Safe Mode", "Assignments stripped upon restore")

    console.print(table)
    console.print(f"\n[bold green]✅ Configuration backup export complete![/bold green]")
    console.print(f"👉 [bold underline]Backup Manifest:[/bold underline] file://{summary.get('manifest_path', '')}")
    console.print(f"👉 [bold underline]Raw JSON Directory:[/bold underline] file://{output_dir}/raw_json")

    if is_timestamped:
        latest_pointer = update_latest_pointer(output_dir, base_dir=base_dir)
        cfg = load_config()
        account_email = cfg.get("account_email", "")
        catalog_path = record_run_in_catalog(
            base_dir=base_dir,
            run_dir=output_dir,
            summary=summary,
            tenant_hint=account_email,
            audit_count=0,
            run_type="Backup",
        )
        console.print(f"👉 [bold underline]Latest Pointer:[/bold underline] file://{latest_pointer}/README.md")
        console.print(f"👉 [bold underline]Master Catalog:[/bold underline] file://{catalog_path}\n")
    else:
        console.print("")


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
    """Compare live policies against saved backups or compare two historical runs offline."""
    from .audit.drift import (
        compare_policies_granular,
        compare_backup_runs,
        display_granular_drift_table,
        render_drift_html_report,
    )

    from_run = getattr(args, "from_run", None)
    to_run = getattr(args, "to_run", None)
    export_html = getattr(args, "html", False)
    use_mock = getattr(args, "mock", False)
    base_dir = getattr(args, "output_dir", "deliverables")
    unsanitize = getattr(args, "unsanitize", False)

    if from_run:
        # Offline run-to-run comparison
        baseline_dir = os.path.abspath(from_run)
        if to_run:
            target_dir = os.path.abspath(to_run)
        else:
            target_dir = get_latest_deliverables_dir(base_dir) or os.path.abspath(base_dir)

        report = compare_backup_runs(baseline_dir, target_dir, unsanitize=unsanitize)
        display_granular_drift_table(report)

        if export_html:
            html_path = os.path.join(target_dir, "DRIFT_REPORT.html")
            out_file = render_drift_html_report(report, html_path, unsanitize=unsanitize)
            console.print(f"👉 [bold underline]Visual Drift HTML Report:[/bold underline] file://{out_file}\n")
        return

    # Comparing live or mock policies against latest backup
    target_dir = get_latest_deliverables_dir(base_dir) or os.path.abspath(base_dir)
    console.print(Panel(
        f"[bold cyan]🔍 Auditing Configuration Drift[/bold cyan]\n"
        f"Backup Directory: {target_dir}/raw_json"
    ))

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

    from .audit.posture import load_policies_from_backup
    saved_policies, scope = load_policies_from_backup(target_dir)

    diffs = compare_policies_granular(saved_policies, policies, baseline_dir=target_dir, unsanitize=unsanitize)
    added = sum(1 for d in diffs if d.status == "Added")
    removed = sum(1 for d in diffs if d.status == "Removed")
    modified = sum(1 for d in diffs if d.status == "Modified")
    unchanged = sum(1 for d in diffs if d.status == "Unchanged")
    total_setting_changes = sum(len(d.setting_diffs) for d in diffs if d.status == "Modified")

    report = {
        "baseline_dir": target_dir,
        "target_dir": "Live Tenant",
        "baseline_label": os.path.basename(target_dir),
        "target_label": "Live Microsoft Intune Tenant" if not use_mock else "Mock Intune Tenant",
        "diffs": diffs,
        "stats": {
            "total_policies_target": len(policies),
            "added": added,
            "removed": removed,
            "modified": modified,
            "unchanged": unchanged,
            "total_setting_changes": total_setting_changes,
        },
    }

    display_granular_drift_table(report)

    if export_html:
        html_path = os.path.join(target_dir, "DRIFT_REPORT.html")
        out_file = render_drift_html_report(report, html_path, unsanitize=unsanitize)
        console.print(f"👉 [bold underline]Visual Drift HTML Report:[/bold underline] file://{out_file}\n")


def cmd_audit(args):
    """Run security posture and best-practice audit against exported backup or mock data."""
    from .audit.posture import (
        load_policies_from_backup,
        evaluate_tenant_posture,
        display_posture_table,
        render_audit_report,
        render_executive_html_report,
        render_executive_pdf_report,
        detect_backup_scope,
    )
    from .mock_data import get_mock_policies
    from .deliverables import get_latest_deliverables_dir

    target_dir = getattr(args, "target_dir", None) or getattr(args, "output_dir", "deliverables")
    profile = getattr(args, "profile", "balanced") or "balanced"
    use_mock = getattr(args, "mock", False)
    fmt = getattr(args, "format", "both") or "both"
    custom_output = getattr(args, "output", None)

    selected_domains = getattr(args, "domains", None)

    if use_mock:
        policies = get_mock_policies()
        run_dir = os.path.abspath(target_dir) if target_dir != "deliverables" else os.path.abspath("deliverables/_mock_audit")
        detected_categories = {p.get("category", "").lower() for p in policies}
        scope = {
            "run_dir": run_dir,
            "detected_categories": detected_categories,
            "is_valid": True,
            "policy_count": len(policies),
        }
    else:
        resolved = os.path.abspath(target_dir)
        if not os.path.exists(os.path.join(resolved, "raw_json")) and not os.path.exists(os.path.join(resolved, "backup_manifest.json")):
            latest = get_latest_deliverables_dir(resolved)
            if latest:
                resolved = latest

        policies, scope = load_policies_from_backup(resolved)
        run_dir = scope["run_dir"]
        if not scope["is_valid"]:
            console.print(f"[bold red]❌ No backup data or raw JSON policies found in:[/bold red] {resolved}")
            console.print("[dim]Hint: Run 'intunedoc backup' first or pass '--mock' to test with sample data.[/dim]\n")
            sys.exit(1)

    evaluation = evaluate_tenant_posture(
        policies=policies,
        profile=profile,
        detected_categories=scope["detected_categories"],
        selected_domains=selected_domains,
    )

    if fmt in ("console", "both"):
        display_posture_table(evaluation, profile_name=profile.replace("-", " ").title())

    report_path = custom_output or os.path.join(run_dir, "AUDIT_RECOMMENDATIONS.md")
    if fmt in ("markdown", "both"):
        rendered_file = render_audit_report(
            evaluation=evaluation,
            output_path=report_path,
            generator_user="Intune Security Auditor",
        )
        console.print(f"👉 [bold underline]Markdown Recommendations:[/bold underline] file://{rendered_file}")

    if fmt in ("html", "both"):
        html_path = os.path.join(run_dir, "EXECUTIVE_AUDIT.html")
        render_executive_html_report(
            evaluation=evaluation,
            output_path=html_path,
            generator_user="Intune Security Auditor",
        )
        console.print(f"👉 [bold underline]Executive HTML Packet:[/bold underline] file://{html_path}")

    if fmt in ("pdf", "both"):
        try:
            pdf_path = os.path.join(run_dir, "EXECUTIVE_AUDIT.pdf")
            render_executive_pdf_report(
                evaluation=evaluation,
                output_path=pdf_path,
                generator_user="Intune Security Auditor",
            )
            console.print(f"👉 [bold underline]Executive Vector PDF:[/bold underline] file://{pdf_path}")
        except Exception as exc:
            console.print(f"[yellow]⚠️ Could not generate PDF: {exc}[/yellow]")

    console.print()


def cmd_batch(args):
    """Execute multi-tenant batch operations (posture audit or backups) across portfolio."""
    from .audit.batch import (
        load_portfolio_config,
        generate_sample_config,
        get_mock_portfolio,
        run_msp_audit_batch,
        display_msp_console_matrix,
        render_msp_markdown_matrix,
        render_msp_html_matrix,
    )

    if getattr(args, "generate_sample", None):
        out = generate_sample_config(args.generate_sample)
        console.print(f"[bold green]✅ Generated sample portfolio manifest:[/bold green] {out}")
        console.print("[dim]Edit this file with your tenant IDs or backup directories.[/dim]\n")
        return

    use_mock = getattr(args, "mock", False)
    config_file = getattr(args, "config", None)
    profile = getattr(args, "profile", "balanced") or "balanced"
    fmt = getattr(args, "format", "all") or "all"
    output_dir = getattr(args, "output_dir", "deliverables/msp_portfolio") or "deliverables/msp_portfolio"

    if use_mock or not config_file:
        if not use_mock and not config_file:
            console.print("[yellow]Notice: No --config provided. Running with sample mock portfolio.[/yellow]")
            console.print("[dim]Hint: Use 'intunedoc batch --generate-sample tenants.json' to create a manifest.[/dim]\n")
        portfolio_name, targets = get_mock_portfolio()
    else:
        try:
            portfolio_name, targets = load_portfolio_config(config_file)
        except Exception as e:
            console.print(f"[bold red]❌ Failed to load portfolio config:[/bold red] {e}")
            sys.exit(1)

    console.print(f"[cyan]Auditing {len(targets)} tenants in portfolio: {portfolio_name}...[/cyan]")
    report = run_msp_audit_batch(portfolio_name=portfolio_name, targets=targets, profile=profile)

    display_msp_console_matrix(report)

    os.makedirs(output_dir, exist_ok=True)

    if fmt in ("markdown", "all"):
        md_path = os.path.join(output_dir, "MSP_PORTFOLIO_AUDIT.md")
        render_msp_markdown_matrix(report, md_path)
        console.print(f"👉 [bold underline]MSP Markdown Matrix:[/bold underline] file://{os.path.abspath(md_path)}")

    if fmt in ("html", "all"):
        html_path = os.path.join(output_dir, "MSP_PORTFOLIO_AUDIT.html")
        render_msp_html_matrix(report, html_path)
        console.print(f"👉 [bold underline]MSP HTML Dashboard:[/bold underline] file://{os.path.abspath(html_path)}")

    console.print()


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
        t_id = os.environ.get("AZURE_TENANT_ID") or os.environ.get("INTUNE_TENANT_ID") or cfg.get("azure_tenant_id")
        c_id = os.environ.get("AZURE_CLIENT_ID") or os.environ.get("INTUNE_CLIENT_ID") or cfg.get("azure_client_id")
        sec = os.environ.get("AZURE_CLIENT_SECRET") or os.environ.get("INTUNE_CLIENT_SECRET") or cfg.get("azure_client_secret")

        if (not t_id or not c_id or not sec) and sys.stdin.isatty():
            console.print("[yellow]SPN credentials not found in environment or .auth/config.json.[/yellow]")
            console.print("[dim]Enter Service Principal values below to test live connectivity:[/dim]\n")
            try:
                from InquirerPy import inquirer
                t_id = t_id or inquirer.text(message="Entra / Intune Tenant ID (GUID):").execute()
                c_id = c_id or inquirer.text(message="Application / Client ID (GUID):").execute()
                sec = sec or inquirer.secret(message="Client Secret:").execute()
            except Exception:
                pass

        if not t_id or not c_id or not sec:
            console.print("[red]❌ SPN credentials missing. Set AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET or run 'intunedoc setup'.[/red]")
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
                output_dir = opts.get("output_dir", "deliverables")
                no_timestamp = False
            cmd_run(RunArgs())
            console.print("\n[dim]Press any key or return to main menu...[/dim]\n")
        elif act == "backup":
            class BackupArgs:
                category = ",".join(opts.get("categories", []))
                mock = opts.get("mock", False)
                unsanitize = opts.get("unsanitize", True)
                output_dir = opts.get("output_dir", "deliverables")
                no_timestamp = False
            cmd_backup(BackupArgs())
            try:
                from InquirerPy import inquirer
                from .tui import interactive_audit_wizard
                target_post_backup = "deliverables/latest" if os.path.exists("deliverables/latest") else opts.get("output_dir", "deliverables")
                console.print("\n[bold cyan]💡 Next Step Recommended:[/bold cyan] Audit this backup against security baselines.")
                run_audit_now = inquirer.confirm(
                    message="Would you like to run the Best-Practice Posture Audit on this backup now?",
                    default=True,
                ).execute()
                if run_audit_now:
                    audit_opts = interactive_audit_wizard(target_post_backup)
                    if audit_opts and audit_opts.get("action") == "audit":
                        class PostBackupAuditArgs:
                            target_dir = audit_opts.get("target_dir", target_post_backup)
                            profile = audit_opts.get("profile", "balanced")
                            mock = False
                            format = "both"
                            output = None
                            domains = audit_opts.get("selected_domains")
                        cmd_audit(PostBackupAuditArgs())
            except Exception as e:
                console.print(f"[yellow]Notice: Post-backup audit bypassed: {e}[/yellow]")
            console.print("\n[dim]Returning to main menu...[/dim]\n")
        elif act in ("login_done", "prereqs_done", "logout_done", "setup_done"):
            continue
        elif act == "setup":
            cmd_setup(None)
        elif act == "login":
            cmd_login(None)
        elif act == "audit":
            class AuditArgs:
                target_dir = opts.get("target_dir", "deliverables")
                profile = opts.get("profile", "balanced")
                mock = opts.get("mock", False)
                format = opts.get("format", "both")
                output = None
                domains = opts.get("selected_domains")
            cmd_audit(AuditArgs())
            console.print("\n[dim]Returning to main menu...[/dim]\n")
        elif act == "lint":
            target_lint = "deliverables/latest" if os.path.exists("deliverables/latest") else "docs"
            class LintArgs:
                directory = target_lint
            cmd_lint_ste(LintArgs())
            console.print("\n[dim]Returning to main menu...[/dim]\n")
        elif act == "diff":
            class DiffArgs:
                output_dir = opts.get("output_dir", "deliverables")
                from_run = opts.get("from_run")
                to_run = opts.get("to_run")
                html = opts.get("html", False)
                mock = opts.get("mock", False)
            cmd_diff(DiffArgs())
            console.print("\n[dim]Returning to main menu...[/dim]\n")
        elif act in ("exit", "cancel"):
            console.print("[bold cyan]👋 Exiting Intune Visual Doc. Goodbye![/bold cyan]\n")
            break


def main():
    setup_graceful_interrupt()
    load_dotenv()

    default_output_dir = os.environ.get("INTUNEDOC_OUTPUT_DIR") or "deliverables"

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
    run_parser.add_argument("--output-dir", type=str, default=default_output_dir, help=f"Base directory where deliverables are stored (default: {default_output_dir})")
    run_parser.add_argument("--no-timestamp", action="store_true", help="Write directly to output directory without creating a timestamped subfolder")

    # backup subcommand
    backup_parser = subparsers.add_parser("backup", help="Export raw JSON policy configurations (fast, no screenshots)")
    backup_parser.add_argument("--category", type=str, default="", help="Comma-separated categories to backup")
    backup_parser.add_argument("--mock", action="store_true", help="Backup mock school district sample data")
    backup_parser.add_argument("--unsanitize", action="store_true", default=True, help="Preserve unmasked raw configuration secrets (default: True for 1-to-1 restore)")
    backup_parser.add_argument("--sanitize", action="store_false", dest="unsanitize", help="Mask sensitive keys and pre-shared secrets in backup")
    backup_parser.add_argument("--output-dir", type=str, default=default_output_dir, help=f"Base directory where deliverables are stored (default: {default_output_dir})")
    backup_parser.add_argument("--no-timestamp", action="store_true", help="Write directly without creating a timestamped subfolder")

    # lint-ste subcommand
    lint_parser = subparsers.add_parser("lint-ste", help="Audit markdown files for ASD-STE100 compliance")
    lint_parser.add_argument("--directory", type=str, default="docs", help="Directory of markdown files to audit (default: docs)")

    # diff subcommand
    diff_parser = subparsers.add_parser("diff", help="View configuration drift compared to last run or between two runs")
    diff_parser.add_argument("--output-dir", type=str, default=default_output_dir, help=f"Deliverables directory containing run snapshots or raw_json/ backups (default: {default_output_dir})")
    diff_parser.add_argument("--from", dest="from_run", type=str, default=None, help="Baseline backup run directory for offline comparison")
    diff_parser.add_argument("--to", dest="to_run", type=str, default=None, help="Target backup run directory (defaults to latest)")
    diff_parser.add_argument("--html", action="store_true", help="Generate interactive DRIFT_REPORT.html with visual comparisons")
    diff_parser.add_argument("--mock", action="store_true", help="Compare mock policies against saved backups")
    diff_parser.add_argument("--unsanitize", action="store_true", help="Preserve unmasked raw configuration secrets in diff and drift reports")

    # audit subcommand
    audit_parser = subparsers.add_parser("audit", help="Audit tenant security posture and best-practice baseline alignment")
    audit_parser.add_argument("target_dir", nargs="?", default=default_output_dir, help=f"Path to deliverables directory, timestamped run, or backup raw_json/ (default: {default_output_dir})")
    audit_parser.add_argument("--profile", choices=["balanced", "strict-stig"], default="balanced", help="Audit profile (default: balanced)")
    audit_parser.add_argument("--mock", action="store_true", help="Audit mock school district sample data")
    audit_parser.add_argument("--format", choices=["console", "markdown", "html", "pdf", "both"], default="both", help="Output format (default: both)")
    audit_parser.add_argument("--output", type=str, default=None, help="Custom file path for AUDIT_RECOMMENDATIONS.md")

    # batch subcommand
    batch_parser = subparsers.add_parser("batch", help="Multi-tenant batch automation and portfolio posture audits")
    batch_parser.add_argument("--config", type=str, default=None, help="Path to portfolio JSON manifest (e.g. tenants.json)")
    batch_parser.add_argument("--profile", choices=["balanced", "strict-stig"], default="balanced", help="Audit profile (default: balanced)")
    batch_parser.add_argument("--mock", action="store_true", help="Audit simulated multi-tenant sample consortium")
    batch_parser.add_argument("--format", choices=["console", "markdown", "html", "all"], default="all", help="Output format (default: all)")
    batch_parser.add_argument("--output-dir", type=str, default="deliverables/msp_portfolio", help="Output directory for portfolio deliverables (default: deliverables/msp_portfolio)")
    batch_parser.add_argument("--generate-sample", type=str, default=None, help="Generate a template tenants.sample.json file")

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
    elif args.command == "backup":
        cmd_backup(args)
    elif args.command == "lint-ste":
        cmd_lint_ste(args)
    elif args.command == "diff":
        cmd_diff(args)
    elif args.command == "audit":
        cmd_audit(args)
    elif args.command == "batch":
        cmd_batch(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
