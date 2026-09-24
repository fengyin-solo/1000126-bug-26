"""冷库管理兜底规则回归测试。

覆盖：参数为空、停用正在作业的冷库、重复提交三类问题。
直接用标准库运行：python -m unittest discover backend/tests
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


class WarehouseGuardrailsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_empty_required_field_is_rejected_with_message(self) -> None:
        # 库区温区为空：不能静默，要明确缺哪一项
        resp = self.client.post(
            "/api/warehouse",
            json={"values": {"冷库编码": "W-EMPTY", "冷库名称": "空温区库", "库区温区": "   "},
                  "client_token": "empty-1"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["ok"])
        self.assertIn("库区温区", body["message"])

    def test_missing_payload_values_are_rejected(self) -> None:
        # 整个 values 都没给：同样要可读报错
        resp = self.client.post("/api/warehouse", json={})
        self.assertFalse(resp.json()["ok"])

    def test_active_warehouse_cannot_be_stopped(self) -> None:
        created = self.client.post(
            "/api/warehouse",
            json={"values": {"冷库编码": "W-ACTIVE", "冷库名称": "作业中库", "库区温区": "冷冻区"},
                  "client_token": "active-1"},
        ).json()
        entry_id = created["entry"]["id"]

        # 正在作业（已启用）的冷库直接停用：ok 必须为 False
        resp = self.client.post(
            f"/api/warehouse/{entry_id}/actions",
            json={"values": {"action": "停用冷库"}, "client_token": "active-stop-1"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["ok"])
        self.assertIn("正在作业", body["message"])

        # 档案状态没有被错误地改成已停用
        detail = self.client.get(f"/api/warehouse/{entry_id}").json()
        self.assertEqual(detail["status"], "已启用")

        # 先检修再停用：允许
        self.client.post(
            f"/api/warehouse/{entry_id}/actions",
            json={"values": {"action": "安排检修"}, "client_token": "active-repair"},
        )
        stopped = self.client.post(
            f"/api/warehouse/{entry_id}/actions",
            json={"values": {"action": "停用冷库"}, "client_token": "active-stop-2"},
        ).json()
        self.assertTrue(stopped["ok"])
        self.assertEqual(stopped["entry"]["status"], "已停用")

    def test_repeated_stop_does_not_duplicate(self) -> None:
        before = self.client.get("/api/warehouse", params={"size": 200}).json()["total"]
        # 同令牌连续点两次停用被拦的作业中库
        for _ in range(2):
            resp = self.client.post(
                "/api/warehouse/1/actions",
                json={"values": {"action": "停用冷库"}, "client_token": "dup-stop"},
            )
            self.assertFalse(resp.json()["ok"])
        after = self.client.get("/api/warehouse", params={"size": 200}).json()["total"]
        self.assertEqual(before, after)

    def test_repeated_create_with_same_token_inserts_once(self) -> None:
        payload = {"values": {"冷库编码": "W-DUP", "冷库名称": "重复库", "库区温区": "冷藏区"}}
        first = self.client.post("/api/warehouse", json={**payload, "client_token": "dup-create"})
        second = self.client.post("/api/warehouse", json={**payload, "client_token": "dup-create"})
        self.assertTrue(first.json()["ok"])
        # 同令牌回放首次结果，不新增第二条
        self.assertEqual(first.json()["entry"]["id"], second.json()["entry"]["id"])

        # 同编码、不同令牌也要被业务规则拦下
        third = self.client.post(
            "/api/warehouse",
            json={"values": {"冷库编码": "W-DUP", "冷库名称": "另一份", "库区温区": "冷冻区"},
                  "client_token": "dup-create-2"},
        )
        self.assertFalse(third.json()["ok"])

        matches = self.client.get("/api/warehouse", params={"keyword": "W-DUP"}).json()["total"]
        self.assertEqual(matches, 1)

    def test_empty_action_is_rejected(self) -> None:
        resp = self.client.post("/api/warehouse/1/actions", json={"values": {}})
        self.assertFalse(resp.json()["ok"])

    def test_seed_archives_preserved(self) -> None:
        # 原有冷库档案一条都不能少
        for code in ("WARE-0001", "WARE-0002", "WARE-0003"):
            self.assertEqual(
                self.client.get("/api/warehouse", params={"keyword": code}).json()["total"],
                1,
            )

    def test_missing_detail_returns_404_with_message(self) -> None:
        resp = self.client.get("/api/warehouse/9999")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("不存在或已归档", resp.json()["detail"])


if __name__ == "__main__":
    unittest.main()
