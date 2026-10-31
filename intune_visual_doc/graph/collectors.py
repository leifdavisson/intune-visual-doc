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
        try:
            raw = self.client.get_all_pages(
                "/deviceManagement/deviceCompliancePolicies?$expand=assignments",
                beta=True
            )
        except Exception as e:
            print(f"[Warning] Failed to fetch Device Compliance policies: {e}")
            return []
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
        try:
            raw = self.client.get_all_pages(
                "/deviceManagement/configurationPolicies?$expand=settings,assignments",
                beta=True
            )
        except Exception as e:
            print(f"[Warning] Failed to fetch Settings Catalog policies: {e}")
            return []
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
        try:
            raw = self.client.get_all_pages(
                "/deviceManagement/deviceConfigurations?$expand=assignments",
                beta=True
            )
        except Exception as e:
            print(f"[Warning] Failed to fetch Device Configuration templates: {e}")
            return []
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

    def get_endpoint_security_policies(self) -> List[Dict[str, Any]]:
        """Fetch Endpoint Security Policies (Antivirus, Disk Encryption, Firewall, EDR) via Intents."""
        try:
            raw = self.client.get_all_pages(
                "/deviceManagement/intents?$expand=settings,assignments",
                beta=True
            )
        except Exception:
            return []

        policies = []
        for intent in raw:
            assignments = self.resolver.parse_assignments(intent.get("assignments", []))
            settings = []
            for s in intent.get("settings", []):
                val = s.get("value")
                def_id = s.get("definitionId", "Setting")
                name = def_id.split(".")[-1] if "." in def_id else def_id
                settings.append({
                    "name": name,
                    "value": str(val) if val is not None else "Configured",
                })
            policies.append({
                "id": intent.get("id"),
                "name": intent.get("displayName", "Unnamed Endpoint Security Policy"),
                "description": intent.get("description", ""),
                "category": "configuration",
                "category_label": "Endpoint Security",
                "platform": "Windows 10/11",
                "last_modified": intent.get("lastModifiedDateTime"),
                "created": intent.get("createdDateTime"),
                "assignments": assignments,
                "settings": settings,
                "raw": intent,
            })
        return policies

    def get_device_management_scripts(self) -> List[Dict[str, Any]]:
        """Fetch PowerShell and Shell Device Management Scripts."""
        try:
            raw = self.client.get_all_pages(
                "/deviceManagement/deviceManagementScripts?$expand=assignments",
                beta=True
            )
        except Exception:
            return []

        policies = []
        for s in raw:
            assignments = self.resolver.parse_assignments(s.get("assignments", []))
            settings = [
                {"name": "RunAsAccount", "value": s.get("runAsAccount", "system")},
                {"name": "EnforceSignatureCheck", "value": str(s.get("enforceSignatureCheck", False))},
                {"name": "RunAs32Bit", "value": str(s.get("runAs32Bit", False))},
                {"name": "FileName", "value": s.get("fileName", "script.ps1")},
            ]
            policies.append({
                "id": s.get("id"),
                "name": s.get("displayName", "Unnamed Device Script"),
                "description": s.get("description", ""),
                "category": "configuration",
                "category_label": "Device Script",
                "platform": "Windows / macOS",
                "last_modified": s.get("lastModifiedDateTime"),
                "created": s.get("createdDateTime"),
                "assignments": assignments,
                "settings": settings,
                "raw": s,
            })
        return policies

    def get_device_enrollment_configurations(self) -> List[Dict[str, Any]]:
        """Fetch Device Enrollment and Autopilot configurations."""
        try:
            raw = self.client.get_all_pages(
                "/deviceManagement/deviceEnrollmentConfigurations?$expand=assignments",
                beta=True
            )
        except Exception:
            return []

        policies = []
        for e in raw:
            assignments = self.resolver.parse_assignments(e.get("assignments", []))
            settings = []
            for k, v in e.items():
                if k not in {"id", "displayName", "description", "createdDateTime", "lastModifiedDateTime",
                             "version", "assignments", "@odata.type", "@odata.context"} and v is not None and not isinstance(v, (list, dict)):
                    settings.append({"name": k, "value": str(v)})
            policies.append({
                "id": e.get("id"),
                "name": e.get("displayName", "Enrollment Configuration"),
                "description": e.get("description", ""),
                "category": "configuration",
                "category_label": "Enrollment Configuration",
                "platform": e.get("@odata.type", "").replace("#microsoft.graph.", ""),
                "last_modified": e.get("lastModifiedDateTime"),
                "created": e.get("createdDateTime"),
                "assignments": assignments,
                "settings": settings,
                "raw": e,
            })
        return policies

    def get_managed_apps(self) -> List[Dict[str, Any]]:
        """Fetch Managed Mobile Applications, assignments, dependencies, and supersedences."""
        try:
            raw = self.client.get_all_pages(
                "/deviceAppManagement/mobileApps?$expand=assignments,relationships",
                beta=True
            )
        except Exception as e:
            print(f"[Warning] Failed to fetch Managed Applications: {e}")
            return []
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
