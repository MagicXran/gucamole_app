"""
Shared script dispatch status evaluation.
"""

from __future__ import annotations

from typing import Any


SCRIPT_STATUS_META = {
    "ready": {"label": "脚本可调度", "tone": "ok"},
    "script_target_not_found": {"label": "未配置脚本", "tone": "warn"},
    "worker_group_empty": {"label": "无节点", "tone": "warn"},
    "executor_unavailable": {"label": "执行器不匹配", "tone": "warn"},
    "no_active_workers": {"label": "无活跃节点", "tone": "warn"},
    "software_issue": {"label": "缺软件", "tone": "warn"},
    "software_inventory_missing": {"label": "待探测", "tone": "warn"},
}


def worker_inventory(node: dict[str, Any]) -> dict[str, Any]:
    runtime_state = dict(node.get("runtime_state_json") or {})
    capabilities = dict(node.get("capabilities_json") or {})
    inventory = runtime_state.get("software_inventory")
    if isinstance(inventory, dict) and inventory:
        return inventory
    inventory = capabilities.get("software_inventory")
    if isinstance(inventory, dict):
        return inventory
    return {}


def evaluate_script_dispatch_target(
    *,
    target: dict[str, Any] | None,
    worker_nodes: list[dict[str, Any]],
    requested_runtime_id: int,
) -> dict[str, Any]:
    if not target:
        meta = SCRIPT_STATUS_META["script_target_not_found"]
        return {
            "requested_runtime_id": requested_runtime_id,
            "worker_group_id": 0,
            "executor_key": "",
            "script_profile_key": None,
            "software_adapter_key": None,
            "software_display_name": "脚本任务",
            "total_nodes": 0,
            "active_nodes": 0,
            "ready_active_nodes": 0,
            "is_schedulable": False,
            "script_status_code": "script_target_not_found",
            "script_status_label": meta["label"],
            "script_status_tone": meta["tone"],
            "summary": "0/0 活跃节点满足 脚本任务",
            "reasons": [{"code": "script_target_not_found", "message": "script mode is not configured for this app"}],
            "worker_nodes": [],
        }

    runtime_config = dict(target.get("runtime_config_json") or {})
    adapter_key = str(runtime_config.get("software_adapter_key") or runtime_config.get("script_profile_key") or "").strip()
    software_name = str(runtime_config.get("software_display_name") or adapter_key or "脚本任务")
    executor_key = str(target.get("executor_key") or "")

    executor_nodes = [
        node for node in worker_nodes
        if executor_key in set(node.get("supported_executor_keys_json") or [])
    ]
    active_nodes = [node for node in executor_nodes if str(node.get("status") or "") == "active"]
    ready_active_nodes = []
    aggregated_issues: dict[str, int] = {}
    worker_items = []

    for node in executor_nodes:
        inventory = worker_inventory(node)
        software_state = inventory.get(adapter_key) if adapter_key else None
        issues = list((software_state or {}).get("issues") or [])
        for issue in issues:
            aggregated_issues[issue] = aggregated_issues.get(issue, 0) + 1
        software_ready = True if not adapter_key else bool((software_state or {}).get("ready"))
        if str(node.get("status") or "") == "active" and software_ready:
            ready_active_nodes.append(node)
        worker_items.append({
            "display_name": str(node.get("display_name") or ""),
            "status": str(node.get("status") or ""),
            "software_ready": software_ready,
            "issues": issues,
        })

    reasons = []
    if not worker_nodes:
        reasons.append({"code": "worker_group_empty", "message": "当前节点组没有任何 Worker 节点"})
    elif not executor_nodes:
        reasons.append({"code": "executor_unavailable", "message": f"当前节点组没有节点支持执行器 {executor_key}"})
    elif not active_nodes:
        reasons.append({"code": "no_active_workers", "message": "当前节点组没有活跃 Worker 节点"})
    elif not ready_active_nodes:
        if aggregated_issues:
            for issue, count in sorted(aggregated_issues.items()):
                reasons.append({"code": "software_issue", "message": f"{issue}（{count} 个节点）"})
        else:
            reasons.append({"code": "software_inventory_missing", "message": f"当前活跃节点未就绪，无法调度 {software_name}"})

    primary_code = "ready" if len(ready_active_nodes) > 0 else (reasons[0]["code"] if reasons else "software_inventory_missing")
    meta = SCRIPT_STATUS_META.get(primary_code, {"label": "脚本不可调度", "tone": "warn"})
    return {
        "requested_runtime_id": int(target.get("requested_runtime_id") or requested_runtime_id),
        "worker_group_id": int(target.get("worker_group_id") or 0),
        "executor_key": executor_key,
        "script_profile_key": runtime_config.get("script_profile_key"),
        "software_adapter_key": adapter_key or None,
        "software_display_name": software_name,
        "total_nodes": len(worker_nodes),
        "active_nodes": len(active_nodes),
        "ready_active_nodes": len(ready_active_nodes),
        "is_schedulable": len(ready_active_nodes) > 0,
        "script_status_code": primary_code,
        "script_status_label": meta["label"],
        "script_status_tone": meta["tone"],
        "summary": f"{len(ready_active_nodes)}/{len(active_nodes)} 活跃节点满足 {software_name}",
        "reasons": reasons,
        "worker_nodes": worker_items,
    }
