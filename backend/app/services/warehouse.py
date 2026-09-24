"""冷库管理业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

import threading
import time
from typing import Any

from app.store import store

MODULE = "warehouse"
REQUIRED_FIELDS = ["冷库编码", "冷库名称", "库区温区"]
STATUS_ORDER = ["已启用", "检修中", "已停用"]
ACTION_RULES = {"启用冷库": "已启用", "安排检修": "检修中", "停用冷库": "已停用"}
NEGATIVE_ACTIONS = ["停用冷库"]
# 正在作业（已启用）的冷库不允许直接停用，需先安排检修，避免作业中断货。
BLOCKED_TRANSITIONS = {("已启用", "停用冷库")}
# 幂等令牌保留时长：窗口内同令牌重复提交直接回放首次结果，不再落第二条记录。
TOKEN_TTL_SECONDS = 300


class WarehouseService:
    def __init__(self) -> None:
        # client_token -> (到期时间, 首次结果快照)，进程内防重；换库后可用唯一索引替代。
        self._tokens: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()

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

    def create_entry(
        self, values: dict[str, Any], client_token: str | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}，请补全后重新提交"

        rows = store.rows(MODULE)
        code = str(values.get("冷库编码")).strip()

        with self._lock:
            replay = self._replay_token(client_token)
            if replay is not None:
                return replay.get("entry"), replay.get("message", "请求已受理，请勿重复提交")

            # 兜底：即使前端没带令牌，相同冷库编码也不再登记第二份档案。
            duplicate = next((row for row in rows if str(row.get("冷库编码", "")).strip() == code), None)
            if duplicate is not None:
                message = f"冷库编码 {code} 已存在（档案 {duplicate.get('id')}），请勿重复登记"
                self._remember_token(client_token, {"entry": None, "message": message})
                return None, message

            entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
            entry.update({field: str(values.get(field)).strip() for field in REQUIRED_FIELDS})
            # 非必填字段有值才写入，保持原档案字段口径不变。
            for field in ["设定温度", "库容吨位", "责任人"]:
                if str(values.get(field) or "").strip():
                    entry[field] = str(values.get(field)).strip()
            entry["status"] = STATUS_ORDER[0]
            entry["pending"] = True
            entry["abnormal"] = False
            rows.append(entry)
            message = "冷库档案已登记"
            self._remember_token(client_token, {"entry": entry, "message": message})
            return entry, message

    def run_action(
        self,
        entry_id: int,
        action: str,
        client_token: str | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"冷库档案 {entry_id} 不存在或归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action or '空'}」不属于冷库管理可执行范围，请选择有效动作后重试"

        with self._lock:
            replay = self._replay_token(client_token)
            if replay is not None:
                return replay.get("entry"), replay.get("message", "请求已受理，请勿重复提交")

            target = ACTION_RULES[action]
            if target not in STATUS_ORDER:
                return None, f"目标状态「{target}」不在允许的状态序列里"

            current = str(entry.get("status", ""))
            if (current, action) in BLOCKED_TRANSITIONS:
                message = (
                    f"冷库档案 {entry_id} 正在作业（{current}），不能直接停用；"
                    "请先执行「安排检修」再停用"
                )
                # 被业务规则拦下的请求同样登记令牌，重试点击不会重复触发流转。
                self._remember_token(client_token, {"entry": None, "message": message})
                return None, message

            # 已是目标状态时幂等返回，重复点击停用不会再写一次流转。
            if current == target:
                message = f"冷库档案已是「{target}」状态，无需重复{action}"
                self._remember_token(client_token, {"entry": entry, "message": message})
                return entry, message

            entry["status"] = target
            entry["pending"] = target != STATUS_ORDER[-1]
            entry["abnormal"] = action in NEGATIVE_ACTIONS
            message = f"冷库档案已{action}"
            self._remember_token(client_token, {"entry": entry, "message": message})
            return entry, message

    # ---- 幂等令牌 ----

    def _replay_token(self, client_token: str | None) -> dict[str, Any] | None:
        if not client_token:
            return None
        record = self._tokens.get(client_token)
        if record is None:
            return None
        expires_at, snapshot = record
        if expires_at < time.monotonic():
            self._tokens.pop(client_token, None)
            return None
        return snapshot

    def _remember_token(self, client_token: str | None, snapshot: dict[str, Any]) -> None:
        if not client_token:
            return
        now = time.monotonic()
        for token, (expires_at, _) in list(self._tokens.items()):
            if expires_at < now:
                self._tokens.pop(token, None)
        self._tokens[client_token] = (now + TOKEN_TTL_SECONDS, snapshot)
