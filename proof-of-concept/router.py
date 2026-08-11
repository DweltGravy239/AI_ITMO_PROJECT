"""Маршрутизация: оценка риска и предварительное решение (pre-gate).

Логика намеренно детерминированная и аудируемая: рискованные категории
всегда уходят человеку, LLM здесь ничего не «решает». Финальный выбор
AUTO_CLOSE vs SUGGEST делается в pipeline после генерации черновика.
"""
import re
from . import config

# Ключевые слова юридических/жалобных обращений (эскалируем как high-risk).
_LEGAL_RE = re.compile(r"жалоб|суд|юрист|lawyer|компенсац|claim|роспотребнадзор", re.I)


def assess_risk(topic: str, pii_flags, injection: bool, text: str) -> dict:
    reasons = []
    if injection:
        reasons.append("prompt_injection")
    if topic in config.RISKY_TOPICS:
        reasons.append(f"risky_topic:{topic}")
    if "card" in pii_flags:
        reasons.append("payment_pii")
    if _LEGAL_RE.search(text):
        reasons.append("legal_complaint")
    return {"level": "high" if reasons else "low", "reasons": reasons}


def pre_gate(topic, confidence, risk, grounded_ok) -> tuple:
    """Возвращает (decision, reason), где decision ∈ {ESCALATE, CANDIDATE}.

    ESCALATE — жёсткая эскалация оператору ещё до генерации ответа.
    CANDIDATE — кандидат на автоматизацию/ассист, идём генерировать черновик.
    """
    if "prompt_injection" in risk["reasons"]:
        return "ESCALATE", "prompt_injection"
    if topic == "unknown" or confidence < config.ASSIST_MIN_CONFIDENCE:
        return "ESCALATE", "low_confidence"
    if risk["level"] == "high":
        return "ESCALATE", "risky_category_human_in_the_loop"
    if not grounded_ok:
        return "ESCALATE", "no_kb_grounding"
    return "CANDIDATE", "eligible_for_automation"
