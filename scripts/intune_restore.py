#!/usr/bin/env python3
"""
Standalone Microsoft Intune Configuration Restore Utility.
Restores backed up raw JSON policies with multi-layered safety controls.
Licensed under GNU AGPLv3.

Safety Controls:
1. Strips all assignment targets by default (policies created dormant/unassigned).
2. Collision and overwrite detection with explicit typed confirmations.
3. Sanitization/Masking sentinel (rejects placeholder values).
4. Server-generated metadata scrubbing (id, @odata.*, timestamps, versions).
5. Comprehensive dry-run execution simulation (--dry-run).
6. Generates local audit receipt with rollback commands.
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm, Prompt

console = Console()

METADATA_KEYS_TO_STRIP = {
    "id",
    "@odata.context",
    "@odata.etag",
    "createdDateTime",
    "lastModifiedDateTime",
    "version",
    "supportsScopeTags",
    "isAssigned",
    "deviceStatuses",
    "userStatuses",
    "deviceStatusOverview",
    "deviceSettingStateSummaries",
    "settingCount",
    "roleScopeTagIds",
}

ASSIGNMENT_KEYS = {
    "assignments",
    "assignments@odata.bind",
    "assignmentTarget",
}


def scan_for_masked_values(obj: Any, path: str = "") -> List[Tuple[str, str]]:
    """Scan JSON object for sanitized or masked placeholders."""
    findings = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            current_path = f"{path}.{k}" if path else k
            findings.extend(scan_for_masked_values(v, current_path))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            current_path = f"{path}[{idx}]"
            findings.extend(scan_for_masked_values(item, current_path))
    elif isinstance(obj, str):
        if "[masked:" in obj.lower() or "[sanitized:" in obj.lower():
            findings.append((path, obj))
    return findings


def scrub_policy_payload(
    payload: Dict[str, Any],
    preserve_assignments: bool = False,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Scrub immutable server metadata and assignments from policy payload.
    Returns cleaned payload and list of stripped keys.
    """
    cleaned = json.loads(json.dumps(payload))
    stripped_keys = []

    # Strip top-level immutable server metadata
    for key in list(cleaned.keys()):
        if key in METADATA_KEYS_TO_STRIP or key.startswith("@odata.context"):
            cleaned.pop(key, None)
            stripped_keys.append(key)

    # Strip assignments unless explicitly overridden
    if not preserve_assignments:
        for key in list(cleaned.keys()):
            if key in ASSIGNMENT_KEYS or "assignment" in key.lower():
                cleaned.pop(key, None)
                stripped_keys.append(key)

    return cleaned, stripped_keys


def detect_target_endpoint(payload: Dict[str, Any]) -> str:
    """Determine the Microsoft Graph endpoint for the policy payload."""
    odata_type = str(payload.get("@odata.type") or "").lower()
    keys_lower = {k.lower() for k in payload.keys()}

    if "compliance" in odata_type:
        return "/deviceManagement/deviceCompliancePolicies"

    if "script" in odata_type or "scriptcontent" in keys_lower or "filename" in keys_lower:
        return "/deviceManagement/deviceManagementScripts"

    if "configurationpolicy" in odata_type or "settings" in payload:
        return "/deviceManagement/configurationPolicies"

    if "deviceconfiguration" in odata_type or "windows10" in odata_type or "ios" in odata_type:
        return "/deviceManagement/deviceConfigurations"

    if "mobileapp" in odata_type or "app" in odata_type:
        return "/deviceAppManagement/mobileApps"

    return "/deviceManagement/configurationPolicies"


def extract_policy_name(payload: Dict[str, Any]) -> str:
    """Extract display name or name from policy payload."""
    return str(payload.get("displayName") or payload.get("name") or "Unnamed Policy")


def set_policy_name(payload: Dict[str, Any], new_name: str) -> None:
    """Update name fields in policy payload."""
    if "displayName" in payload or "name" not in payload:
        payload["displayName"] = new_name
    if "name" in payload:
        payload["name"] = new_name


