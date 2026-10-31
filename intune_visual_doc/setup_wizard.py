"""
Setup wizard for Intune Visual Doc dedicated service principals and service accounts.
Configures unattended SPN (intunedoc-reader-spn) and screenshot maker (svc-intunedoc-screenshot).
Enforces strict read-only access for documentation and backup extraction.
"""

import os
import sys
import json
import stat
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

TENANT_WRITE_WARNING = (
    "[bold yellow]⚠️  TENANT WRITE NOTICE:[/bold yellow]\n"
    "This setup wizard is the [bold red]ONLY[/bold red] feature in intune-visual-doc that makes changes to your tenant.\n"
    "It creates the App Registration or guides service user creation.\n"
    "All other operations (generating documentation, screenshots, drift detection, STE audits) are [bold green]100% READ-ONLY[/bold green]."
)

# Project Naming Convention
DEFAULT_SPN_NAME = "intunedoc-reader-spn"
DEFAULT_USER_NAME = "svc-intunedoc-screenshot"
DEFAULT_USER_DISPLAY = "IntuneDoc Screenshot Service"

# Microsoft Graph App ID
GRAPH_RESOURCE_APP_ID = "00000003-0000-0000-c000-000000000000"

# Strict Read-Only Application Permissions (Roles) for Microsoft Graph
READ_ONLY_PERMISSIONS = [
    {
        "name": "DeviceManagementConfiguration.Read.All",
        "id": "dc377aa6-52d8-4e23-b271-2a7ae04cedf3",
        "description": "Read Intune device configuration and compliance policies",
    },
    {
        "name": "DeviceManagementApps.Read.All",
        "id": "e40edd52-0699-41e5-8ab8-33e15001d640",
        "description": "Read managed applications and deployment assignments",
    },
    {
        "name": "DeviceManagementServiceConfig.Read.All",
        "id": "2f51be20-0bb4-4fed-bf7b-db946066c75e",
        "description": "Read Intune tenant and device enrollment configuration",
    },
    {
        "name": "Directory.Read.All",
        "id": "7ab7862c-4c0f-45da-866c-5e49c950552f",
        "description": "Read directory groups, scope tags, and user assignments",
    },
    {
        "name": "AuditLog.Read.All",
        "id": "b0afded3-358c-46d8-8326-63365cf57f70",
        "description": "Read administrator audit events and change records",
    },
]


def generate_spn_bash_script(app_name: str = DEFAULT_SPN_NAME) -> str:
    """Generate ready-to-run Bash script using Azure CLI to create read-only SPN."""
    perm_args = " ".join([f"{p['id']}=Role" for p in READ_ONLY_PERMISSIONS])
    script = f"""#!/usr/bin/env bash
# ==============================================================================
# Setup Read-Only Unattended Service Principal for intune-visual-doc
# License: GNU AGPLv3
#
# NOTICE: This script makes changes to your Microsoft Entra tenant.
# All permissions granted are STRICTLY READ-ONLY for documentation and backup.
# ==============================================================================
set -euo pipefail

APP_NAME="{app_name}"
GRAPH_APP_ID="{GRAPH_RESOURCE_APP_ID}"

echo "=== Intune Visual Doc - Read-Only SPN Setup ==="
echo "Creating application: $APP_NAME"

# Check Azure CLI login
if ! az account show >/dev/null 2>&1; then
    echo "ERROR: Please run 'az login' before running this script." >&2
    exit 1
fi

TENANT_ID=$(az account show --query tenantId -o tsv)
echo "Tenant ID: $TENANT_ID"

# 1. Create Entra Application Registration
echo "Step 1: Creating App Registration..."
APP_ID=$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv)
if [ -z "$APP_ID" ]; then
    APP_ID=$(az ad app create --display-name "$APP_NAME" \\
        --sign-in-audience AzureADMyOrg \\
        --query appId -o tsv)
    echo "Created App ID: $APP_ID"
else
    echo "Found existing App ID: $APP_ID"
fi

# 2. Add Microsoft Graph Read-Only Application Permissions
echo "Step 2: Assigning Microsoft Graph Read-Only Application Permissions..."
az ad app permission add \\
    --id "$APP_ID" \\
    --api "$GRAPH_APP_ID" \\
    --api-permissions {perm_args}

# 3. Create Service Principal Enterprise Application
echo "Step 3: Creating Enterprise Application Service Principal..."
SP_ID=$(az ad sp list --filter "appId eq '$APP_ID'" --query "[0].id" -o tsv)
if [ -z "$SP_ID" ]; then
    az ad sp create --id "$APP_ID" >/dev/null
    echo "Created Service Principal for App ID: $APP_ID"
else
    echo "Service Principal already exists."
fi

# 4. Create Client Secret (valid for 1 year)
echo "Step 4: Generating Client Secret..."
SECRET_VALUE=$(az ad app credential reset \\
    --id "$APP_ID" \\
    --display-name "intunedoc-auto-key" \\
    --years 1 \\
    --query password -o tsv)

# 5. Grant Admin Consent
echo "Step 5: Granting Tenant Admin Consent..."
az ad app permission admin-consent --id "$APP_ID"

echo ""
echo "=============================================================================="
echo "🎉 Setup Complete! Save these credentials into .auth/config.json or .env"
echo "=============================================================================="
echo "AZURE_TENANT_ID=\"$TENANT_ID\""
echo "AZURE_CLIENT_ID=\"$APP_ID\""
echo "AZURE_CLIENT_SECRET=\"$SECRET_VALUE\""
echo "=============================================================================="
"""
    return script


