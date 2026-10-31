"""
Resolver for Entra ID (Azure AD) Group IDs and assignment targets.
"""

from typing import Dict, Any, List, Optional
from .client import GraphClient


class TargetResolver:
    def __init__(self, client: GraphClient):
        self.client = client
        self.group_cache: Dict[str, str] = {}

    def resolve_group_name(self, group_id: str) -> str:
        """Resolve an Entra ID group GUID to its friendly display name."""
        if not group_id:
            return "Unknown"
        if group_id in self.group_cache:
            return self.group_cache[group_id]

        try:
            res = self.client.get(f"/groups/{group_id}?$select=id,displayName")
            name = res.get("displayName", group_id)
            self.group_cache[group_id] = name
            return name
        except Exception:
            # Fall back to GUID if permission missing or group deleted
            self.group_cache[group_id] = group_id
            return group_id

    def parse_assignments(self, assignments_raw: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Parse Graph assignment objects into friendly target dictionaries:
        Returns list of {"type": "Included"|"Excluded", "target": "All Devices" | Group Name}
        """
        results = []
        if not assignments_raw:
            return results

        for assign in assignments_raw:
            target = assign.get("target", {})
            odata_type = target.get("@odata.type", "")

            # Default to Included unless exclusion target
            assign_type = "Excluded" if "exclusion" in odata_type.lower() else "Included"

            if "allDevicesAssignmentTarget" in odata_type:
                target_name = "All Devices"
            elif "allLicensedUsersAssignmentTarget" in odata_type:
                target_name = "All Users"
            elif "groupAssignmentTarget" in odata_type:
                gid = target.get("groupId")
                target_name = self.resolve_group_name(gid) if gid else "Unknown Group"
            else:
                target_name = odata_type.split(".")[-1] if odata_type else "Custom Target"

            results.append({
                "type": assign_type,
                "target": target_name,
            })

        return results
