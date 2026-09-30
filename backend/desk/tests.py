import json

from django.test import Client, TestCase

from desk.auth_utils import hash_password
from desk.models import OffsetSubmission, PresetChangeLog, ScreenPreset, User


class ScreeningPresetAcceptanceTest(TestCase):
    """按刀号筛查预设的验收流程：甲乙各一笔、预设过滤、清空回整表、删预设留流水。"""

    def setUp(self):
        self.machinist = User.objects.create(
            username="machinist",
            role=User.Role.MACHINIST,
            password=hash_password("machine123456"),
        )
        self.auditor = User.objects.create(
            username="auditor",
            role=User.Role.AUDITOR,
            password=hash_password("audit123456"),
        )
        self.client = Client()

    def login(self, username, password):
        res = self.client.post(
            "/api/auth/login",
            data=json.dumps({"username": username, "password": password}),
            content_type="application/json",
        )
        assert res.status_code == 200, res.content
        return res.json()["token"]

    def auth(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def submit(self, token, tool_code, offset_um):
        res = self.client.post(
            "/api/submissions",
            data=json.dumps({"tool_code": tool_code, "offset_um": offset_um}),
            content_type="application/json",
            **self.auth(token),
        )
        assert res.status_code == 200, res.content
        return res.json()

    def test_screening_preset_flow(self):
        machinist_token = self.login("machinist", "machine123456")
        auditor_token = self.login("auditor", "audit123456")

        # 先各交甲刀乙刀各一笔
        self.submit(machinist_token, "甲01", 5)
        self.submit(machinist_token, "乙01", 20)

        # 未建预设前整表两笔都在
        res = self.client.get("/api/submissions", **self.auth(machinist_token))
        self.assertEqual(len(res.json()), 2)

        # 复核员也能新建命名预设
        res = self.client.post(
            "/api/presets",
            data=json.dumps({"name": "乙字头", "tool_prefix": "乙"}),
            content_type="application/json",
            **self.auth(auditor_token),
        )
        self.assertEqual(res.status_code, 200, res.content)

        # 操作员建字头为甲的预设
        res = self.client.post(
            "/api/presets",
            data=json.dumps({"name": "甲字头", "tool_prefix": "甲"}),
            content_type="application/json",
            **self.auth(machinist_token),
        )
        self.assertEqual(res.status_code, 200, res.content)
        preset_jia_id = res.json()["id"]

        # 预设列表两人都能点名看到
        res = self.client.get("/api/presets", **self.auth(auditor_token))
        names = {p["name"] for p in res.json()}
        self.assertEqual(names, {"甲字头", "乙字头"})

        # 甲列表应只剩甲刀（服务端过滤，不是前端藏行）
        res = self.client.get(
            "/api/submissions", {"tool_prefix": "甲"}, **self.auth(machinist_token)
        )
        rows = res.json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tool_code"], "甲01")

        # 复核员用同一接口同一参数，结果一致（同源）
        res = self.client.get(
            "/api/submissions", {"tool_prefix": "甲"}, **self.auth(auditor_token)
        )
        self.assertEqual([r["tool_code"] for r in res.json()], ["甲01"])

        # 清空条件（不传字头）后两笔都应露脸
        res = self.client.get("/api/submissions", **self.auth(machinist_token))
        self.assertEqual({r["tool_code"] for r in res.json()}, {"甲01", "乙01"})
        res = self.client.get(
            "/api/submissions", {"tool_prefix": ""}, **self.auth(machinist_token)
        )
        self.assertEqual(len(res.json()), 2)

        # 复核员不得抹掉别人的预设
        res = self.client.delete(
            f"/api/presets/{preset_jia_id}", **self.auth(auditor_token)
        )
        self.assertEqual(res.status_code, 403)
        self.assertTrue(ScreenPreset.objects.filter(pk=preset_jia_id).exists())

        # 创建人删掉预设甲
        res = self.client.delete(
            f"/api/presets/{preset_jia_id}", **self.auth(machinist_token)
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(ScreenPreset.objects.filter(pk=preset_jia_id).exists())

        # 流水须留痕迹：新建与删除各一条，称呼与字头快照都在
        logs = list(
            PresetChangeLog.objects.filter(preset_name="甲字头").order_by("id")
        )
        self.assertEqual([log.action for log in logs], ["create", "delete"])
        self.assertTrue(all(log.tool_prefix == "甲" for log in logs))
        self.assertEqual(logs[0].actor, self.machinist)
        self.assertEqual(logs[1].actor, self.machinist)

        # 流水接口同样查得到
        res = self.client.get("/api/preset-logs", **self.auth(auditor_token))
        jia_logs = [log for log in res.json() if log["preset_name"] == "甲字头"]
        self.assertEqual({log["action"] for log in jia_logs}, {"create", "delete"})

    def test_preset_validation(self):
        token = self.login("machinist", "machine123456")

        # 称呼与字头都不能为空
        for body in (
            {"name": "", "tool_prefix": "甲"},
            {"name": "空字头", "tool_prefix": "  "},
        ):
            res = self.client.post(
                "/api/presets",
                data=json.dumps(body),
                content_type="application/json",
                **self.auth(token),
            )
            self.assertEqual(res.status_code, 400, body)

        # 称呼唯一
        self.client.post(
            "/api/presets",
            data=json.dumps({"name": "甲字头", "tool_prefix": "甲"}),
            content_type="application/json",
            **self.auth(token),
        )
        res = self.client.post(
            "/api/presets",
            data=json.dumps({"name": "甲字头", "tool_prefix": "乙"}),
            content_type="application/json",
            **self.auth(token),
        )
        self.assertEqual(res.status_code, 409)

        # 删除不存在的预设
        res = self.client.delete("/api/presets/9999", **self.auth(token))
        self.assertEqual(res.status_code, 404)

        # 未登录一律 401
        self.assertEqual(self.client.get("/api/presets").status_code, 401)
        self.assertEqual(self.client.get("/api/preset-logs").status_code, 401)
        self.assertEqual(
            self.client.get("/api/submissions", {"tool_prefix": "甲"}).status_code,
            401,
        )

    def test_delete_preset_and_log_are_atomic(self):
        """删预设与写流水同事务：流水写入失败则预设一并回滚。"""
        from unittest import mock

        from desk import services

        preset = ScreenPreset.objects.create(
            name="甲字头", tool_prefix="甲", created_by=self.machinist
        )
        with mock.patch.object(
            services.PresetChangeLog.objects,
            "create",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                services.delete_preset(user=self.machinist, preset=preset)
        self.assertTrue(ScreenPreset.objects.filter(pk=preset.pk).exists())

    def test_auditor_still_cannot_submit_offset(self):
        token = self.login("auditor", "audit123456")
        res = self.client.post(
            "/api/submissions",
            data=json.dumps({"tool_code": "甲02", "offset_um": 3}),
            content_type="application/json",
            **self.auth(token),
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(OffsetSubmission.objects.count(), 0)
