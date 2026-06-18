"""End-to-end match sanity checks."""

from __future__ import annotations

from pathlib import Path

from gen_sim import generate_sim

INSTANCE = Path(__file__).parent.parent / "instances" / "skirmish_3v3.json"


def test_match_runs_and_is_decisive_or_times_out():
    data = generate_sim(INSTANCE)
    assert data["outcome"] in {"blue", "red", "draw", "timeout"}
    assert len(data["trajectory"]) > 1
    # the shipped instance is tuned to be decisive
    assert data["outcome"] == "blue"


def test_survivor_counts_are_monotone_non_increasing():
    data = generate_sim(INSTANCE)
    series = data["survivor_series"]
    for team in ("blue", "red"):
        counts = [s.get(team, 0) for s in series]
        assert all(b <= a for a, b in zip(counts, counts[1:], strict=False))


def test_positions_stay_bounded():
    data = generate_sim(INSTANCE)
    W = data["arena"]["W"]
    H = data["arena"]["H"]
    for frame in data["trajectory"]:
        for a in frame["assets"]:
            # walls keep live assets in; allow a small margin for overshoot/coasting
            assert -3.0 <= a["x"] <= W + 3.0
            assert -3.0 <= a["y"] <= H + 3.0