def generate_spn_powershell_script(app_name: str = DEFAULT_SPN_NAME) -> str:
    """Generate ready-to-run PowerShell script to create read-only SPN via Microsoft.Graph module."""
    script = f"""# ==============================================================================
# Setup Read-Only Unattended Service Principal for intune-visual-doc
# License: GNU AGPLv3
#
# NOTICE: This script makes changes to your Microsoft Entra tenant.
# All permissions granted are STRICTLY READ-ONLY for documentation and backup.
# ==============================================================================
$ErrorActionPreference = "Stop"

$AppName = "{app_name}"
$GraphAppId = "{GRAPH_RESOURCE_APP_ID}"

Write-Host "=== Intune Visual Doc - Read-Only SPN Setup ===" -ForegroundColor Cyan

# Ensure Microsoft.Graph module is present
if (-not (Get-Module -ListAvailable -Name Microsoft.Graph.Applications)) {{
    Write-Host "Installing Microsoft.Graph.Applications module..." -ForegroundColor Yellow
    Install-Module Microsoft.Graph.Applications -Scope CurrentUser -Force -AllowClobber
}}

Connect-MgGraph -Scopes "Application.ReadWrite.All", "AppRoleAssignment.ReadWrite.All" -NoWelcome

$Context = Get-MgContext
$TenantId = $Context.TenantId
Write-Host "Connected to Tenant ID: $TenantId" -ForegroundColor Green

# 1. Find or Create Application
Write-Host "Step 1: Finding or Creating Application Registration: $AppName..."
$App = Get-MgApplication -Filter "DisplayName eq '$AppName'" | Select-Object -First 1
if (-not $App) {{
    $App = New-MgApplication -DisplayName $AppName -SignInAudience "AzureADMyOrg"
    Write-Host "Created Application: $($App.AppId)" -ForegroundColor Green
}} else {{
    Write-Host "Application already exists: $($App.AppId)" -ForegroundColor Yellow
}}

# 2. Get Microsoft Graph Service Principal
$GraphSp = Get-MgServicePrincipal -Filter "AppId eq '$GraphAppId'" | Select-Object -First 1
if (-not $GraphSp) {{
    throw "Microsoft Graph Service Principal not found in tenant."
}}

# 3. Create or Get Local Service Principal
Write-Host "Step 2: Ensuring Enterprise Application Service Principal exists..."
$LocalSp = Get-MgServicePrincipal -Filter "AppId eq '$($App.AppId)'" | Select-Object -First 1
if (-not $LocalSp) {{
    $LocalSp = New-MgServicePrincipal -AppId $App.AppId
}}

# 4. Assign Read-Only App Roles
Write-Host "Step 3: Assigning Microsoft Graph Read-Only Application Roles..."
$RolesToAssign = @(
    "DeviceManagementConfiguration.Read.All",
    "DeviceManagementApps.Read.All",
    "DeviceManagementServiceConfig.Read.All",
    "Directory.Read.All",
    "AuditLog.Read.All"
)

foreach ($RoleName in $RolesToAssign) {{
    $AppRole = $GraphSp.AppRoles | Where-Object {{ $_.Value -eq $RoleName -and $_.AllowedMemberTypes -contains "Application" }} | Select-Object -First 1
    if ($AppRole) {{
        $ExistingAssignment = Get-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $LocalSp.Id | Where-Object {{ $_.AppRoleId -eq $AppRole.Id }}
        if (-not $ExistingAssignment) {{
            New-MgServicePrincipalAppRoleAssignment `
                -ServicePrincipalId $LocalSp.Id `
                -PrincipalId $LocalSp.Id `
                -ResourceId $GraphSp.Id `
                -AppRoleId $AppRole.Id | Out-Null
            Write-Host "  Assigned: $RoleName" -ForegroundColor Green
        }} else {{
            Write-Host "  Already assigned: $RoleName" -ForegroundColor Gray
        }}
    }}
}}

# 5. Create Client Secret
Write-Host "Step 4: Generating 1-Year Client Secret..."
$SecretParams = @{{
    PasswordCredential = @{{
        DisplayName = "intunedoc-auto-key"
        EndDateTime = (Get-Date).AddYears(1)
    }}
}}
$NewSecret = Add-MgApplicationPassword -ApplicationId $App.Id -BodyParameter $SecretParams

Write-Host "`n==============================================================================" -ForegroundColor Green
Write-Host "🎉 Setup Complete! Save these credentials into .auth/config.json or .env" -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host "AZURE_TENANT_ID=`"$TenantId`""
Write-Host "AZURE_CLIENT_ID=`"$($App.AppId)`""
Write-Host "AZURE_CLIENT_SECRET=`"$($NewSecret.SecretText)`""
Write-Host "==============================================================================" -ForegroundColor Green
"""
    return script


