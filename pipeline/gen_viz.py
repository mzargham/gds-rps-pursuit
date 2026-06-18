"""Mermaid diagrams of the GDS structure (gds-viz)."""

from __future__ import annotations

from gds import project_canonical
from gds_viz import canonical_to_mermaid, spec_to_mermaid, system_to_mermaid

from gen_formal import build_spec, build_system


def generate_viz() -> dict:
    spec = build_spec()
    system = build_system()
    canonical = project_canonical(spec)
    return {
        "title": "Diagrams",
        "description": "Three views of the GDS: the compiled system graph, the "
                       "architecture by role, and the canonical h = f∘g decomposition.",
        "diagrams": {
            "system": {
                "label": "Compiled system (SystemIR)",
                "mermaid": system_to_mermaid(system),
            },
            "spec": {
                "label": "Architecture by role (GDSSpec)",
                "mermaid": spec_to_mermaid(spec),
            },
            "canonical": {
                "label": "Canonical decomposition h = f∘g",
                "mermaid": canonical_to_mermaid(canonical),
            },
        },
    }


if __name__ == "__main__":
    data = generate_viz()
    for key, d in data["diagrams"].items():
        print(f"--- {key}: {d['label']} ---")
        print(d["mermaid"][:200])
        print()
