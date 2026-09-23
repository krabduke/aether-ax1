"""Nothing that turns may touch anything that does not turn with it.

    python3 tools/audit_rotor.py        (runs itself under Blender)

The other geometry gates cannot see this. `audit_intersect` passes a blade
tip that rubs its casing -- they meet at zero depth, which is how a vane is
meant to meet its band -- and `audit_joints` and `audit_support` would count
the rub as a joint and be glad of it. In a turbine engine it is a failure:
a fan blade on its case, a drum on the stator band above it, the LP shaft on
the HP shaft round it.

So every part on a spool (spec.SPOOLS) is measured against every part that
is not on the same spool -- the static structure and, for the two
counter-rotating spools, each other -- and must stay MIN_CLEAR away. The
only exceptions are the places a rotor is meant to touch something else:
its bearings, and the tower shaft's pinion on the HP shaft's bevel.

The distance is measured from every vertex of each part to the other's
surface (a BVH nearest-point query), both ways. That is exact to within the
tessellation, which is all the running clearances here need.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "engine"))
import _interfere  # noqa: E402

PKG = "engine/parts"
MIN_CLEAR = 0.5       # mm

# (rotating part prefix, other part prefix): meant to touch
EXEMPT = [
    ("shaft_", "brg_"),          # a bearing's inner race is shrunk on its shaft
    ("towershaft", "shaft_hp"),  # the pinion meshes with the bevel
]


def exempt(a, b):
    return any((a.startswith(p) and b.startswith(q)) or
               (a.startswith(q) and b.startswith(p)) for p, q in EXEMPT)


def main():
    if not _interfere.in_blender():
        _interfere.rerun_in_blender(__file__, _interfere.script_args())
    import spec
    from mathutils import Vector
    m = _interfere.Model(ROOT, PKG)
    rot = [n for n in m.names if spec.spool_of(n)]
    bad = []
    checked = 0
    for a in rot:
        sa = spec.spool_of(a)
        for b in m.names:
            if b == a or spec.spool_of(b) == sa or exempt(a, b):
                continue
            if spec.spool_of(b) and b < a:
                continue            # each LP x HP pair once
            if not m.meet(a, b, MIN_CLEAR):
                continue
            checked += 1
            best = None
            for x, y in ((a, b), (b, a)):
                lo, hi = m.box[y]
                pts = [p for p in m.parts[x][0]
                       if all(lo[i] - MIN_CLEAR <= p[i] <= hi[i] + MIN_CLEAR
                              for i in range(3))]
                for p in pts[::max(1, len(pts) // 40000)]:
                    hit = m.tree[y].find_nearest(Vector(p), MIN_CLEAR)
                    if hit[0] is not None and (best is None or hit[3] < best[0]):
                        best = (hit[3], p)
            if best is not None:
                bad.append((best[0], a, b, best[1]))
    print(f"{len(rot)} rotating parts, {checked} pairs within reach checked "
          f"for {MIN_CLEAR:g} mm running clearance")
    for d, a, b, p in sorted(bad):
        print(f"  x  {d:5.2f} mm  {a} ({spec.spool_of(a)})  x  {b} "
              f"({spec.spool_of(b) or 'static'})  at "
              f"({p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f})")
    print("\n" + ("PASS  every rotor runs clear of everything it does not turn with"
                  if not bad else f"FAIL  {len(bad)} rotor rubs"))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
