"""Generate viewer/parts.json from build/parts.csv, engine/spec.py and the
cycle.

    python3 tools/make_manifest.py [out.json]

The viewer holds no engineering of its own. Which parts turn and which way,
where the nozzle flaps hinge, the alloy palette, the flowpath the airflow
particles ride and the temperatures they are coloured by -- all of it comes
from here, so a change to the engine reaches the page by `make manifest`
and cannot be half-applied in the HTML.
"""

import csv
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "engine"))
import spec     # noqa: E402
import cycle    # noqa: E402
from parts import nozzle   # noqa: E402

MODULES = [
    ("01 Fan", "Fan", "#8FA8B3", "cold"),
    ("02 Compressor", "Compressor", "#A3AAB0", "cold"),
    ("03 Combustor", "Combustor", "#C9763F", "hot"),
    ("04 Turbines", "Turbines", "#B8562E", "hot"),
    ("05 Augmentor", "Augmentor", "#D0843F", "hot"),
    ("06 Nozzle", "Swivel nozzle", "#9C7A63", "hot"),
    ("07 Frames and casings", "Frames & casings", "#6E7A7E", "struct"),
    ("08 Spools and bearings", "Spools & bearings", "#858A86", "struct"),
    ("09 Accessories", "Accessories", "#7C8470", "struct"),
]


def r1(v, n=1):
    return round(float(v), n)


def flow():
    """Streams for the airflow particles: (x, inner r, outer r) in mm along
    each one, and total temperature in C along the core at dry and reheat."""
    c = spec.CYCLE
    k = lambda t: r1(t - 273.15, 0)
    core = [(x, a, b) for (x, a, b) in spec.FAN_PATH] + \
           [(x, a, b) for (x, a, b) in spec.CDFS_PATH[1:]] + \
           [(x, a, b) for (x, a, b) in spec.CORE_PATH[1:]]
    # after the turbine: the mixed stream fills the augmentor to the nozzle
    A = spec.AUGMENTOR
    core += [(A["x_mixer1"], 150.0, A["liner_r"] - 10.0),
             (A["x_liner1"], 40.0, A["liner_r"] - 10.0),
             (spec.NOZZLE["x_static1"], 30.0, nozzle.R_IN - 10.0),
             (spec.NOZZLE["x_throat"], 10.0, nozzle.R8 - 8.0),
             (spec.NOZZLE["x_exit"], 10.0, nozzle.R9 - 8.0)]
    bypass = [(x, a, b) for (x, a, b) in spec.BYPASS_PATH]
    third = [(x, a, b) for (x, a, b) in spec.THIRD_PATH]
    S = spec
    t_core = [(0.0, k(c["t2"])), (408.0, k(c["t13"])),
              (678.0, k(c["t21"])), (1340.0, k(c["t3"])),
              (1440.0, k(c["t3"])), (1690.0, k(c["t4"])),
              (1808.0, k(c["t41"])), (2008.0, k(c["t5"])),
              (A["x_mixer1"], k(c["t6"]))]
    t_dry = t_core + [(spec.NOZZLE["x_exit"], k(c["t6"]))]
    t_wet = t_core + [(A["vane_x0"] + A["vane_chord"], k(0.5 * (c["t6"] + c["t7"]))),
                      (A["x_liner1"], k(c["t7"])),
                      (spec.NOZZLE["x_exit"], k(c["t7"] * 0.97))]
    return {"core": [[r1(v) for v in p] for p in core],
            "bypass": [[r1(v) for v in p] for p in bypass],
            "third": [[r1(v) for v in p] for p in third],
            "t_core_dry": t_dry, "t_core_ab": t_wet,
            "t_bypass": k(c["t16"]), "t_third": k(c["t3s"])}


