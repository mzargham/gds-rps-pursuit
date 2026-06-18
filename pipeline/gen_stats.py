"""Aggregate statistics over repeated runs — the model-driven tuning story.

This reproduces, in miniature, the analysis used to tune the model: because the
simulation is generated from the spec, we can run it hundreds of times under
varied parameters and *measure* the consequences of a design choice instead of
guessing. The site's analysis page narrates these numbers.

Everything here is deterministic (fixed seed ranges) so the page is reproducible.
"""

from __future__ import annotations

import dataclasses
import random
import statistics as st
from collections import Counter
from pathlib import Path

import ontology
from dynamics import FieldParams
from gen_sim import load_instance
from leaders import GreedyLeader, RandomLeader, make_leader
from match import run_match
from ontology import Asset

FIELD = FieldParams(k_wall=0.8, wall_w=1.0)
RUN = dict(cadence=0.4, sample_dt=0.05, t_max=25.0)  # capped: ensembles, not the showcase match
JITTER = 1.1  # initial-position perturbation, so each seed is a distinct scenario


def _roster(instance_path: Path):
    cfg = load_instance(instance_path)["cfg"]
    return [(a["id"], a["class"], a["team"], a["x"], a["y"]) for a in cfg["assets"]]


def _fresh(roster, seed: int) -> list[Asset]:
    """Roster with seeded initial-position jitter (a fresh scenario per seed)."""
    rng = random.Random(seed)
    return [Asset(id=i, class_name=c, team=t,
                  x=x + rng.uniform(-JITTER, JITTER), y=y + rng.uniform(-JITTER, JITTER))
            for (i, c, t, x, y) in roster]


def _spread(traj) -> float:
    v = [(st.pstdev([a["x"] for a in f["assets"]]) +
          st.pstdev([a["y"] for a in f["assets"]])) / 2 for f in traj]
    return sum(v) / len(v)


def _death_time(events, aid):
    for e in sorted(events, key=lambda e: e["t"]):
        if aid in (e.get("loser"), e.get("victim"), e.get("a"), e.get("b")):
            return e["t"]
    return None


def _self_elim(result) -> tuple[int, int]:
    """(kill-cone strikes, strikes whose attacker dies within 1.2s)."""
    kills = [e for e in result["events"] if e["kind"] == "rps"]
    sd = sum(1 for e in kills
             if (dt := _death_time(result["events"], e["winner"])) and 0 < dt - e["t"] <= 1.2)
    return len(kills), sd


def _battery(roster, leaders_factory, seeds):
    rows = []
    for seed in seeds:
        result = run_match(_fresh(roster, seed), leaders_factory(seed), field=FIELD, **RUN)
        kills, sd = _self_elim(result)
        rows.append({
            "outcome": result["outcome"],
            "duration": result["duration"],
            "spread": _spread(result["trajectory"]),
            "events": Counter(e["kind"] for e in result["events"]),
            "kills": kills,
            "self_elim": sd,
        })
    return rows


# ---------------------------------------------------------------------------
# Analyses
# ---------------------------------------------------------------------------
def headline(roster, n=40) -> dict:
    rows = _battery(roster, lambda s: {"blue": GreedyLeader(), "red": RandomLeader(seed=s)},
                    range(n))
    outcomes = Counter(r["outcome"] for r in rows)
    ev = Counter()
    for r in rows:
        ev.update(r["events"])
    tot_k = sum(r["kills"] for r in rows)
    tot_sd = sum(r["self_elim"] for r in rows)
    return {
        "n": n,
        "outcomes": dict(outcomes),
        "mean_duration": round(st.mean(r["duration"] for r in rows), 2),
        "mean_spread": round(st.mean(r["spread"] for r in rows), 2),
        "durations": [r["duration"] for r in rows],
        "event_mix": {k: round(v / n, 2) for k, v in ev.items()},
        "self_elim_pct": round(100 * tot_sd / max(tot_k, 1)),
    }


