"""
Settings catalog and policy flattening utilities for Microsoft Intune.
Licensed under GNU AGPLv3.
"""

from typing import Dict, Any, List, Optional


def is_effective_assignment(assignment: Dict[str, Any]) -> bool:
    """
    Check if an assignment target represents an active inclusion rather than an exclusion.
    """
    if not isinstance(assignment, dict):
        return False

    target = assignment.get("target") or {}
    if not isinstance(target, dict):
        # Fallback if assignment structure is flattened
        a_type = str(assignment.get("type", "")).lower()
        return "exclu" not in a_type

    target_type = str(target.get("@odata.type", "")).lower()
    if "exclusion" in target_type:
        return False

    # Also check if target dictionary or assignment has explicit exclusion flag
    if assignment.get("type") == "Excluded":
        return False

    return True


def flatten_settings_catalog(settings_raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Recursively flatten nested Settings Catalog definition instances and child collections.
    Preserves full definition IDs (e.g. device_vendor_msft_laps_policies_backupdirectory).
    """
    items: List[Dict[str, Any]] = []

    def _extract_instance(instance: Dict[str, Any]) -> None:
        if not instance or not isinstance(instance, dict):
            return

        def_id = (
            instance.get("settingDefinitionId")
            or instance.get("definitionId")
            or instance.get("id")
            or "Setting"
        )
        choice_obj = instance.get("choiceSettingValue") or {}
        simple_obj = instance.get("simpleSettingValue") or {}
        bool_obj = instance.get("booleanSettingValue") or {}

        val = (
            choice_obj.get("value")
            if choice_obj.get("value") is not None
            else (
                simple_obj.get("value")
                if simple_obj.get("value") is not None
                else bool_obj.get("value")
            )
        )

        if val is None:
            simple_coll = instance.get("simpleSettingCollectionValue") or []
            if simple_coll:
                val = ", ".join(str(x.get("value")) for x in simple_coll if x.get("value") is not None)

        if val is None:
            choice_coll = instance.get("choiceSettingCollectionValue") or []
            if choice_coll:
                val = ", ".join(str(x.get("value")) for x in choice_coll if x.get("value") is not None)

        val_str = str(val) if val is not None else "Configured"
        prefix = f"{def_id}_"
        if val_str.startswith(prefix) and len(val_str) > len(prefix):
            val_str = val_str[len(prefix):]

        name = def_id.split("_")[-1] if "_" in def_id else def_id
        items.append({
            "name": name,
            "full_definition": def_id,
            "value": val_str,
        })

        for child in choice_obj.get("children") or []:
            _extract_instance(child)

        for grp in instance.get("groupSettingCollectionValue") or []:
            for child in grp.get("children") or []:
                _extract_instance(child)

    for s in settings_raw:
        inst = s.get("settingInstance") if "settingInstance" in s else s
        _extract_instance(inst)

    return items


def flatten_compliance_settings(policy: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract configured compliance requirements from a device compliance policy.
    """
    items = []
    ignored = {
        "id", "displayName", "description", "createdDateTime", "lastModifiedDateTime",
        "version", "@odata.type", "@odata.context", "roleScopeTagIds", "assignments",
        "scheduledActionsForRule", "deviceStatusOverview", "deviceSettingStateSummaries",
    }
    for k, v in policy.items():
        if k in ignored or v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            items.append({
                "name": k,
                "full_definition": f"compliance_{k}",
                "value": str(v),
            })
    return items
