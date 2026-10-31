#!/usr/bin/env bash
# ==============================================================================
# Setup Read-Only Unattended Service Principal for intune-visual-doc
# License: GNU AGPLv3
#
# NOTICE: This script makes changes to your Microsoft Entra tenant.
# All permissions granted are STRICTLY READ-ONLY for documentation and backup.
# ==============================================================================
set -euo pipefail

APP_NAME="intunedoc-reader-spn"
GRAPH_APP_ID="00000003-0000-0000-c000-000000000000"

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
    APP_ID=$(az ad app create --display-name "$APP_NAME" \
        --sign-in-audience AzureADMyOrg \
        --query appId -o tsv)
    echo "Created App ID: $APP_ID"
else
    echo "Found existing App ID: $APP_ID"
fi

# 2. Add Microsoft Graph Read-Only Application Permissions
echo "Step 2: Assigning Microsoft Graph Read-Only Application Permissions..."
az ad app permission add \
    --id "$APP_ID" \
    --api "$GRAPH_APP_ID" \
    --api-permissions dc377aa6-52d8-4e23-b271-2a7ae04cedf3=Role e40edd52-0699-41e5-8ab8-33e15001d640=Role 2f51be20-0bb4-4fed-bf7b-db946066c75e=Role 7ab7862c-4c0f-45da-866c-5e49c950552f=Role b0afded3-358c-46d8-8326-63365cf57f70=Role 4544c501-f5f2-441d-89e5-ea751d81b83d=Role 313fd57c-2656-430d-9b5f-0e136690736e=Role

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
SECRET_VALUE=$(az ad app credential reset \
    --id "$APP_ID" \
    --display-name "intunedoc-auto-key" \
    --years 1 \
    --query password -o tsv)

# 5. Grant Admin Consent
echo "Step 5: Granting Tenant Admin Consent..."
az ad app permission admin-consent --id "$APP_ID"

echo ""
echo "=============================================================================="
echo "🎉 Setup Complete! Save these credentials into .auth/config.json or .env"
echo "=============================================================================="
echo "AZURE_TENANT_ID="$TENANT_ID""
echo "AZURE_CLIENT_ID="$APP_ID""
echo "AZURE_CLIENT_SECRET="$SECRET_VALUE""
echo "=============================================================================="
