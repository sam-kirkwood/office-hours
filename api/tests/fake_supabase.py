"""Minimal fake Supabase client for tests.

Records the call chain (table, op, filters, payload) and returns canned data
per (table, op) via responders the test registers up front.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class CapturedCall:
    table: str
    op: str  # "select" | "insert" | "upsert"
    filters: list[tuple]
    payload: Any | None


@dataclass
class FakeResult:
    data: list[dict[str, Any]]


class FakeQuery:
    def __init__(self, table: str, op: str, client: FakeSupabase) -> None:
        self._table = table
        self._op = op
        self._filters: list[tuple] = []
        self._payload: Any | None = None
        self._client = client

    # selects
    def select(self, *_args, **_kwargs) -> FakeQuery:
        return self

    def eq(self, col: str, val: Any) -> FakeQuery:
        self._filters.append(("eq", col, val))
        return self

    def is_(self, col: str, val: Any) -> FakeQuery:
        self._filters.append(("is_", col, val))
        return self

    def ilike(self, col: str, val: Any) -> FakeQuery:
        self._filters.append(("ilike", col, val))
        return self

    def in_(self, col: str, val: Any) -> FakeQuery:
        self._filters.append(("in_", col, val))
        return self

    def contains(self, col: str, val: Any) -> FakeQuery:
        self._filters.append(("contains", col, val))
        return self

    def lt(self, col: str, val: Any) -> FakeQuery:
        self._filters.append(("lt", col, val))
        return self

    def lte(self, col: str, val: Any) -> FakeQuery:
        self._filters.append(("lte", col, val))
        return self

    def gt(self, col: str, val: Any) -> FakeQuery:
        self._filters.append(("gt", col, val))
        return self

    def gte(self, col: str, val: Any) -> FakeQuery:
        self._filters.append(("gte", col, val))
        return self

    def text_search(self, col: str, query: str, **_kwargs: Any) -> FakeQuery:
        self._filters.append(("text_search", col, query))
        return self

    def or_(self, filter_string: str) -> FakeQuery:
        self._filters.append(("or_", None, filter_string))
        return self

    def limit(self, _n: int) -> FakeQuery:
        return self

    def order(self, _col: str, **_kwargs) -> FakeQuery:
        return self

    def single(self) -> FakeQuery:
        return self

    # terminal
    def execute(self) -> FakeResult:
        return self._client._dispatch(self)


class FakeTable:
    def __init__(self, name: str, client: FakeSupabase) -> None:
        self._name = name
        self._client = client

    def select(self, *args, **kwargs) -> FakeQuery:
        return FakeQuery(self._name, "select", self._client).select(*args, **kwargs)

    def insert(self, payload: Any) -> FakeQuery:
        q = FakeQuery(self._name, "insert", self._client)
        q._payload = payload
        return q

    def update(self, payload: Any) -> FakeQuery:
        q = FakeQuery(self._name, "update", self._client)
        q._payload = payload
        return q

    def upsert(self, payload: Any, **_kwargs: Any) -> FakeQuery:
        q = FakeQuery(self._name, "upsert", self._client)
        q._payload = payload
        return q

    def delete(self) -> FakeQuery:
        return FakeQuery(self._name, "delete", self._client)



class FakeSupabase:
    def __init__(self) -> None:
        self.calls: list[CapturedCall] = []
        self._responders: dict[tuple[str, str], Callable[[CapturedCall], Any]] = {}

    def table(self, name: str) -> FakeTable:
        return FakeTable(name, self)

    def respond(
        self, table: str, op: str, responder: Callable[[CapturedCall], list[dict] | Exception]
    ) -> None:
        self._responders[(table, op)] = responder

    def _dispatch(self, query: FakeQuery) -> FakeResult:
        call = CapturedCall(
            table=query._table,
            op=query._op,
            filters=list(query._filters),
            payload=query._payload,
        )
        self.calls.append(call)
        responder = self._responders.get((call.table, call.op))
        if responder is None:
            return FakeResult(data=[])
        result = responder(call)
        if isinstance(result, Exception):
            raise result
        return FakeResult(data=result)
