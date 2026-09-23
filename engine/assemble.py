"""Build the complete engine in Blender. Run under `blender --background`.

Pipeline per object:
    pure-Python (verts, faces) in mm
      -> scaled to metres and made into a bpy mesh
      -> normals made to point outward, THEN boolean cutters applied
         (film-cooling holes, dilution holes, screech holes, swirler holes)
      -> material assigned by name, filed into a collection, shaded

Writes build/parts.csv so the result can be checked against spec.py by
measurement rather than by eye, and so the viewer's manifest knows which
parts turn, on which spool, and which way.
"""

import csv
import math
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import spec              # noqa: E402
import mesh as meshlib   # noqa: E402
import materials         # noqa: E402
from parts import (fan, compressor, combustor, turbine, augmentor,  # noqa: E402
                   nozzle, frames, spools, accessories)

MM = 0.001   # geometry is authored in mm; the Blender scene is in metres

MODULES = [
    ("fan", fan, "01 Fan"),
    ("compressor", compressor, "02 Compressor"),
    ("combustor", combustor, "03 Combustor"),
    ("turbine", turbine, "04 Turbines"),
    ("augmentor", augmentor, "05 Augmentor"),
    ("nozzle", nozzle, "06 Nozzle"),
    ("frames", frames, "07 Frames and casings"),
    ("spools", spools, "08 Spools and bearings"),
    ("accessories", accessories, "09 Accessories"),
]
COLLECTIONS = [m[2] for m in MODULES]
MODULE_BY_NAME = [(m[0], m[1]) for m in MODULES]

# Casings go with the frames whichever module builds them, so the cutaway
# and the exploded view can lift the whole pressure vessel as one.
CASING_PREFIXES = ("case_", "inlet_case", "containment", "flange_")


def collection_for(name, module_collection):
    if name.startswith(CASING_PREFIXES):
        return "07 Frames and casings"
    return module_collection


def spool_for(name):
    return spec.spool_of(name)


def material_for(name):
    """Longest matching key in MATERIAL_MAP wins, so 'blades_hpc_r1' beats
    'blades_hpc' and 'nozzle_sidewall' beats 'nozzle'."""
    best, best_len = spec.DEFAULT_MATERIAL, -1
    for key, mat in spec.MATERIAL_MAP.items():
        if name.startswith(key) and len(key) > best_len:
            best, best_len = mat, len(key)
    return best


# --------------------------------------------------------------------------

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"


def make_object(name, verts, faces, collection, scale=MM):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x * scale, y * scale, z * scale) for (x, y, z) in verts],
                   [], [list(f) for f in faces])
    me.validate(verbose=False)
    me.update()
    obj = bpy.data.objects.new(name, me)
    collection.objects.link(obj)
    return obj


