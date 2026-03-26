#!/usr/bin/env python3
"""
第一阶段 QA 回归脚本（QA-001 ~ QA-004）

执行方式（仓库根目录）:
  ./.venv/bin/python tools/phase1_qa_regression.py

输出:
  docs/phase1-qa-regression-report.md
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import math
import os
import shutil
import struct
import sys
import tempfile
import time
import wave
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image


@dataclass
class CaseResult:
    qa_id: str
    case_id: str
    title: str
    success: bool
    duration_ms: float
    detail: str


class QARegressionRunner:
    def __init__(self, repo_root: Path, report_path: Path) -> None:
        self.repo_root = repo_root
        self.report_path = report_path
        self.workspace = Path(tempfile.mkdtemp(prefix="phase1_qa_"))
        self.media_dir = self.workspace / "media"
        self.media_dir.mkdir(parents=True, exist_ok=True)

        self.history_store_path = self.workspace / "history_store.json"
        self.media_retention_store_path = self.workspace / "media_retention_store.json"
        self.pc_cache_dir = self.workspace / "pc_cache"
        self.pc_cache_dir.mkdir(parents=True, exist_ok=True)

        self.api_root = self.repo_root / "services" / "wechat-api"
        self.pc_root = self.repo_root / "apps" / "pc"
        self.tmp_download_dir = self.workspace / "tmp_downloads"
        self.tmp_download_dir.mkdir(parents=True, exist_ok=True)

        self.valid_voice_path = self.media_dir / "qa_voice_ok.wav"
        self.short_voice_path = self.media_dir / "qa_voice_short.wav"
        self.invalid_face_path = self.media_dir / "qa_face_dark.png"
        self.valid_face_path = self.media_dir / "qa_face_valid.png"

        self.client: Any = None
        self.storage_service: Any = None
        self.email_service: Any = None
        self.media_retention_service: Any = None
        self.pc_logic: Any = None
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
    def _old_iso(days_ago: int) -> str:
        return (
            datetime.now(timezone.utc) - timedelta(days=days_ago)
        ).isoformat(timespec="seconds").replace("+00:00", "Z")

    @staticmethod
    def _extract_error_detail(response_json: Any) -> str:
        if isinstance(response_json, dict):
            detail = response_json.get("detail")
            if isinstance(detail, str):
                return detail
            if isinstance(detail, list):
                return json.dumps(detail, ensure_ascii=False)
        return json.dumps(response_json, ensure_ascii=False)

    @staticmethod
    def _parse_pc_label(emotion_text: str) -> str:
        text = (emotion_text or "").strip()
        if ":" not in text:
            return text
        return text.split(":", 1)[1].strip()

    def _set_test_env(self) -> None:
        # 隔离历史数据，避免污染开发环境。
        os.environ["HISTORY_STORE_PATH"] = str(self.history_store_path)
        os.environ["HISTORY_RETENTION_DAYS"] = "180"
        os.environ["MEDIA_RETENTION_STORE_PATH"] = str(self.media_retention_store_path)
        os.environ["MEDIA_RETENTION_HOURS"] = "24"

        # 语音链路使用 mock 转写，保证本地无外部依赖可跑通。
        os.environ["SPEECH_STT_PROVIDER"] = "mock"
        os.environ["SPEECH_STT_MOCK_TEXT"] = "今天有点紧张但我还能慢慢调整"
        os.environ["SPEECH_STT_TIMEOUT_SEC"] = "5"

        # 强制临时文件落到隔离目录，便于校验媒体清理策略。
        os.environ["TMPDIR"] = str(self.tmp_download_dir)
        tempfile.tempdir = str(self.tmp_download_dir)

    def _write_wav(self, output_path: Path, duration_sec: float, amplitude: float) -> None:
        sample_rate = 16000
        freq = 440.0
        frame_count = max(1, int(duration_sec * sample_rate))
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            frames = bytearray()
            for index in range(frame_count):
                value = int(32767.0 * amplitude * math.sin(2.0 * math.pi * freq * (index / sample_rate)))
                frames.extend(struct.pack("<h", value))
            wav_file.writeframes(bytes(frames))

    def _prepare_media(self) -> None:
        self._write_wav(self.valid_voice_path, duration_sec=2.5, amplitude=0.45)
        self._write_wav(self.short_voice_path, duration_sec=0.12, amplitude=0.05)

        dark = Image.fromarray(np.zeros((720, 720, 3), dtype=np.uint8))
        dark.save(self.invalid_face_path)

    def _import_backend_and_pc(self) -> None:
        sys.path.insert(0, str(self.api_root))
        from fastapi.testclient import TestClient  # type: ignore

        from app.main import app  # type: ignore
        import app.services.email_service as email_service  # type: ignore
        import app.services.media_retention_service as media_retention_service  # type: ignore
        import app.services.storage_service as storage_service  # type: ignore
        from app.services.analysis_service import FaceQualityRejectError, _validate_face_quality  # type: ignore

        self.client = TestClient(app)
        self.storage_service = storage_service
        self.email_service = email_service
        self.media_retention_service = media_retention_service

        # 从后端 assets 中自动选一个可通过自拍质量校验的图片，拷贝到 ASCII 路径。
        candidates = sorted((self.api_root / "app" / "core" / "images").rglob("*.png"))
        selected_source: Path | None = None
        for candidate in candidates:
            try:
                image_np = np.array(Image.open(candidate).convert("RGB"))
                _validate_face_quality(image_np)
                selected_source = candidate
                break
            except FaceQualityRejectError:
                continue
            except Exception:
                continue

        self._ensure(selected_source is not None, "未找到可通过人脸质量校验的测试图片。")
        shutil.copyfile(selected_source, self.valid_face_path)

        # 导入 PC 端逻辑模块。
        pc_main_path = self.pc_root / "main.py"
        if str(self.pc_root) not in sys.path:
            sys.path.insert(0, str(self.pc_root))
        spec = importlib.util.spec_from_file_location("qa_pc_main_module", str(pc_main_path))
        self._ensure(spec is not None and spec.loader is not None, "加载 PC main.py 失败。")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        # QA 回归中关闭 PC 端 TTS，避免语音线程影响测试稳定性和耗时统计。
        module.speak_text_in_thread = lambda *args, **kwargs: None

        self.pc_logic = module.AppLogic()
        self.pc_logic.cache_dir = str(self.pc_cache_dir)
        self.pc_logic.history_cache_file = str(self.pc_cache_dir / "history_summary.json")
        self.pc_logic._ensure_history_cache_ready()

    def _headers(self, user_id: str) -> dict[str, str]:
        return {"X-EC-USER-ID": user_id}

    def _post_analyze(self, payload: dict[str, Any], user_id: str):
        return self.client.post("/api/analyze", json=payload, headers=self._headers(user_id))

    def _get_history(self, user_id: str):
        return self.client.get("/api/history?limit=50&offset=0", headers=self._headers(user_id))

    def _clear_history(self, user_id: str) -> None:
        self.client.delete("/api/history", headers=self._headers(user_id))

    def _run_case(self, qa_id: str, case_id: str, title: str, fn: Callable[[], None]) -> None:
        start = time.perf_counter()
        try:
            fn()
            success = True
            detail = "PASS"
        except AssertionError as exc:
            success = False
            detail = f"ASSERT: {exc}"
        except Exception as exc:  # pragma: no cover - 防御性兜底
            success = False
            detail = f"ERROR: {type(exc).__name__}: {exc}"
        duration_ms = (time.perf_counter() - start) * 1000.0
        self.results.append(
            CaseResult(
                qa_id=qa_id,
                case_id=case_id,
                title=title,
                success=success,
                duration_ms=duration_ms,
                detail=detail,
            )
        )

    def _qa_001(self) -> None:
        user = "qa-mini-main"

        def case_text_chain() -> None:
            payload = {
                "input_modes": ["text"],
                "text": "我今天很开心，阳光明媚！",
                "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
            }
            resp = self._post_analyze(payload, user)
            self._ensure(resp.status_code == 200, f"text 链路失败: {resp.text}")
            body = resp.json()
            card = body.get("result_card", {})
            required_fields = {
                "primary_emotion",
                "secondary_emotions",
                "emotion_overview",
                "trigger_tags",
                "poem_response",
                "poem_interpretation",
                "guochao_comfort",
                "daily_suggestion",
            }
            self._ensure(required_fields.issubset(set(card.keys())), "result_card 固定结构字段不完整。")

        def case_voice_chain() -> None:
            payload = {
                "input_modes": ["voice"],
                "audio": {"local_path": str(self.valid_voice_path)},
                "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
            }
            resp = self._post_analyze(payload, user)
            self._ensure(resp.status_code == 200, f"voice 链路失败: {resp.text}")
            body = resp.json()
            self._ensure("voice" in body.get("input_modes", []), "voice 输入模式未生效。")
            transcript = body.get("system_fields", {}).get("speech_transcript")
            self._ensure(bool((transcript or "").strip()), "voice 链路未产生有效转写文本。")

        def case_selfie_chain() -> None:
            payload = {
                "input_modes": ["selfie"],
                "image": {"local_path": str(self.valid_face_path)},
                "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
            }
            resp = self._post_analyze(payload, user)
            self._ensure(resp.status_code == 200, f"selfie 链路失败: {resp.text}")
            body = resp.json()
            self._ensure("selfie" in body.get("input_modes", []), "selfie 输入模式未生效。")

        def case_voice_fail_recover() -> None:
            bad_payload = {
                "input_modes": ["voice"],
                "audio": {"local_path": str(self.short_voice_path)},
                "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
            }
            bad_resp = self._post_analyze(bad_payload, user)
            self._ensure(bad_resp.status_code == 400, "短语音未触发失败路径。")
            detail = self._extract_error_detail(bad_resp.json())
            self._ensure("[VOICE_" in detail, f"语音失败错误码不符合预期: {detail}")

            recover_payload = {
                "input_modes": ["text"],
                "text": "改用文字继续提交。",
                "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
            }
            recover_resp = self._post_analyze(recover_payload, user)
            self._ensure(recover_resp.status_code == 200, f"语音失败后文字恢复失败: {recover_resp.text}")

        def case_selfie_fail_recover() -> None:
            bad_payload = {
                "input_modes": ["selfie"],
                "image": {"local_path": str(self.invalid_face_path)},
                "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
            }
            bad_resp = self._post_analyze(bad_payload, user)
            self._ensure(bad_resp.status_code == 400, "无效自拍未触发失败路径。")
            detail = self._extract_error_detail(bad_resp.json())
            self._ensure("[FACE_" in detail, f"自拍失败错误码不符合预期: {detail}")

            recover_payload = {
                "input_modes": ["text"],
                "text": "自拍失败后改用文字继续。",
                "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
            }
            recover_resp = self._post_analyze(recover_payload, user)
            self._ensure(recover_resp.status_code == 200, f"自拍失败后文字恢复失败: {recover_resp.text}")

        self._run_case("QA-001", "QA-001-1", "小程序文本链路通过", case_text_chain)
        self._run_case("QA-001", "QA-001-2", "小程序语音链路通过", case_voice_chain)
        self._run_case("QA-001", "QA-001-3", "小程序自拍链路通过", case_selfie_chain)
        self._run_case("QA-001", "QA-001-4", "小程序语音失败后可恢复", case_voice_fail_recover)
        self._run_case("QA-001", "QA-001-5", "小程序自拍失败后可恢复", case_selfie_fail_recover)

    def _qa_002(self) -> None:
        face_np = np.array(Image.open(self.valid_face_path).convert("RGB"))
        dark_np = np.array(Image.open(self.invalid_face_path).convert("RGB"))

        def case_pc_text() -> None:
            result = self.pc_logic.process_analysis("今天完成作业后很踏实。", None, None)
            self._ensure(len(result) == 9, "PC 文本链路返回结构异常。")
            self._ensure((result[0] or "").startswith("检测到的情绪:"), "PC 文本链路未返回情绪结果。")

        def case_pc_voice() -> None:
            result = self.pc_logic.process_analysis("", None, str(self.valid_voice_path))
            self._ensure(len(result) == 9, "PC 录音链路返回结构异常。")
            self._ensure((result[0] or "").startswith("检测到的情绪:"), "PC 录音链路未返回情绪结果。")
            self._ensure("VOICE_" not in (result[5] or ""), "PC 录音主链路触发了错误恢复分支。")

        def case_pc_camera() -> None:
            result = self.pc_logic.process_analysis("", face_np, None)
            self._ensure(len(result) == 9, "PC 摄像头链路返回结构异常。")
            self._ensure((result[0] or "").startswith("检测到的情绪:"), "PC 摄像头链路未返回情绪结果。")

        def case_pc_voice_recover() -> None:
            result = self.pc_logic.process_analysis("录音失败时保留文本输入。", None, str(self.short_voice_path))
            self._ensure((result[0] or "").startswith("检测到的情绪:"), "PC 语音失败后未保留可用文本链路。")
            self._ensure("VOICE_" in (result[5] or ""), "PC 语音失败恢复提示缺失。")

        def case_pc_camera_recover() -> None:
            result = self.pc_logic.process_analysis("拍照失败时保留文本输入。", dark_np, None)
            self._ensure((result[0] or "").startswith("检测到的情绪:"), "PC 拍照失败后未保留可用文本链路。")
            self._ensure("FACE_" in (result[5] or ""), "PC 拍照失败恢复提示缺失。")

        def case_consistency_with_mini() -> None:
            text = "我今天很开心，阳光明媚！"
            backend_payload = {
                "input_modes": ["text"],
                "text": text,
                "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": "qa-consistency"},
            }
            backend_resp = self._post_analyze(backend_payload, "qa-consistency")
            self._ensure(backend_resp.status_code == 200, f"小程序口径基线请求失败: {backend_resp.text}")
            backend_label = (
                backend_resp.json().get("result_card", {}).get("primary_emotion", {}).get("label", "").strip()
            )
            self._ensure(bool(backend_label), "小程序口径基线缺少主情绪标签。")

            pc_result = self.pc_logic.process_analysis(text, None, None)
            pc_label = self._parse_pc_label(pc_result[0])
            self._ensure(backend_label == pc_label, f"PC 与小程序口径不一致: mini={backend_label}, pc={pc_label}")

        self._run_case("QA-002", "QA-002-1", "PC 文本链路通过", case_pc_text)
        self._run_case("QA-002", "QA-002-2", "PC 录音链路通过", case_pc_voice)
        self._run_case("QA-002", "QA-002-3", "PC 摄像头链路通过", case_pc_camera)
        self._run_case("QA-002", "QA-002-4", "PC 录音失败后可恢复", case_pc_voice_recover)
        self._run_case("QA-002", "QA-002-5", "PC 拍照失败后可恢复", case_pc_camera_recover)
        self._run_case("QA-002", "QA-002-6", "PC 与小程序主情绪口径一致", case_consistency_with_mini)

    def _qa_003(self) -> None:
        def case_summary_no_raw_media() -> None:
            user = "qa-privacy-summary"
            self._clear_history(user)
            payload = {
                "input_modes": ["text", "selfie", "voice"],
                "text": "验证历史摘要字段。",
                "image": {"local_path": str(self.valid_face_path)},
                "audio": {"local_path": str(self.valid_voice_path)},
                "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
            }
            resp = self._post_analyze(payload, user)
            self._ensure(resp.status_code == 200, f"隐私摘要基线请求失败: {resp.text}")

            history_resp = self._get_history(user)
            self._ensure(history_resp.status_code == 200, f"读取历史失败: {history_resp.text}")
            body = history_resp.json()
            items = body.get("items", [])
            self._ensure(len(items) >= 1, "未写入历史摘要。")
            summary = items[0]

            expected_keys = {
                "history_id",
                "request_id",
                "analyzed_at",
                "input_modes",
                "primary_emotion",
                "secondary_emotions",
                "emotion_overview_summary",
                "trigger_tags",
                "poem_response_summary",
                "guochao_name",
                "daily_suggestion_summary",
                "mail_sent",
            }
            self._ensure(set(summary.keys()) == expected_keys, "历史摘要字段与约定不一致。")
            forbidden_names = {"image", "audio", "url", "path", "file_id"}
            for key in summary.keys():
                lowered = key.lower()
                self._ensure(
                    not any(token in lowered for token in forbidden_names),
                    f"历史摘要出现原始媒体字段: {key}",
                )

        def case_save_history_switch() -> None:
            user = "qa-privacy-settings"
            self._clear_history(user)

            disable_resp = self.client.put(
                "/api/settings",
                json={"save_history": False},
                headers=self._headers(user),
            )
            self._ensure(disable_resp.status_code == 200, f"关闭历史开关失败: {disable_resp.text}")

            disabled_payload = {
                "input_modes": ["text"],
                "text": "关闭历史后不应写入。",
                "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
            }
            analyze_resp = self._post_analyze(disabled_payload, user)
            self._ensure(analyze_resp.status_code == 200, f"关闭历史后分析失败: {analyze_resp.text}")
            history_after_disable = self._get_history(user).json()
            self._ensure(history_after_disable.get("total", 0) == 0, "关闭历史开关后仍写入了历史。")

            enable_resp = self.client.put(
                "/api/settings",
                json={"save_history": True},
                headers=self._headers(user),
            )
            self._ensure(enable_resp.status_code == 200, f"开启历史开关失败: {enable_resp.text}")

            enabled_payload = {
                "input_modes": ["text"],
                "text": "开启历史后应恢复写入。",
                "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
            }
            analyze_resp2 = self._post_analyze(enabled_payload, user)
            self._ensure(analyze_resp2.status_code == 200, f"开启历史后分析失败: {analyze_resp2.text}")
            history_after_enable = self._get_history(user).json()
            self._ensure(history_after_enable.get("total", 0) >= 1, "开启历史开关后未恢复写入。")

        def case_delete_and_clear() -> None:
            user = "qa-privacy-delete"
            self._clear_history(user)

            for index in range(3):
                payload = {
                    "input_modes": ["text"],
                    "text": f"删除用例 {index}",
                    "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
                }
                resp = self._post_analyze(payload, user)
                self._ensure(resp.status_code == 200, f"写入删除用例历史失败: {resp.text}")

            list_resp = self._get_history(user)
            self._ensure(list_resp.status_code == 200, f"读取删除用例历史失败: {list_resp.text}")
            items = list_resp.json().get("items", [])
            self._ensure(len(items) >= 2, "删除用例历史数量不足。")
            target_history_id = items[0].get("history_id", "")
            self._ensure(bool(target_history_id), "删除用例缺少 history_id。")

            delete_resp = self.client.delete(f"/api/history/{target_history_id}", headers=self._headers(user))
            self._ensure(delete_resp.status_code == 200, f"删除单条历史失败: {delete_resp.text}")
            self._ensure(delete_resp.json().get("deleted_count", 0) == 1, "删除单条历史 deleted_count 异常。")

            clear_resp = self.client.delete("/api/history", headers=self._headers(user))
            self._ensure(clear_resp.status_code == 200, f"清空历史失败: {clear_resp.text}")
            after_clear = self._get_history(user)
            self._ensure(after_clear.status_code == 200, f"清空后读取历史失败: {after_clear.text}")
            self._ensure(after_clear.json().get("total", -1) == 0, "清空后仍存在历史数据。")

        def case_retention_cleanup() -> None:
            user = "qa-privacy-retention"
            self._clear_history(user)

            payload = {
                "input_modes": ["text"],
                "text": "用于 retention 验证。",
                "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
            }
            base_resp = self._post_analyze(payload, user)
            self._ensure(base_resp.status_code == 200, f"retention 基线分析失败: {base_resp.text}")

            self._ensure(self.history_store_path.exists(), "history store 文件不存在。")
            with self.history_store_path.open("r", encoding="utf-8") as f:
                store_payload = json.load(f)

            bucket = store_payload.get("users", {}).get(user, {})
            history_items = bucket.get("history", [])
            self._ensure(len(history_items) >= 1, "retention 基线历史为空。")

            old_entry = copy.deepcopy(history_items[0])
            old_entry.setdefault("summary", {})
            old_entry.setdefault("internal_fields", {})
            old_entry["summary"]["history_id"] = f"his_old_{int(time.time())}"
            old_entry["summary"]["analyzed_at"] = self._old_iso(200)
            old_entry["internal_fields"]["analyzed_at"] = self._old_iso(200)
            history_items.append(old_entry)

            with self.history_store_path.open("w", encoding="utf-8") as f:
                json.dump(store_payload, f, ensure_ascii=False, indent=2)

            list_resp = self._get_history(user)
            self._ensure(list_resp.status_code == 200, f"retention 清理触发失败: {list_resp.text}")
            total = list_resp.json().get("total", -1)
            self._ensure(total == 1, f"retention 清理后数量异常，预期 1 实际 {total}")

            with self.history_store_path.open("r", encoding="utf-8") as f:
                persisted = json.load(f)
            persisted_items = persisted.get("users", {}).get(user, {}).get("history", [])
            self._ensure(len(persisted_items) == 1, "retention 清理结果未持久化到存储。")

        def case_temp_media_cleanup() -> None:
            user = "qa-privacy-temp-media"
            self._clear_history(user)

            # 先清理残留，避免误判。
            for stale in self.tmp_download_dir.glob("wechat_media_*"):
                stale.unlink(missing_ok=True)

            created_paths: list[Path] = []
            original_resolve = self.storage_service.resolve_file_id_to_temp_path

            def fake_resolve_file_id_to_temp_path(file_id: str, field_name: str) -> str:
                is_image = "image" in field_name.lower()
                source = self.valid_face_path if is_image else self.valid_voice_path
                suffix = ".png" if is_image else ".wav"
                temp_path = self.tmp_download_dir / f"wechat_media_{len(created_paths)}{suffix}"
                shutil.copyfile(source, temp_path)
                created_paths.append(temp_path)
                return str(temp_path)

            self.storage_service.resolve_file_id_to_temp_path = fake_resolve_file_id_to_temp_path
            try:
                payload = {
                    "input_modes": ["text", "selfie", "voice"],
                    "text": "验证临时媒体清理。",
                    "image": {"url": "https://mock.invalid/qa-face.png"},
                    "audio": {"url": "https://mock.invalid/qa-voice.wav"},
                    "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
                }
                resp = self._post_analyze(payload, user)
                self._ensure(resp.status_code == 200, f"URL 媒体分析失败: {resp.text}")

                self._ensure(len(created_paths) >= 2, "未生成预期的临时媒体文件。")
                leftovers = [path for path in created_paths if path.exists()]
                self._ensure(
                    len(leftovers) == 0,
                    f"存在未清理的临时媒体文件: {[str(item) for item in leftovers]}",
                )
            finally:
                self.storage_service.resolve_file_id_to_temp_path = original_resolve

        def case_cloud_media_retention_cleanup() -> None:
            user = "qa-privacy-cloud-retention"
            self._clear_history(user)
            self.media_retention_store_path.unlink(missing_ok=True)

            file_id_image = "cloud://qa-env.12345/emotion-culture/images/qa_face.png"
            file_id_audio = "cloud://qa-env.12345/emotion-culture/audio/qa_voice.wav"

            created_paths: list[Path] = []
            deleted_batches: list[list[str]] = []

            original_resolve = self.storage_service.resolve_file_id_to_temp_path
            original_delete_cloud = self.media_retention_service.delete_cloud_file_ids

            def fake_resolve_file_id_to_temp_path(file_id: str, field_name: str) -> str:
                is_image = "image" in field_name.lower()
                source = self.valid_face_path if is_image else self.valid_voice_path
                suffix = ".png" if is_image else ".wav"
                temp_path = self.tmp_download_dir / f"wechat_media_retention_{len(created_paths)}{suffix}"
                shutil.copyfile(source, temp_path)
                created_paths.append(temp_path)
                return str(temp_path)

            def fake_delete_cloud_file_ids(file_ids: list[str]) -> dict[str, list[str]]:
                ids = list(dict.fromkeys(file_ids))
                deleted_batches.append(ids)
                return {"deleted_ids": ids, "failed_ids": []}

            self.storage_service.resolve_file_id_to_temp_path = fake_resolve_file_id_to_temp_path
            self.media_retention_service.delete_cloud_file_ids = fake_delete_cloud_file_ids
            try:
                payload = {
                    "input_modes": ["text", "selfie", "voice"],
                    "text": "验证 cloud 媒体 24 小时保留清理。",
                    "image": {"file_id": file_id_image},
                    "audio": {"file_id": file_id_audio},
                    "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
                }
                resp = self._post_analyze(payload, user)
                self._ensure(resp.status_code == 200, f"cloud file_id 媒体分析失败: {resp.text}")

                self._ensure(self.media_retention_store_path.exists(), "媒体保留追踪文件未生成。")
                with self.media_retention_store_path.open("r", encoding="utf-8") as f:
                    store = json.load(f)
                tracked_items = store.get("items", [])
                tracked_ids = sorted(item.get("file_id") for item in tracked_items if isinstance(item, dict))
                self._ensure(
                    sorted([file_id_audio, file_id_image]) == tracked_ids,
                    f"媒体保留追踪文件内容异常: {tracked_ids}",
                )

                old_time = self._old_iso(days_ago=2)
                for item in tracked_items:
                    if isinstance(item, dict):
                        item["tracked_at"] = old_time
                with self.media_retention_store_path.open("w", encoding="utf-8") as f:
                    json.dump(store, f, ensure_ascii=False, indent=2)

                cleanup_outcome = self.media_retention_service.cleanup_expired_media()
                self._ensure(cleanup_outcome.get("expired", 0) >= 2, "未识别出过期 cloud 媒体。")
                self._ensure(cleanup_outcome.get("deleted", 0) >= 2, "过期 cloud 媒体未执行删除。")
                self._ensure(len(deleted_batches) >= 1, "未触发 cloud 媒体删除调用。")
                deleted_ids = sorted({file_id for batch in deleted_batches for file_id in batch})
                self._ensure(
                    deleted_ids == sorted([file_id_audio, file_id_image]),
                    f"删除调用 file_id 不匹配: {deleted_ids}",
                )

                with self.media_retention_store_path.open("r", encoding="utf-8") as f:
                    persisted = json.load(f)
                persisted_items = persisted.get("items", [])
                self._ensure(len(persisted_items) == 0, "过期 cloud 媒体删除后仍残留追踪记录。")
            finally:
                self.storage_service.resolve_file_id_to_temp_path = original_resolve
                self.media_retention_service.delete_cloud_file_ids = original_delete_cloud

        self._run_case("QA-003", "QA-003-1", "历史摘要不存原始媒体字段", case_summary_no_raw_media)
        self._run_case("QA-003", "QA-003-2", "历史保存开关即时生效", case_save_history_switch)
        self._run_case("QA-003", "QA-003-3", "支持删除单条与清空全部历史", case_delete_and_clear)
        self._run_case("QA-003", "QA-003-4", "180 天摘要保留策略可验证", case_retention_cleanup)
        self._run_case("QA-003", "QA-003-5", "原始媒体临时文件可自动清理", case_temp_media_cleanup)
        self._run_case("QA-003", "QA-003-6", "cloud file_id 过期媒体可自动清理", case_cloud_media_retention_cleanup)

    def _measure_latency(
        self, payload_factory: Callable[[int], dict[str, Any]], user_id: str, rounds: int = 3
    ) -> list[float]:
        latencies = []
        for index in range(rounds):
            payload = payload_factory(index)
            start = time.perf_counter()
            resp = self._post_analyze(payload, user_id)
            elapsed = time.perf_counter() - start
            self._ensure(resp.status_code == 200, f"性能样本请求失败: {resp.text}")
            latencies.append(elapsed)
        return latencies

    def _qa_004(self) -> None:
        def case_text_latency() -> None:
            user = "qa-perf-text"
            # warm-up
            self._post_analyze(
                {
                    "input_modes": ["text"],
                    "text": "warm up",
                    "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
                },
                user,
            )

            latencies = self._measure_latency(
                lambda i: {
                    "input_modes": ["text"],
                    "text": f"文本性能样本 {i}",
                    "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
                },
                user_id=user,
            )
            max_latency = max(latencies)
            self.metrics["text_latency_max_s"] = round(max_latency, 3)
            self._ensure(max_latency <= 3.0, f"文本分析耗时超标: {max_latency:.3f}s > 3s")

        def case_selfie_latency() -> None:
            user = "qa-perf-selfie"
            latencies = self._measure_latency(
                lambda i: {
                    "input_modes": ["selfie"],
                    "image": {"local_path": str(self.valid_face_path)},
                    "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
                },
                user_id=user,
            )
            max_latency = max(latencies)
            self.metrics["selfie_latency_max_s"] = round(max_latency, 3)
            self._ensure(max_latency <= 8.0, f"自拍/拍照分析耗时超标: {max_latency:.3f}s > 8s")

        def case_voice_latency() -> None:
            user = "qa-perf-voice"
            latencies = self._measure_latency(
                lambda i: {
                    "input_modes": ["voice"],
                    "audio": {"local_path": str(self.valid_voice_path)},
                    "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
                },
                user_id=user,
            )
            max_latency = max(latencies)
            self.metrics["voice_latency_max_s"] = round(max_latency, 3)
            self._ensure(max_latency <= 12.0, f"语音分析耗时超标: {max_latency:.3f}s > 12s")

        def case_email_not_blocking_and_retryable() -> None:
            user = "qa-perf-email"
            analyze_payload = {
                "input_modes": ["text"],
                "text": "验证邮件失败不阻塞主结果。",
                "client": {"platform": "mp-weixin", "version": "0.1.0", "user_id": user},
            }
            analyze_start = time.perf_counter()
            analyze_resp = self._post_analyze(analyze_payload, user)
            analyze_elapsed = time.perf_counter() - analyze_start
            self._ensure(analyze_resp.status_code == 200, f"邮件回归前分析失败: {analyze_resp.text}")
            analysis_request_id = analyze_resp.json().get("request_id", "")
            self._ensure(bool(analysis_request_id), "分析结果缺少 request_id。")

            original_send_fn = self.email_service.send_analysis_email

            def fake_send_analysis_email(**kwargs):  # type: ignore[no-untyped-def]
                time.sleep(2.0)
                return False, "邮件发送失败：模拟网络超时"

            self.email_service.send_analysis_email = fake_send_analysis_email
            try:
                email_payload = {
                    "to_email": "qa@example.com",
                    "analysis_request_id": analysis_request_id,
                    "thoughts": "用于重试能力验证。",
                    "poem_text": "poem",
                    "comfort_text": "comfort",
                }
                first_start = time.perf_counter()
                first_resp = self.client.post(
                    "/api/send-email",
                    json=email_payload,
                    headers=self._headers(user),
                )
                first_elapsed = time.perf_counter() - first_start

                second_resp = self.client.post(
                    "/api/send-email",
                    json=email_payload,
                    headers=self._headers(user),
                )

                self.metrics["analyze_vs_email_analyze_s"] = round(analyze_elapsed, 3)
                self.metrics["analyze_vs_email_send_s"] = round(first_elapsed, 3)

                self._ensure(first_resp.status_code == 200, f"邮件失败回归（首次）请求失败: {first_resp.text}")
                self._ensure(second_resp.status_code == 200, f"邮件失败回归（重试）请求失败: {second_resp.text}")
                body1 = first_resp.json()
                body2 = second_resp.json()
                self._ensure(body1.get("success") is False, "首次邮件失败回归未命中失败分支。")
                self._ensure(body2.get("success") is False, "重试邮件失败回归未命中失败分支。")
                self._ensure(body1.get("retryable") is True, "首次邮件失败未标记 retryable。")
                self._ensure(body2.get("retryable") is True, "重试邮件失败未标记 retryable。")
                self._ensure(
                    analyze_elapsed < first_elapsed,
                    "分析主流程耗时未显著小于邮件失败耗时，无法证明邮件不阻塞主结果。",
                )
            finally:
                self.email_service.send_analysis_email = original_send_fn

        self._run_case("QA-004", "QA-004-1", "文本分析耗时 <= 3s", case_text_latency)
        self._run_case("QA-004", "QA-004-2", "自拍/拍照分析耗时 <= 8s", case_selfie_latency)
        self._run_case("QA-004", "QA-004-3", "语音分析耗时 <= 12s", case_voice_latency)
        self._run_case("QA-004", "QA-004-4", "邮件失败不阻塞主结果且可重试", case_email_not_blocking_and_retryable)

    def _write_report(self) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)

        total = len(self.results)
        passed = sum(1 for item in self.results if item.success)
        failed = total - passed
        overall_status = "PASS" if failed == 0 else "FAIL"

        grouped: dict[str, list[CaseResult]] = {}
        for result in self.results:
            grouped.setdefault(result.qa_id, []).append(result)

        lines: list[str] = []
        lines.append("# 第一阶段 QA 回归报告")
        lines.append("")
        lines.append(f"- 执行时间(UTC): `{self._now_iso()}`")
        lines.append(f"- 代码仓库: `{self.repo_root}`")
        lines.append(f"- 历史存储隔离路径: `{self.history_store_path}`")
        lines.append(f"- 总体结果: **{overall_status}** (`{passed}/{total}` 通过)")
        lines.append("")
        lines.append("## 分任务汇总")
        lines.append("")
        lines.append("| QA 任务 | 通过/总数 | 结果 |")
        lines.append("|---|---:|---|")
        for qa_id in sorted(grouped.keys()):
            qa_cases = grouped[qa_id]
            qa_passed = sum(1 for item in qa_cases if item.success)
            qa_total = len(qa_cases)
            qa_status = "PASS" if qa_passed == qa_total else "FAIL"
            lines.append(f"| {qa_id} | {qa_passed}/{qa_total} | {qa_status} |")
        lines.append("")
        lines.append("## 用例明细")
        lines.append("")
        lines.append("| 用例ID | QA | 用例 | 结果 | 耗时(ms) | 说明 |")
        lines.append("|---|---|---|---|---:|---|")
        for item in self.results:
            status_text = "PASS" if item.success else "FAIL"
            lines.append(
                f"| {item.case_id} | {item.qa_id} | {item.title} | {status_text} | {item.duration_ms:.1f} | {item.detail} |"
            )

        if self.metrics:
            lines.append("")
            lines.append("## 稳定性指标")
            lines.append("")
            for key in sorted(self.metrics.keys()):
                lines.append(f"- `{key}`: `{self.metrics[key]}`")

        self.report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run(self) -> int:
        self._set_test_env()
        self._prepare_media()
        self._import_backend_and_pc()

        self._qa_001()
        self._qa_002()
        self._qa_003()
        self._qa_004()

        self._write_report()

        failed = [item for item in self.results if not item.success]
        if failed:
            return 1
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run phase1 QA-001~QA-004 regression checks.")
    parser.add_argument(
        "--report",
        default="docs/phase1-qa-regression-report.md",
        help="Path to markdown report output (relative to repo root by default).",
    )
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[1]
    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = (repo_root / report_path).resolve()

    runner = QARegressionRunner(repo_root=repo_root, report_path=report_path)
    code = runner.run()
    print(f"phase1 qa regression exit_code={code}, report={report_path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
