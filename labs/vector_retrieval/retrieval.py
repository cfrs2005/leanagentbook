"""Transparent retrieval primitives; no labels are accepted by rankers."""
import math
import re
from collections import Counter, defaultdict


def tokens(text):
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower())


def _pair(a, b):
    if not a or len(a) != len(b):
        raise ValueError("Vectors must have equal, nonzero dimensions")
    if not all(math.isfinite(v) for v in (*a, *b)):
        raise ValueError("Vectors must be finite")


def dot(a, b):
    _pair(a, b)
    return sum(x * y for x, y in zip(a, b))


def normalize(a):
    _pair(a, a)
    norm = math.sqrt(dot(a, a))
    if norm == 0:
        raise ValueError("Zero vector has no cosine direction")
    return [x / norm for x in a]


def cosine(a, b):
    return dot(normalize(a), normalize(b))


def l2(a, b):
    _pair(a, b)
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def ranked(scores):
    if not all(math.isfinite(v) for v in scores.values()):
        raise ValueError("Scores must be finite")
    return sorted(scores, key=lambda key: (-scores[key], key))


class BM25:
    def __init__(self, documents, k1=1.2, b=0.75):
        if not documents or k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("Invalid corpus or BM25 parameters")
        self.counts = {key: Counter(tokens(text)) for key, text in documents.items()}
        self.lengths = {key: sum(value.values()) for key, value in self.counts.items()}
        self.avg = sum(self.lengths.values()) / len(documents)
        if self.avg == 0:
            raise ValueError("Corpus contains no tokens")
        self.df = Counter(term for count in self.counts.values() for term in count)
        self.k1, self.b = k1, b

    def scores(self, query):
        result = {}
        for key, count in self.counts.items():
            score = 0.0
            for term in set(tokens(query)):
                freq = count[term]
                if not freq:
                    continue
                idf = math.log(1 + (len(self.counts) - self.df[term] + 0.5) / (self.df[term] + 0.5))
                length = 1 - self.b + self.b * self.lengths[key] / self.avg
                score += idf * freq * (self.k1 + 1) / (freq + self.k1 * length)
            result[key] = score
        return result


def rrf(lists, constant=60):
    if not math.isfinite(constant) or constant < 0:
        raise ValueError("RRF constant must be finite and nonnegative")
    scores = defaultdict(float)
    for items in lists:
        if len(items) != len(set(items)):
            raise ValueError("Each ranked list must contain unique IDs")
        for rank, key in enumerate(items, 1):
            scores[key] += 1 / (constant + rank)
    return ranked(scores)


def weighted_fusion(left, right, weight=0.5):
    if not 0 <= weight <= 1:
        raise ValueError("Weight must lie in [0, 1]")
    def scale(scores):
        ranked(scores)
        if not scores:
            return {}
        low, high = min(scores.values()), max(scores.values())
        return {key: (value - low) / (high - low) if high > low else 0.0
                for key, value in scores.items()}
    a, b = scale(left), scale(right)
    return ranked({key: weight * a.get(key, 0) + (1 - weight) * b.get(key, 0)
                   for key in a.keys() | b.keys()})


# Hand-authored concepts, not learned embeddings. Used only for offline mechanics.
CONCEPTS = [
    "password credential login signin authentication account reset recover",
    "battery power energy charging charger dock recharge",
    "network wireless wifi connection disconnect offline router",
    "payment invoice charge bill billing refund money",
    "delete deletion erase remove retention privacy data",
    "backup restore recovery snapshot disaster",
    "robot machine motor wheel motion stuck movement",
    "certificate tls ssl encryption secure expired",
    "storage disk capacity full space volume",
    "permission access role tenant authorization forbidden",
    "temperature heat thermal hot cool overheating",
    "retry duplicate idempotency request timeout",
]


def teaching_vector(text):
    words = Counter(tokens(text))
    # A constant component makes unknown text defined but uninformative.
    return normalize([0.1] + [float(sum(words[w] for w in group.split())) for group in CONCEPTS])


def teaching_rerank(query, candidates, documents):
    """Lexical overlap demonstration, explicitly not a Cross Encoder."""
    query_words = set(tokens(query))
    scores = {}
    for key in candidates:
        words = set(tokens(documents[key]))
        scores[key] = len(query_words & words) / max(1, len(query_words | words))
    return ranked(scores)


def metrics(order, relevance, k=5):
    if k < 1 or len(order) != len(set(order)):
        raise ValueError("Invalid cutoff or duplicate document")
    relevant = {key for key, grade in relevance.items() if grade > 0}
    if not relevant:
        raise ValueError("No positive judgments: evaluate abstention separately")
    top = order[:k]
    recall = len(set(top) & relevant) / len(relevant)
    rr = next((1 / rank for rank, key in enumerate(top, 1) if key in relevant), 0)
    def dcg(grades):
        return sum((2 ** grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(grades, 1))
    ideal = dcg(sorted(relevance.values(), reverse=True)[:k])
    return {"recall": recall, "mrr": rr, "ndcg": dcg([relevance.get(key, 0) for key in top]) / ideal}