def tuning_sweep(roster, seeds=range(12)) -> dict:
    """The decision that drove the stand-off policy: self-elimination vs draws,
    as we vary the stand-off distance (engage factor) and the kill-cone reach."""
    orig_classes = dict(ontology.CLASSES)
    orig_ef = ontology.ENGAGE_FACTOR
    grid = []
    try:
        for ef in (0.0, 0.4, 0.8):
            for km in (1.0, 1.3):
                ontology.ENGAGE_FACTOR = ef
                ontology.CLASSES = {
                    k: dataclasses.replace(v, kill_radius=orig_classes[k].kill_radius * km)
                    for k, v in orig_classes.items()
                }
                rows = _battery(roster,
                                lambda s: {"blue": GreedyLeader(), "red": RandomLeader(seed=s)},
                                seeds)
                tot_k = sum(r["kills"] for r in rows)
                tot_sd = sum(r["self_elim"] for r in rows)
                outs = Counter(r["outcome"] for r in rows)
                n = len(rows)
                grid.append({
                    "engage_factor": ef,
                    "kill_mult": km,
                    "self_elim_pct": round(100 * tot_sd / max(tot_k, 1)),
                    "decisive_pct": round(100 * (outs["blue"] + outs["red"]) / n),
                    "draw_pct": round(100 * (outs["draw"] + outs["timeout"]) / n),
                })
    finally:
        ontology.ENGAGE_FACTOR = orig_ef
        ontology.CLASSES = orig_classes
    return {"n": len(list(seeds)), "grid": grid}


def leader_matchups(roster, seeds=range(20)) -> dict:
    def fac(blue_kind, red_kind):
        return lambda s: {"blue": make_leader(blue_kind if isinstance(blue_kind, str)
                                               else {"type": "random", "seed": s}),
                          "red": make_leader(red_kind if isinstance(red_kind, str)
                                             else {"type": "random", "seed": s + 100})}
    matchups = [
        ("greedy", "greedy"),
        ("greedy", {"random"}),
        ({"random"}, {"random"}),
    ]
    out = []
    for blue, red in matchups:
        bk = blue if isinstance(blue, str) else "random"
        rk = red if isinstance(red, str) else "random"
        rows = _battery(roster, fac(blue, red), seeds)
        outs = Counter(r["outcome"] for r in rows)
        n = len(rows)
        out.append({
            "blue": bk, "red": rk,
            "blue_win_pct": round(100 * outs["blue"] / n),
            "red_win_pct": round(100 * outs["red"] / n),
            "stalemate_pct": round(100 * (outs["draw"] + outs["timeout"]) / n),
        })
    return {"n": len(list(seeds)), "matchups": out}


def generate_stats(instance_path: Path) -> dict:
    roster = _roster(instance_path)
    hl = headline(roster)
    sweep = tuning_sweep(roster)
    leaders = leader_matchups(roster)

    naive = next(r for r in sweep["grid"] if r["engage_factor"] == 0.0 and r["kill_mult"] == 1.0)
    tuned = next(r for r in sweep["grid"] if r["engage_factor"] == 0.8 and r["kill_mult"] == 1.3)

    return {
        "title": "Analysis",
        "intro": (
            "Because the simulation is generated from the symbolic spec, every "
            "design choice is testable: we run the model hundreds of times and "
            "measure the outcome distribution rather than arguing about it. This "
            "page reproduces, at small scale, the analysis used to tune the model — "
            "the same loop that turned a brittle prototype into the match on the "
            "arena page."
        ),
        "headline": hl,
        "tuning_sweep": sweep,
        "tuning_takeaway": {
            "naive_self_elim_pct": naive["self_elim_pct"],
            "tuned_self_elim_pct": tuned["self_elim_pct"],
            "tuned_decisive_pct": tuned["decisive_pct"],
            "text": (
                "Symptom: attackers killed their prey and then rammed the fresh "
                f"corpse — the kill-cone striker self-eliminated {naive['self_elim_pct']}% of "
                "the time. Lengthening the kill cone alone cut that but collapsed "
                "matches into mutual-annihilation draws. Adding a stand-off "
                "engagement distance (strike from cone reach, don't ram) and a "
                "modest reach increase together dropped self-elimination to "
                f"{tuned['self_elim_pct']}% while keeping {tuned['decisive_pct']}% of matches "
                "decisive. We measured each lever instead of guessing."
            ),
        },
        "leaders": leaders,
    }


if __name__ == "__main__":
    import json
    data = generate_stats(Path(__file__).parent / "instances" / "skirmish_3v3.json")
    print(json.dumps(data["tuning_takeaway"], indent=2))
    print("outcomes:", data["headline"]["outcomes"])
    print("leaders:", [(m["blue"], "vs", m["red"], m["blue_win_pct"]) for m in data["leaders"]["matchups"]])
