# ==============================================================================
# Setup Read-Only Unattended Service Principal for intune-visual-doc
# License: GNU AGPLv3
#
# NOTICE: This script makes changes to your Microsoft Entra tenant.
# All permissions granted are STRICTLY READ-ONLY for documentation and backup.
# ==============================================================================
$ErrorActionPreference = "Stop"

$AppName = "intunedoc-reader-spn"
$GraphAppId = "00000003-0000-0000-c000-000000000000"

Write-Host "=== Intune Visual Doc - Read-Only SPN Setup ===" -ForegroundColor Cyan

# Ensure Microsoft.Graph module is present
if (-not (Get-Module -ListAvailable -Name Microsoft.Graph.Applications)) {
    Write-Host "Installing Microsoft.Graph.Applications module..." -ForegroundColor Yellow
    Install-Module Microsoft.Graph.Applications -Scope CurrentUser -Force -AllowClobber
}

Connect-MgGraph -Scopes "Application.ReadWrite.All", "AppRoleAssignment.ReadWrite.All" -NoWelcome

$Context = Get-MgContext
$TenantId = $Context.TenantId
Write-Host "Connected to Tenant ID: $TenantId" -ForegroundColor Green

# 1. Find or Create Application
Write-Host "Step 1: Finding or Creating Application Registration: $AppName..."
$App = Get-MgApplication -Filter "DisplayName eq '$AppName'" | Select-Object -First 1
if (-not $App) {
    $App = New-MgApplication -DisplayName $AppName -SignInAudience "AzureADMyOrg"
    Write-Host "Created Application: $($App.AppId)" -ForegroundColor Green
} else {
    Write-Host "Application already exists: $($App.AppId)" -ForegroundColor Yellow
}

# 2. Get Microsoft Graph Service Principal
$GraphSp = Get-MgServicePrincipal -Filter "AppId eq '$GraphAppId'" | Select-Object -First 1
if (-not $GraphSp) {
    throw "Microsoft Graph Service Principal not found in tenant."
}

# 3. Create or Get Local Service Principal
Write-Host "Step 2: Ensuring Enterprise Application Service Principal exists..."
$LocalSp = Get-MgServicePrincipal -Filter "AppId eq '$($App.AppId)'" | Select-Object -First 1
if (-not $LocalSp) {
    $LocalSp = New-MgServicePrincipal -AppId $App.AppId
}

# 4. Assign Read-Only App Roles
Write-Host "Step 3: Assigning Microsoft Graph Read-Only Application Roles..."
$RolesToAssign = @(
    "DeviceManagementConfiguration.Read.All",
    "DeviceManagementApps.Read.All",
    "DeviceManagementServiceConfig.Read.All",
    "Directory.Read.All",
    "AuditLog.Read.All"
)

foreach ($RoleName in $RolesToAssign) {
    $AppRole = $GraphSp.AppRoles | Where-Object { $_.Value -eq $RoleName -and $_.AllowedMemberTypes -contains "Application" } | Select-Object -First 1
    if ($AppRole) {
        $ExistingAssignment = Get-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $LocalSp.Id | Where-Object { $_.AppRoleId -eq $AppRole.Id }
        if (-not $ExistingAssignment) {
            New-MgServicePrincipalAppRoleAssignment `
                -ServicePrincipalId $LocalSp.Id `
                -PrincipalId $LocalSp.Id `
                -ResourceId $GraphSp.Id `
                -AppRoleId $AppRole.Id | Out-Null
            Write-Host "  Assigned: $RoleName" -ForegroundColor Green
        } else {
            Write-Host "  Already assigned: $RoleName" -ForegroundColor Gray
        }
    }
}

# 5. Create Client Secret
Write-Host "Step 4: Generating 1-Year Client Secret..."
$SecretParams = @{
    PasswordCredential = @{
        DisplayName = "intunedoc-auto-key"
        EndDateTime = (Get-Date).AddYears(1)
    }
}
$NewSecret = Add-MgApplicationPassword -ApplicationId $App.Id -BodyParameter $SecretParams

Write-Host "`n==============================================================================" -ForegroundColor Green
Write-Host "🎉 Setup Complete! Save these credentials into .auth/config.json or .env" -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host "AZURE_TENANT_ID=`"$TenantId`""
Write-Host "AZURE_CLIENT_ID=`"$($App.AppId)`""
Write-Host "AZURE_CLIENT_SECRET=`"$($NewSecret.SecretText)`""
Write-Host "==============================================================================" -ForegroundColor Green
