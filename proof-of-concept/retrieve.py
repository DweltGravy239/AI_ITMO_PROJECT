"""Поиск релевантного фрагмента базы знаний (retrieval).

Здесь — TF-IDF + косинусная близость на чистом Python. Это STAND-IN для
плотных эмбеддингов: в целевой системе документы и запрос кодируются
многоязычной sentence-embedding моделью (например, семейства e5/LaBSE),
а поиск идёт по векторной БД (Qdrant/pgvector). Интерфейс тот же —
`query(text) -> список кандидатов с оценкой близости`, поэтому замена
ретривера не трогает остальную систему (см. docs/architecture.md).
"""
import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]+", re.UNICODE)


def _tokenize(text: str):
    return [t.lower() for t in _TOKEN_RE.findall(text)]


class TfidfRetriever:
    def __init__(self, docs):
        """docs: список dict с ключами id / text (и любыми доп. полями)."""
        self.docs = docs
        toks = [_tokenize(d["text"]) for d in docs]
        n = len(docs)

        df = Counter()
        for t in toks:
            for w in set(t):
                df[w] += 1
        self.idf = {w: math.log((1 + n) / (1 + c)) + 1.0 for w, c in df.items()}

        self._vecs = [self._vectorize(t) for t in toks]
        self._norms = [self._norm(v) for v in self._vecs]

    def _vectorize(self, tokens):
        if not tokens:
            return {}
        tf = Counter(tokens)
        return {w: (c / len(tokens)) * self.idf[w]
                for w, c in tf.items() if w in self.idf}

    @staticmethod
    def _norm(vec):
        return math.sqrt(sum(v * v for v in vec.values())) or 1e-9

    def query(self, text: str, top_k: int = 3):
        q = self._vectorize(_tokenize(text))
        qn = self._norm(q)
        sims = []
        for i, dv in enumerate(self._vecs):
            dot = sum(qv * dv.get(w, 0.0) for w, qv in q.items())
            sims.append((dot / (qn * self._norms[i]), i))
        sims.sort(reverse=True)
        return [{"doc": self.docs[i], "score": round(s, 4)} for s, i in sims[:top_k]]
