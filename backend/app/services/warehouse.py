"""冷库管理业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "warehouse"
REQUIRED_FIELDS = ["冷库编码", "冷库名称", "库区温区"]
OPTIONAL_FIELDS = ["设定温度", "库容吨位", "责任人"]
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS
STATUS_ORDER = ["已启用", "检修中", "已停用"]
ACTION_RULES = {"启用冷库": "已启用", "安排检修": "检修中", "停用冷库": "已停用"}
NEGATIVE_ACTIONS = ["停用冷库"]

# 允许的状态流转：作业中的冷库必须先安排检修，检修通过后才能停用，
# 已停用冷库不能直接停用或继续作业。
TRANSITIONS: dict[str, dict[str, str]] = {
    "已启用": {"安排检修": "检修中"},
    "检修中": {"启用冷库": "已启用", "停用冷库": "已停用"},
    "已停用": {"启用冷库": "已启用"},
}


class BusinessRuleError(Exception):
    """业务规则不允许继续执行：参数可纠正，调用方应当原样提示并允许重试。"""


class WarehouseService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("冷库编码", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def recent_logs(self, entry_id: int, limit: int = 20) -> list[dict[str, Any]]:
        """读取单条冷库档案最近的动作留痕，最新的排前面。"""
        logs = [log for log in store.action_logs(MODULE) if log.get("entry_id") == entry_id]
        return list(reversed(logs[-limit:]))

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        # 必填字段与选填字段都保留在冷库档案上，不让档案出现缺列。
        for field in ALL_FIELDS:
            value = values.get(field)
            entry[field] = str(value).strip() if value is not None and str(value).strip() else None
        entry["status"] = STATUS_ORDER[0]
        entry["启用状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        *,
        request_id: str | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            raise BusinessRuleError(f"冷库档案 {entry_id} 不存在或已归档")
        action = str(action or "").strip()
        if action not in ACTION_RULES:
            raise BusinessRuleError(f"动作「{action}」不属于冷库管理可执行范围")
        target = ACTION_RULES[action]

        logs = store.action_logs(MODULE)
        # 幂等兜底：重复提交同一请求时直接回放上次结果，不再产生第二条记录。
        if request_id:
            for log in reversed(logs):
                if log.get("request_id") == request_id:
                    return entry, f"该请求已处理，无需重复提交：{log.get('message')}"

        current = str(entry.get("status") or "")
        if current == target:
            # 状态未发生变化的重复动作不记日志，避免残留重复的停用记录。
            raise BusinessRuleError(f"冷库当前已是「{current}」状态，请勿重复{action}")
        allowed = TRANSITIONS.get(current, {})
        if action not in allowed:
            reason = self._block_reason(current, action)
            raise BusinessRuleError(f"{reason}，冷库仍为「{current}」状态，本次{action}未生效")

        entry["status"] = target
        entry["启用状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        message = f"冷库档案已{action}"
        logs.append({
            "id": max((int(log.get("id", 0)) for log in logs), default=0) + 1,
            "entry_id": entry_id,
            "action": action,
            "from_status": current,
            "to_status": target,
            "request_id": request_id,
            "message": message,
            "operated_at": datetime.now().isoformat(timespec="seconds"),
        })
        return entry, message

    def _block_reason(self, current: str, action: str) -> str:
        if action == "停用冷库":
            if current == "已启用":
                return "冷库正在作业，不能直接停用，请先安排检修，检修通过后再停用"
            if current == "已停用":
                return "冷库已停用，无需再次停用"
        if action == "启用冷库" and current == "已启用":
            return "冷库已在启用中，无需重复启用"
        if action == "安排检修" and current == "检修中":
            return "冷库已在检修中，无需重复安排"
        return f"冷库当前为「{current}」状态，不允许直接{action}"
