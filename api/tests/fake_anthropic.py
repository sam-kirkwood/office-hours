"""Minimal fake Anthropic client for tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeUsage:
    input_tokens: int = 100
    output_tokens: int = 200
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class FakeResponse:
    content: list[FakeTextBlock]
    usage: FakeUsage = field(default_factory=FakeUsage)


def make_response(text: str, **usage_overrides) -> FakeResponse:
    return FakeResponse(content=[FakeTextBlock(text=text)], usage=FakeUsage(**usage_overrides))


class FakeMessages:
    def __init__(self) -> None:
        self.queued: list[FakeResponse] = []
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs) -> FakeResponse:
        self.calls.append(kwargs)
        if not self.queued:
            raise AssertionError("FakeMessages.create called with no queued response")
        return self.queued.pop(0)


class FakeAnthropic:
    def __init__(self) -> None:
        self.messages = FakeMessages()

    def queue(self, text: str, **usage_overrides) -> None:
        self.messages.queued.append(make_response(text, **usage_overrides))
