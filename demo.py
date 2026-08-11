#!/usr/bin/env python3
"""Демонстрация PoC: end-to-end happy path + fallback/risky path.

Запуск:  python demo.py
Демонстрирует все 6 шагов сценария из ТЗ, включая обязательный шаг №6 —
эскалацию рискованного/low-confidence тикета оператору вместо автозакрытия,
а также корректную деградацию при недоступности LLM.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from poc.pipeline import process_ticket, load_kb  # noqa: E402
from poc import config, logstore                   # noqa: E402

ACTION_LABEL = {
    "AUTO_CLOSE": "🟢 АВТОЗАКРЫТИЕ (ответ ушёл пользователю)",
    "SUGGEST":    "🟡 ЧЕРНОВИК ОПЕРАТОРУ (suggest-режим)",
    "ESCALATE":   "🔴 ЭСКАЛАЦИЯ ОПЕРАТОРУ (не закрываем автоматически)",
    "SHADOW":     "⚪ SHADOW (действие только залогировано)",
}


def show(rec: dict):
    print(f"[{rec['ticket_id']}] канал={rec['channel']} язык={rec['lang']}")
    print(f"   вход (после PII-редактирования): {rec['input_redacted']}")
    print(f"   тема={rec['topic']}  уверенность={rec['confidence']}  риск={rec['risk_level']}")
    if rec["risk_reasons"]:
        print(f"   риск-причины: {', '.join(rec['risk_reasons'])}")
    if rec["pii_flags"]:
        print(f"   PII отредактированы: {', '.join(rec['pii_flags'])}")
    if rec["injection_hits"]:
        print(f"   ⚠ prompt injection: {rec['injection_hits']}")
    top = rec["retrieved"][0] if rec["retrieved"] else None
    if top:
        print(f"   найдено в KB: {top['id']} (близость {top['score']})")
    print(f"   → {ACTION_LABEL.get(rec['action'], rec['action'])}  [{rec['reason']}]")
    if rec["draft"]:
        first_line = rec["draft"].splitlines()[0]
        print(f"   черновик: {first_line} …")
    print()


def main():
    logstore.reset_log()
    load_kb()

    with open(os.path.join(config.DATA_DIR, "tickets.json"), encoding="utf-8") as f:
        tickets = json.load(f)

    print("=" * 70)
    print(f"РЕЖИМ: {config.DEFAULT_MODE}  (LLM доступен)")
    print("=" * 70)
    for t in tickets:
        show(process_ticket(t))

    # --- Демонстрация деградации: тот же безопасный тикет при отказе LLM -----
    print("=" * 70)
    print("СЦЕНАРИЙ ДЕГРАДАЦИИ: LLM недоступен (SIMULATE_LLM_DOWN=1)")
    print("Ожидаемо: даже безопасный FAQ не автозакрывается, а уходит оператору")
    print("=" * 70)
    os.environ["SIMULATE_LLM_DOWN"] = "1"
    show(process_ticket(tickets[0]))  # t1 — обычно AUTO_CLOSE, теперь ESCALATE
    os.environ["SIMULATE_LLM_DOWN"] = "0"

    print(f"Аудит-лог решений записан в: {os.path.relpath(logstore.LOG_PATH)}")


if __name__ == "__main__":
    main()
