"""Генерация черновика ответа (медленный, асинхронный путь).

МОК-LLM: черновик собирается из найденного фрагмента KB. Это упрощение —
в целевой системе здесь RAG-вызов LLM, где retrieved-фрагменты подаются
как контекст (grounding), а данные пользователя изолированы от инструкции.

Отказ LLM моделируется переменной окружения SIMULATE_LLM_DOWN=1 — чтобы
продемонстрировать корректную деградацию (см. fallback-путь в demo.py).
Реальный вызов LLM можно включить через USE_REAL_LLM=1 (оставлен как
заглушка, по умолчанию выключен, чтобы PoC работал офлайн без ключей).
"""
import os


def _llm_available() -> bool:
    return os.getenv("SIMULATE_LLM_DOWN", "0") != "1"


def _real_llm_call(prompt: str) -> str:  # pragma: no cover - опциональная ветка
    """Заглушка реального вызова LLM. По умолчанию не используется."""
    raise NotImplementedError(
        "Реальный LLM отключён в PoC. Включается через USE_REAL_LLM=1 "
        "и реализацию вызова провайдера здесь."
    )


def generate_draft(retrieved, lang: str = "ru") -> dict:
    """Возвращает {draft, llm_used, llm_available}."""
    if not _llm_available():
        return {"draft": None, "llm_used": False, "llm_available": False}

    if not retrieved:
        return {"draft": None, "llm_used": False, "llm_available": True}

    top = retrieved[0]["doc"]
    body = top["body"]

    if os.getenv("USE_REAL_LLM", "0") == "1":  # pragma: no cover
        prompt = f"Ответь пользователю, опираясь только на факт:\n{body}"
        draft = _real_llm_call(prompt)
        return {"draft": draft, "llm_used": True, "llm_available": True}

    # Мок-генерация: шаблон + факт из KB.
    if lang == "en":
        draft = (f"Hi! Thanks for reaching out.\n\n{body}\n\n"
                 f"If this doesn't solve it, just reply and an agent will help.\n\n"
                 f"[auto-draft · grounded on KB:{top['id']}]")
    else:
        draft = (f"Здравствуйте! Спасибо за обращение.\n\n{body}\n\n"
                 f"Если это не помогло — ответьте на сообщение, и подключится оператор.\n\n"
                 f"[авто-черновик · опора на KB:{top['id']}]")
    return {"draft": draft, "llm_used": True, "llm_available": True}
