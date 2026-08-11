"""Классификация темы тикета и оценка уверенности.

Это BASELINE на ключевых словах — сознательное упрощение. В целевой
системе тема определяется откалиброванным ML-классификатором
(TF-IDF+linear как baseline → дообученный многоязычный трансформер),
а уверенность берётся из калиброванных вероятностей (см. docs/ml.md).

Здесь уверенность — это сатурирующая функция от числа совпавших ключевых
слов с поправкой на «отрыв» лучшей темы от второй (мера неоднозначности).
"""
import math
import re

_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]+", re.UNICODE)

# Ключевые слова по темам (ru + en). Мультиязычность — нарочно, каналы разные.
TOPIC_KEYWORDS = {
    "password_reset":   ["пароль", "password", "войти", "войду", "login", "восстанов",
                          "reset", "забыл", "доступ", "sign in"],
    "invoice":          ["счет", "счёт", "invoice", "чек", "receipt", "квитанц",
                          "оплата документ", "платеж", "billing"],
    "delivery_status":  ["доставка", "заказ", "delivery", "order", "трек", "tracking",
                          "статус", "где мой", "посылк"],
    "app_issue":        ["приложение", "app", "вылетает", "crash", "открывается",
                          "обновлени", "update", "зависает", "не работает приложение"],
    "refund":           ["верните", "вернуть", "возврат", "refund", "деньги обратно",
                          "money back", "средства", "чарджбэк", "chargeback"],
    "account_deletion": ["удалите аккаунт", "удалить аккаунт", "delete account",
                          "удалите мои данные", "удалить данные", "удалите профиль"],
    "data_request":     ["персональные данные", "personal data", "gdpr", "152-фз",
                          "запрос данных", "право на забвение"],
    "security":         ["взлом", "hacked", "2fa", "двухфактор", "фрод", "fraud",
                          "подозрительн", "мошенник", "unauthorized"],
}


def _tokens(text: str):
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def classify(text: str) -> dict:
    low = text.lower()
    scores = {}
    for topic, kws in TOPIC_KEYWORDS.items():
        hit = sum(1 for kw in kws if kw in low)
        if hit:
            scores[topic] = hit

    if not scores:
        return {"topic": "unknown", "confidence": 0.0, "scores": {}}

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_topic, best = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0

    # Сатурирующая уверенность от силы совпадения.
    base = 1.0 - math.exp(-0.9 * best)        # 1 совпадение≈0.59, 2≈0.83, 3≈0.93
    # Поправка на неоднозначность: чем ближе вторая тема, тем ниже уверенность.
    margin = (best - second) / best
    confidence = round(base * (0.6 + 0.4 * margin), 3)

    return {"topic": best_topic, "confidence": confidence, "scores": scores}
