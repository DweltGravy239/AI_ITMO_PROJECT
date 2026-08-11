"""Аудит-лог решений в формате JSON Lines (append-only).

Каждое автоматическое решение сохраняется и может быть проаудировано —
это требование ТЗ. В целевой системе — append-only хранилище
(ClickHouse / отдельная таблица), здесь — файл decisions.log.jsonl.
"""
import json
import os
from datetime import datetime, timezone

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "decisions.log.jsonl")


def log_decision(record: dict) -> None:
    record = dict(record)
    record["ts"] = datetime.now(timezone.utc).isoformat()
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def reset_log() -> None:
    if os.path.exists(LOG_PATH):
        os.remove(LOG_PATH)
