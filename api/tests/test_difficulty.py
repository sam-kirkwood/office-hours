import pytest

from difficulty import difficulty_for


@pytest.mark.parametrize(
    ("curve", "band", "expected"),
    [
        ("gentle", "intro", 1),
        ("gentle", "core", 2),
        ("gentle", "advanced", 3),
        ("standard", "intro", 2),
        ("standard", "core", 3),
        ("standard", "advanced", 4),
        ("aggressive", "intro", 3),
        ("aggressive", "core", 4),
        ("aggressive", "advanced", 5),
    ],
)
def test_difficulty_for_table(curve: str, band: str, expected: int) -> None:
    assert difficulty_for(curve, band) == expected


def test_difficulty_for_unknown_curve_raises() -> None:
    with pytest.raises(ValueError):
        difficulty_for("brutal", "core")


def test_difficulty_for_unknown_band_raises() -> None:
    with pytest.raises(ValueError):
        difficulty_for("standard", "research")
