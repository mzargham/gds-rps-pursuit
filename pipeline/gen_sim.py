"""Run a match instance and emit ``match.json`` for the presentation layer.

Showcases: the symbolic field (``dynamics``) bound to ``gds_continuous`` via the
hybrid loop in ``match``.
"""

from __future__ import annotations

import json
from pathlib import Path

from dynamics import FieldParams
from leaders import make_leader
from match import run_match
from ontology import Asset, CLASSES


def load_instance(path: Path) -> dict:
    """Load an instance config into assets, leaders, gains, and run kwargs."""
    cfg = json.loads(Path(path).read_text())

    assets = [
        Asset(id=a["id"], class_name=a["class"], team=a["team"], x=a["x"], y=a["y"])
        for a in cfg["assets"]
    ]
    leaders = {
        team: make_leader(spec["leader"]) for team, spec in cfg["teams"].items()
    }

    arena = cfg.get("arena", {})
    fcfg = cfg.get("field", {})
    field = FieldParams(W=arena.get("W", 16.0), H=arena.get("H", 16.0), **fcfg)

    return {
        "cfg": cfg,
        "assets": assets,
        "leaders": leaders,
        "field": field,
        "run": cfg.get("run", {}),
    }


def _roster(cfg: dict) -> list[dict]:
    out = []
    for a in cfg["assets"]:
        cls = CLASSES[a["class"]]
        out.append({
            "id": a["id"],
            "team": a["team"],
            "class": a["class"],
            "type": cls.type.value,
            "glyph": cls.glyph,
            "collision_radius": cls.collision_radius,
            "kill_radius": cls.kill_radius,
            "kill_half_angle": round(cls.kill_half_angle, 4),
        })
    return out


def generate_sim(instance_path: Path) -> dict:
    inst = load_instance(instance_path)
    cfg = inst["cfg"]
    result = run_match(
        inst["assets"], inst["leaders"], field=inst["field"], **inst["run"]
    )
    return {
        "title": "Match",
        "name": cfg["name"],
        "description": cfg.get("description", ""),
        "arena": cfg.get("arena", {"W": 16.0, "H": 16.0}),
        "teams": {t: {"color": s.get("color"), "leader": s["leader"]}
                  for t, s in cfg["teams"].items()},
        "roster": _roster(cfg),
        **result,
    }


if __name__ == "__main__":
    here = Path(__file__).parent
    data = generate_sim(here / "instances" / "skirmish_3v3.json")
    print(f"outcome={data['outcome']} duration={data['duration']} "
          f"frames={len(data['trajectory'])} events={len(data['events'])} "
          f"final={data['final_survivors']}")