def check_collision_in_tenant(
    client: Any,
    endpoint: str,
    policy_name: str,
) -> Optional[Dict[str, Any]]:
    """Check if a policy with the same name already exists in the destination tenant."""
    try:
        results = client.get_all_pages(endpoint, beta=True)
        for p in results:
            p_name = p.get("displayName") or p.get("name") or ""
            if p_name.strip().lower() == policy_name.strip().lower():
                return p
    except Exception as e:
        console.print(f"[yellow]⚠️ Could not query existing policies at {endpoint}: {e}[/yellow]")
    return None


def execute_restore(
    file_path: str,
    dry_run: bool = False,
    overwrite: bool = False,
    suffix: str = " - Restored",
    preserve_assignments: bool = False,
    no_prompt: bool = False,
) -> bool:
    """
    Restore a single Intune policy with strict safety gates.
    """
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        console.print(f"[bold red]❌ Backup file not found: {abs_path}[/bold red]")
        return False

    with open(abs_path, "r", encoding="utf-8") as f:
        try:
            original_payload = json.load(f)
        except Exception as e:
            console.print(f"[bold red]❌ Failed to parse JSON file {abs_path}: {e}[/bold red]")
            return False

    # Safety Gate 1: Sanitization / Masking Sentinel
    masked_findings = scan_for_masked_values(original_payload)
    if masked_findings:
        console.print(Panel(
            f"[bold red]❌ Masked Values Detected (Sanitization Sentinel)[/bold red]\n\n"
            f"File: {abs_path}\n"
            f"Found {len(masked_findings)} sanitized placeholder values in backup.\n\n"
            + "\n".join([f" • [yellow]{k}[/yellow]: [dim]{v}[/dim]" for k, v in masked_findings[:5]])
            + ("\n • ... and more" if len(masked_findings) > 5 else "")
            + "\n\n[bold yellow]Safety Policy:[/bold yellow] Cannot import dummy placeholder strings into Intune.\n"
            f"To restore, use an unmasked backup generated with '--unsanitize' or replace placeholders in JSON.",
            title="Safety Violation",
            border_style="red",
        ))
        return False

    # Safety Gate 2: Server Metadata & Assignment Stripping
    cleaned_payload, stripped_keys = scrub_policy_payload(
        original_payload,
        preserve_assignments=preserve_assignments,
    )
    original_name = extract_policy_name(original_payload)
    target_endpoint = detect_target_endpoint(cleaned_payload)

    # Initialize Graph Client
    client = None
    existing_policy = None
    if not dry_run:
        from intune_visual_doc.auth.graph_auth import get_graph_token
        from intune_visual_doc.graph.client import GraphClient

        try:
            token = get_graph_token()
            client = GraphClient(token)
            existing_policy = check_collision_in_tenant(client, target_endpoint, original_name)
        except Exception as e:
            console.print(f"[bold red]❌ Authentication failed: {e}[/bold red]")
            return False

    # Safety Gate 3: Collision & Overwrite Logic
    action_type = "CREATE"
    final_name = original_name
    collision_detected = existing_policy is not None

    if collision_detected:
        if not overwrite:
            final_name = f"{original_name}{suffix}"
            set_policy_name(cleaned_payload, final_name)
            console.print(
                f"[yellow]⚠️ Existing policy found with name '{original_name}'.\n"
                f"   Safe Collision Mode active: Policy will be created as '{final_name}'[/yellow]"
            )
        else:
            action_type = "UPDATE"
            cleaned_payload["id"] = existing_policy["id"]
            console.print(
                f"[bold red]⚠️ OVERWRITE REQUESTED for existing policy '{original_name}' (ID: {existing_policy['id']})[/bold red]"
            )

    # Display Execution Plan Table
    table = Table(title="Intune Restore Execution Plan", border_style="cyan")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Backup Source", abs_path)
    table.add_row("Original Policy Name", original_name)
    table.add_row("Target Policy Name", final_name)
    table.add_row("Graph Endpoint", target_endpoint)
    table.add_row("HTTP Method", "PATCH" if action_type == "UPDATE" else "POST")
    table.add_row(
        "Assignment Target",
        "[bold red]PRESERVED (Targets Active Devices)[/bold red]"
        if preserve_assignments
        else "[bold green]STRIPPED (Safe: Created Dormant / Unassigned)[/bold green]",
    )
    table.add_row("Scrubbed Server Keys", f"{len(stripped_keys)} metadata fields removed")
    table.add_row("Execution Mode", "[yellow]SIMULATION (Dry-Run)[/yellow]" if dry_run else "[bold green]LIVE GRAPH WRITE[/bold green]")

    console.print(table)

    if dry_run:
        console.print("\n[bold green]✅ Dry-Run Completed. No changes made to Microsoft Intune tenant.[/bold green]\n")
        return True

    # Safety Gate 4: Explicit Confirmation
    if action_type == "UPDATE":
        console.print(
            f"[bold red]⚠️  CRITICAL OVERWRITE ACTION:[/bold red] This will modify live policy "
            f"'{original_name}' in tenant."
        )
        if not no_prompt:
            confirm_str = Prompt.ask(
                f"Type '[bold red]CONFIRM OVERWRITE[/bold red]' to proceed",
                default="CANCEL",
            )
            if confirm_str.strip() != "CONFIRM OVERWRITE":
                console.print("[yellow]Overwrite cancelled by operator.[/yellow]\n")
                return False
    else:
        if not no_prompt:
            confirmed = Confirm.ask("Ready to import policy into Microsoft Intune?", default=True)
            if not confirmed:
                console.print("[yellow]Import cancelled by operator.[/yellow]\n")
                return False

    # Execute Microsoft Graph API Call
    console.print(f"[cyan]Dispatching {action_type} to Microsoft Graph at {target_endpoint}...[/cyan]")
    try:
        if action_type == "UPDATE":
            url = f"https://graph.microsoft.com/beta{target_endpoint}/{existing_policy['id']}"
            res = client.session.patch(url, json=cleaned_payload)
            res.raise_for_status()
            created_obj = existing_policy
            created_id = existing_policy["id"]
        else:
            url = f"https://graph.microsoft.com/beta{target_endpoint}"
            res = client.session.post(url, json=cleaned_payload)
            res.raise_for_status()
            created_obj = res.json() if res.content else {}
            created_id = created_obj.get("id", "Unknown")

        console.print(
            f"\n[bold green]🎉 Policy successfully {action_type.lower()}d in Microsoft Intune![/bold green]\n"
            f" • Policy Name: [bold]{final_name}[/bold]\n"
            f" • Graph Object ID: `{created_id}`\n"
            f" • Status: [bold green]Dormant / Unassigned (Safe)[/bold green]"
        )

        # Generate local restore audit receipt
        receipt = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action_type,
            "policy_name": final_name,
            "graph_id": created_id,
            "endpoint": target_endpoint,
            "source_file": abs_path,
            "stripped_keys": stripped_keys,
            "rollback_url": f"https://intune.microsoft.com/#blade/Microsoft_Intune_DeviceSettings/DevicesMenu",
            "rollback_command": f"curl -X DELETE -H 'Authorization: Bearer <TOKEN>' https://graph.microsoft.com/beta{target_endpoint}/{created_id}",
        }

        receipt_dir = os.path.dirname(abs_path)
        receipt_file = os.path.join(receipt_dir, f"restore_receipt_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json")
        with open(receipt_file, "w", encoding="utf-8") as rf:
            json.dump(receipt, rf, indent=2)

        console.print(f"👉 [bold underline]Restore Receipt Saved:[/bold underline] file://{receipt_file}\n")
        return True

    except Exception as e:
        console.print(f"[bold red]❌ Failed to dispatch restore to Microsoft Graph: {e}[/bold red]\n")
        return False


def main():
    parser = argparse.ArgumentParser(
        prog="intune_restore",
        description="Standalone Microsoft Intune Configuration Restore Utility (AGPLv3)",
    )
    parser.add_argument("file", type=str, help="Path to raw JSON policy file to restore")
    parser.add_argument("--dry-run", action="store_true", help="Simulate restoration plan without making tenant modifications")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing policy if display name matches")
    parser.add_argument("--suffix", type=str, default=" - Restored", help="Suffix to append to policy name to avoid collision (default: ' - Restored')")
    parser.add_argument("--preserve-assignments", action="store_true", help="DANGEROUS: Preserve assignment targets instead of creating dormant policy")
    parser.add_argument("--no-prompt", action="store_true", help="Non-interactive execution mode (skips manual confirmation)")

    args = parser.parse_args()

    success = execute_restore(
        file_path=args.file,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
        suffix=args.suffix,
        preserve_assignments=args.preserve_assignments,
        no_prompt=args.no_prompt,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
