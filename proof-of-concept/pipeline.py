"""Оркестрация обработки одного тикета (end-to-end).

Порядок ровно как в целевой архитектуре (docs/architecture.md):
  normalize → classify → (injection) → retrieve → pre-gate → [generate → safety]
  → финальное действие → запись в аудит-лог.

Возвращает запись-решение (dict), пригодную и для лога, и для печати.
"""
import json
import os

from . import config, normalize, classify, retrieve, generate, safety, router, logstore

_KB_CACHE = None


def load_kb():
    global _KB_CACHE
    if _KB_CACHE is None:
        with open(os.path.join(config.DATA_DIR, "kb.json"), encoding="utf-8") as f:
            kb = json.load(f)
        # Для ретривера склеиваем заголовок, синонимы-теги и тело.
        # aliases эмулируют многоязычность, которую в целевой системе даёт
        # эмбеддинг-модель; в PoC на TF-IDF без них ломается кросс-язычный поиск.
        docs = [{**a, "text": a["title"] + ". " + a.get("aliases", "") + ". " + a["body"]}
                for a in kb]
        _KB_CACHE = (retrieve.TfidfRetriever(docs), {a["id"]: a for a in kb})
    return _KB_CACHE


def process_ticket(ticket: dict, mode: str = None) -> dict:
    mode = mode or config.DEFAULT_MODE
    retriever, kb_by_id = load_kb()

    raw = ticket["text"]
    norm = normalize.normalize(raw)
    cls = classify.classify(norm["redacted"])
    injection, inj_hits = safety.detect_injection(raw)
    risk = router.assess_risk(cls["topic"], norm["pii_flags"], injection, raw)

    retrieved = retriever.query(norm["redacted"], top_k=3)
    grounded_ok = safety.grounded(retrieved, config.RETRIEVAL_MIN_SIM)

    decision, reason = router.pre_gate(cls["topic"], cls["confidence"], risk, grounded_ok)

    draft = None
    llm_used = False
    llm_available = True

    if decision == "CANDIDATE":
        gen = generate.generate_draft(retrieved, lang=norm["lang"])
        llm_used = gen["llm_used"]
        llm_available = gen["llm_available"]

        if not llm_available or gen["draft"] is None:
            # Деградация: LLM недоступен → не отправляем ничего пользователю,
            # маршрутизируем оператору с приложенным фрагментом KB.
            action, reason = "ESCALATE", "llm_unavailable_degraded"
        elif not safety.output_safety_ok(gen["draft"]):
            action, reason = "ESCALATE", "output_safety_block"
        else:
            draft = gen["draft"]
            is_safe_cat = cls["topic"] in config.AUTOCLOSE_ALLOWLIST
            high_conf = cls["confidence"] >= config.AUTO_CLOSE_MIN_CONFIDENCE
            if mode == "SHADOW":
                action = "SHADOW"
                reason = "would_auto_close" if (is_safe_cat and high_conf) else "would_suggest"
            elif mode == "AUTO" and is_safe_cat and high_conf and risk["level"] == "low":
                action, reason = "AUTO_CLOSE", "safe_category_high_confidence"
            else:
                action, reason = "SUGGEST", "assist_operator"
    else:
        action = "ESCALATE"

    record = {
        "ticket_id": ticket.get("id"),
        "channel": ticket.get("channel"),
        "mode": mode,
        "lang": norm["lang"],
        "topic": cls["topic"],
        "confidence": cls["confidence"],
        "risk_level": risk["level"],
        "risk_reasons": risk["reasons"],
        "pii_flags": norm["pii_flags"],
        "pii_redacted": bool(norm["pii_flags"]),
        "injection_hits": inj_hits,
        "retrieved": [{"id": r["doc"]["id"], "score": r["score"]} for r in retrieved],
        "grounded": grounded_ok,
        "llm_used": llm_used,
        "llm_available": llm_available,
        "action": action,
        "reason": reason,
        # В логе храним уже отредактированный текст — сырые PII не попадают в аудит.
        "input_redacted": norm["redacted"],
        "draft": draft,
    }
    logstore.log_decision(record)
    return record
