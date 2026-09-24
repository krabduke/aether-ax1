"""Check the built engine against its design by measurement.

    python3 engine/verify.py

Reads build/parts.csv (written by assemble.py) for what was built, and the
pure-Python geometry and cycle for what was meant, and fails on any
disagreement. Four groups:

  CYCLE      the cycle closes: the mixer is balanced, the turbines deliver
             the work the compressors take, and the headline figures in
             spec.py are the cycle's own
  FLOWPATH   the axial Mach number the drawn annulus implies, at every
             station, from the cycle's mass flow and total conditions there;
             each blade row's solidity; the axial gap between every pair of
             rows, measured off the lofted aerofoils rather than their
             nominal chords
  BUILD      envelope, blade tips against their casings, the nozzle throat
             against the cycle's choked area, every part given a material
  SPOOLS     every rotor row is on a spool and every spool turns
"""

import csv
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import spec      # noqa: E402
import cycle     # noqa: E402
import blades    # noqa: E402


class Check:
    def __init__(self):
        self.fails, self.n = [], 0

    def band(self, label, got, lo, hi, fmt="{:.3f}"):
        self.n += 1
        s = fmt.format(got)
        if not (lo <= got <= hi):
            self.fails.append(f"{label}: {s} outside {lo}..{hi}")
            print(f"  x   {label:50s} {s:>9s}  (want {lo}..{hi})")
            return False
        print(f"  ok  {label:50s} {s:>9s}  ({lo}..{hi})")
        return True

    def true(self, label, cond, detail=""):
        self.n += 1
        if not cond:
            self.fails.append(f"{label}: {detail}")
            print(f"  x   {label:50s} {detail}")
            return False
        print(f"  ok  {label:50s} {detail}")
        return True


def area(path, x):
    a, b = spec.annulus(spec.PATHS[path], x)
    return math.pi * (b * b - a * a) * 1e-6


def mach(path, x, w, tt, pt, hot=False):
    g, cp = (cycle.G_HOT, cycle.CP_HOT) if hot else (cycle.G_AIR, cycle.CP_AIR)
    return cycle.axial_mach(w, tt, pt, area(path, x), g, cp)


def row_extent(row):
    """Actual axial extent of a row's aerofoil, off the lofted mesh."""
    r0 = lambda x: row.hub(x)
    r1 = lambda x: row.tip(x)
    v, _ = blades.loft(row, r0, r1, spec.RES["airfoil_chord_pts"],
                       spec.RES["airfoil_span_pts"])
    xs = [p[0] for p in v]
    return min(xs), max(xs)


def solidity(row, s):
    g = math.radians(abs(row.stagger_hub + (row.stagger_tip - row.stagger_hub) * s))
    x0, x1 = row.span_x(s)
    xm = 0.5 * (x0 + x1)
    r = row.hub(xm) + (row.tip(xm) - row.hub(xm)) * s
    true_chord = (x1 - x0) / max(math.cos(g), 0.3)
    return true_chord / (2.0 * math.pi * r / row.count)


