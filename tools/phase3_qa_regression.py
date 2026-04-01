#!/usr/bin/env python3
"""
第三阶段 M5 QA 回归脚本

执行方式（仓库根目录）:
  ./.venv/bin/python tools/phase3_qa_regression.py

输出:
  docs/phase3-m5-qa-regression-report.md
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
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
    ("DATA-301", "DATA-301-1", "媒体生命周期追踪与过期清理有效"),
    ("DATA-302", "DATA-302-1", "小程序域名与云环境配置口径一致"),
    ("QA-301", "QA-301-1", "古典风图池按情绪标签命中"),
    ("QA-301", "QA-301-2", "国潮风图池按触发标签命中"),
    ("QA-302", "QA-302-1", "弱网下 URL 失败可回退 file_id/本地素材"),
    ("QA-302", "QA-302-2", "风格图空池失败不阻塞主分析与邮件"),
    ("QA-303", "QA-303-1", "页面与邮件解析的静态图片来源一致"),
    ("QA-304", "QA-304-1", "拒绝授权时直接阻断"),
    ("QA-304", "QA-304-2", "超周限额时返回明确错误"),
    ("QA-304", "QA-304-3", "积分不足时返回明确错误"),
    ("QA-304", "QA-304-4", "任务失败后积分回滚且配额释放"),
]


class Phase3QARegressionRunner:
    def __init__(self, repo_root: Path, report_path: Path) -> None:
        self.repo_root = repo_root
        self.report_path = report_path
        self.workspace = Path(tempfile.mkdtemp(prefix="phase3_qa_"))
        self.api_root = self.repo_root / "services" / "wechat-api"

        self.client: Any = None
        self.results: list[CaseResult] = []
        self.metrics: dict[str, Any] = {}
        self.media_generate_service: Any = None
        self.media_retention_service: Any = None
        self.points_service: Any = None
        self.quota_service: Any = None
        self.storage_service: Any = None
        self.email_service: Any = None

    @staticmethod
    def _ensure(condition: bool, message: str) -> None:
        if not condition:
            raise AssertionError(message)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    def _set_test_env(self) -> None:
        os.environ["HISTORY_STORE_PATH"] = str(self.workspace / "history_store.json")
        os.environ["MEDIA_RETENTION_STORE_PATH"] = str(self.workspace / "media_retention_store.json")
        os.environ["MEDIA_RETENTION_HOURS"] = "24"
        os.environ["MEDIA_RETENTION_MAX_ITEMS"] = "1000"
        os.environ["MEDIA_POINTS_STORE_PATH"] = str(self.workspace / "media_points_store.json")
        os.environ["MEDIA_QUOTA_STORE_PATH"] = str(self.workspace / "media_quota_store.json")
        os.environ["MEDIA_GEN_DEFAULT_POINTS"] = "12"
        os.environ["MEDIA_GEN_PROVIDER"] = "local_mock"
        os.environ["MEDIA_GEN_PROVIDER_MAX_RETRIES"] = "0"
        os.environ["MEDIA_GEN_PROVIDER_RETRY_BACKOFF_MS"] = "0"
        os.environ["MEDIA_GEN_REQUIRE_CONSENT"] = "0"
        os.environ["MEDIA_GEN_ENABLE_WEEKLY_QUOTA"] = "0"
        os.environ["MEDIA_GEN_ENABLE_POINTS"] = "0"
        os.environ["WECHAT_CLOUDBASE_ENV"] = "prod-9gok8bmyd517976f"

    def _import_backend(self) -> None:
        if str(self.api_root) not in sys.path:
            sys.path.insert(0, str(self.api_root))

        from fastapi.testclient import TestClient  # type: ignore
        from app.main import app  # type: ignore
        import app.services.email_service as email_service  # type: ignore
        import app.services.media_generate_service as media_generate_service  # type: ignore
        import app.services.media_retention_service as media_retention_service  # type: ignore
        import app.services.points_service as points_service  # type: ignore
        import app.services.quota_service as quota_service  # type: ignore
        import app.services.storage_service as storage_service  # type: ignore

        self.client = TestClient(app)
        self.email_service = email_service
        self.media_generate_service = media_generate_service
        self.media_retention_service = media_retention_service
        self.points_service = points_service
        self.quota_service = quota_service
        self.storage_service = storage_service

    def _headers(self, user_id: str) -> dict[str, str]:
        return {"x-openid": user_id}

    def _reset_media_generate_state(self) -> None:
        self.media_generate_service._TASKS.clear()
        self.media_generate_service._TASK_TOKEN_INDEX.clear()

    def _reset_point_and_quota_stores(self) -> None:
        for name in ("media_points_store.json", "media_quota_store.json"):
            (self.workspace / name).unlink(missing_ok=True)

    def _set_pool_env(self, *, classical: list[dict[str, Any]] | None = None, guochao: list[dict[str, Any]] | None = None) -> None:
        os.environ["MEDIA_GEN_STATIC_POOL_CLASSICAL_JSON"] = json.dumps(classical or [], ensure_ascii=False)
        os.environ["MEDIA_GEN_STATIC_POOL_GUOCHAO_JSON"] = json.dumps(guochao or [], ensure_ascii=False)
        os.environ["MEDIA_GEN_STATIC_POOL_TECH_JSON"] = "[]"
        os.environ["MEDIA_GEN_STATIC_POOL_COMMON_JSON"] = "[]"
        os.environ["MEDIA_GEN_STATIC_POOL_CLASSICAL"] = ""
        os.environ["MEDIA_GEN_STATIC_POOL_GUOCHAO"] = ""
        os.environ["MEDIA_GEN_STATIC_POOL_TECH"] = ""
        os.environ["MEDIA_GEN_STATIC_POOL_COMMON"] = ""

    def _poll_media_task(self, user_id: str, task_id: str, *, timeout_sec: float = 5.0) -> dict[str, Any]:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            response = self.client.get(f"/api/media-generate/{task_id}", headers=self._headers(user_id))
            self._ensure(response.status_code == 200, f"查询风格图任务失败: {response.text}")
            payload = response.json()
            status = str(payload.get("status") or "")
            if status in {"succeeded", "failed"}:
                return payload
            time.sleep(0.05)
        raise AssertionError(f"风格图任务超时未结束: {task_id}")

    def _create_media_task(self, user_id: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        response = self.client.post("/api/media-generate", json=payload, headers=self._headers(user_id))
        body = response.json()
        return response.status_code, body

    def _post_analyze(self, user_id: str, text: str) -> dict[str, Any]:
        response = self.client.post(
            "/api/analyze",
            json={
                "input_modes": ["text"],
                "text": text,
                "client": {"platform": "mp-weixin", "version": "0.3.0", "user_id": user_id},
            },
            headers=self._headers(user_id),
        )
        self._ensure(response.status_code == 200, f"analyze 失败: {response.text}")
        return response.json()

    def _run_case(self, qa_id: str, case_id: str, title: str, fn: Callable[[], None]) -> None:
        started = time.perf_counter()
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

        duration_ms = (time.perf_counter() - started) * 1000.0
        self.results.append(
            CaseResult(
                qa_id=qa_id,
                case_id=case_id,
                title=title,
                status=status,
                duration_ms=duration_ms,
                detail=detail,
            )
        )

    def _run_data_cases(self) -> None:
        def case_media_retention_cleanup() -> None:
            store_path = Path(os.environ["MEDIA_RETENTION_STORE_PATH"])
            store_path.unlink(missing_ok=True)

            added = self.media_retention_service.record_cloud_file_ids(
                [
                    "cloud://prod-xxx.bucket/images/stage3_image_1.jpg",
                    "cloud://prod-xxx.bucket/audio/stage3_voice_1.wav",
                ],
                source="phase3_qa",
            )
            self._ensure(added == 2, f"新增追踪数量异常: {added}")
            payload = json.loads(store_path.read_text(encoding="utf-8"))
            self._ensure(len(payload.get("items", [])) == 2, "媒体追踪存储未写入 2 条记录。")

            expired_at = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat(timespec="seconds").replace(
                "+00:00",
                "Z",
            )
            for item in payload.get("items", []):
                item["tracked_at"] = expired_at
            store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            original_delete = self.media_retention_service.delete_cloud_file_ids
            try:
                self.media_retention_service.delete_cloud_file_ids = lambda ids: {  # type: ignore[assignment]
                    "deleted_ids": list(ids),
                    "failed_ids": [],
                }
                outcome = self.media_retention_service.cleanup_expired_media()
            finally:
                self.media_retention_service.delete_cloud_file_ids = original_delete  # type: ignore[assignment]

            self._ensure(outcome.get("expired") == 2, f"过期媒体识别异常: {outcome}")
            self._ensure(outcome.get("deleted") == 2, f"过期媒体删除异常: {outcome}")
            final_payload = json.loads(store_path.read_text(encoding="utf-8"))
            self._ensure(len(final_payload.get("items", [])) == 0, "过期媒体删除后仍有残留。")

        def case_domain_config_consistency() -> None:
            config_path = self.repo_root / "apps" / "wechat-mini" / "config" / "index.js"
            config_text = config_path.read_text(encoding="utf-8")

            def extract(name: str) -> str:
                for raw_line in config_text.splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("//"):
                        continue
                    match = re.search(rf"{name}:\s*\"([^\"]+)\"", line)
                    if match:
                        return match.group(1).strip()
                return ""

            api_base = extract("apiBaseUrl")
            cloud_env = extract("cloudEnv")
            container_env = extract("containerEnv")
            container_service = extract("containerService")

            self._ensure(api_base.startswith("https://"), f"apiBaseUrl 非 https: {api_base}")
            self._ensure("tcloudbase.com" in api_base, f"apiBaseUrl 非云托管域名: {api_base}")
            self._ensure(cloud_env and cloud_env == container_env, "cloudEnv 与 containerEnv 不一致。")
            self._ensure(container_service == "emotion-culture-api", f"containerService 异常: {container_service}")

            doc_text = (self.repo_root / "docs" / "wechat-mini-frontend-dev.md").read_text(encoding="utf-8")
            self._ensure("no `request` legal-domain configuration is required" in doc_text, "域名策略文档未同步。")
            self.metrics["api_base_url"] = api_base
            self.metrics["cloud_env"] = cloud_env

        self._run_case("DATA-301", "DATA-301-1", "媒体生命周期追踪与过期清理有效", case_media_retention_cleanup)
        self._run_case("DATA-302", "DATA-302-1", "小程序域名与云环境配置口径一致", case_domain_config_consistency)

    def _run_qa_301(self) -> None:
        def case_classical_match() -> None:
            self._reset_media_generate_state()
            self._reset_point_and_quota_stores()
            os.environ["MEDIA_GEN_REQUIRE_CONSENT"] = "0"
            os.environ["MEDIA_GEN_ENABLE_WEEKLY_QUOTA"] = "0"
            os.environ["MEDIA_GEN_ENABLE_POINTS"] = "0"
            self._set_pool_env(
                classical=[
                    {
                        "id": "classical_joy",
                        "url": "https://cdn.example.com/classical_joy.jpg",
                        "style": "classical",
                        "emotion_tags": ["joyful", "开心"],
                        "weight": 9,
                        "active": True,
                        "updated_at": "2026-04-01T00:00:00Z",
                    },
                    {
                        "id": "classical_sad",
                        "url": "https://cdn.example.com/classical_sad.jpg",
                        "style": "classical",
                        "emotion_tags": ["sad", "难过", "低落"],
                        "weight": 9,
                        "active": True,
                        "updated_at": "2026-04-01T00:00:00Z",
                    },
                ]
            )

            status_code, created = self._create_media_task(
                "phase3-qa-classical",
                {
                    "request_token": "qa301_classical",
                    "style": "classical",
                    "emotion_code": "sad",
                    "emotion_label": "难过",
                    "trigger_tags": ["学业压力"],
                    "prompt": "古典风静态陪伴图片，主情绪：难过，关键词：学业压力",
                    "consent_confirmed": True,
                },
            )
            self._ensure(status_code == 200, f"创建古典风任务失败: {created}")
            task = self._poll_media_task("phase3-qa-classical", created["task_id"])
            result = task.get("result") or {}
            self._ensure(task.get("status") == "succeeded", f"古典风任务未成功: {task}")
            self._ensure(
                result.get("generated_image_url") == "https://cdn.example.com/classical_sad.jpg",
                f"古典风命中错误: {result}",
            )

        def case_guochao_match() -> None:
            self._reset_media_generate_state()
            self._reset_point_and_quota_stores()
            os.environ["MEDIA_GEN_REQUIRE_CONSENT"] = "0"
            os.environ["MEDIA_GEN_ENABLE_WEEKLY_QUOTA"] = "0"
            os.environ["MEDIA_GEN_ENABLE_POINTS"] = "0"
            self._set_pool_env(
                guochao=[
                    {
                        "id": "guochao_study",
                        "url": "https://cdn.example.com/guochao_study.jpg",
                        "style": "guochao",
                        "emotion_tags": ["学业压力", "考试紧张"],
                        "weight": 8,
                        "active": True,
                        "updated_at": "2026-04-01T00:00:00Z",
                    },
                    {
                        "id": "guochao_sleep",
                        "url": "https://cdn.example.com/guochao_sleep.jpg",
                        "style": "guochao",
                        "emotion_tags": ["睡眠不足", "疲惫"],
                        "weight": 8,
                        "active": True,
                        "updated_at": "2026-04-01T00:00:00Z",
                    },
                ]
            )

            status_code, created = self._create_media_task(
                "phase3-qa-guochao",
                {
                    "request_token": "qa301_guochao",
                    "style": "guochao",
                    "emotion_code": "neutral",
                    "emotion_label": "平静",
                    "trigger_tags": ["学业压力"],
                    "prompt": "国潮风静态陪伴图片，主情绪：平静，关键词：学业压力",
                    "consent_confirmed": True,
                },
            )
            self._ensure(status_code == 200, f"创建国潮风任务失败: {created}")
            task = self._poll_media_task("phase3-qa-guochao", created["task_id"])
            result = task.get("result") or {}
            self._ensure(task.get("status") == "succeeded", f"国潮风任务未成功: {task}")
            self._ensure(
                result.get("generated_image_url") == "https://cdn.example.com/guochao_study.jpg",
                f"国潮风命中错误: {result}",
            )

        self._run_case("QA-301", "QA-301-1", "古典风图池按情绪标签命中", case_classical_match)
        self._run_case("QA-301", "QA-301-2", "国潮风图池按触发标签命中", case_guochao_match)

    def _run_qa_302(self) -> None:
        def case_url_fallback_to_assets() -> None:
            original_resolve = self.storage_service.resolve_file_id_to_temp_path

            def fake_resolve(source: str, field_name: str) -> str:
                if source.startswith("https://unstable.example.com/"):
                    raise ValueError(f"{field_name} download failed: timeout")
                return original_resolve(source, field_name)

            self.storage_service.resolve_file_id_to_temp_path = fake_resolve
            try:
                resolved = self.storage_service.resolve_input_file(
                    local_path=None,
                    file_url="https://unstable.example.com/poet.png",
                    file_id="/assets/tangsong/苏轼.png",
                    field_name="qa302_image",
                    prefer_file_id=False,
                )
            finally:
                self.storage_service.resolve_file_id_to_temp_path = original_resolve

            self._ensure(resolved.path is not None, "弱网回退后未解析到文件。")
            self._ensure(resolved.path.endswith("苏轼.png"), f"弱网回退未落到本地素材: {resolved.path}")

        def case_empty_pool_does_not_block_email() -> None:
            self._reset_media_generate_state()
            self._reset_point_and_quota_stores()
            os.environ["MEDIA_GEN_REQUIRE_CONSENT"] = "0"
            os.environ["MEDIA_GEN_ENABLE_WEEKLY_QUOTA"] = "0"
            os.environ["MEDIA_GEN_ENABLE_POINTS"] = "0"
            self._set_pool_env(classical=[], guochao=[])
            analyze_body = self._post_analyze("phase3-qa-empty-pool", "今天有些紧张，但我还是想慢慢稳住。")

            status_code, created = self._create_media_task(
                "phase3-qa-empty-pool",
                {
                    "request_token": "qa302_empty_pool",
                    "style": "tech",
                    "emotion_code": "anxious",
                    "emotion_label": "紧张",
                    "trigger_tags": ["学习节奏"],
                    "prompt": "科技风静态陪伴图片，主情绪：紧张，关键词：学习节奏",
                    "consent_confirmed": True,
                },
            )
            self._ensure(status_code == 200, f"创建科技风任务失败: {created}")
            task = self._poll_media_task("phase3-qa-empty-pool", created["task_id"])
            self._ensure(task.get("status") == "failed", f"空池任务未失败: {task}")
            self._ensure(task.get("error_code") == "MEDIA_GEN_POOL_EMPTY", f"错误码异常: {task}")

            captured: dict[str, Any] = {}
            original_send = self.email_service.send_analysis_email
            try:
                self.email_service.send_analysis_email = lambda **kwargs: captured.update(kwargs) or (True, "mock ok")  # type: ignore[assignment]
                payload = {
                    "to_email": "qa@example.com",
                    "analysis_request_id": analyze_body.get("request_id"),
                    "thoughts": "phase3 weak network fallback",
                    "poem_text": analyze_body["poem"]["text"],
                    "comfort_text": analyze_body["guochao"]["comfort"],
                    "poet_image_file_id": analyze_body["poet_image_url"],
                    "guochao_image_file_id": analyze_body["guochao_image_url"],
                }
                response = self.client.post("/api/send-email", json=payload, headers=self._headers("phase3-qa-empty-pool"))
            finally:
                self.email_service.send_analysis_email = original_send  # type: ignore[assignment]

            body = response.json()
            self._ensure(response.status_code == 200, f"邮件接口失败: {response.text}")
            self._ensure(body.get("success") is True, f"邮件发送未成功: {body}")
            self._ensure(captured.get("poet_image_np") is not None, "诗词图片未成功进入邮件链路。")
            self._ensure(captured.get("guochao_image_np") is not None, "国潮图片未成功进入邮件链路。")

        self._run_case("QA-302", "QA-302-1", "弱网下 URL 失败可回退 file_id/本地素材", case_url_fallback_to_assets)
        self._run_case("QA-302", "QA-302-2", "风格图空池失败不阻塞主分析与邮件", case_empty_pool_does_not_block_email)

    def _run_qa_303(self) -> None:
        def case_page_email_consistency() -> None:
            analyze_body = self._post_analyze("phase3-qa-consistency", "最近有点疲惫，但我想继续坚持。")
            captured_paths: dict[str, str | None] = {}
            original_resolve = self.email_service.resolve_input_file
            original_send = self.email_service.send_analysis_email

            def wrapped_resolve(*args: Any, **kwargs: Any) -> Any:
                result = original_resolve(*args, **kwargs)
                field_name = kwargs.get("field_name") or (args[3] if len(args) >= 4 else "")
                if isinstance(field_name, str):
                    if field_name.startswith("poet_image_path"):
                        captured_paths["poet"] = result.path
                    if field_name.startswith("guochao_image_path"):
                        captured_paths["guochao"] = result.path
                return result

            self.email_service.resolve_input_file = wrapped_resolve  # type: ignore[assignment]
            self.email_service.send_analysis_email = lambda **kwargs: (True, "mock ok")  # type: ignore[assignment]
            try:
                response = self.client.post(
                    "/api/send-email",
                    json={
                        "to_email": "qa@example.com",
                        "analysis_request_id": analyze_body.get("request_id"),
                        "thoughts": "phase3 consistency check",
                        "poem_text": analyze_body["poem"]["text"],
                        "comfort_text": analyze_body["guochao"]["comfort"],
                        "poet_image_file_id": analyze_body["poet_image_url"],
                        "guochao_image_file_id": analyze_body["guochao_image_url"],
                    },
                    headers=self._headers("phase3-qa-consistency"),
                )
            finally:
                self.email_service.resolve_input_file = original_resolve  # type: ignore[assignment]
                self.email_service.send_analysis_email = original_send  # type: ignore[assignment]

            self._ensure(response.status_code == 200, f"邮件接口失败: {response.text}")
            self._ensure(response.json().get("success") is True, f"邮件发送未成功: {response.text}")
            self._ensure(captured_paths.get("poet"), "未记录诗词图片解析路径。")
            self._ensure(captured_paths.get("guochao"), "未记录国潮图片解析路径。")
            self._ensure(
                Path(str(captured_paths["poet"])).name == Path(analyze_body["poet_image_url"]).name,
                f"页面/邮件诗词图片不一致: {captured_paths}",
            )
            self._ensure(
                Path(str(captured_paths["guochao"])).name == Path(analyze_body["guochao_image_url"]).name,
                f"页面/邮件国潮图片不一致: {captured_paths}",
            )

        self._run_case("QA-303", "QA-303-1", "页面与邮件解析的静态图片来源一致", case_page_email_consistency)

    def _run_qa_304(self) -> None:
        def case_consent_rejected() -> None:
            self._reset_media_generate_state()
            self._reset_point_and_quota_stores()
            os.environ["MEDIA_GEN_REQUIRE_CONSENT"] = "1"
            os.environ["MEDIA_GEN_ENABLE_WEEKLY_QUOTA"] = "0"
            os.environ["MEDIA_GEN_ENABLE_POINTS"] = "0"
            self._set_pool_env(
                classical=[
                    {
                        "id": "classical_default",
                        "url": "https://cdn.example.com/classical_default.jpg",
                        "style": "classical",
                        "emotion_tags": [],
                        "active": True,
                    }
                ]
            )
            response = self.client.post(
                "/api/media-generate",
                json={"style": "classical", "consent_confirmed": False},
                headers=self._headers("phase3-qa-consent"),
            )
            self._ensure(response.status_code == 403, f"授权拒绝状态码异常: {response.text}")
            self._ensure("MEDIA_GEN_CONSENT_REQUIRED" in response.text, f"授权拒绝错误码异常: {response.text}")

        def case_weekly_limit() -> None:
            self._reset_media_generate_state()
            self._reset_point_and_quota_stores()
            os.environ["MEDIA_GEN_REQUIRE_CONSENT"] = "0"
            os.environ["MEDIA_GEN_ENABLE_WEEKLY_QUOTA"] = "1"
            os.environ["MEDIA_GEN_WEEKLY_LIMIT"] = "1"
            os.environ["MEDIA_GEN_ENABLE_POINTS"] = "0"
            self._set_pool_env(
                classical=[
                    {
                        "id": "classical_limit",
                        "url": "https://cdn.example.com/classical_limit.jpg",
                        "style": "classical",
                        "emotion_tags": [],
                        "active": True,
                    }
                ]
            )
            first_status, first_body = self._create_media_task(
                "phase3-qa-limit",
                {"request_token": "limit_1", "style": "classical", "consent_confirmed": True},
            )
            self._ensure(first_status == 200, f"首个任务创建失败: {first_body}")
            first_task = self._poll_media_task("phase3-qa-limit", first_body["task_id"])
            self._ensure(first_task.get("status") == "succeeded", f"首个任务未成功: {first_task}")

            second = self.client.post(
                "/api/media-generate",
                json={"request_token": "limit_2", "style": "classical", "consent_confirmed": True},
                headers=self._headers("phase3-qa-limit"),
            )
            self._ensure(second.status_code == 429, f"超限状态码异常: {second.text}")
            self._ensure("MEDIA_GEN_WEEKLY_LIMIT_EXCEEDED" in second.text, f"超限错误码异常: {second.text}")

        def case_points_insufficient() -> None:
            self._reset_media_generate_state()
            self._reset_point_and_quota_stores()
            os.environ["MEDIA_GEN_REQUIRE_CONSENT"] = "0"
            os.environ["MEDIA_GEN_ENABLE_WEEKLY_QUOTA"] = "0"
            os.environ["MEDIA_GEN_ENABLE_POINTS"] = "1"
            os.environ["MEDIA_GEN_POINTS_COST"] = "999"
            self._set_pool_env(
                classical=[
                    {
                        "id": "classical_points",
                        "url": "https://cdn.example.com/classical_points.jpg",
                        "style": "classical",
                        "emotion_tags": [],
                        "active": True,
                    }
                ]
            )
            response = self.client.post(
                "/api/media-generate",
                json={"style": "classical", "consent_confirmed": True},
                headers=self._headers("phase3-qa-points"),
            )
            self._ensure(response.status_code == 402, f"积分不足状态码异常: {response.text}")
            self._ensure("MEDIA_GEN_POINTS_INSUFFICIENT" in response.text, f"积分不足错误码异常: {response.text}")

        def case_rollback_after_failure() -> None:
            self._reset_media_generate_state()
            self._reset_point_and_quota_stores()
            os.environ["MEDIA_GEN_REQUIRE_CONSENT"] = "0"
            os.environ["MEDIA_GEN_ENABLE_WEEKLY_QUOTA"] = "1"
            os.environ["MEDIA_GEN_WEEKLY_LIMIT"] = "1"
            os.environ["MEDIA_GEN_ENABLE_POINTS"] = "1"
            os.environ["MEDIA_GEN_POINTS_COST"] = "3"
            os.environ["MEDIA_GEN_DEFAULT_POINTS"] = "5"
            self._set_pool_env(
                classical=[
                    {
                        "id": "classical_rollback",
                        "url": "https://cdn.example.com/classical_rollback.jpg",
                        "style": "classical",
                        "emotion_tags": [],
                        "active": True,
                    }
                ]
            )
            os.environ["MEDIA_GEN_PROVIDER"] = "invalid_provider"

            status_code, created = self._create_media_task(
                "phase3-qa-rollback",
                {"request_token": "rollback_1", "style": "classical", "consent_confirmed": True},
            )
            self._ensure(status_code == 200, f"失败任务创建失败: {created}")
            task = self._poll_media_task("phase3-qa-rollback", created["task_id"])
            self._ensure(task.get("status") == "failed", f"失败任务未失败: {task}")
            self._ensure(task.get("error_code") == "MEDIA_GEN_PROVIDER_DISABLED", f"失败错误码异常: {task}")

            balance_after_failure = self.points_service.get_points_balance("phase3-qa-rollback")
            self._ensure(balance_after_failure == 5, f"积分未回滚到初始值: {balance_after_failure}")

            os.environ["MEDIA_GEN_PROVIDER"] = "local_mock"
            next_status, next_body = self._create_media_task(
                "phase3-qa-rollback",
                {"request_token": "rollback_2", "style": "classical", "consent_confirmed": True},
            )
            self._ensure(next_status == 200, f"回滚后任务无法重建: {next_body}")
            next_task = self._poll_media_task("phase3-qa-rollback", next_body["task_id"])
            self._ensure(next_task.get("status") == "succeeded", f"回滚后任务未成功: {next_task}")

        self._run_case("QA-304", "QA-304-1", "拒绝授权时直接阻断", case_consent_rejected)
        self._run_case("QA-304", "QA-304-2", "超周限额时返回明确错误", case_weekly_limit)
        self._run_case("QA-304", "QA-304-3", "积分不足时返回明确错误", case_points_insufficient)
        self._run_case("QA-304", "QA-304-4", "任务失败后积分回滚且配额释放", case_rollback_after_failure)

    def _write_report(self) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        cases_sorted = sorted(self.results, key=lambda item: item.case_id)
        total = len(cases_sorted)
        passed = sum(1 for item in cases_sorted if item.status == "PASS")
        overall = "PASS" if passed == total else "FAIL"

        grouped: dict[str, list[CaseResult]] = {}
        for item in cases_sorted:
            grouped.setdefault(item.qa_id, []).append(item)

        lines: list[str] = []
        lines.append("# 第三阶段 M5 QA 回归报告")
        lines.append("")
        lines.append(f"- 执行时间(UTC): `{self._now_iso()}`")
        lines.append(f"- 代码仓库: `{self.repo_root}`")
        lines.append(f"- 隔离工作目录: `{self.workspace}`")
        lines.append(f"- 总体结果: **{overall}** (`{passed}/{total}` 通过)")
        lines.append("")
        lines.append("## 分任务汇总")
        lines.append("")
        lines.append("| 任务 | 通过/总数 | 结果 |")
        lines.append("|---|---:|---|")
        for qa_id in sorted(grouped.keys()):
            qa_cases = grouped[qa_id]
            qa_passed = sum(1 for item in qa_cases if item.status == "PASS")
            qa_total = len(qa_cases)
            qa_status = "PASS" if qa_passed == qa_total else "FAIL"
            lines.append(f"| {qa_id} | {qa_passed}/{qa_total} | {qa_status} |")

        lines.append("")
        lines.append("## 用例明细")
        lines.append("")
        lines.append("| 用例ID | 任务 | 用例 | 结果 | 耗时(ms) | 说明 |")
        lines.append("|---|---|---|---|---:|---|")
        for item in cases_sorted:
            lines.append(
                f"| {item.case_id} | {item.qa_id} | {item.title} | {item.status} | {item.duration_ms:.1f} | {item.detail} |"
            )

        lines.append("")
        lines.append("## 关键说明")
        lines.append("")
        lines.append("- `QA-301` 已覆盖静态图池的风格 + 情绪/触发标签命中。")
        lines.append("- `QA-302` 为本地弱网/失败模拟回归，覆盖 URL 失败回退与空池失败不阻塞主链路。")
        lines.append("- `QA-303` 验证结果页静态图与邮件发送解析到同一素材来源。")
        lines.append("- `QA-304` 复核第三阶段硬约束，避免 M5 收口时回退。")
        if self.metrics:
            lines.append("")
            lines.append("## 指标与配置快照")
            lines.append("")
            for key in sorted(self.metrics.keys()):
                lines.append(f"- `{key}`: `{self.metrics[key]}`")

        self.report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run(self) -> int:
        self._set_test_env()
        self._import_backend()
        self._run_data_cases()
        self._run_qa_301()
        self._run_qa_302()
        self._run_qa_303()
        self._run_qa_304()
        self._write_report()
        failures = [item for item in self.results if item.status != "PASS"]
        return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run phase3 M5 QA regression checks.")
    parser.add_argument(
        "--report",
        default="docs/phase3-m5-qa-regression-report.md",
        help="Path to markdown report output.",
    )
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[1]
    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = (repo_root / report_path).resolve()

    runner = Phase3QARegressionRunner(repo_root=repo_root, report_path=report_path)
    code = runner.run()
    print(f"phase3 qa regression exit_code={code}, report={report_path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
