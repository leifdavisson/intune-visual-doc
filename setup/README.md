# Intune Visual Doc — Dedicated Identity Setup Guides

> [!WARNING]
> **TENANT WRITE NOTICE**:
> This setup folder contains the **ONLY** procedures in `intune-visual-doc` that create or modify tenant objects.
> All other documentation, diff, and audit workflows are strictly **100% READ-ONLY**.

## 1. Unattended Service Principal (`intunedoc-reader-spn`)

For automated documentation, nightly CI/CD jobs, and configuration backups via Microsoft Graph API.

### Required Permissions (Strictly Read-Only)
| API | Permission | Type | Purpose |
| :--- | :--- | :--- | :--- |
| Microsoft Graph | `DeviceManagementConfiguration.Read.All` | Application | Read Intune device configurations & compliance |
| Microsoft Graph | `DeviceManagementApps.Read.All` | Application | Read managed applications & assignments |
| Microsoft Graph | `DeviceManagementServiceConfig.Read.All` | Application | Read Intune service configurations |
| Microsoft Graph | `Directory.Read.All` | Application | Read Entra groups, scope tags, and targets |
| Microsoft Graph | `AuditLog.Read.All` | Application | Read administrative audit change events |
| Microsoft Graph | `DeviceManagementRBAC.Read.All` | Application | Read Intune RBAC roles and scope tags |
| Microsoft Graph | `DeviceManagementManagedDevices.Read.All` | Application | Read managed devices and compliance state |

### Automated Setup Scripts
- **Linux / macOS / Cloud Shell (Azure CLI)**:
  ```bash
  chmod +x setup/setup_spn.sh
  ./setup/setup_spn.sh
  ```
- **Windows / PowerShell Core (`Microsoft.Graph`)**:
  ```powershell
  .\setup\setup_spn.ps1
  ```

---

## 2. Screenshot Maker Service Account (`svc-intunedoc-screenshot`)

For interactive and browser-hooked Playwright visual blade screenshot capture in Microsoft Intune Admin Center.

### Required Roles & Licenses (Strictly Read-Only)
1. **Entra ID Directory Role**: `Directory Readers` (or `Global Reader`).
2. **Intune RBAC Role**: `Read Only Operator` (assigned in Intune Admin Center > Tenant admin > Roles).
3. **License**: Microsoft Intune Plan 1 (required to render Intune blades).

### Script Execution
```powershell
.\setup\setup_screenshot_user.ps1
```
