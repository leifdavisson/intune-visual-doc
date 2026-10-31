"""
Interactive Terminal User Interface (TUI) for Intune Visual Doc.
Features interactive option toggles with live CLI command preview.
"""

from InquirerPy import inquirer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def render_banner():
    console.print(
        Panel.fit(
            "[bold cyan]🛡️  Intune Visual Doc[/bold cyan]\n"
            "[dim]Automated Intune Settings Documentation with Microsoft Graph & Playwright Screenshots[/dim]\n"
            "[green]Standards: ASD-STE100 | License: GNU AGPLv3[/green]",
            border_style="cyan",
        )
    )


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
            {"name": "📝 3. Run ASD-STE100 Linter on Documents", "value": "lint"},
            {"name": "🔍 4. View Configuration Drift (Diff)", "value": "diff"},
            {"name": "❌ 5. Exit", "value": "exit"},
        ],
        default="run",
    ).execute()

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

    use_mock = inquirer.confirm(
        message="Use Mock / Sample Data (instant offline test without live tenant)?",
        default=False,
    ).execute()

    screenshots = True
    if not use_mock:
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