def recalc_normals(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.select_set(False)


def apply_cutters(obj, cut_verts, cut_faces):
    """Boolean-difference a joined cutter out of obj, then bin the cutter.
    Exact solver, self-intersection on: a cutter is many solids joined."""
    cutter = make_object(obj.name + "__cutter", cut_verts, cut_faces,
                         bpy.context.scene.collection)
    recalc_normals(cutter)
    m = obj.modifiers.new("holes", "BOOLEAN")
    m.operation = "DIFFERENCE"
    m.solver = "EXACT"
    m.use_self = True
    m.object = cutter
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.object.modifier_apply(modifier=m.name)
        ok = True
    except RuntimeError as exc:
        print(f"    ! boolean failed on {obj.name}: {exc}")
        obj.modifiers.remove(m)
        ok = False
    bpy.data.objects.remove(cutter, do_unlink=True)
    return ok


def build_proto(name, proto, collection):
    """Cut the holes in one aerofoil, then array it and add the rest of the
    part: the same mesh as cutting the whole row, far cheaper."""
    one, holes, count, rest = proto
    obj = make_object(name, *one, collection)
    recalc_normals(obj)
    ok = apply_cutters(obj, *holes)
    verts = [tuple(v.co / MM) for v in obj.data.vertices]
    faces = [tuple(p.vertices) for p in obj.data.polygons]
    v, f = meshlib.replicate(verts, faces, count)
    if rest is not None:
        v, f = meshlib.join((v, f), rest)
    me = bpy.data.meshes.new(name + "_row")
    me.from_pydata([(x * MM, y * MM, z * MM) for (x, y, z) in v], [],
                   [list(fc) for fc in f])
    me.validate(verbose=False)
    me.update()
    old = obj.data
    obj.data = me
    bpy.data.meshes.remove(old)
    return obj, ok


def shade_smooth(obj, angle_deg=32.0):
    """Smooth across gentle curvature, sharp across creases, marked edge by
    edge. The operator for this fails silently in background mode and leaves
    everything smooth, which shades thin-walled rings black."""
    me = obj.data
    for p in me.polygons:
        p.use_smooth = True
    limit = math.cos(math.radians(angle_deg))
    normals = [tuple(p.normal) for p in me.polygons]
    faces_of_edge = {}
    for pi, poly in enumerate(me.polygons):
        for ek in poly.edge_keys:
            faces_of_edge.setdefault(ek, []).append(pi)
    edge_by_key = {e.key: e for e in me.edges}
    n = 0
    for ek, fs in faces_of_edge.items():
        e = edge_by_key.get(ek)
        if e is None:
            continue
        if len(fs) != 2 or sum(a * b for a, b in zip(normals[fs[0]],
                                                     normals[fs[1]])) < limit:
            e.use_edge_sharp = True
            n += 1
    return n


# --------------------------------------------------------------------------

def main():
    t0 = time.time()
    clear_scene()
    mats = materials.build_all()
    cols = {}
    for cname in COLLECTIONS:
        c = bpy.data.collections.new(cname)
        bpy.context.scene.collection.children.link(c)
        cols[cname] = c

    # Build every module before making any object, and pool the cutters, so
    # a cutter aimed at a part another module builds still reaches it.
    built_all, cutters = [], {}
    for modname, module, cname in MODULES:
        built = module.build()
        for key, geom in built.items():
            if key.startswith("cut:"):
                cutters.setdefault(key[4:], []).append(geom)
        built_all.append((modname, cname, built))

    rows, n_bool, n_ok, n_sharp = [], 0, 0, 0
    for modname, mcol, built in built_all:
        t1 = time.time()
        protos = getattr(dict(MODULE_BY_NAME)[modname], "PROTO", {})
        objs = {k: v for k, v in built.items() if not k.startswith("cut:")}
        for name, (verts, faces) in sorted(objs.items()):
            cname = collection_for(name, mcol)
            if name in protos:
                obj, ok = build_proto(name, protos[name], cols[cname])
                n_bool += 1
                n_ok += int(ok)
                recalc_normals(obj)
            else:
                obj = make_object(name, verts, faces, cols[cname])
                # outward before cutting: the boolean reads inside from normals
                recalc_normals(obj)
                for cut in cutters.get(name, ()):
                    n_bool += 1
                    if apply_cutters(obj, *cut):
                        n_ok += 1
                    recalc_normals(obj)
            mat = material_for(name)
            obj.data.materials.append(mats[mat])
            n_sharp += shade_smooth(obj)
            co = [tuple(v.co) for v in obj.data.vertices]
            bb = meshlib.bbox(co)
            r_max = max((math.hypot(c[1], c[2]) for c in co), default=0.0)
            sp = spool_for(name)
            rows.append({
                "name": name, "collection": cname, "module": modname,
                "material": mat,
                "verts": len(obj.data.vertices),
                "faces": len(obj.data.polygons),
                "x_min_mm": round(bb[0] / MM, 1), "x_max_mm": round(bb[3] / MM, 1),
                "y_min_mm": round(bb[1] / MM, 1), "y_max_mm": round(bb[4] / MM, 1),
                "z_min_mm": round(bb[2] / MM, 1), "z_max_mm": round(bb[5] / MM, 1),
                "r_max_mm": round(r_max / MM, 1),
                "spool": sp,
                # LP and HP turn opposite ways: that cancels most of the
                # gyroscopic couple the airframe would otherwise fight
                "spin": 1.0 if sp == "lp" else (-1.0 if sp == "hp" else ""),
            })
        print(f"  [{modname}] {len(objs)} objects in {time.time() - t1:.1f}s")

    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    rows.sort(key=lambda r: r["name"])
    with open(os.path.join(ROOT, "build", "parts.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    tv = sum(r["verts"] for r in rows)
    tf = sum(r["faces"] for r in rows)
    print(f"\n{len(rows)} objects | {tv:,} verts | {tf:,} faces")
    print(f"booleans: {n_ok}/{n_bool} applied")
    if n_ok < n_bool:
        # a cut that did not go through leaves the material it was meant to
        # remove, and every audit downstream would measure a part that was
        # never built
        raise SystemExit(f"{n_bool - n_ok} booleans failed")
    print(f"sharp edges marked: {n_sharp:,}")
    blend = os.path.join(ROOT, "build", "aether.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print(f"blend -> {blend}\ntotal {time.time() - t0:.1f}s")


if __name__ == "__main__":
    # Blender exits 0 even when a background script raises, so a build that
    # dropped a whole module would report success. Fail loudly instead.
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
