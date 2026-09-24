"""冷库管理兜底回归：参数为空、提交失败、重复提交与档案保留。

直接运行：backend/.venv/bin/python tests/test_warehouse.py
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
        # store 是进程内单例，每个用例重新导入，拿到干净的种子数据。
        import app.store as store_module

        store_module.store.__init__()
        self.client = TestClient(app)

    def test_empty_required_field_returns_400_with_message(self) -> None:
        """库区温区为空：保存不能静默无反应，要指出缺哪个字段。"""
        response = self.client.post(
            "/api/warehouse",
            json={"values": {"冷库编码": "W-X", "冷库名称": "测试库", "库区温区": "  "}},
        )
        self.assertEqual(response.status_code, 400)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "MISSING_FIELDS")
        self.assertIn("库区温区", detail["fields"])
        # 建档失败，列表不能多出记录。
        self.assertEqual(self.client.get("/api/warehouse").json()["total"], 3)

    def test_create_keeps_full_profile(self) -> None:
        """登记成功后必填、选填字段都保留，原档案字段不缺列。"""
        response = self.client.post(
            "/api/warehouse",
            json={"values": {
                "冷库编码": "W-NEW", "冷库名称": "新库", "库区温区": "冷冻区",
                "设定温度": "-18℃", "库容吨位": "500吨", "责任人": "张三",
            }},
        )
        self.assertEqual(response.status_code, 200)
        entry = response.json()["entry"]
        for field in ["冷库编码", "冷库名称", "库区温区", "设定温度", "库容吨位", "责任人"]:
            self.assertTrue(entry[field])
        self.assertEqual(entry["status"], "已启用")

    def test_cannot_disable_active_warehouse(self) -> None:
        """停用作业中(已启用)冷库必须失败，并给出可读原因；状态不能被改动。"""
        response = self.client.post(
            "/api/warehouse/1/actions", json={"values": {"action": "停用冷库"}}
        )
        self.assertEqual(response.status_code, 409)
        message = response.json()["detail"]["message"]
        self.assertIn("正在作业", message)
        self.assertIn("先安排检修", message)
        self.assertEqual(self.client.get("/api/warehouse/1").json()["status"], "已启用")

    def test_legal_disable_path_and_log(self) -> None:
        """检修中的冷库可以停用，详情里能看到留痕，原档案字段保留。"""
        response = self.client.post(
            "/api/warehouse/2/actions", json={"values": {"action": "停用冷库"}}
        )
        self.assertEqual(response.status_code, 200)
        detail = self.client.get("/api/warehouse/2").json()
        self.assertEqual(detail["status"], "已停用")
        self.assertEqual(detail["冷库编码"], "WARE-0002")
        logs = detail["动作留痕"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["from_status"], "检修中")
        self.assertEqual(logs[0]["to_status"], "已停用")

    def test_repeated_disable_without_record(self) -> None:
        """已停用再停用：业务拦下，且不残留第二条相同记录。"""
        self.client.post(
            "/api/warehouse/2/actions", json={"values": {"action": "停用冷库"}}
        )
        repeat = self.client.post(
            "/api/warehouse/2/actions", json={"values": {"action": "停用冷库"}}
        )
        self.assertEqual(repeat.status_code, 409)
        logs = self.client.get("/api/warehouse/2").json()["动作留痕"]
        self.assertEqual(len(logs), 1)

    def test_same_request_id_is_idempotent(self) -> None:
        """同一 request_id 重复提交只生效一次，留痕只有一条。"""
        body = {"values": {"action": "安排检修", "request_id": "rid-x"}}
        first = self.client.post("/api/warehouse/1/actions", json=body)
        second = self.client.post("/api/warehouse/1/actions", json=body)
        self.assertTrue(first.json()["ok"])
        self.assertTrue(second.json()["ok"])
        self.assertIn("无需重复提交", second.json()["message"])
        logs = self.client.get("/api/warehouse/1").json()["动作留痕"]
        self.assertEqual([log["request_id"] for log in logs], ["rid-x"])

    def test_export_route_not_captured_by_id(self) -> None:
        """/export 不能被 /{entry_id} 当成编号解析。"""
        response = self.client.get("/api/warehouse/export")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["module"], "warehouse")

    def test_overview_cards_are_complete(self) -> None:
        """概览卡片恒为四项（业务模块/今日新增/待处理/异常量），可正常显示零值。"""
        labels = [card["label"] for card in self.client.get("/api/overview").json()["cards"]]
        self.assertEqual(labels, ["业务模块", "今日新增", "待处理", "异常量"])

    def test_unknown_entry_actions_are_rejected(self) -> None:
        response = self.client.post(
            "/api/warehouse/999/actions", json={"values": {"action": "停用冷库"}}
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("不存在", response.json()["detail"]["message"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