def nozzle_kinematics():
    """What the viewer needs to swivel the nozzle: each bearing's centre and
    axis in the engine's frame (mm), which parts turn on it, and the fold
    angle against the middle bearing's turn, to invert for a target."""
    import math
    fr1, fr2 = nozzle.oblique(1), nozzle.oblique(2)
    table = [[r1(d, 2), r1(math.degrees(math.acos(max(-1.0, min(1.0,
              nozzle.fold(math.radians(d))[0])))), 3)]
             for d in range(0, 181, 2)]
    return {
        "bearings": [
            {"c": [spec.NOZZLE["x_brg1"], 0.0, 0.0], "n": [1.0, 0.0, 0.0],
             "parts": nozzle.GROUPS["fwd"]},
            {"c": [r1(v, 3) for v in fr1[0]], "n": [r1(v, 6) for v in fr1[1]],
             "parts": nozzle.GROUPS["mid"]},
            {"c": [r1(v, 3) for v in fr2[0]], "n": [r1(v, 6) for v in fr2[1]],
             "parts": nozzle.GROUPS["aft"]},
        ],
        "fold_table": table,
        "max_fold_deg": r1(nozzle.max_fold_deg()),
        "exit_x": r1(nozzle.X9), "exit_r": r1(nozzle.R9),
        "throat_x": r1(nozzle.X8),
        "throat_r": r1(nozzle.R8),
    }


def main():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "build", "parts.csv"))))
    mods = []
    for key, label, color, kind in MODULES:
        mine = [r for r in rows if r["collection"] == key]
        if not mine:
            continue
        mods.append({"key": key, "label": label, "color": color, "kind": kind,
                     "x0": min(float(r["x_min_mm"]) for r in mine),
                     "x1": max(float(r["x_max_mm"]) for r in mine),
                     "parts": len(mine),
                     "faces": sum(int(r["faces"]) for r in mine)})
    parts = {r["name"]: {"m": r["collection"], "mat": r["material"],
                         "x0": float(r["x_min_mm"]), "x1": float(r["x_max_mm"]),
                         "f": int(r["faces"]),
                         "spool": r["spool"] or None,
                         "spin": float(r["spin"]) if r["spin"] else None}
             for r in rows}
    c = spec.CYCLE
    out = {
        "engine": spec.ENGINE_NAME,
        "tagline": spec.ENGINE_TAGLINE,
        "figures": {
            "thrust_dry_kn": r1(spec.THRUST_DRY_N / 1000.0),
            "thrust_ab_kn": r1(spec.THRUST_AB_N / 1000.0),
            "airflow_kg_s": r1(spec.AIRFLOW_KG_S),
            "opr": spec.OVERALL_PRESSURE_RATIO,
            "fpr": spec.FAN_PRESSURE_RATIO,
            "bpr": spec.BYPASS_RATIO,
            "bpr_total": spec.BYPASS_RATIO_TOTAL,
            "t4_k": spec.T4_K,
            "sfc_dry": r1(c["sfc_dry"]), "sfc_ab": r1(c["sfc_wet"]),
            "mass_kg": spec.DRY_WEIGHT_KG,
            "tw": r1(spec.THRUST_AB_N / (spec.DRY_WEIGHT_KG * 9.80665), 2),
            "stages": f"{spec.N_FAN_STAGES}F-{spec.N_CDFS_STAGES}CDFS-"
                      f"{spec.N_HPC_STAGES}HPC-{spec.N_HPT_STAGES}HPT-"
                      f"{spec.N_LPT_STAGES}LPT",
            "airfoils": spec.total_airfoils(),
            "length_mm": r1(max(float(r["x_max_mm"]) for r in rows)
                            - min(float(r["x_min_mm"]) for r in rows), 0),
        },
        "stations": {k: [r1(c["t" + k] - 273.15, 0), r1(c["p" + k] / 1000.0, 0)]
                     for k in ("2", "13", "21", "3", "4", "41", "5", "6")},
        "palette": {k: {"rgb": list(v[0]), "metal": v[1], "rough": v[2]}
                    for k, v in spec.PALETTE.items()},
        "flow": flow(),
        "nozzle": nozzle_kinematics(),
        "modules": mods,
        "parts": parts,
    }
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "viewer",
                                                              "parts.json")
    json.dump(out, open(path, "w"), indent=1)
    print(f"  -> {path}  ({len(parts)} parts, {len(mods)} modules)")


if __name__ == "__main__":
    main()
