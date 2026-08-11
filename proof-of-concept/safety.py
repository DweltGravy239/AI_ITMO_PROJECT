"""Слой безопасности.

  * detect_injection  — грубая детекция prompt injection по паттернам.
    В целевой системе — отдельный классификатор + строгий разбор структуры
    промпта (данные пользователя никогда не попадают в «инструкцию» LLM).
  * output_safety_ok  — проверка, что в черновике не осталось сырых PII
    и запрещённых конструкций перед отправкой пользователю.
  * grounded          — проверка, что ответ опирается на найденный фрагмент
    KB (для мок-LLM тривиальна; для реального LLM — проверка цитируемости).
"""
import re

_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous",
    r"disregard\s+(all\s+)?previous",
    r"system\s+prompt",
    r"reveal\s+your",
    r"you\s+are\s+now",
    r"jailbreak",
    r"игнорируй\s+(все|всё)?",
    r"забудь\s+(все|всё)?\s+инструкци",
    r"переопредели",
    r"притворись,?\s+что",
]


def detect_injection(text: str):
    low = text.lower()
    hits = [p for p in _INJECTION_PATTERNS if re.search(p, low)]
    return (len(hits) > 0, hits)


def output_safety_ok(draft) -> bool:
    """False, если в черновике осталась сырая PII (например, номер карты)."""
    if not draft:
        return True
    if re.search(r"(?:\d[ \-]?){13,19}", draft):
        return False
    return True


def grounded(retrieved, min_sim: float) -> bool:
    """Есть ли в KB достаточно близкий фрагмент, чтобы на него опираться."""
    return bool(retrieved) and retrieved[0]["score"] >= min_sim
