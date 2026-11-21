"""Scoped, versioned teaching memory; rule extraction, no model or remote service."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
import sqlite3
import time


VALUES = {
    "language": {"中文", "English"},
    "format": {"表格", "段落", "图解"},
    "units": {"metric", "imperial"},
    "site": {"alpha", "beta", "gamma"},
}
ALIASES = {
    "language": ("language", "语言", "中文", "english"),
    "format": ("format", "格式", "报告", "表格", "图解"),
    "units": ("units", "单位", "公制", "英制"),
    "site": ("site", "站点", "工作地点"),
}


@dataclass(frozen=True)
class Scope:
    tenant: str
    subject: str
    project: str

    def __post_init__(self):
        if any(not isinstance(x, str) or not x.strip() for x in self.args()):
            raise ValueError("Empty scope")

    def args(self):
        return (self.tenant, self.subject, self.project)


class Conflict(ValueError):
    """An explicit correction used an obsolete version."""


def extract(role: str, text: str):
    """Accept a deliberately narrow user-authored syntax, never document instructions."""
    if role != "user" or not isinstance(text, str):
        return None
    match = re.fullmatch(r"(记住|更正)：([a-z]+)=([^\n=]+)", text.strip())
    if not match:
        return None
    action, key, value = match.groups()
    if key not in VALUES or value not in VALUES[key]:
        return None
    return {"key": key, "value": value, "correction": action == "更正"}


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class Memory:
    def __init__(self, path, clock=time.time):
        self.clock = clock
        self.db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA secure_delete=ON;
        CREATE TABLE IF NOT EXISTS memories(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          tenant TEXT NOT NULL, subject TEXT NOT NULL, project TEXT NOT NULL,
          key TEXT NOT NULL, value TEXT NOT NULL, source_id TEXT NOT NULL,
          version INTEGER NOT NULL, state TEXT NOT NULL,
          created REAL NOT NULL, expires REAL NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS one_active
          ON memories(tenant,subject,project,key) WHERE state='active';
        CREATE TABLE IF NOT EXISTS audit(
          seq INTEGER PRIMARY KEY AUTOINCREMENT,
          tenant TEXT NOT NULL, subject TEXT NOT NULL, project TEXT NOT NULL,
          event TEXT NOT NULL, memory_id INTEGER, at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS receipts(
          tenant TEXT NOT NULL, subject TEXT NOT NULL, project TEXT NOT NULL,
          source_id TEXT NOT NULL, PRIMARY KEY(tenant,subject,project,source_id));
        """)

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")

    def event(self, scope, kind, memory_id=None):
        # No source text, key or value enters the audit log.
        self.db.execute("INSERT INTO audit(tenant,subject,project,event,memory_id,at) VALUES(?,?,?,?,?,?)",
                        (*scope.args(), kind, memory_id, self.clock()))

    def ingest(self, scope, role, text, source_id, ttl=3600, expected_version=None):
        candidate = extract(role, text)
        if candidate is None:
            return {"status": "ignored"}
        if (not isinstance(source_id, str) or not re.fullmatch(r"msg-[a-zA-Z0-9-]{1,40}", source_id)
                or type(ttl) not in (int, float) or not math.isfinite(ttl) or ttl <= 0
                or (expected_version is not None and (type(expected_version) is not int or expected_version < 0))):
            raise ValueError("Invalid source, expiry or expected version")
        key, value = candidate["key"], candidate["value"]
        now = self.clock()
        with self.transaction():
            received = self.db.execute("INSERT OR IGNORE INTO receipts VALUES(?,?,?,?)", (*scope.args(), source_id))
            if not received.rowcount:
                return {"status": "already_seen"}
            self.db.execute("UPDATE memories SET state='expired' WHERE tenant=? AND subject=? AND project=? AND expires<=? AND state IN ('active','pending')",
                            (*scope.args(), now))
            old = self.db.execute("SELECT * FROM memories WHERE tenant=? AND subject=? AND project=? AND key=? AND state='active'",
                                  (*scope.args(), key)).fetchone()
            version = old["version"] if old else 0
            if candidate["correction"] and expected_version != version:
                raise Conflict("Read the current version before correcting")
            if old and old["value"] == value:
                self.event(scope, "duplicate", old["id"])
                return {"status": "duplicate", "id": old["id"], "version": version}
            state = "active" if old is None or candidate["correction"] else "pending"
            if state == "pending":
                pending = self.db.execute("SELECT * FROM memories WHERE tenant=? AND subject=? AND project=? AND key=? AND value=? AND state='pending'",
                                          (*scope.args(), key, value)).fetchone()
                if pending:
                    return {"status": "pending", "id": pending["id"], "version": pending["version"]}
            if state == "active":
                self.db.execute("UPDATE memories SET state='superseded' WHERE tenant=? AND subject=? AND project=? AND key=? AND state IN ('active','pending')",
                                (*scope.args(), key))
            max_version = self.db.execute("SELECT COALESCE(MAX(version),0) FROM memories WHERE tenant=? AND subject=? AND project=? AND key=?",
                                          (*scope.args(), key)).fetchone()[0]
            row = self.db.execute("INSERT INTO memories(tenant,subject,project,key,value,source_id,version,state,created,expires) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                  (*scope.args(), key, value, source_id, max_version + 1, state, now, now + ttl))
            self.event(scope, state, row.lastrowid)
            return {"status": state, "id": row.lastrowid, "version": max_version + 1}

    def recall(self, scope, query, limit=4, half_life=86400):
        if (not isinstance(query, str) or type(limit) is not int or limit < 1
                or type(half_life) not in (int, float) or not math.isfinite(half_life) or half_life <= 0):
            raise ValueError("Invalid recall parameters")
        now = self.clock()
        records = self.db.execute("SELECT * FROM memories WHERE tenant=? AND subject=? AND project=? AND state='active' AND expires>?",
                                  (*scope.args(), now)).fetchall()
        result = []
        for row in records:
            matches = sum(term in query.lower() for term in ALIASES[row["key"]])
            if matches:
                result.append({"id": row["id"], "key": row["key"], "value": row["value"],
                               "version": row["version"], "source_id": row["source_id"],
                               "expires": row["expires"],
                               "score": matches * 2 ** (-max(0, now - row["created"]) / half_life)})
        result.sort(key=lambda item: (-item["score"], item["id"]))
        return result[:limit]

    def forget(self, scope, key):
        if key not in VALUES:
            raise ValueError("Unknown memory key")
        with self.transaction():
            cursor = self.db.execute("DELETE FROM memories WHERE tenant=? AND subject=? AND project=? AND key=?",
                                     (*scope.args(), key))
            self.event(scope, "forgotten")
            return cursor.rowcount

    def audit(self, scope):
        return [dict(row) for row in self.db.execute(
            "SELECT seq,event,memory_id,at FROM audit WHERE tenant=? AND subject=? AND project=? ORDER BY seq", scope.args())]

    def context(self, scope, query, system, turns=(), byte_budget=1200, reserve_bytes=200):
        """Build fresh context; budget the exact serialized UTF-8 bytes, not tokens."""
        if (type(byte_budget) is not int or type(reserve_bytes) is not int
                or reserve_bytes < 0 or byte_budget <= reserve_bytes
                or not isinstance(system, str) or not isinstance(query, str)):
            raise ValueError("Invalid budget or required content")
        # Caller supplies complete user/assistant pairs; never keep half a tool exchange.
        if any(not isinstance(t, dict) or set(t) != {"user", "assistant"}
               or any(not isinstance(v, str) for v in t.values()) for t in turns):
            raise ValueError("Expected complete dialogue pairs")
        payload = {"system": system, "current_user": query, "untrusted_memory": [], "history": []}
        fits = lambda: len(encode(payload).encode("utf-8")) + reserve_bytes <= byte_budget
        if not fits():
            raise ValueError("Required context exceeds budget")
        for memory in self.recall(scope, query):
            item = {k: memory[k] for k in ("id", "key", "value", "version", "source_id")}
            payload["untrusted_memory"].append(item)
            if not fits():
                payload["untrusted_memory"].pop()
        # Keep a contiguous recent window; an oversized recent turn stops older inclusion.
        for turn in reversed(turns):
            payload["history"].insert(0, turn)
            if not fits():
                payload["history"].pop(0)
                break
        return {"payload": payload, "used_bytes": len(encode(payload).encode("utf-8")),
                "reserve_bytes": reserve_bytes, "budget_bytes": byte_budget,
                "measurement": "UTF-8 bytes; not model tokens"}


def evaluate(dataset_path):
    """Independent fixture labels score actual recall after each lifecycle event."""
    dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    now = [1000.0]
    store = Memory(":memory:", clock=lambda: now[0])
    results = []
    tp = fp = fn = exact = 0
    try:
        for event in dataset["events"]:
            scope = Scope(*event["scope"])
            now[0] += event.get("advance", 0)
            if event["action"] == "remember":
                store.ingest(scope, event.get("role", "user"), event["text"], event["source"],
                             event.get("ttl", 3600), event.get("expected_version"))
            elif event["action"] == "forget":
                store.forget(scope, event["key"])
            elif event["action"] == "query":
                actual = sorted(f'{r["key"]}={r["value"]}' for r in store.recall(scope, event["query"]))
                gold = event["expected"]
                if len(gold) != len(set(gold)):
                    raise ValueError("Duplicate gold item")
                hits = len(set(actual) & set(gold))
                tp += hits
                fp += len(set(actual) - set(gold))
                fn += len(set(gold) - set(actual))
                exact += set(actual) == set(gold)
                results.append({"query": event["query"], "scope": event["scope"],
                                "actual": actual, "expected": gold, "passed": set(actual) == set(gold)})
            else:
                raise ValueError("Unknown event")
        return {"dataset_version": dataset["version"], "queries": len(results), "exact_matches": exact,
                "true_positive": tp, "false_positive": fp, "false_negative": fn,
                "precision": tp / (tp + fp) if tp + fp else None,
                "recall": tp / (tp + fn) if tp + fn else None,
                "wrong_memory_rate": fp / (tp + fp) if tp + fp else None,
                "measurement": "synthetic, rule extraction and lexical aliases; no LLM", "results": results}
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path(__file__).with_name("dataset.json"))
    args = parser.parse_args()
    result = evaluate(args.dataset)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["queries"] and result["exact_matches"] == result["queries"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
