"""Authoritative SQLite event store (BUILD_SPEC §7.1).

Every event and any world revision it causes are written in one SQLite transaction. Events are
hash-chained: ``event_hash = sha256(canonical(envelope without event_hash))`` and each event carries
the previous event's hash (genesis: 64 zeros). The first event (``run_started``) binds the frozen
run manifest by hash. JSONL is an export of this store, never a competing authority.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..canonical import canonical_str, sha256_bytes, sha256_obj, strict_json_loads
from ..contracts.events import (
    EVENT_ACTORS,
    GENESIS_PREV_HASH,
    EventEnvelope,
    validate_payload,
)

SCHEMA = """
CREATE TABLE runs (
  run_id TEXT PRIMARY KEY,
  manifest_json TEXT NOT NULL,
  manifest_sha256 TEXT NOT NULL
);
CREATE TABLE events (
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  sequence INTEGER NOT NULL,
  envelope_json TEXT NOT NULL,
  event_type TEXT NOT NULL,
  event_hash TEXT NOT NULL,
  PRIMARY KEY (run_id, sequence)
);
CREATE TABLE revisions (
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  resource_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  value_json TEXT NOT NULL,
  value_sha256 TEXT NOT NULL,
  event_sequence INTEGER,
  PRIMARY KEY (run_id, resource_id, revision)
);
CREATE TABLE artifacts (
  sha256 TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  body BLOB NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass(frozen=True)
class PendingEvent:
    event_type: str
    actor_kind: str
    tick: int
    payload: dict[str, Any]


@dataclass(frozen=True)
class PendingRevision:
    resource_id: str
    revision: int
    value: Any
    # index into the same batch's events list of the resource_revised event
    event_index: int


def compute_event_hash(envelope_without_hash: dict[str, Any]) -> str:
    return sha256_obj(envelope_without_hash)


class EvidenceStore:
    """One SQLite file. Readers use ``open_readonly``; they never change state."""

    def __init__(self, path: Path, *, clock: Callable[[], str] = utc_now, _readonly: bool = False):
        self.path = Path(path)
        self.clock = clock
        if _readonly:
            uri = f"{self.path.resolve().as_uri()}?mode=ro"
            self.conn = sqlite3.connect(uri, uri=True, isolation_level=None)
        else:
            if self.path.exists():
                raise FileExistsError(f"refusing to reuse an existing store: {self.path}")
            self.conn = sqlite3.connect(self.path, isolation_level=None)
            self.conn.executescript(SCHEMA)
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._readonly = _readonly

    @classmethod
    def open_readonly(cls, path: Path) -> EvidenceStore:
        return cls(path, _readonly=True)

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------ writes

    def begin_run(self, run_id: str, manifest: dict[str, Any], initial: dict[str, Any]) -> str:
        """Register a run, its frozen manifest and the initial resource revisions."""
        self._require_writable()
        m_sha = sha256_obj(manifest)
        with self._txn():
            self.conn.execute(
                "INSERT INTO runs VALUES (?,?,?)", (run_id, canonical_str(manifest), m_sha)
            )
            for rid, st in initial.items():
                self.conn.execute(
                    "INSERT INTO revisions VALUES (?,?,?,?,?,NULL)",
                    (run_id, rid, st["revision"], canonical_str(st["value"]),
                     sha256_obj(st["value"])),
                )
        return m_sha

    def put_artifact(self, kind: str, body: bytes) -> str:
        self._require_writable()
        h = sha256_bytes(body)
        with self._txn():
            self.conn.execute(
                "INSERT OR IGNORE INTO artifacts VALUES (?,?,?)", (h, kind, body)
            )
        return h

    def append(
        self,
        run_id: str,
        events: Sequence[PendingEvent],
        revisions: Sequence[PendingRevision] = (),
    ) -> list[dict[str, Any]]:
        """Append events (and the revisions they cause) atomically. Returns stored envelopes."""
        self._require_writable()
        stored: list[dict[str, Any]] = []
        with self._txn():
            row = self.conn.execute(
                "SELECT sequence, event_hash FROM events WHERE run_id=? "
                "ORDER BY sequence DESC LIMIT 1",
                (run_id,),
            ).fetchone()
            seq, prev = (row[0] + 1, row[1]) if row else (0, GENESIS_PREV_HASH)
            for ev in events:
                if ev.actor_kind not in EVENT_ACTORS.get(ev.event_type, ()):
                    raise ValueError(f"{ev.event_type} may not be emitted by {ev.actor_kind}")
                validate_payload(ev.event_type, ev.payload)
                env = {
                    "schema_version": "1.0",
                    "run_id": run_id,
                    "sequence": seq,
                    "event_type": ev.event_type,
                    "timestamp_utc": self.clock(),
                    "tick": ev.tick,
                    "actor_kind": ev.actor_kind,
                    "payload": ev.payload,
                    "prev_hash": prev,
                }
                env["event_hash"] = compute_event_hash(env)
                EventEnvelope.model_validate(env, strict=True)
                self.conn.execute(
                    "INSERT INTO events VALUES (?,?,?,?,?)",
                    (run_id, seq, canonical_str(env), ev.event_type, env["event_hash"]),
                )
                stored.append(env)
                prev = env["event_hash"]
                seq += 1
            for rv in revisions:
                ev_seq = stored[rv.event_index]["sequence"]
                if stored[rv.event_index]["event_type"] != "resource_revised":
                    raise ValueError("a revision must be bound to a resource_revised event")
                self.conn.execute(
                    "INSERT INTO revisions VALUES (?,?,?,?,?,?)",
                    (run_id, rv.resource_id, rv.revision, canonical_str(rv.value),
                     sha256_obj(rv.value), ev_seq),
                )
        return stored

    # ------------------------------------------------------------------ reads

    def manifest(self, run_id: str) -> tuple[dict[str, Any], str]:
        row = self.conn.execute(
            "SELECT manifest_json, manifest_sha256 FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return strict_json_loads(row[0]), row[1]

    def events(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT envelope_json FROM events WHERE run_id=? ORDER BY sequence", (run_id,)
        ).fetchall()
        return [strict_json_loads(r[0]) for r in rows]

    def revisions(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT resource_id, revision, value_json, value_sha256, event_sequence "
            "FROM revisions WHERE run_id=? ORDER BY resource_id, revision",
            (run_id,),
        ).fetchall()
        return [
            {
                "resource_id": r[0],
                "revision": r[1],
                "value": strict_json_loads(r[2]),
                "value_sha256": r[3],
                "event_sequence": r[4],
            }
            for r in rows
        ]

    def artifact(self, sha: str) -> bytes:
        row = self.conn.execute("SELECT body FROM artifacts WHERE sha256=?", (sha,)).fetchone()
        if row is None:
            raise KeyError(sha)
        return bytes(row[0])

    def artifacts(self) -> list[tuple[str, str, bytes]]:
        return [
            (r[0], r[1], bytes(r[2]))
            for r in self.conn.execute("SELECT sha256, kind, body FROM artifacts ORDER BY sha256")
        ]

    def run_ids(self) -> list[str]:
        return [r[0] for r in self.conn.execute("SELECT run_id FROM runs ORDER BY run_id")]

    # ------------------------------------------------------------------ internals

    def _require_writable(self) -> None:
        if self._readonly:
            raise PermissionError("read-only store")

    class _Txn:
        def __init__(self, conn: sqlite3.Connection) -> None:
            self.conn = conn

        def __enter__(self) -> None:
            self.conn.execute("BEGIN IMMEDIATE")

        def __exit__(self, exc_type, exc, tb) -> None:
            if exc_type is None:
                self.conn.execute("COMMIT")
            else:
                self.conn.execute("ROLLBACK")

    def _txn(self) -> EvidenceStore._Txn:
        return EvidenceStore._Txn(self.conn)
