#!/usr/bin/env python3
"""
第二阶段 QA 回归脚本（QA-201 ~ QA-204）

执行方式（仓库根目录）:
  ./.venv/bin/python tools/phase2_qa_regression.py

输出:
  docs/phase2-qa-regression-report.md
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


@dataclass
class CaseResult:
    qa_id: str
    case_id: str
    title: str
    status: str
    duration_ms: float
    detail: str


CASE_CATALOG: list[tuple[str, str, str]] = [
    ("QA-201", "QA-201-1", "小程序日历链路通过"),
    ("QA-201", "QA-201-2", "小程序连续打卡链路通过"),
    ("QA-201", "QA-201-3", "小程序周报链路通过"),
    ("QA-201", "QA-201-4", "小程序收藏链路通过"),
    ("QA-202", "QA-202-1", "后端日历聚合口径一致"),
    ("QA-202", "QA-202-2", "后端周报聚合口径一致"),
    ("QA-202", "QA-202-3", "收藏接口权限与越权保护"),
    ("QA-202", "QA-202-4", "配置守卫语义一致"),
    ("QA-203", "QA-203-1", "PC 趋势摘要回看可用"),
    ("QA-203", "QA-203-2", "PC 周报回看可用"),
    ("QA-203", "QA-203-3", "PC 收藏回看可用"),
    ("QA-204", "QA-204-1", "日历聚合接口耗时达标"),
    ("QA-204", "QA-204-2", "周报聚合接口耗时达标"),
    ("QA-204", "QA-204-3", "收藏写接口耗时达标"),
    ("QA-204", "QA-204-4", "留存接口失败不阻塞主分析"),
]


class Phase2QARegressionRunner:
    def __init__(self, repo_root: Path, report_path: Path, run_qas: set[str]) -> None:
        self.repo_root = repo_root
        self.report_path = report_path
        self.run_qas = run_qas

        self.workspace = Path(tempfile.mkdtemp(prefix="phase2_qa_"))
        self.history_store_path = self.workspace / "history_store.json"
        self.pc_cache_dir = self.workspace / "pc_cache"
        self.pc_cache_dir.mkdir(parents=True, exist_ok=True)

        self.api_root = self.repo_root / "services" / "wechat-api"
        self.pc_root = self.repo_root / "apps" / "pc"

        self.client: Any = None
        self.pc_logic_cls: Any = None
        self.results: list[CaseResult] = []
        self.metrics: dict[str, float] = {}

    @staticmethod
    def _ensure(condition: bool, message: str) -> None:
        if not condition:
            raise AssertionError(message)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    @staticmethod
    def _extract_error_detail(response_json: Any) -> str:
        if isinstance(response_json, dict):
            detail = response_json.get("detail")
            if isinstance(detail, str):
                return detail
            if isinstance(detail, list):
                return json.dumps(detail, ensure_ascii=False)
        return json.dumps(response_json, ensure_ascii=False)

    def _set_test_env(self) -> None:
        os.environ["HISTORY_STORE_PATH"] = str(self.history_store_path)
        os.environ["HISTORY_RETENTION_DAYS"] = "180"
        os.environ["SPEECH_STT_PROVIDER"] = "mock"
        os.environ["SPEECH_STT_MOCK_TEXT"] = "今天情绪有起伏，但我会慢慢调整"
        os.environ["VOICE_REQUIRE_TRANSCRIPT"] = "0"
        os.environ["RETENTION_SERVICE_ENABLED"] = "on"
        os.environ["RETENTION_WEEKLY_REPORT_ENABLED"] = "on"
        os.environ["RETENTION_FAVORITES_ENABLED"] = "on"

    def _import_backend(self) -> None:
        sys.path.insert(0, str(self.api_root))
        from fastapi.testclient import TestClient  # type: ignore
        from app.main import app  # type: ignore

        self.client = TestClient(app)

    def _import_pc_module(self) -> None:
        if self.pc_logic_cls is not None:
            return
        pc_main_path = self.pc_root / "main.py"
        if str(self.pc_root) not in sys.path:
            sys.path.insert(0, str(self.pc_root))
        spec = importlib.util.spec_from_file_location("phase2_qa_pc_main_module", str(pc_main_path))
        self._ensure(spec is not None and spec.loader is not None, "加载 PC main.py 失败。")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        # 关闭 TTS 线程，避免回归过程不稳定。
        module.speak_text_in_thread = lambda *args, **kwargs: None
        self.pc_logic_cls = module.AppLogic

    def _headers(self, user_id: str) -> dict[str, str]:
        return {"X-EC-USER-ID": user_id}

    def _post_analyze(self, user_id: str, text: str) -> Any:
        payload = {
            "input_modes": ["text"],
            "text": text,
            "client": {"platform": "mp-weixin", "version": "0.2.0", "user_id": user_id},
        }
        return self.client.post("/api/analyze", json=payload, headers=self._headers(user_id))

    def _clear_retention_state(self, user_id: str) -> None:
        self.client.delete("/api/history", headers=self._headers(user_id))
        self.client.delete("/api/favorites", headers=self._headers(user_id))
        self.client.delete("/api/retention/weekly-reports", headers=self._headers(user_id))

    def _read_store(self) -> dict[str, Any]:
        if not self.history_store_path.exists():
            return {"version": 2, "users": {}}
        return json.loads(self.history_store_path.read_text(encoding="utf-8"))

    def _write_store(self, payload: dict[str, Any]) -> None:
        self.history_store_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _inject_yesterday_checkin(self, user_id: str) -> None:
        payload = self._read_store()
        users = payload.setdefault("users", {})
        bucket = users.setdefault(user_id, {})
        retention = bucket.setdefault("retention", {})
        checkins = retention.setdefault("checkins", {})
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        if yesterday not in checkins:
            checkins[yesterday] = {
                "day": yesterday,
                "request_id": f"ana_{yesterday.replace('-', '')}",
                "analyzed_at": f"{yesterday}T08:00:00Z",
                "primary_emotion_code": "neutral",
                "primary_emotion_label": "平静",
                "input_modes": ["text"],
                "analyses_count": 1,
                "updated_at": self._now_iso(),
            }
        self._write_store(payload)

    def _build_pc_logic_with_backend_bridge(self, user_id: str) -> Any:
        self._import_pc_module()
        os.environ["PC_RETENTION_API_BASE"] = "http://phase2-qa.local"
        os.environ["PC_RETENTION_USER_ID"] = user_id
        logic = self.pc_logic_cls()
        logic.cache_dir = str(self.pc_cache_dir)
        logic.history_cache_file = str(self.pc_cache_dir / f"{user_id}_history_summary.json")
        logic._ensure_history_cache_ready()
        logic.retention_api_base = "http://phase2-qa.local"
        logic.retention_user_id = user_id

        def bridge(path: str, query: dict[str, Any] | None = None) -> dict[str, Any]:
            response = self.client.get(path, params=query or {}, headers=self._headers(user_id))
            if response.status_code >= 400:
                raise RuntimeError(self._extract_error_detail(response.json()))
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("后端接口返回格式异常。")
            return payload

        logic._retention_api_get_json = bridge
        return logic

    def _measure_api_latency(
        self,
        call: Callable[[], Any],
        validator: Callable[[Any], None],
        rounds: int = 5,
    ) -> list[float]:
        latencies: list[float] = []
        for _ in range(rounds):
            start = time.perf_counter()
            response = call()
            elapsed = time.perf_counter() - start
            validator(response)
            latencies.append(elapsed)
        return latencies

    def _run_case(self, qa_id: str, case_id: str, title: str, fn: Callable[[], None]) -> None:
        start = time.perf_counter()
        try:
            fn()
            status = "PASS"
            detail = "PASS"
        except AssertionError as exc:
            status = "FAIL"
            detail = f"ASSERT: {exc}"
        except Exception as exc:  # pragma: no cover
            status = "FAIL"
            detail = f"ERROR: {type(exc).__name__}: {exc}"
        duration_ms = (time.perf_counter() - start) * 1000.0
        self.results.append(
            CaseResult(
                qa_id=qa_id,
                case_id=case_id,
                title=title,
                status=status,
                duration_ms=duration_ms,
                detail=detail,
            ),
        )

    def _qa_201(self) -> None:
        def case_calendar_chain() -> None:
            user = "qa2-mini-calendar"
            self._clear_retention_state(user)
            resp = self._post_analyze(user, "今天有些紧张，但我在慢慢整理思路。")
            self._ensure(resp.status_code == 200, f"analyze 失败: {resp.text}")

            calendar_resp = self.client.get("/api/retention/calendar", headers=self._headers(user))
            self._ensure(calendar_resp.status_code == 200, f"calendar 失败: {calendar_resp.text}")
            body = calendar_resp.json()
            items = body.get("items", [])
            self._ensure(len(items) == int(body.get("total_days", 0)), "日历 item 数量与 total_days 不一致。")
            self._ensure(bool(body.get("checked_today")), "分析后今日打卡状态未更新。")
            self._ensure(any(bool(item.get("has_checkin")) for item in items), "日历未出现打卡记录。")
            for item in items:
                self._ensure(item.get("analyzed_at") is None, "日历脱敏字段 analyzed_at 应为空。")

        def case_streak_chain() -> None:
            user = "qa2-mini-streak"
            self._clear_retention_state(user)
            resp = self._post_analyze(user, "连续打卡验证。")
            self._ensure(resp.status_code == 200, f"analyze 失败: {resp.text}")
            self._inject_yesterday_checkin(user)

            calendar_resp = self.client.get("/api/retention/calendar", headers=self._headers(user))
            self._ensure(calendar_resp.status_code == 200, f"calendar 失败: {calendar_resp.text}")
            body = calendar_resp.json()
            self._ensure(int(body.get("current_streak", 0)) >= 2, f"current_streak 异常: {body}")
            self._ensure(int(body.get("longest_streak", 0)) >= 2, f"longest_streak 异常: {body}")

        def case_weekly_chain() -> None:
            user = "qa2-mini-weekly"
            self._clear_retention_state(user)
            resp = self._post_analyze(user, "周报聚合校验。")
            self._ensure(resp.status_code == 200, f"analyze 失败: {resp.text}")

            weekly_resp = self.client.get("/api/retention/weekly-report", headers=self._headers(user))
            self._ensure(weekly_resp.status_code == 200, f"weekly-report 失败: {weekly_resp.text}")
            body = weekly_resp.json()
            self._ensure(len(body.get("daily_digests", [])) == 7, "weekly daily_digests 长度应为 7。")
            self._ensure(bool((body.get("insight") or "").strip()), "weekly insight 为空。")
            self._ensure((body.get("source") or "").strip() in {"generated", "cache"}, "weekly source 非法。")

            week_start = body.get("week_start")
            delete_resp = self.client.delete(
                f"/api/retention/weekly-report?week_start={week_start}",
                headers=self._headers(user),
            )
            self._ensure(delete_resp.status_code == 200, f"删除周报快照失败: {delete_resp.text}")
            weekly_resp2 = self.client.get("/api/retention/weekly-report", headers=self._headers(user))
            self._ensure(weekly_resp2.status_code == 200, f"删除后重取周报失败: {weekly_resp2.text}")

        def case_favorites_chain() -> None:
            user = "qa2-mini-favorites"
            self._clear_retention_state(user)
            upsert_payload = {
                "favorite_type": "poem",
                "target_id": "poem_phase2_001",
                "title": "明月松间照，清泉石上流。",
                "subtitle": "王维",
                "content_summary": "收藏链路回归验证。",
                "request_id": "ana_qa2_favorite_001",
                "metadata": {"scene": "qa"},
            }
            upsert_resp = self.client.post("/api/favorites", json=upsert_payload, headers=self._headers(user))
            self._ensure(upsert_resp.status_code == 200, f"收藏写入失败: {upsert_resp.text}")
            upsert_body = upsert_resp.json()
            item = upsert_body.get("item", {})
            favorite_id = item.get("favorite_id")
            self._ensure(bool(favorite_id), "收藏返回缺少 favorite_id。")
            self._ensure("request_id" not in item and "metadata" not in item, "收藏查询字段未脱敏。")

            status_resp = self.client.get(
                "/api/favorites/status?favorite_type=poem&target_id=poem_phase2_001",
                headers=self._headers(user),
            )
            self._ensure(status_resp.status_code == 200, f"收藏状态查询失败: {status_resp.text}")
            self._ensure(status_resp.json().get("is_favorited") is True, "收藏状态未生效。")

            delete_resp = self.client.delete(f"/api/favorites/{favorite_id}", headers=self._headers(user))
            self._ensure(delete_resp.status_code == 200, f"删除收藏失败: {delete_resp.text}")
            clear_resp = self.client.delete("/api/favorites", headers=self._headers(user))
            self._ensure(clear_resp.status_code == 200, f"清空收藏失败: {clear_resp.text}")

        self._run_case("QA-201", "QA-201-1", "小程序日历链路通过", case_calendar_chain)
        self._run_case("QA-201", "QA-201-2", "小程序连续打卡链路通过", case_streak_chain)
        self._run_case("QA-201", "QA-201-3", "小程序周报链路通过", case_weekly_chain)
        self._run_case("QA-201", "QA-201-4", "小程序收藏链路通过", case_favorites_chain)

    def _qa_202(self) -> None:
        def case_calendar_consistency() -> None:
            user = "qa2-backend-calendar"
            self._clear_retention_state(user)
            self._post_analyze(user, "日历口径一致性样本一")
            self._inject_yesterday_checkin(user)

            resp = self.client.get("/api/retention/calendar", headers=self._headers(user))
            self._ensure(resp.status_code == 200, f"calendar 失败: {resp.text}")
            body = resp.json()
            items = body.get("items", [])
            checked_days = sum(1 for item in items if bool(item.get("has_checkin")))
            self._ensure(checked_days == int(body.get("checked_days", -1)), "checked_days 与明细聚合不一致。")
            self._ensure(int(body.get("total_days", 0)) == len(items), "total_days 与 items 长度不一致。")

        def case_weekly_consistency() -> None:
            user = "qa2-backend-weekly"
            self._clear_retention_state(user)
            self._post_analyze(user, "周报口径一致性样本一")
            self._post_analyze(user, "周报口径一致性样本二")

            resp = self.client.get("/api/retention/weekly-report", headers=self._headers(user))
            self._ensure(resp.status_code == 200, f"weekly-report 失败: {resp.text}")
            body = resp.json()
            digests = body.get("daily_digests", [])
            total_checkin_days = sum(1 for item in digests if bool(item.get("has_checkin")))
            self._ensure(total_checkin_days == int(body.get("total_checkin_days", -1)), "周报总打卡天数口径不一致。")
            for item in digests:
                self._ensure(item.get("analyzed_at") is None, "周报脱敏字段 analyzed_at 应为空。")

        def case_favorites_authz() -> None:
            user_a = "qa2-authz-a"
            user_b = "qa2-authz-b"
            self._clear_retention_state(user_a)
            self._clear_retention_state(user_b)

            upsert_resp = self.client.post(
                "/api/favorites",
                json={
                    "favorite_type": "poem",
                    "target_id": "poem_authz_001",
                    "title": "authz",
                    "subtitle": "case",
                    "content_summary": "authz case",
                },
                headers=self._headers(user_a),
            )
            self._ensure(upsert_resp.status_code == 200, f"user_a 收藏写入失败: {upsert_resp.text}")
            favorite_id = upsert_resp.json().get("item", {}).get("favorite_id", "")
            self._ensure(bool(favorite_id), "user_a 返回 favorite_id 为空。")

            cross_delete = self.client.delete(f"/api/favorites/{favorite_id}", headers=self._headers(user_b))
            self._ensure(cross_delete.status_code == 404, f"跨用户删除应失败: {cross_delete.text}")

            status_a = self.client.get(
                "/api/favorites/status?favorite_type=poem&target_id=poem_authz_001",
                headers=self._headers(user_a),
            )
            self._ensure(status_a.status_code == 200 and status_a.json().get("is_favorited") is True, "user_a 收藏被误删。")

        def case_config_guards() -> None:
            user = "qa2-config-guard"
            env_keys = [
                "RETENTION_SERVICE_ENABLED",
                "RETENTION_FAVORITES_ENABLED",
            ]
            env_backup = {key: os.environ.get(key) for key in env_keys}
            try:
                os.environ["RETENTION_SERVICE_ENABLED"] = "off"
                resp = self.client.get("/api/retention/calendar", headers=self._headers(user))
                self._ensure(resp.status_code == 503, f"RETENTION_SERVICE_ENABLED=off 未生效: {resp.text}")

                os.environ["RETENTION_SERVICE_ENABLED"] = "on"
                os.environ["RETENTION_FAVORITES_ENABLED"] = "off"
                resp2 = self.client.get("/api/favorites", headers=self._headers(user))
                self._ensure(resp2.status_code == 503, f"RETENTION_FAVORITES_ENABLED=off 未生效: {resp2.text}")

                os.environ["RETENTION_FAVORITES_ENABLED"] = "on"
                write_off = self.client.put(
                    "/api/retention/write-settings",
                    json={"write_enabled": False},
                    headers=self._headers(user),
                )
                self._ensure(write_off.status_code == 200, f"write-settings 关闭失败: {write_off.text}")
                blocked = self.client.post(
                    "/api/favorites",
                    json={
                        "favorite_type": "poem",
                        "target_id": "poem_guard_001",
                        "title": "guard",
                    },
                    headers=self._headers(user),
                )
                self._ensure(blocked.status_code == 409, f"write 关闭后收藏写入应失败: {blocked.text}")

                write_on = self.client.put(
                    "/api/retention/write-settings",
                    json={"write_enabled": True},
                    headers=self._headers(user),
                )
                self._ensure(write_on.status_code == 200, f"write-settings 开启失败: {write_on.text}")
                allowed = self.client.post(
                    "/api/favorites",
                    json={
                        "favorite_type": "poem",
                        "target_id": "poem_guard_001",
                        "title": "guard",
                    },
                    headers=self._headers(user),
                )
                self._ensure(allowed.status_code == 200, f"write 开启后收藏写入仍失败: {allowed.text}")
            finally:
                for key, value in env_backup.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

        self._run_case("QA-202", "QA-202-1", "后端日历聚合口径一致", case_calendar_consistency)
        self._run_case("QA-202", "QA-202-2", "后端周报聚合口径一致", case_weekly_consistency)
        self._run_case("QA-202", "QA-202-3", "收藏接口权限与越权保护", case_favorites_authz)
        self._run_case("QA-202", "QA-202-4", "配置守卫语义一致", case_config_guards)

    def _qa_203(self) -> None:
        def seed_user_data(user_id: str) -> None:
            self._clear_retention_state(user_id)
            self._post_analyze(user_id, "PC 留存回看样本一。")
            self._post_analyze(user_id, "PC 留存回看样本二。")
            self.client.post(
                "/api/favorites",
                json={
                    "favorite_type": "poem",
                    "target_id": "poem_pc_qa_001",
                    "title": "春风又绿江南岸",
                    "subtitle": "王安石",
                    "content_summary": "PC 收藏回看样本。",
                },
                headers=self._headers(user_id),
            )
            self.client.post(
                "/api/favorites",
                json={
                    "favorite_type": "guochao",
                    "target_id": "guochao_pc_qa_001",
                    "title": "国潮伙伴",
                    "subtitle": "平静陪伴",
                    "content_summary": "PC 收藏回看样本。",
                },
                headers=self._headers(user_id),
            )

        def case_pc_trend_panel() -> None:
            user = "qa2-pc-trend"
            seed_user_data(user)
            logic = self._build_pc_logic_with_backend_bridge(user)
            text, status = logic.refresh_retention_trend_panel()
            self._ensure("最近 7 天" in text and "最近 30 天" in text, f"趋势面板内容异常: {text}")
            self._ensure("后端留存接口" in status, f"趋势面板来源异常: {status}")

        def case_pc_weekly_panel() -> None:
            user = "qa2-pc-weekly"
            seed_user_data(user)
            logic = self._build_pc_logic_with_backend_bridge(user)
            text, status = logic.refresh_weekly_report_panel(0)
            self._ensure("周区间：" in text, f"周报面板内容异常: {text}")
            self._ensure("后端周报接口" in status, f"周报面板来源异常: {status}")
            next_offset, next_text, next_status = logic.shift_weekly_report_offset(0, -1)
            self._ensure(next_offset == -1, f"周报切周偏移异常: {next_offset}")
            self._ensure(isinstance(next_text, str) and isinstance(next_status, str), "周报切周返回结构异常。")

        def case_pc_favorites_panel() -> None:
            user = "qa2-pc-favorites"
            seed_user_data(user)
            logic = self._build_pc_logic_with_backend_bridge(user)
            _choices, detail, status = logic.refresh_favorites_panel("all", None)
            self._ensure("后端接口" in status, f"收藏面板来源异常: {status}")
            self._ensure(len(logic._favorites_cache_by_id) >= 1, "收藏面板未加载到收藏数据。")
            first_id = next(iter(logic._favorites_cache_by_id.keys()))
            detail_text = logic.show_favorite_detail(first_id)
            self._ensure("类型：" in detail_text and "favorite_id：" in detail_text, f"收藏详情内容异常: {detail_text}")

        self._run_case("QA-203", "QA-203-1", "PC 趋势摘要回看可用", case_pc_trend_panel)
        self._run_case("QA-203", "QA-203-2", "PC 周报回看可用", case_pc_weekly_panel)
        self._run_case("QA-203", "QA-203-3", "PC 收藏回看可用", case_pc_favorites_panel)

    def _qa_204(self) -> None:
        def case_calendar_latency() -> None:
            user = "qa2-perf-calendar"
            self._clear_retention_state(user)
            self._post_analyze(user, "日历性能回归样本。")
            latencies = self._measure_api_latency(
                call=lambda: self.client.get("/api/retention/calendar", headers=self._headers(user)),
                validator=lambda resp: self._ensure(resp.status_code == 200, f"calendar 请求失败: {resp.text}"),
                rounds=5,
            )
            max_latency = max(latencies)
            self.metrics["calendar_latency_max_s"] = round(max_latency, 4)
            self._ensure(max_latency <= 0.8, f"日历聚合接口耗时超标: {max_latency:.4f}s > 0.8s")

        def case_weekly_latency() -> None:
            user = "qa2-perf-weekly"
            self._clear_retention_state(user)
            self._post_analyze(user, "周报性能回归样本。")
            latencies = self._measure_api_latency(
                call=lambda: self.client.get("/api/retention/weekly-report", headers=self._headers(user)),
                validator=lambda resp: self._ensure(resp.status_code == 200, f"weekly 请求失败: {resp.text}"),
                rounds=5,
            )
            max_latency = max(latencies)
            self.metrics["weekly_report_latency_max_s"] = round(max_latency, 4)
            self._ensure(max_latency <= 1.2, f"周报聚合接口耗时超标: {max_latency:.4f}s > 1.2s")

        def case_favorite_write_latency() -> None:
            user = "qa2-perf-favorite"
            self._clear_retention_state(user)

            def write_once(index: int) -> Any:
                return self.client.post(
                    "/api/favorites",
                    json={
                        "favorite_type": "poem",
                        "target_id": f"poem_perf_{index}",
                        "title": "性能测试收藏",
                        "subtitle": "perf",
                        "content_summary": "favorite write latency",
                    },
                    headers=self._headers(user),
                )

            latencies: list[float] = []
            for index in range(5):
                start = time.perf_counter()
                resp = write_once(index)
                elapsed = time.perf_counter() - start
                self._ensure(resp.status_code == 200, f"收藏写入请求失败: {resp.text}")
                latencies.append(elapsed)

            max_latency = max(latencies)
            self.metrics["favorite_write_latency_max_s"] = round(max_latency, 4)
            self._ensure(max_latency <= 0.5, f"收藏写接口耗时超标: {max_latency:.4f}s > 0.5s")

        def case_retention_failure_not_blocking_analyze() -> None:
            user = "qa2-fallback-main"
            self._clear_retention_state(user)
            backup = os.environ.get("RETENTION_SERVICE_ENABLED")
            try:
                os.environ["RETENTION_SERVICE_ENABLED"] = "off"
                retention_resp = self.client.get("/api/retention/calendar", headers=self._headers(user))
                self._ensure(retention_resp.status_code == 503, f"留存失败场景构造失败: {retention_resp.text}")

                analyze_resp = self._post_analyze(user, "留存接口失败时主分析仍应可用。")
                self._ensure(analyze_resp.status_code == 200, f"主分析被留存失败阻塞: {analyze_resp.text}")
                self.metrics["retention_fallback_ratio"] = 1.0
            finally:
                if backup is None:
                    os.environ.pop("RETENTION_SERVICE_ENABLED", None)
                else:
                    os.environ["RETENTION_SERVICE_ENABLED"] = backup

        self._run_case("QA-204", "QA-204-1", "日历聚合接口耗时达标", case_calendar_latency)
        self._run_case("QA-204", "QA-204-2", "周报聚合接口耗时达标", case_weekly_latency)
        self._run_case("QA-204", "QA-204-3", "收藏写接口耗时达标", case_favorite_write_latency)
        self._run_case("QA-204", "QA-204-4", "留存接口失败不阻塞主分析", case_retention_failure_not_blocking_analyze)

    def _mark_not_run_cases(self) -> None:
        existing_ids = {item.case_id for item in self.results}
        for qa_id, case_id, title in CASE_CATALOG:
            if case_id in existing_ids:
                continue
            self.results.append(
                CaseResult(
                    qa_id=qa_id,
                    case_id=case_id,
                    title=title,
                    status="NOT_RUN",
                    duration_ms=0.0,
                    detail="本次未执行",
                ),
            )

    @staticmethod
    def _metric_text(value: float | None) -> str:
        if value is None:
            return "待执行"
        return f"{value:.4f}"

    def _write_report(self) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        cases_sorted = sorted(self.results, key=lambda item: item.case_id)

        executed = [item for item in cases_sorted if item.status != "NOT_RUN"]
        executed_total = len(executed)
        executed_passed = sum(1 for item in executed if item.status == "PASS")
        total = len(cases_sorted)
        overall_status = "PASS" if executed_total > 0 and executed_passed == executed_total else "FAIL"
        if executed_total < total and overall_status == "PASS":
            overall_status = "PARTIAL_PASS"

        grouped: dict[str, list[CaseResult]] = {}
        for result in cases_sorted:
            grouped.setdefault(result.qa_id, []).append(result)

        lines: list[str] = []
        lines.append("# 第二阶段 QA 回归报告")
        lines.append("")
        lines.append(f"- 执行时间(UTC): `{self._now_iso()}`")
        lines.append(f"- 代码仓库: `{self.repo_root}`")
        lines.append(f"- 历史存储隔离路径: `{self.history_store_path}`")
        lines.append(
            f"- 总体结果: **{overall_status}** (`{executed_passed}/{executed_total}` 已执行通过，`{executed_total}/{total}` 已执行)"
        )
        lines.append("")
        lines.append("## 分任务汇总")
        lines.append("")
        lines.append("| QA 任务 | 通过/总数 | 结果 |")
        lines.append("|---|---:|---|")
        for qa_id in sorted(grouped.keys()):
            qa_cases = grouped[qa_id]
            qa_executed = [item for item in qa_cases if item.status != "NOT_RUN"]
            if not qa_executed:
                lines.append(f"| {qa_id} | 0/{len(qa_cases)} | NOT_RUN |")
                continue
            qa_passed = sum(1 for item in qa_executed if item.status == "PASS")
            qa_status = "PASS" if qa_passed == len(qa_executed) else "FAIL"
            lines.append(f"| {qa_id} | {qa_passed}/{len(qa_cases)} | {qa_status} |")

        lines.append("")
        lines.append("## 用例明细")
        lines.append("")
        lines.append("| 用例ID | QA | 用例 | 结果 | 耗时(ms) | 说明 |")
        lines.append("|---|---|---|---|---:|---|")
        for item in cases_sorted:
            lines.append(
                f"| {item.case_id} | {item.qa_id} | {item.title} | {item.status} | {item.duration_ms:.1f} | {item.detail} |"
            )

        lines.append("")
        lines.append("## 稳定性指标")
        lines.append("")
        lines.append(f"- `calendar_latency_max_s`: `{self._metric_text(self.metrics.get('calendar_latency_max_s'))}`")
        lines.append(f"- `weekly_report_latency_max_s`: `{self._metric_text(self.metrics.get('weekly_report_latency_max_s'))}`")
        lines.append(f"- `favorite_write_latency_max_s`: `{self._metric_text(self.metrics.get('favorite_write_latency_max_s'))}`")
        lines.append(f"- `retention_fallback_ratio`: `{self._metric_text(self.metrics.get('retention_fallback_ratio'))}`")

        self.report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run(self) -> int:
        self._set_test_env()
        self._import_backend()

        if "QA-201" in self.run_qas:
            self._qa_201()
        if "QA-202" in self.run_qas:
            self._qa_202()
        if "QA-203" in self.run_qas:
            self._qa_203()
        if "QA-204" in self.run_qas:
            self._qa_204()

        self._mark_not_run_cases()
        self._write_report()

        failures = [item for item in self.results if item.status == "FAIL"]
        return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run phase2 QA regression checks.")
    parser.add_argument(
        "--report",
        default="docs/phase2-qa-regression-report.md",
        help="Path to markdown report output.",
    )
    parser.add_argument(
        "--qas",
        default="QA-201,QA-202,QA-203,QA-204",
        help="Comma-separated QA ids to run, e.g. QA-201,QA-202",
    )
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[1]
    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = (repo_root / report_path).resolve()

    qas = {item.strip() for item in args.qas.split(",") if item.strip()}
    runner = Phase2QARegressionRunner(repo_root=repo_root, report_path=report_path, run_qas=qas)
    code = runner.run()
    print(f"phase2 qa regression exit_code={code}, report={report_path}, run_qas={sorted(qas)}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