def main():
    c = Check()
    cy = spec.CYCLE
    d = cycle.DESIGN

    print("\nCYCLE")
    c.band("mixer core/bypass total-pressure ratio", cy["mixer_pr"], 0.97, 1.03)
    c.band("bypass ratio (second stream / core), solved", cy["bpr2"], 0.2, 1.2)
    c.band("overall pressure ratio", cy["opr"], 25.0, 45.0, "{:.1f}")
    hp_in = (cy["work_hpc"] + cy["work_cdfs"] + d["p_offtake"]) / d["eta_mech"]
    hp_out = cy["w4"] * cycle.CP_HOT * (cy["t4"] - cy["t41"])
    c.band("HP turbine work / HP compressor + CDFS + offtake", hp_out / hp_in,
           0.999, 1.001, "{:.4f}")
    lp_out = cy["w45"] * cycle.CP_HOT * (cy["t45"] - cy["t5"])
    c.band("LP turbine work / fan work", lp_out / (cy["work_fan"] / d["eta_mech"]),
           0.999, 1.001, "{:.4f}")
    c.true("spec thrust is the cycle's (dry)",
           abs(spec.THRUST_DRY_N - cy["thrust_dry"]) < 100.0,
           f"{spec.THRUST_DRY_N / 1000:.1f} kN")
    c.true("spec thrust is the cycle's (reheat)",
           abs(spec.THRUST_AB_N - cy["thrust_wet"]) < 100.0,
           f"{spec.THRUST_AB_N / 1000:.1f} kN")
    c.band("reheat thrust-to-weight of the engine",
           spec.THRUST_AB_N / (spec.DRY_WEIGHT_KG * 9.80665), 7.0, 11.0, "{:.2f}")
    c.band("dry SFC, mg/(N s)", cy["sfc_dry"], 17.0, 26.0, "{:.1f}")
    c.band("reheat SFC, mg/(N s)", cy["sfc_wet"], 38.0, 60.0, "{:.1f}")

    print("\nFLOWPATH  (axial Mach number the annulus implies)")
    w, w3, wc, w2 = cy["w"], cy["w3"], cy["w_core"], cy["w2"]
    stations = [
        ("fan face", "fan", 0.0, w, cy["t2"], cy["p2"], False, (0.45, 0.66)),
        ("fan mid", "fan", 232.0, w, math.sqrt(cy["t2"] * cy["t13"]),
         math.sqrt(cy["p2"] * cy["p13"]), False, (0.35, 0.60)),
        ("fan exit", "fan", 408.0, w, cy["t13"], cy["p13"], False, (0.30, 0.55)),
        ("third stream entry, cruise share", "third", 490.0, 0.24 * w,
         cy["t13"], cy["p13"], False, (0.25, 0.55)),
        ("third stream duct", "third", 1000.0, w3, cy["t3s"], cy["p3s"], False,
         (0.05, 0.40)),
        ("CDFS inlet", "cdfs", 555.0, w - w3, cy["t13"], cy["p13"], False,
         (0.35, 0.60)),
        ("CDFS exit", "cdfs", 678.0, w - w3, cy["t21"], cy["p21"], False,
         (0.35, 0.60)),
        ("core, after the splitter", "core", 740.0, wc, cy["t21"], cy["p21"],
         False, (0.35, 0.60)),
        ("HPC inlet", "core", 832.0, wc, cy["t21"], cy["p21"], False, (0.40, 0.62)),
        ("HPC middle", "core", 1100.0, wc, math.sqrt(cy["t21"] * cy["t3"]),
         math.sqrt(cy["p21"] * cy["p3"]), False, (0.30, 0.55)),
        ("HPC exit", "core", 1340.0, wc, cy["t3"], cy["p3"], False, (0.20, 0.40)),
        ("bypass duct entry", "bypass", 740.0, w2, cy["t16"], cy["p16"], False,
         (0.25, 0.55)),
        ("bypass duct at the combustor", "bypass", 1600.0, w2, cy["t16"],
         cy["p16"], False, (0.20, 0.45)),
        ("HP turbine exit", "core", 1808.0, cy["w4"], cy["t41"], cy["p41"], True,
         (0.15, 0.50)),
        ("LP turbine exit", "core", 2008.0, cy["w45"], cy["t5"], cy["p5"], True,
         (0.20, 0.55)),
    ]
    for (label, path, x, ww, tt, pt, hot, (lo, hi)) in stations:
        m = mach(path, x, ww, tt, pt, hot)
        if m is None:
            c.true(label, False, "annulus too small to pass the flow")
        else:
            c.band(f"{label} (x {x:.0f})", m, lo, hi)

    print("\nFLOWPATH  (blade rows)")
    lo, hi = spec.SOLIDITY_BAND
    for row in spec.all_rows():
        if row.name in spec.SOLIDITY_EXEMPT:
            continue
        sig = [solidity(row, s) for s in (0.0, 0.5, 1.0)]
        c.band(f"{row.name} solidity, least of hub/mid/tip", min(sig), lo, hi,
               "{:.2f}")
        c.band(f"{row.name} solidity, most of hub/mid/tip", max(sig), lo, hi,
               "{:.2f}")
    rows = sorted(spec.all_rows(), key=lambda r: r.x)
    ext = {r.name: row_extent(r) for r in rows}
    for a, b in zip(rows, rows[1:]):
        gap = ext[b.name][0] - ext[a.name][1]
        c.band(f"axial gap {a.name} -> {b.name}, mm", gap, 6.0, 400.0, "{:.1f}")

    print("\nBUILD")
    path = os.path.join(ROOT, "build", "parts.csv")
    if not os.path.exists(path):
        print("build/parts.csv missing -- run `make build` first")
        return 1
    parts = {r["name"]: r for r in csv.DictReader(open(path))}
    f = lambda n, k: float(parts[n][k])
    x0 = min(float(r["x_min_mm"]) for r in parts.values())
    x1 = max(float(r["x_max_mm"]) for r in parts.values())
    # the engine plus a metre of swivel duct
    c.band("overall length, mm", x1 - x0, 4600.0, 4850.0, "{:.0f}")
    # The round part of the engine, flanges included; the swivel's motors
    # and the nozzle actuators are externals, like the gearbox
    body = [r for r in parts.values()
            if r["collection"] != "09 Accessories"
            and not r["name"].startswith(("swivel_drive_", "nozzle_actuators",
                                          "swivel_rotary_union", "ab_fuel_control",
                                          "ab_igniter"))]
    rmax = max(float(r["r_max_mm"]) for r in body)
    c.band("maximum diameter without externals, mm", 2 * rmax, 900.0, 1040.0,
           "{:.0f}")
    for row in spec.all_rows():
        key = (f"fan_blisk_{row.name[-1]}" if row.name.startswith("fan_r")
               else "cdfs_blisk" if row.name == "cdfs_r"
               else f"blades_{row.name}" if row.rotor else None)
        if key is None or key not in parts:
            continue
        clr = spec.TIP_CLEARANCE.get(row.path, spec.TIP_CLEARANCE["core"])
        want = max(row.tip(x) for x in (row.x, row.x_te)) - clr
        c.band(f"{row.name} tip radius, built vs annulus - clearance, mm",
               f(key, "r_max_mm") - want, -1.5, 0.3, "{:+.2f}")
    import importlib
    nz = importlib.import_module("parts.nozzle")
    a8 = math.pi * nz.R8 ** 2 * 1e-6
    c.band("nozzle throat area / cycle's choked area at max reheat",
           a8 / cy["a8_wet"], 0.99, 1.01, "{:.4f}")
    a9 = math.pi * nz.R9 ** 2 * 1e-6
    c.band("nozzle exit / throat area vs full expansion",
           (a9 / a8) / cy["a9_a8_wet"], 0.99, 1.01, "{:.4f}")
    # the seals are on the gas line, so the built throat is the smallest
    # radius any convergent seal reaches
    sv, _ = nz._flap_set(nz.X_S1, nz.X8, spec.NOZZLE["conv_t"], 12.0, 10.0)[1]
    c.band("nozzle built throat radius (convergent seals), mm",
           min(math.hypot(p[1], p[2]) for p in sv), nz.R8 - 2.0, nz.R8 + 2.0,
           "{:.1f}")
    c.band("swivel: full travel folds the jet, degrees", nz.max_fold_deg(),
           90.0, 100.0, "{:.1f}")
    worst = 0.0
    for pitch in range(0, 96, 5):
        for yaw in (-12, 0, 12):
            ang = nz.swivel_pose(pitch, yaw)
            d = nz._rot((1.0, 0.0, 0.0), ang[0], nz.fold(ang[1]))
            t = (math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)),
                 math.sin(math.radians(yaw)),
                 -math.sin(math.radians(pitch)) * math.cos(math.radians(yaw)))
            worst = max(worst, math.degrees(math.acos(max(-1.0, min(1.0,
                        sum(d[i] * t[i] for i in range(3)))))))
    c.band("swivel: the bearing schedule points the jet where asked, worst "
           "error over 0-95 down and 12 either side, degrees", worst, 0.0, 0.05,
           "{:.4f}")
    # the core splitter divides the CDFS exit in the cycle's ratio
    xs = spec.SPLITTER2_X
    h, t = spec.annulus(spec.CDFS_PATH, xs)
    rs = spec.SPLITTER2_R
    implied = (t * t - rs * rs) / (rs * rs - h * h)
    c.band("bypass ratio implied by the splitter at equal flux / cycle's",
           implied / cy["bpr2"], 0.85, 1.15, "{:.3f}")
    unmat = [n for n, r in parts.items() if r["material"] not in spec.PALETTE]
    c.true("every part has a material from the palette", not unmat,
           ", ".join(unmat[:5]) or f"{len(parts)} parts")
    for col in ("01 Fan", "02 Compressor", "03 Combustor", "04 Turbines",
                "05 Augmentor", "06 Nozzle", "07 Frames and casings",
                "08 Spools and bearings", "09 Accessories"):
        c.true(f"collection {col} is populated",
               any(r["collection"] == col for r in parts.values()),
               f"{sum(r['collection'] == col for r in parts.values())} parts")

    print("\nSPOOLS")
    for k, names in spec.SPOOLS.items():
        missing = [n for n in names if n not in parts]
        c.true(f"{k.upper()} spool parts all built", not missing,
               ", ".join(missing) or f"{len(names)} parts")
        spins = {parts[n]["spin"] for n in names if n in parts}
        c.true(f"{k.upper()} spool turns one way", len(spins) == 1,
               ", ".join(sorted(spins)))
    lp = parts["shaft_lp"]["spin"]
    hp = parts["shaft_hp"]["spin"]
    c.true("the spools counter-rotate", float(lp) * float(hp) < 0,
           f"LP {lp}, HP {hp}")

    print()
    if c.fails:
        print(f"FAIL  {len(c.fails)} of {c.n} checks")
        return 1
    print(f"PASS  all {c.n} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
