"""Render the assembled engine. Run under `blender --background`.

    blender -b build/aether.blend -P engine/render.py -- <mode> [samples]

Modes: hero, rear, cutaway, exploded, all (those four), closeups (detail
shots used to inspect the model: fan face, core, turbine, combustor, nozzle,
gearbox), or any single closeup by name.
"""

import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "renders")

X_MID = 2.245       # engine centre, metres: inlet to nozzle exit
SPAN = 3.75


def setup_world(strength=0.35):
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    grad = nt.nodes.new("ShaderNodeTexGradient")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    tex = nt.nodes.new("ShaderNodeTexCoord")
    mapn = nt.nodes.new("ShaderNodeMapping")
    mapn.inputs["Rotation"].default_value = (math.radians(90), 0, 0)
    ramp.color_ramp.elements[0].color = (0.010, 0.012, 0.015, 1)
    ramp.color_ramp.elements[1].color = (0.105, 0.115, 0.130, 1)
    nt.links.new(tex.outputs["Generated"], mapn.inputs["Vector"])
    nt.links.new(mapn.outputs["Vector"], grad.inputs["Vector"])
    nt.links.new(grad.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    bg.inputs["Strength"].default_value = strength


def area_light(name, loc, target, energy, size):
    d = bpy.data.lights.new(name, type="AREA")
    d.energy = energy
    d.size = size
    d.shape = "RECTANGLE"
    d.size_y = size * 0.55
    o = bpy.data.objects.new(name, d)
    o.location = loc
    bpy.context.scene.collection.objects.link(o)
    aim(o, target)
    return o


def setup_lights(scale=1.0):
    for o in [o for o in bpy.data.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o, do_unlink=True)
    c = (X_MID, 0.0, 0.0)
    # a raking key from high front-left, a soft low fill, a rim from behind
    # to separate the silhouette from the background, and a kicker on the nose
    area_light("key", (X_MID - 2.5, -6.5, 5.0), c, 1300 * scale, 7.0)
    area_light("fill", (X_MID + 2.0, 6.0, -2.0), c, 380 * scale, 9.0)
    area_light("rim", (X_MID + 6.5, 3.0, 3.5), c, 1300 * scale, 4.0)
    area_light("nose", (X_MID - 7.0, -2.0, 1.2), c, 500 * scale, 3.5)


def aim(obj, look_at):
    d = Vector(look_at) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def setup_camera(loc, look_at, lens=60.0):
    cam = bpy.data.cameras.new("cam")
    cam.lens = lens
    cam.clip_start = 0.02
    obj = bpy.data.objects.new("cam", cam)
    obj.location = loc
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.scene.camera = obj
    aim(obj, look_at)
    return obj


def setup_render(samples=64, res=(1920, 1080)):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.samples = samples
    s.cycles.use_denoising = True
    s.cycles.max_bounces = 6
    s.cycles.caustics_reflective = False
    s.render.resolution_x, s.render.resolution_y = res
    s.render.film_transparent = False
    s.view_settings.view_transform = "AgX"
    s.view_settings.exposure = -0.7
    s.view_settings.look = "AgX - Medium High Contrast"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        s.cycles.device = "GPU"
    except Exception as exc:
        print("  (GPU unavailable, using CPU:", exc, ")")


def reset():
    """Undo what a previous mode did: cameras, section modifiers, hidden and
    moved objects."""
    for o in list(bpy.data.objects):
        if o.type == "CAMERA" or o.name.startswith("__"):
            bpy.data.objects.remove(o, do_unlink=True)
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        for m in list(o.modifiers):
            if m.name == "section":
                o.modifiers.remove(m)
        o.hide_render = False
        if "home" in o:
            o.location = tuple(o["home"])
        else:
            o["home"] = tuple(o.location)


def shoot(name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name + ".png")
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("  ->", path)


# --------------------------------------------------------------------------
# sectioning

SECTION = ("case_", "inlet_case", "containment", "flange_", "intermediate_case",
           "core_cowl", "core_splitter", "fan_frame_hub", "service_struts",
           "tms_hx", "mode_valve", "combustor_liner_", "combustor_inner_case",
           "combustor_dome", "augmentor_", "mixer", "swivel_fixed_ring",
           "swivel_duct_", "nozzle_static_ring", "fuel_manifold",
           "ab_fuel_manifold",
           "vsv_actuation", "sump_", "tailcone")


def section(x0=-1.0, x1=5.0, hide_externals=True):
    """Peel the static shells off the camera's side (y < 0) between x0 and
    x1, leave the rotors and blades whole, and hide the externals that would
    otherwise hang in front of the cut."""
    bpy.ops.mesh.primitive_cube_add(size=1)
    cutter = bpy.context.active_object
    cutter.name = "__section"
    cutter.scale = (x1 - x0, 2.0, 2.4)
    cutter.location = (0.5 * (x0 + x1), -1.0, 0.0)
    cutter.hide_render = True
    n = 0
    for o in bpy.data.objects:
        if o.type != "MESH" or o is cutter:
            continue
        if hide_externals and o.users_collection and \
                o.users_collection[0].name == "09 Accessories":
            o.hide_render = True
            continue
        if hide_externals and o.name in ("fuel_nozzles", "igniters"):
            o.hide_render = True
            continue
        if not o.name.startswith(SECTION):
            continue
        m = o.modifiers.new("section", "BOOLEAN")
        m.operation = "DIFFERENCE"
        m.solver = "FLOAT"
        m.object = cutter
        n += 1
    print(f"  sectioned {n} shells")


# --------------------------------------------------------------------------

def mode_hero(samples):
    reset(); setup_render(samples); setup_world(); setup_lights()
    area_light("face", (X_MID - 8.6, -3.4, 0.9), (0, 0, 0), 700, 3.0)
    setup_camera((X_MID - 7.9, -7.2, 2.7), (X_MID - 0.35, 0, -0.05), lens=58)
    shoot("01_hero")


def mode_rear(samples):
    reset(); setup_render(samples); setup_world(); setup_lights()
    area_light("tail", (X_MID + 6.0, -2.5, 2.0), (X_MID + 1.8, 0, 0), 700, 3.0)
    setup_camera((X_MID + 6.4, -5.3, 2.1), (X_MID + 0.8, 0, -0.05), lens=55)
    shoot("02_rear_quarter")


def mode_cutaway(samples):
    reset(); setup_render(samples); setup_world(0.28); setup_lights()
    section()
    area_light("bore", (X_MID - 0.2, -3.8, 1.2), (X_MID, 0, 0), 500, 7.0)
    area_light("bore2", (X_MID + 1.0, -2.4, 2.8), (X_MID, 0, 0), 250, 5.0)
    setup_camera((X_MID - 1.8, -9.0, 2.8), (X_MID + 0.05, 0, -0.05), lens=52)
    shoot("03_cutaway")


def mode_exploded(samples):
    reset(); setup_render(samples); setup_world(); setup_lights()
    moves = {
        "01 Fan": (-0.9, 0.0), "02 Compressor": (-0.3, 0.0),
        "03 Combustor": (0.25, 0.0), "04 Turbines": (0.75, 0.0),
        "05 Augmentor": (1.3, 0.0), "06 Nozzle": (1.95, 0.0),
        "07 Frames and casings": (0.4, 1.35),
        "08 Spools and bearings": (0.4, -1.25),
        "09 Accessories": (0.4, -2.05),
    }
    for cname, (dx, dz) in moves.items():
        col = bpy.data.collections.get(cname)
        for o in (col.objects if col else ()):
            o.location.x += dx
            o.location.z += dz
    setup_camera((X_MID - 4.2, -14.6, 3.4), (X_MID + 0.7, 0, -0.1), lens=46)
    shoot("04_exploded")


# close-ups: (name, camera, target, lens, section?)
CLOSEUPS = {
    "c1_fan_face": ((-2.6, -1.0, 0.45), (0.0, 0.0, 0.0), 45, False),
    "c2_compressor": ((0.9, -1.55, 0.55), (0.95, 0.0, 0.05), 38, True),
    "c3_combustor_turbine": ((1.65, -1.25, 0.45), (1.72, 0.0, 0.08), 40, True),
    "c4_nozzle": ((5.3, -1.7, 0.9), (4.15, 0.0, 0.0), 42, False),
    "c7_swivel": ((3.4, -2.2, 0.7), (3.45, 0.0, 0.0), 40, False),
    "c5_gearbox": ((0.2, -1.6, -1.2), (0.65, 0.0, -0.45), 40, False),
    "c6_augmentor": ((2.4, -1.5, 0.5), (2.45, 0.0, 0.0), 38, True),
}


def mode_closeup(name, samples):
    reset(); setup_render(samples, (1600, 900)); setup_world(0.3)
    cam, tgt, lens, cut = CLOSEUPS[name]
    setup_lights(0.6)
    if cut:
        section()
    area_light("near", tuple(c + d for c, d in zip(cam, (0.3, -0.6, 0.9))),
               tgt, 130, 1.6)
    setup_camera(cam, tgt, lens)
    shoot(name)


def pose_swivel(pitch_deg, yaw_deg=0.0):
    """Turn the swivel's three bearings to point the jet pitch_deg down: each
    group of parts is carried by every bearing in front of it."""
    from mathutils import Matrix, Vector
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from parts import nozzle
    angles = nozzle.swivel_pose(pitch_deg, yaw_deg)
    fr = [nozzle.square(nozzle.N["x_brg1"]), nozzle.oblique(1), nozzle.oblique(2)]
    chain = Matrix.Identity(4)
    for k, key in enumerate(("fwd", "mid", "aft")):
        c = Vector(fr[k][0]) * 0.001
        R = Matrix.Rotation(angles[k], 4, Vector(fr[k][1]))
        chain = chain @ Matrix.Translation(c) @ R @ Matrix.Translation(-c)
        for name in nozzle.GROUPS[key]:
            o = bpy.data.objects.get(name)
            if o is not None:
                o.matrix_world = chain @ o.matrix_world


def mode_hover(samples):
    """The nozzle folded straight down, as for a vertical landing."""
    reset(); setup_render(samples); setup_world(); setup_lights()
    pose_swivel(90.0)
    area_light("tail", (X_MID + 5.0, -4.0, 1.5), (X_MID + 1.2, 0, -0.4), 700, 3.0)
    setup_camera((X_MID + 4.2, -6.6, 1.2), (X_MID + 0.9, 0, -0.35), lens=50)
    shoot("05_hover")


MODES = {"hero": mode_hero, "rear": mode_rear, "cutaway": mode_cutaway,
         "exploded": mode_exploded, "hover": mode_hover}


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["hero"]
    mode = argv[0] if argv else "hero"
    samples = int(argv[1]) if len(argv) > 1 else 64
    if mode == "all":
        for m in ("hero", "rear", "cutaway", "exploded", "hover"):
            MODES[m](samples)
    elif mode == "closeups":
        for n in CLOSEUPS:
            mode_closeup(n, samples)
    elif mode in CLOSEUPS:
        mode_closeup(mode, samples)
    else:
        MODES[mode](samples)
