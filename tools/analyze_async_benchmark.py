#!/usr/bin/env python3
"""
异步分析压测脚本（本地基线）

示例：
  ./.venv/bin/python tools/analyze_async_benchmark.py \
    --requests 80 --concurrency 8 --timeout-sec 90 --poll-interval-ms 300
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import tempfile
import time
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _iso_now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _pct(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    rank = max(0, min(len(sorted_values) - 1, math.ceil(len(sorted_values) * (p / 100.0)) - 1))
    return sorted_values[rank]


def _generate_wav(path: Path, *, duration_sec: float = 2.2, sample_rate: int = 16000, freq: float = 220.0) -> None:
    total_frames = int(duration_sec * sample_rate)
    amplitude = 9000
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for index in range(total_frames):
            value = int(amplitude * math.sin(2.0 * math.pi * freq * index / sample_rate))
            wf.writeframesraw(int(value).to_bytes(2, byteorder="little", signed=True))


@dataclass
class BenchResult:
    success: bool
    latency_s: float
    detail: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Run async analyze benchmark (local baseline).")
    parser.add_argument("--requests", type=int, default=80)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--timeout-sec", type=int, default=90)
    parser.add_argument("--poll-interval-ms", type=int, default=300)
    parser.add_argument("--report", default="docs/phase2-async-benchmark-report.md")
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[1]
    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = (repo_root / report_path).resolve()

    workspace = Path(tempfile.mkdtemp(prefix="async_bench_"))
    history_store = workspace / "history_store.json"
    media_store = workspace / "media_retention_store.json"
    wav_path = workspace / "bench_voice.wav"
    _generate_wav(wav_path)

    os.environ["HISTORY_STORE_PATH"] = str(history_store)
    os.environ["HISTORY_RETENTION_DAYS"] = "30"
    os.environ["MEDIA_RETENTION_STORE_PATH"] = str(media_store)
    os.environ["SPEECH_STT_PROVIDER"] = "mock"
    os.environ["SPEECH_STT_MOCK_TEXT"] = "这是异步压测语音样本"
    os.environ["SPEECH_ASR_SERVICE"] = "on"
    os.environ["VOICE_REQUIRE_TRANSCRIPT"] = "0"
    os.environ["RETENTION_SERVICE_ENABLED"] = "on"
    os.environ["RETENTION_WEEKLY_REPORT_ENABLED"] = "on"
    os.environ["RETENTION_FAVORITES_ENABLED"] = "on"

    import sys

    api_root = repo_root / "services" / "wechat-api"
    if str(api_root) not in sys.path:
        sys.path.insert(0, str(api_root))

    from fastapi.testclient import TestClient  # type: ignore
    from app.main import app  # type: ignore

    client = TestClient(app)
    poll_interval_s = max(0.1, args.poll_interval_ms / 1000.0)
    timeout_sec = max(20, args.timeout_sec)

    def _run_one(index: int) -> BenchResult:
        user_id = f"bench-user-{index % 12}"
        payload = {
            "input_modes": ["text", "voice"],
            "text": f"异步压测样本 {index}",
            "audio_path": str(wav_path),
            "client": {
                "platform": "benchmark",
                "version": "1.0.0",
                "user_id": user_id,
            },
        }
        headers = {"X-EC-USER-ID": user_id}
        start = time.perf_counter()

        try:
            create_resp = client.post("/api/analyze/async", json=payload, headers=headers)
        except Exception as exc:  # pragma: no cover
            return BenchResult(False, time.perf_counter() - start, f"create exception: {exc}")

        if create_resp.status_code != 200:
            return BenchResult(False, time.perf_counter() - start, f"create status={create_resp.status_code}")

        task_id = str(create_resp.json().get("task_id") or "").strip()
        if not task_id:
            return BenchResult(False, time.perf_counter() - start, "missing task_id")

        deadline = time.perf_counter() + timeout_sec
        last_detail = ""
        while time.perf_counter() < deadline:
            status_resp = client.get(f"/api/analyze/async/{task_id}", headers=headers)
            if status_resp.status_code != 200:
                last_detail = f"poll status={status_resp.status_code}"
                time.sleep(poll_interval_s)
                continue

            body = status_resp.json()
            status = str(body.get("status") or "").strip().lower()
            if status == "succeeded":
                return BenchResult(True, time.perf_counter() - start, "ok")
            if status == "failed":
                detail = str(body.get("error_detail") or "").strip() or "failed without detail"
                return BenchResult(False, time.perf_counter() - start, detail)

            last_detail = status or "unknown"
            time.sleep(poll_interval_s)

        return BenchResult(False, time.perf_counter() - start, f"timeout waiting task, last={last_detail}")

    t0 = time.perf_counter()
    results: list[BenchResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        futures = [executor.submit(_run_one, i) for i in range(max(1, args.requests))]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    total_elapsed = time.perf_counter() - t0

    total = len(results)
    successes = [item for item in results if item.success]
    failures = [item for item in results if not item.success]
    success_rate = (len(successes) / total * 100.0) if total else 0.0
    latencies = [item.latency_s for item in successes]
    p50 = _pct(latencies, 50)
    p90 = _pct(latencies, 90)
    p95 = _pct(latencies, 95)

    failure_top: dict[str, int] = {}
    for item in failures:
        key = item.detail[:160]
        failure_top[key] = failure_top.get(key, 0) + 1
    failure_rank = sorted(failure_top.items(), key=lambda pair: pair[1], reverse=True)[:5]

    lines: list[str] = []
    lines.append("# 异步分析压测报告（本地基线）")
    lines.append("")
    lines.append(f"- 执行时间(UTC): `{_iso_now_utc()}`")
    lines.append(f"- 代码仓库: `{repo_root}`")
    lines.append("- 压测方式: `FastAPI TestClient + 并发轮询`")
    lines.append(f"- 请求总数: `{total}`")
    lines.append(f"- 并发度: `{max(1, args.concurrency)}`")
    lines.append(f"- 单任务超时: `{timeout_sec}s`")
    lines.append(f"- 轮询间隔: `{poll_interval_s:.3f}s`")
    lines.append(f"- 压测总耗时: `{total_elapsed:.3f}s`")
    lines.append("")
    lines.append("## 结果指标")
    lines.append("")
    lines.append(f"- 最终成功率: `{success_rate:.2f}%` (`{len(successes)}/{total}`)")
    lines.append(f"- `P50`: `{p50:.3f}s`")
    lines.append(f"- `P90`: `{p90:.3f}s`")
    lines.append(f"- `P95`: `{p95:.3f}s`")
    lines.append("")
    lines.append("## 失败统计（Top）")
    lines.append("")
    if failure_rank:
        lines.append("| 失败原因 | 次数 |")
        lines.append("|---|---:|")
        for reason, count in failure_rank:
            lines.append(f"| {reason} | {count} |")
    else:
        lines.append("- 无失败。")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(
        {
            "requests": total,
            "concurrency": max(1, args.concurrency),
            "success_rate": round(success_rate, 2),
            "p50": round(p50, 3),
            "p90": round(p90, 3),
            "p95": round(p95, 3),
            "report": str(report_path),
        },
        ensure_ascii=False,
    ))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
