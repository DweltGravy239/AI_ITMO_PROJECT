"""Нормализация входящего тикета.

Что делает на «горячем» пути ДО любого вызова внешних сервисов:
  * определяет язык (наивно, по доле кириллицы);
  * редактирует PII (карты, e-mail, телефоны) — чтобы сырые персональные
    данные не ушли во внешний LLM API и не попали в логи;
  * считает ключ дедупликации (для схлопывания дублей при инцидентах).

В целевой системе PII-детекция — это связка regex + NER-модель;
здесь только regex как упрощение (см. docs/ml.md).
"""
import re
import hashlib

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+", re.UNICODE)
# Последовательность из 13–19 цифр (с пробелами/дефисами) — кандидат в номер карты
_CARD_RE = re.compile(r"(?:\d[ \-]?){13,19}")
# Телефоноподобная последовательность из 7–15 цифр
_PHONE_RE = re.compile(r"\+?\d[\d\-\s()]{5,}\d")


def detect_lang(text: str) -> str:
    """Очень грубое определение языка: ru, если кириллицы больше, иначе en."""
    cyr = sum(1 for c in text if "а" <= c.lower() <= "я" or c in "ёЁ")
    lat = sum(1 for c in text if "a" <= c.lower() <= "z")
    return "ru" if cyr >= lat else "en"


def redact_pii(text: str):
    """Возвращает (очищенный_текст, список_типов_найденных_PII)."""
    flags = []

    def _card(m):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19:
            flags.append("card")
            return "[CARD]"
        return m.group()

    # Порядок важен: карты редактируем раньше телефонов (перекрывающиеся паттерны).
    text = _CARD_RE.sub(_card, text)

    if _EMAIL_RE.search(text):
        flags.append("email")
    text = _EMAIL_RE.sub("[EMAIL]", text)

    def _phone(m):
        digits = re.sub(r"\D", "", m.group())
        if 7 <= len(digits) <= 15:
            flags.append("phone")
            return "[PHONE]"
        return m.group()

    text = _PHONE_RE.sub(_phone, text)
    return text, sorted(set(flags))


def dedup_key(text: str) -> str:
    """Ключ дедупликации по нормализованному тексту (для схлопывания дублей)."""
    norm = re.sub(r"\s+", " ", text.lower()).strip()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]


def normalize(text: str) -> dict:
    lang = detect_lang(text)
    redacted, pii = redact_pii(text)
    return {
        "lang": lang,
        "redacted": redacted,
        "pii_flags": pii,
        "dedup_key": dedup_key(redacted),
    }
