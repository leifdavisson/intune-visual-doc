# Microsoft Intune Tenant Documentation

> 🕒 **Documentation Stamp**: Generated on **2026-10-31 19:37:18 UTC** by **Intune Administrator**
>
> 📋 **Admin Audit Integration**: [View Recent Admin Audit Logs](audit/ADMIN_AUDIT_LOG.md) | [Open in Intune Portal](https://intune.microsoft.com/#view/Microsoft_Intune_DeviceSettings/TenantAdminMenuBlade/~/auditLogs)

Welcome to the automated Microsoft Intune configuration reference for this tenant.
This repository documents active settings, group assignments, and visual portal screenshots.

---

## Tenant Health & Hygiene Summary

| Metric | Total Count | Description |
| :--- | :--- | :--- |
| **Total Policies Documented** | `5` | Total active policies extracted across all categories. |
| **Assigned Policies** | `🟢 4` | Policies targeted to users or devices. |
| **Unassigned / Dormant Policies** | `🟡 1` | Policies created without active target assignments. |
| **Security Baselines** | `🛡️ 1` | Policies enforcing baseline security (BitLocker, Antivirus, etc.). |
| **Secret Sanitization** | `Enabled (Secrets Masked)` | Sensitive keys and credentials sanitized. |

---

## Documentation Categories

### Device Compliance Policies

- **Documentation**: [Microsoft Learn: Compliance Overview](https://learn.microsoft.com/en-us/mem/intune/protect/device-compliance-get-started)
- **Total Policies**: `1`

| Policy Name | Platform | Status | Last Modified | View Document |
| :--- | :--- | :--- | :--- | :--- |
| **Staff and Student Device Compliance Policy** | Windows 10/11 | `🟢 Assigned` | 2026-10-20T16:45:10Z | [Open Guide](compliance/staff-and-student-device-compliance-policy.md) |

### Configuration Profiles & Settings Catalog

- **Documentation**: [Microsoft Learn: Settings Catalog](https://learn.microsoft.com/en-us/mem/intune/configuration/settings-catalog)
- **Total Policies**: `3`

| Policy Name | Platform | Status | Last Modified | View Document |
| :--- | :--- | :--- | :--- | :--- |
| **BitLocker - Windows 11 Enterprise Baseline** | Windows 11 | `🟢 Assigned` | 2026-10-12T14:15:22Z | [Open Guide](configuration/bitlocker-windows-11-enterprise-baseline.md) |
| **Windows Autopilot Deployment Profile - District Desktops** | Windows 11 | `🟢 Assigned` | 2026-10-05T12:00:00Z | [Open Guide](configuration/windows-autopilot-deployment-profile-district-desktops.md) |
| **Draft Lab Kiosk Restrictions (Unassigned)** | Windows 11 | `🟡 Unassigned` | 2026-10-28T09:20:00Z | [Open Guide](configuration/draft-lab-kiosk-restrictions-unassigned.md) |

### Mobile & Managed Applications

- **Documentation**: [Microsoft Learn: App Management](https://learn.microsoft.com/en-us/mem/intune/apps/app-management)
- **Total Policies**: `1`

| Policy Name | Platform | Status | Last Modified | View Document |
| :--- | :--- | :--- | :--- | :--- |
| **Company Portal App (Offline)** | Windows | `🟢 Assigned` | 2026-09-18T15:30:00Z | [Open Guide](apps/company-portal-app-offline.md) |


---

## Direct Links & Resources

- [Microsoft Intune Admin Center](https://intune.microsoft.com)
- [Microsoft Learn Intune Documentation](https://learn.microsoft.com/en-us/mem/intune/)
- [Microsoft Graph API Overview](https://learn.microsoft.com/en-us/graph/overview)
- [Playwright Web Automation](https://playwright.dev/)
- [ASD-STE100 Specification](https://asd-ste100.org/)

---
*Documentation generated automatically by [intune-visual-doc](https://github.com/leifdavisson/intune_docs).*