def generate_screenshot_user_script(user_name: str = DEFAULT_USER_NAME, domain: str = "<your-tenant-domain>") -> str:
    """Generate ready-to-run PowerShell script to configure dedicated screenshot maker account."""
    upn = f"{user_name}@{domain}"
    script = f"""# ==============================================================================
# Setup Read-Only Screenshot Maker Service Account for intune-visual-doc
# License: GNU AGPLv3
#
# Account Name: {user_name}
# Purpose: Playwright Intune Admin Center Blade Visual Screenshot Capture
# Role: Microsoft Entra 'Directory Readers' + Intune 'Read Only Operator'
#
# NOTICE: This script makes changes to your Microsoft Entra tenant.
# All permissions granted are STRICTLY READ-ONLY. No write access is granted.
# ==============================================================================
$ErrorActionPreference = "Stop"

$UserPrincipalName = "{upn}"
$DisplayName = "{DEFAULT_USER_DISPLAY}"

Write-Host "=== Intune Visual Doc - Screenshot Maker Setup ===" -ForegroundColor Cyan

# Connect to Graph
Connect-MgGraph -Scopes "User.ReadWrite.All", "RoleManagement.ReadWrite.Directory" -NoWelcome

# 1. Create Cloud-Only User Account
Write-Host "Step 1: Creating Service Account: $UserPrincipalName..."
$PasswordProfile = @{{
    ForceChangePasswordNextSignIn = $false
    Password = "P@" + [System.Guid]::NewGuid().ToString().Substring(0, 14) + "!A1"
}}

$ExistingUser = Get-MgUser -Filter "UserPrincipalName eq '$UserPrincipalName'" | Select-Object -First 1
if (-not $ExistingUser) {{
    $User = New-MgUser `
        -AccountEnabled `
        -DisplayName $DisplayName `
        -UserPrincipalName $UserPrincipalName `
        -MailNickname "{user_name}" `
        -PasswordProfile $PasswordProfile
    Write-Host "Created User: $($User.UserPrincipalName)" -ForegroundColor Green
    Write-Host "Temporary Initial Password: $($PasswordProfile.Password)" -ForegroundColor Yellow
}} else {{
    $User = $ExistingUser
    Write-Host "User already exists: $($User.UserPrincipalName)" -ForegroundColor Yellow
}}

# 2. Assign Entra Directory Role: Directory Readers (Read-Only)
Write-Host "Step 2: Assigning Microsoft Entra Directory Role: Directory Readers..."
$DirectoryReadersTemplateId = "88d8e3e3-8f55-4a1e-953a-9b9898e8876b" # Directory Readers template ID
$RoleDef = Get-MgRoleManagementDirectoryRoleDefinition -Filter "DisplayName eq 'Directory Readers'" | Select-Object -First 1

if ($RoleDef) {{
    $ExistingRole = Get-MgRoleManagementDirectoryRoleAssignment -Filter "PrincipalId eq '$($User.Id)' and RoleDefinitionId eq '$($RoleDef.Id)'"
    if (-not $ExistingRole) {{
        New-MgRoleManagementDirectoryRoleAssignment `
            -PrincipalId $User.Id `
            -RoleDefinitionId $RoleDef.Id `
            -DirectoryScopeId "/" | Out-Null
        Write-Host "Assigned Directory Readers role successfully." -ForegroundColor Green
    }} else {{
        Write-Host "User already has Directory Readers role." -ForegroundColor Gray
    }}
}}

Write-Host "`n==============================================================================" -ForegroundColor Cyan
Write-Host "MANDATORY MANUAL PORTAL STEPS (INTUNE RBAC & LICENSE):" -ForegroundColor Yellow
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "1. LICENSE: Assign a Microsoft Intune Plan 1 license to $UserPrincipalName"
Write-Host "   (Required to open the Intune Admin Center blades without licensing errors)."
Write-Host ""
Write-Host "2. INTUNE RBAC: In https://intune.microsoft.com -> Tenant administration -> Roles:"
Write-Host "   - Select 'Read Only Operator'"
Write-Host "   - Click Assignments -> Assign"
Write-Host "   - Name: 'IntuneDoc-Screenshot-Read-Only'"
Write-Host "   - Members: Add $UserPrincipalName"
Write-Host "   - Scope Groups: Select All Devices / All Users"
Write-Host ""
Write-Host "3. BROWSER SETUP: Open Microsoft Edge or Chrome, create a new profile,"
Write-Host "   sign in as $UserPrincipalName, and complete MFA / initial password change."
Write-Host "==============================================================================" -ForegroundColor Cyan
"""
    return script


