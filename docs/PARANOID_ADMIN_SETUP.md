# Paranoid Administrator Manual Setup Guide

[Back to Main README](../README.md)

This guide is for administrators who refuse automated scripts.
You can configure read-only identities manually in Microsoft web portals.
No automation script will touch your tenant.
Every step uses least-privilege principles.

> [!WARNING]
> **TENANT WRITE NOTICE**:
> Identity creation is the **ONLY** time you configure tenant objects for `intune-visual-doc`.
> All documentation, diff, and audit routines are strictly **100% READ-ONLY**.

---

## 1. Security Invariants and Least-Privilege Rules

Paranoid administrators must verify these security boundaries:

1. **Zero Write Permissions**:
   Never assign `.ReadWrite` permissions or `.Create` permissions to any documentation identity.

2. **Zero Directory Admin Roles for the Service Principal**:
   The application registration requires application permissions only.
   Do not assign `Global Administrator` or `Intune Administrator` roles to the service principal.

3. **Restricted Screenshot Service Account**:
   Assign the built-in [Intune RBAC](https://learn.microsoft.com/en-us/mem/intune/fundamentals/role-based-access-control) role named `Read Only Operator`.
   Assign the Microsoft Entra role `Directory Readers`.
   This combination blocks all administrative write actions in the portal.

---

## 2. Manual Setup for Unattended Service Principal (`intunedoc-reader-spn`)

Follow these click paths in the [Microsoft Entra admin center](https://entra.microsoft.com):

### Step 2.1: Register the Application
1. Sign in to the [Microsoft Entra admin center](https://entra.microsoft.com) as an Application Administrator or Global Administrator.
2. Select **Identity** > **Applications** > **App registrations**.
3. Select **+ New registration**.
4. Enter `intunedoc-reader-spn` for the name.
5. Select **Accounts in this organizational directory only (Single tenant)**.
6. Leave **Redirect URI** blank.
7. Select **Register**.

### Step 2.2: Note Tenant and Application Identifiers
1. From the application **Overview** blade, copy these values:
   - **Application (client) ID**: A GUID identifying your application.
   - **Directory (tenant) ID**: A GUID identifying your Microsoft Entra tenant.

### Step 2.3: Assign Microsoft Graph Read-Only Permissions
1. Under **Manage**, select **API permissions**.
2. Select **+ Add a permission**.
3. Select **Microsoft Graph**.
4. Select **Application permissions** (not Delegated permissions).
5. Search for and check each permission from the [Microsoft Graph Permissions Reference](https://learn.microsoft.com/en-us/graph/permissions-reference):
   - `DeviceManagementConfiguration.Read.All`
   - `DeviceManagementApps.Read.All`
   - `DeviceManagementServiceConfig.Read.All`
   - `Directory.Read.All`
   - `AuditLog.Read.All`
   - `DeviceManagementRBAC.Read.All`
   - `DeviceManagementManagedDevices.Read.All`
6. Select **Add permissions**.
7. Select **Grant admin consent for [Your Organization]**.
8. Confirm with **Yes**.
9. Verify that every permission displays a green check mark in the **Status** column.

### Step 2.4: Create Client Secret
1. Under **Manage**, select **Certificates & secrets**.
2. Under the **Client secrets** tab, select **+ New client secret**.
3. Enter `intunedoc-reader-key` in the **Description** box.
4. Select an expiration window (for example, 180 days or 365 days).
5. Select **Add**.
6. Copy the string in the **Value** column immediately. Store this string securely.

### Step 2.5: Paranoid Audit Check for the SPN
1. Navigate to **Identity** > **Applications** > **Enterprise applications**.
2. Search for `intunedoc-reader-spn` and open it.
3. Select **Permissions**.
4. Verify that every permission ends with `.Read.All`.
5. Verify that no `.ReadWrite` permissions exist.
6. Select **Roles and administrators**.
7. Verify that no directory roles are assigned to the application.

---

## 3. Manual Setup for Screenshot Service Account (`svc-intunedoc-screenshot`)

Follow these click paths to configure the interactive visual capture user:

### Step 3.1: Create the Cloud User
1. In the [Microsoft Entra admin center](https://entra.microsoft.com), select **Identity** > **Users** > **All users**.
2. Select **+ New user** > **Create new user**.
3. Enter `svc-intunedoc-screenshot` for the User principal name.
4. Enter `IntuneDoc Screenshot Service` for the Display name.
5. Generate a strong temporary password.
6. Under **Assignments**, select **Add role**.
7. Select **Directory Readers** (read-only Entra role).
8. Select **Review + create**, then select **Create**.

### Step 3.2: Assign Intune License
1. Select the new user `svc-intunedoc-screenshot`.
2. Under **Manage**, select **Licenses**.
3. Select **+ Assignments**.
4. Assign a **Microsoft Intune Plan 1** license (or M365 Business Premium / E3 / E5).
5. Select **Save**.

### Step 3.3: Assign Intune Read Only Operator RBAC Role
1. Sign in to the [Microsoft Intune admin center](https://intune.microsoft.com).
2. Select **Tenant administration** > **Roles** > **All roles**.
3. Select the built-in role named **Read Only Operator**.
4. Select **Assignments** > **+ Assign**.
5. Set assignment name to `IntuneDoc-Screenshot-Read-Only`.
6. Select **Next**.
7. Under **Admin Groups**, select **Add groups** or **Add users**.
8. Add the user `svc-intunedoc-screenshot`.
9. Select **Next**.
10. Under **Scope (Groups)**, select **All Devices** and **All Users**.
11. Select **Next**, then select **Save**.

### Step 3.4: Paranoid Audit Check for the Screenshot User
1. Verify that the account does not have `Global Administrator` or `Intune Administrator`.
2. Open an InPrivate or Incognito browser window.
3. Sign in to `https://intune.microsoft.com` as `svc-intunedoc-screenshot`.
4. Navigate to any policy blade (for example, **Devices** > **Compliance**).
5. Verify that all **Create**, **Edit**, **Delete**, and **Save** buttons are hidden or disabled.
6. Complete initial password setup and MFA registration.

---

## 4. Connect Credentials to Intune Visual Doc

Save your manual credentials into the secure local vault:

```bash
intunedoc setup
```
Select option 4: **Enter & Test Stored SPN Credentials in .auth/config.json**.
Enter your Tenant ID, Client ID, and Client Secret.
The tool validates read access against Microsoft Graph immediately.
It writes `.auth/config.json` with strict `0600` permissions.

You can verify the connection at any time:
```bash
intunedoc setup --test-spn
```

---
*Document standard: [ASD-STE100](https://asd-ste100.org/) | License: [GNU AGPLv3](https://www.gnu.org/licenses/agpl-3.0).*
