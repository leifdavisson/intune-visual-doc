"""
Collectors for Microsoft Intune settings, policies, and audit logs.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from .client import GraphClient
from .resolver import TargetResolver


class PolicyCollector:
    def __init__(self, client: GraphClient):
        self.client = client
        self.resolver = TargetResolver(client)

    def get_compliance_policies(self) -> List[Dict[str, Any]]:
        """Fetch all Device Compliance Policies with assignments."""
        raw = self.client.get_all_pages(
            "/deviceManagement/deviceCompliancePolicies?$expand=assignments",
            beta=True
        )
        policies = []
        for p in raw:
            assignments = self.resolver.parse_assignments(p.get("assignments", []))
            policies.append({
                "id": p.get("id"),
                "name": p.get("displayName", "Unnamed Policy"),
                "description": p.get("description", ""),
                "category": "compliance",
                "category_label": "Device Compliance",
                "platform": p.get("@odata.type", "").replace("#microsoft.graph.", "").replace("CompliancePolicy", ""),
                "last_modified": p.get("lastModifiedDateTime"),
                "created": p.get("createdDateTime"),
                "version": p.get("version"),
                "assignments": assignments,
                "settings": self._flatten_compliance_settings(p),
                "raw": p,
            })
        return policies

    def get_configuration_policies(self) -> List[Dict[str, Any]]:
        """Fetch Settings Catalog policies with full settings expansion."""
        raw = self.client.get_all_pages(
            "/deviceManagement/configurationPolicies?$expand=settings,assignments",
            beta=True
        )
        policies = []
        for p in raw:
            assignments = self.resolver.parse_assignments(p.get("assignments", []))
            settings = self._flatten_settings_catalog(p.get("settings", []))
            policies.append({
                "id": p.get("id"),
                "name": p.get("name", "Unnamed Configuration"),
                "description": p.get("description", ""),
                "category": "configuration",
                "category_label": "Settings Catalog",
                "platform": p.get("platforms", "windows10"),
                "last_modified": p.get("lastModifiedDateTime"),
                "created": p.get("createdDateTime"),
                "assignments": assignments,
                "settings": settings,
                "raw": p,
            })
        return policies

    def get_device_configurations(self) -> List[Dict[str, Any]]:
        """Fetch legacy template Device Configurations with assignments."""
        raw = self.client.get_all_pages(
            "/deviceManagement/deviceConfigurations?$expand=assignments",
            beta=True
        )
        policies = []
        for p in raw:
            assignments = self.resolver.parse_assignments(p.get("assignments", []))
            policies.append({
                "id": p.get("id"),
                "name": p.get("displayName", "Unnamed Template"),
                "description": p.get("description", ""),
                "category": "configuration",
                "category_label": "Configuration Template",
                "platform": p.get("@odata.type", "").replace("#microsoft.graph.", "").replace("Configuration", ""),
                "last_modified": p.get("lastModifiedDateTime"),
                "created": p.get("createdDateTime"),
                "version": p.get("version"),
                "assignments": assignments,
                "settings": self._flatten_template_settings(p),
                "raw": p,
            })
        return policies

    def get_managed_apps(self) -> List[Dict[str, Any]]:
        """Fetch Managed Mobile Applications, assignments, dependencies, and supersedences."""
        raw = self.client.get_all_pages(
            "/deviceAppManagement/mobileApps?$expand=assignments,relationships",
            beta=True
        )
        apps = []
        for a in raw:
            assignments = self.resolver.parse_assignments(a.get("assignments", []))
            
            # Parse app supersedences and dependencies if present
            relationships = a.get("relationships", [])
            superseded_apps = []
            dependent_apps = []
            for r in relationships:
                r_type = r.get("@odata.type", "")
                target_app_id = r.get("targetId", "")
                if "supersedence" in r_type.lower():
                    superseded_apps.append(target_app_id)
                elif "dependency" in r_type.lower():
                    dependent_apps.append(target_app_id)

            settings = [
                {"name": "Publisher", "value": a.get("publisher", "Not specified")},
                {"name": "App Version", "value": a.get("displayVersion", "N/A")},
                {"name": "Install Context", "value": a.get("installCommandLine", "Device/User")},
            ]
            if superseded_apps:
                settings.append({"name": "Supersedes Apps", "value": ", ".join(superseded_apps)})
            if dependent_apps:
                settings.append({"name": "App Dependencies", "value": ", ".join(dependent_apps)})

            apps.append({
                "id": a.get("id"),
                "name": a.get("displayName", "Unnamed Application"),
                "description": a.get("description", ""),
                "category": "apps",
                "category_label": "Mobile Application",
                "publisher": a.get("publisher", ""),
                "last_modified": a.get("lastModifiedDateTime"),
                "created": a.get("createdDateTime"),
                "assignments": assignments,
                "settings": settings,
                "raw": a,
            })
        return apps

    def get_audit_logs(self, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch Intune Administrative Audit Events from the past N days."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        filter_query = f"activityDateTime ge {cutoff}"
        try:
            raw = self.client.get_all_pages(
                f"/deviceManagement/auditEvents?$filter={filter_query}&$orderby=activityDateTime desc",
                beta=True
            )
        except Exception:
            # Fall back without filter if server orderby/filter is restricted
            raw = self.client.get_all_pages("/deviceManagement/auditEvents", beta=True)

        events = []
        for e in raw:
            actor = e.get("actor", {})
            user_principal = actor.get("userPrincipalName") or actor.get("displayName") or "System / Service"
            resources = e.get("resources", [])
            target_name = resources[0].get("displayName", "Tenant Resource") if resources else "Tenant"

            events.append({
                "id": e.get("id"),
                "timestamp": e.get("activityDateTime"),
                "actor": user_principal,
                "action": e.get("activityType", "Update"),
                "category": e.get("category", "Device Configuration"),
                "target": target_name,
                "raw": e,
            })
        return events

    def _flatten_settings_catalog(self, settings_raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Flatten nested Settings Catalog definition instances into rows."""
        items = []
        for s in settings_raw:
            instance = s.get("settingInstance", {})
            def_id = instance.get("settingDefinitionId", "Setting")
            val = instance.get("choiceSettingValue", {}).get("value") or \
                  instance.get("simpleSettingValue", {}).get("value") or \
                  instance.get("booleanSettingValue", {}).get("value")

            name = def_id.split("_")[-1] if "_" in def_id else def_id
            items.append({
                "name": name,
                "full_definition": def_id,
                "value": str(val) if val is not None else "Configured",
            })
        return items

    def _flatten_compliance_settings(self, policy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract configured compliance requirements."""
        items = []
        ignore_keys = {"id", "displayName", "description", "createdDateTime", "lastModifiedDateTime",
                       "version", "assignments", "@odata.type", "@odata.context"}
        for k, v in policy.items():
            if k not in ignore_keys and v is not None:
                items.append({
                    "name": k,
                    "value": str(v),
                })
        return items

    def _flatten_template_settings(self, policy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract configured device configuration template values."""
        items = []
        ignore_keys = {"id", "displayName", "description", "createdDateTime", "lastModifiedDateTime",
                       "version", "assignments", "@odata.type", "@odata.context"}
        for k, v in policy.items():
            if k not in ignore_keys and v is not None and not isinstance(v, (list, dict)):
                items.append({
                    "name": k,
                    "value": str(v),
                })
        return items