def export_setup_scripts(output_dir: str = "setup") -> List[str]:
    """Export bash and powershell setup scripts into the specified directory."""
    os.makedirs(output_dir, exist_ok=True)

    bash_path = os.path.join(output_dir, "setup_spn.sh")
    ps1_path = os.path.join(output_dir, "setup_spn.ps1")
    user_ps1_path = os.path.join(output_dir, "setup_screenshot_user.ps1")
    readme_path = os.path.join(output_dir, "README.md")

    # Write Bash script
    with open(bash_path, "w", encoding="utf-8") as f:
        f.write(generate_spn_bash_script())
    try:
        os.chmod(bash_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    except Exception:
        pass

    # Write PowerShell SPN script
    with open(ps1_path, "w", encoding="utf-8") as f:
        f.write(generate_spn_powershell_script())

    # Write PowerShell User script
    with open(user_ps1_path, "w", encoding="utf-8") as f:
        f.write(generate_screenshot_user_script())

    # Write README
    readme_content = f"""# Intune Visual Doc — Dedicated Identity Setup Guides

> [!WARNING]
> **TENANT WRITE NOTICE**:
> This setup folder contains the **ONLY** procedures in `intune-visual-doc` that create or modify tenant objects.
> All other documentation, diff, and audit workflows are strictly **100% READ-ONLY**.

## 1. Unattended Service Principal (`{DEFAULT_SPN_NAME}`)

For automated documentation, nightly CI/CD jobs, and configuration backups via Microsoft Graph API.

### Required Permissions (Strictly Read-Only)
| API | Permission | Type | Purpose |
| :--- | :--- | :--- | :--- |
| Microsoft Graph | `DeviceManagementConfiguration.Read.All` | Application | Read Intune device configurations & compliance |
| Microsoft Graph | `DeviceManagementApps.Read.All` | Application | Read managed applications & assignments |
| Microsoft Graph | `DeviceManagementServiceConfig.Read.All` | Application | Read Intune service configurations |
| Microsoft Graph | `Directory.Read.All` | Application | Read Entra groups, scope tags, and targets |
| Microsoft Graph | `AuditLog.Read.All` | Application | Read administrative audit change events |

### Automated Setup Scripts
- **Linux / macOS / Cloud Shell (Azure CLI)**:
  ```bash
  chmod +x setup/setup_spn.sh
  ./setup/setup_spn.sh
  ```
- **Windows / PowerShell Core (`Microsoft.Graph`)**:
  ```powershell
  .\\setup\\setup_spn.ps1
  ```

---

## 2. Screenshot Maker Service Account (`{DEFAULT_USER_NAME}`)

For interactive and browser-hooked Playwright visual blade screenshot capture in Microsoft Intune Admin Center.

### Required Roles & Licenses (Strictly Read-Only)
1. **Entra ID Directory Role**: `Directory Readers` (or `Global Reader`).
2. **Intune RBAC Role**: `Read Only Operator` (assigned in Intune Admin Center > Tenant admin > Roles).
3. **License**: Microsoft Intune Plan 1 (required to render Intune blades).

### Script Execution
```powershell
.\\setup\\setup_screenshot_user.ps1
```
"""
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)

    return [bash_path, ps1_path, user_ps1_path, readme_path]


