import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


_LOCK = threading.RLock()


def _store_path() -> Path:
    raw = (os.getenv("MEDIA_POINTS_STORE_PATH", "/tmp/emotion_culture/media_points_store.json") or "").strip()
    candidate = Path(raw).expanduser()
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def _default_points() -> int:
    raw = (os.getenv("MEDIA_GEN_DEFAULT_POINTS", "12") or "").strip()
    try:
        value = int(raw)
        return max(0, value)
    except ValueError:
        return 12


def _iso_now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_store() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return {"version": 1, "users": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "users": {}}
    if not isinstance(payload, dict):
        return {"version": 1, "users": {}}
    if not isinstance(payload.get("users"), dict):
        payload["users"] = {}
    return payload


def _save_store(payload: dict[str, Any]) -> None:
    path = _store_path()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp.replace(path)


def _ensure_user_bucket(payload: dict[str, Any], user_id: str) -> dict[str, Any]:
    users = payload.setdefault("users", {})
    bucket = users.get(user_id)
    if not isinstance(bucket, dict):
        bucket = {}
        users[user_id] = bucket
    balance = bucket.get("balance")
    if not isinstance(balance, int):
        bucket["balance"] = _default_points()
    ledger = bucket.get("ledger")
    if not isinstance(ledger, list):
        bucket["ledger"] = []
    return bucket


def get_points_balance(user_id: str) -> int:
    normalized_user = (user_id or "").strip()
    if not normalized_user:
        return 0
    with _LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user)
        _save_store(payload)
        return int(bucket.get("balance", 0))


def _find_debit_for_task(ledger: list[dict[str, Any]], task_id: str) -> Optional[dict[str, Any]]:
    for entry in ledger:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "debit":
            continue
        if str(entry.get("task_id") or "").strip() == task_id:
            return entry
    return None


def _has_refund(ledger: list[dict[str, Any]], debit_txn_id: str) -> bool:
    for entry in ledger:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "refund":
            continue
        if str(entry.get("rollback_of") or "").strip() == debit_txn_id:
            return True
    return False


def _find_credit_for_action(ledger: list[dict[str, Any]], action_key: str) -> Optional[dict[str, Any]]:
    for entry in ledger:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "credit":
            continue
        if str(entry.get("action_key") or "").strip() == action_key:
            return entry
    return None


def credit_points_for_action(user_id: str, action_key: str, *, points: int, reason: str) -> dict[str, Any]:
    normalized_user = (user_id or "").strip()
    normalized_action = (action_key or "").strip()
    bonus = max(0, int(points or 0))
    if not normalized_user or not normalized_action:
        raise ValueError("POINTS_CREDIT_INVALID: missing user_id or action_key")
    if bonus <= 0:
        return {"awarded": False, "txn_id": None, "balance": get_points_balance(normalized_user), "points": 0}

    with _LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user)
        ledger = bucket["ledger"]
        existing = _find_credit_for_action(ledger, normalized_action)
        if existing:
            return {
                "awarded": False,
                "txn_id": str(existing.get("txn_id") or ""),
                "balance": int(bucket.get("balance", 0)),
                "points": int(existing.get("amount") or bonus),
            }

        txn_id = f"ptx_cr_{uuid.uuid4().hex[:12]}"
        bucket["balance"] = int(bucket.get("balance", 0)) + bonus
        ledger.append(
            {
                "txn_id": txn_id,
                "type": "credit",
                "action_key": normalized_action,
                "amount": bonus,
                "reason": reason,
                "created_at": _iso_now_utc(),
            }
        )
        _save_store(payload)
        return {"awarded": True, "txn_id": txn_id, "balance": int(bucket["balance"]), "points": bonus}


def deduct_points_for_task(user_id: str, task_id: str, *, points: int, reason: str) -> dict[str, Any]:
    normalized_user = (user_id or "").strip()
    normalized_task = (task_id or "").strip()
    cost = max(0, int(points or 0))
    if not normalized_user or not normalized_task:
        raise ValueError("MEDIA_GEN_POINTS_INVALID: missing user_id or task_id")
    if cost <= 0:
        return {"charged": False, "txn_id": None, "balance": get_points_balance(normalized_user), "points": 0}

    with _LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user)
        ledger = bucket["ledger"]
        existing = _find_debit_for_task(ledger, normalized_task)
        if existing and not _has_refund(ledger, str(existing.get("txn_id") or "")):
            return {
                "charged": False,
                "txn_id": str(existing.get("txn_id") or ""),
                "balance": int(bucket.get("balance", 0)),
                "points": int(existing.get("amount") or cost),
            }

        balance = int(bucket.get("balance", 0))
        if balance < cost:
            raise ValueError(
                f"MEDIA_GEN_POINTS_INSUFFICIENT: need={cost}, current={balance}"
            )

        txn_id = f"ptx_{uuid.uuid4().hex[:12]}"
        bucket["balance"] = balance - cost
        ledger.append(
            {
                "txn_id": txn_id,
                "type": "debit",
                "task_id": normalized_task,
                "amount": cost,
                "reason": reason,
                "created_at": _iso_now_utc(),
            }
        )
        _save_store(payload)
        return {"charged": True, "txn_id": txn_id, "balance": int(bucket["balance"]), "points": cost}


def refund_points_transaction(
    user_id: str,
    debit_txn_id: str,
    *,
    reason: str,
) -> dict[str, Any]:
    normalized_user = (user_id or "").strip()
    normalized_txn = (debit_txn_id or "").strip()
    if not normalized_user or not normalized_txn:
        return {"refunded": False, "balance": get_points_balance(normalized_user)}

    with _LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user)
        ledger = bucket["ledger"]
        debit_entry: Optional[dict[str, Any]] = None
        for entry in ledger:
            if not isinstance(entry, dict):
                continue
            if entry.get("type") != "debit":
                continue
            if str(entry.get("txn_id") or "").strip() == normalized_txn:
                debit_entry = entry
                break

        if not debit_entry:
            return {"refunded": False, "balance": int(bucket.get("balance", 0))}
        if _has_refund(ledger, normalized_txn):
            return {"refunded": False, "balance": int(bucket.get("balance", 0))}

        amount = max(0, int(debit_entry.get("amount") or 0))
        if amount <= 0:
            return {"refunded": False, "balance": int(bucket.get("balance", 0))}

        bucket["balance"] = int(bucket.get("balance", 0)) + amount
        ledger.append(
            {
                "txn_id": f"ptx_ref_{uuid.uuid4().hex[:12]}",
                "type": "refund",
                "rollback_of": normalized_txn,
                "task_id": debit_entry.get("task_id"),
                "amount": amount,
                "reason": reason,
                "created_at": _iso_now_utc(),
            }
        )
        _save_store(payload)
        return {"refunded": True, "balance": int(bucket["balance"]), "points": amount}
