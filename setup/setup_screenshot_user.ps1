# ==============================================================================
# Setup Read-Only Screenshot Maker Service Account for intune-visual-doc
# License: GNU AGPLv3
#
# Account Name: svc-intunedoc-screenshot
# Purpose: Playwright Intune Admin Center Blade Visual Screenshot Capture
# Role: Microsoft Entra 'Directory Readers' + Intune 'Read Only Operator'
#
# NOTICE: This script makes changes to your Microsoft Entra tenant.
# All permissions granted are STRICTLY READ-ONLY. No write access is granted.
# ==============================================================================
$ErrorActionPreference = "Stop"

$UserPrincipalName = "svc-intunedoc-screenshot@<your-tenant-domain>"
$DisplayName = "IntuneDoc Screenshot Service"

Write-Host "=== Intune Visual Doc - Screenshot Maker Setup ===" -ForegroundColor Cyan

# Connect to Graph
Connect-MgGraph -Scopes "User.ReadWrite.All", "RoleManagement.ReadWrite.Directory" -NoWelcome

# 1. Create Cloud-Only User Account
Write-Host "Step 1: Creating Service Account: $UserPrincipalName..."
$PasswordProfile = @{
    ForceChangePasswordNextSignIn = $false
    Password = "P@" + [System.Guid]::NewGuid().ToString().Substring(0, 14) + "!A1"
}

$ExistingUser = Get-MgUser -Filter "UserPrincipalName eq '$UserPrincipalName'" | Select-Object -First 1
if (-not $ExistingUser) {
    $User = New-MgUser `
        -AccountEnabled `
        -DisplayName $DisplayName `
        -UserPrincipalName $UserPrincipalName `
        -MailNickname "svc-intunedoc-screenshot" `
        -PasswordProfile $PasswordProfile
    Write-Host "Created User: $($User.UserPrincipalName)" -ForegroundColor Green
    Write-Host "Temporary Initial Password: $($PasswordProfile.Password)" -ForegroundColor Yellow
} else {
    $User = $ExistingUser
    Write-Host "User already exists: $($User.UserPrincipalName)" -ForegroundColor Yellow
}

# 2. Assign Entra Directory Role: Directory Readers (Read-Only)
Write-Host "Step 2: Assigning Microsoft Entra Directory Role: Directory Readers..."
$DirectoryReadersTemplateId = "88d8e3e3-8f55-4a1e-953a-9b9898e8876b" # Directory Readers template ID
$RoleDef = Get-MgRoleManagementDirectoryRoleDefinition -Filter "DisplayName eq 'Directory Readers'" | Select-Object -First 1

if ($RoleDef) {
    $ExistingRole = Get-MgRoleManagementDirectoryRoleAssignment -Filter "PrincipalId eq '$($User.Id)' and RoleDefinitionId eq '$($RoleDef.Id)'"
    if (-not $ExistingRole) {
        New-MgRoleManagementDirectoryRoleAssignment `
            -PrincipalId $User.Id `
            -RoleDefinitionId $RoleDef.Id `
            -DirectoryScopeId "/" | Out-Null
        Write-Host "Assigned Directory Readers role successfully." -ForegroundColor Green
    } else {
        Write-Host "User already has Directory Readers role." -ForegroundColor Gray
    }
}

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
