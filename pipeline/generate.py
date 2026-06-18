"""Generate all JSON artifacts for the gds-rps-pursuit site.

Run: ``uv run python generate.py``

Writes ``output/*.json`` and copies them into ``../site/public/data/`` so the
Vite site can fetch them.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from gen_formal import generate_formal
from gen_sim import generate_sim
from gen_stats import generate_stats
from gen_viz import generate_viz

HERE = Path(__file__).parent
OUTPUT = HERE / "output"
SITE_DATA = HERE.parent / "site" / "public" / "data"
INSTANCE = HERE / "instances" / "skirmish_3v3.json"


def write_json(name: str, data: dict) -> None:
    OUTPUT.mkdir(exist_ok=True)
    path = OUTPUT / name
    path.write_text(json.dumps(data, indent=2))
    print(f"  wrote {path.relative_to(HERE)} ({path.stat().st_size // 1024} KB)")


def main() -> None:
    print("Generating gds-rps-pursuit data...\n")

    print("[match] running the symbolic hybrid simulation")
    match = generate_sim(INSTANCE)
    print(f"  outcome={match['outcome']} duration={match['duration']} "
          f"frames={len(match['trajectory'])} captures={len(match['events'])}")
    write_json("match.json", match)

    print("\n[formal] building GDSSpec + canonical + symbolic export")
    formal = generate_formal(INSTANCE)
    v = formal["verification"]
    assert v["errors"] == 0, f"GDS verification failed: {v}"
    print(f"  verify errors={v['errors']} passed={v['checks_passed']}/{v['checks_total']}")
    write_json("formal.json", formal)

    print("\n[viz] rendering Mermaid diagrams")
    write_json("viz_diagrams.json", generate_viz())

    print("\n[stats] running repeated-match analysis (this takes a moment)")
    stats = generate_stats(INSTANCE)
    print(f"  self-elimination {stats['tuning_takeaway']['naive_self_elim_pct']}% → "
          f"{stats['tuning_takeaway']['tuned_self_elim_pct']}%; "
          f"outcomes {stats['headline']['outcomes']}")
    write_json("stats.json", stats)

    # copy into the site
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    for f in OUTPUT.glob("*.json"):
        shutil.copy(f, SITE_DATA / f.name)
    print(f"\nCopied JSON → {SITE_DATA.relative_to(HERE.parent)}")
    print("Done.")


if __name__ == "__main__":
    main()