def verify_spn_credentials(tenant_id: str, client_id: str, client_secret: str) -> Dict[str, Any]:
    """
    Test SPN credentials against Microsoft Graph and verify read-only access.
    Returns dictionary with result status and tenant details.
    """
    import msal

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=authority,
    )
    res = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

    if "access_token" not in res:
        return {
            "success": False,
            "error": res.get("error_description", res.get("error", "Unknown token acquisition failure")),
        }

    token = res["access_token"]

    # Verify read access against /organization endpoint
    req = urllib.request.Request(
        "https://graph.microsoft.com/v1.0/organization?$select=id,displayName,verifiedDomains",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "IntuneVisualDoc/1.0"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            orgs = data.get("value", [])
            org_name = orgs[0].get("displayName", "Unknown Tenant") if orgs else "Entra Tenant"
            return {
                "success": True,
                "org_name": org_name,
                "tenant_id": tenant_id,
                "client_id": client_id,
                "token": token,
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Token acquired but organization read test failed: {e}",
        }


def display_setup_banner():
    """Print the setup header with clear warning panel."""
    console.print(
        Panel.fit(
            "[bold cyan]⚙️  Intune Visual Doc — Read-Only Identity Setup Wizard[/bold cyan]\n"
            "[dim]Configure Unattended SPN or Dedicated Screenshot Service Account[/dim]\n"
            "[green]Standards: ASD-STE100 | License: GNU AGPLv3[/green]",
            border_style="cyan",
        )
    )
    console.print(Panel(TENANT_WRITE_WARNING, border_style="yellow"))


def interactive_setup_wizard():
    """Run interactive setup wizard in TUI."""
    from InquirerPy import inquirer
    from .prerequisites import load_config, save_config

    display_setup_banner()

    choice = inquirer.select(
        message="Select identity to configure:",
        choices=[
            {"name": "🤖 1. Configure Unattended Read-Only SPN (intunedoc-reader-spn)", "value": "spn"},
            {"name": "📸 2. Guide Dedicated Screenshot Maker (svc-intunedoc-screenshot)", "value": "user"},
            {"name": "📁 3. Export Ready-to-Run Setup Scripts to ./setup/", "value": "export"},
            {"name": "🔑 4. Enter & Test Stored SPN Credentials in .auth/config.json", "value": "test_spn"},
            {"name": "⬅️  5. Return to Main Workflow", "value": "back"},
        ],
        default="spn",
    ).execute()

    if choice == "back":
        return

    if choice == "export":
        files = export_setup_scripts()
        console.print("[bold green]✅ Exported setup scripts successfully:[/bold green]")
        for f in files:
            console.print(f"  • {f}")
        console.print("\n[dim]You can execute these scripts from any admin terminal or Azure Cloud Shell.[/dim]\n")
        return

    if choice == "spn":
        console.print(Panel(
            f"[bold cyan]🤖 Unattended Read-Only SPN Setup[/bold cyan]\n\n"
            f"Recommended Name: [bold green]{DEFAULT_SPN_NAME}[/bold green]\n"
            f"Role: Automated documentation and disaster recovery backups.\n"
            f"Permissions: [bold yellow]Strictly READ-ONLY[/bold yellow] Microsoft Graph Application roles.\n\n"
            f"Required Graph Permissions:\n"
            f"  • DeviceManagementConfiguration.Read.All\n"
            f"  • DeviceManagementApps.Read.All\n"
            f"  • DeviceManagementServiceConfig.Read.All\n"
            f"  • Directory.Read.All\n"
            f"  • AuditLog.Read.All\n\n"
            f"[bold]NO Directory Admin Roles Required.[/bold]",
            border_style="cyan",
        ))

        spn_action = inquirer.select(
            message="How would you like to set up the SPN?",
            choices=[
                {"name": "📁 Export scripts to ./setup/ and view manual steps", "value": "export"},
                {"name": "🔑 Enter Tenant ID, Client ID, and Client Secret now", "value": "enter"},
                {"name": "⬅️  Cancel", "value": "cancel"},
            ],
            default="enter",
        ).execute()

        if spn_action == "export":
            export_setup_scripts()
            console.print("[bold green]✅ Generated setup/setup_spn.sh and setup/setup_spn.ps1[/bold green]")
            console.print("[dim]Run either script with tenant admin privileges to complete creation.[/dim]\n")
            return

        if spn_action == "enter":
            choice = "test_spn"  # Fall through to entering credentials

    if choice == "test_spn":
        cfg = load_config()
        curr_t_id = cfg.get("azure_tenant_id", "")
        curr_c_id = cfg.get("azure_client_id", "")

        tenant_id = inquirer.text(
            message="Enter Microsoft Entra Tenant ID (GUID or domain):",
            default=curr_t_id,
        ).execute().strip()

        client_id = inquirer.text(
            message=f"Enter Application / Client ID for {DEFAULT_SPN_NAME}:",
            default=curr_c_id,
        ).execute().strip()

        client_secret = inquirer.secret(
            message="Enter Client Secret value:",
        ).execute().strip()

        if not tenant_id or not client_id or not client_secret:
            console.print("[yellow]⚠️ Incomplete credentials provided. Operation cancelled.[/yellow]\n")
            return

        console.print("[yellow]Testing SPN token acquisition and read access with Microsoft Graph...[/yellow]")
        test_res = verify_spn_credentials(tenant_id, client_id, client_secret)

        if test_res.get("success"):
            console.print(f"[bold green]🎉 Success! Authenticated to tenant: {test_res.get('org_name')}[/bold green]")
            save_confirm = inquirer.confirm(
                message="Save these credentials securely to .auth/config.json (0600 permissions)?",
                default=True,
            ).execute()
            if save_confirm:
                cfg["azure_tenant_id"] = tenant_id
                cfg["azure_client_id"] = client_id
                cfg["azure_client_secret"] = client_secret
                save_config(cfg)
                console.print("[bold green]✅ Stored in .auth/config.json. Unattended runs are now ready![/bold green]\n")
        else:
            console.print(f"[bold red]❌ SPN verification failed:[/bold red] {test_res.get('error')}\n")

    if choice == "user":
        console.print(Panel(
            f"[bold cyan]📸 Dedicated Screenshot Maker Service Account[/bold cyan]\n\n"
            f"Account Name: [bold green]{DEFAULT_USER_NAME}@[your-tenant-domain][/bold green]\n"
            f"Display Name: [bold]{DEFAULT_USER_DISPLAY}[/bold]\n"
            f"Purpose: Headless or visible Playwright blade captures in Intune Admin Center.\n\n"
            f"[bold yellow]Strict Least-Privilege Role Posture:[/bold yellow]\n"
            f"  1. [bold]Microsoft Entra Role:[/bold] 'Directory Readers' (Read-only directory access)\n"
            f"  2. [bold]Intune RBAC Role:[/bold] 'Read Only Operator' (Assigned in Intune portal)\n"
            f"  3. [bold]License Required:[/bold] Microsoft Intune Plan 1 (to load blades)\n\n"
            f"[bold red]CRITICAL: Do NOT grant Global Administrator or Intune Administrator.[/bold red]",
            border_style="cyan",
        ))

        export_user = inquirer.confirm(
            message="Export setup/setup_screenshot_user.ps1 script now?",
            default=True,
        ).execute()

        if export_user:
            export_setup_scripts()
            console.print("[bold green]✅ Exported setup/setup_screenshot_user.ps1[/bold green]")
            console.print("[dim]Run this script in PowerShell to automate service user provisioning.[/dim]\n")
