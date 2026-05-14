"""Difficulty selection for Phase 3.

Without struggle signals (Phase 5), the daily problem's difficulty is a pure
function of the user's chosen `surveys.difficulty_curve` and the canonical
topic's `difficulty_band`. Per dev-docs/phase-3-plan.md §Step 7.
"""

from typing import Literal

DifficultyCurve = Literal["gentle", "standard", "aggressive"]
DifficultyBand = Literal["intro", "core", "advanced"]

_TABLE: dict[DifficultyCurve, dict[DifficultyBand, int]] = {
    "gentle":     {"intro": 1, "core": 2, "advanced": 3},
    "standard":   {"intro": 2, "core": 3, "advanced": 4},
    "aggressive": {"intro": 3, "core": 4, "advanced": 5},
}


def difficulty_for(curve: str, band: str) -> int:
    try:
        return _TABLE[curve][band]  # type: ignore[index]
    except KeyError as exc:
        raise ValueError(f"unknown curve/band combination: {curve!r} / {band!r}") from exc
