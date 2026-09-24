"""Structural audit for the Aether AX-1. See tools/_structure.py for the checks.

    python3 tools/audit_structure.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _structure as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CFG = {
    "gap_mm": 0.5,
    "exempt_attached": {},
    "mirror_tol_mm": 1.0,
    "exempt_mirror": {},
    "distinct_tol_mm": 0.5,
    "exempt_distinct": {},
    "exempt_shape": {
        # in a combustor the dome is the bulkhead across the head of the
        # annulus -- 10 mm deep and 700 across -- not a cap
        "combustor_dome": "a combustor dome is a bulkhead, not a cap",
    },
    "singletons": {
        "spinner": (("spinner",), 1),
        "LP shaft": (("shaft_lp",), 1),
        "HP shaft": (("shaft_hp",), 1),
        "combustor dome": (("combustor_dome",), 1),
        "accessory gearbox": (("gearbox",), 1),
        "tower shaft": (("towershaft",), 1),
        "mode valve": (("mode_valve",), 1),
        "third-stream heat exchanger": (("tms_hx",), 1),
        "swivel fixed ring": (("swivel_fixed_ring",), 1),
        "bearings": (("brg_*",), 5),
        "FADEC channels": (("fadec_*",), 2),
        "generators": (("generator_*",), 2),
    },
}

if __name__ == "__main__":
    n = S.report(os.path.join(ROOT, "build", "parts.csv"), CFG, "Aether AX-1")
    sys.exit(0 if n == 0 else 1)
