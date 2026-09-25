"""Does the engine hold together, and is every load path and circuit joined?

    python3 tools/audit_joints.py

Every other geometry audit is one-sided: `audit_intersect` fails parts that
touch when they should not. A fuel line that stops 40 mm short of the
manifold it feeds passes it, because not touching is exactly what it wants.
This is the other side, stated as obligations:

  ASSEMBLY   every part is attached to the engine, however indirectly
  CIRCUITS   each declared run of material is continuous, link by link --
             load paths from each rotor through its bearings to the mounts,
             and the fuel, oil, air and control circuits
  MODULES    no two modules build a part under the same name, and every
             cutter reaches the part it is aimed at

CONTACT is 2 mm. Parts that are bolted, welded or seated together here meet
at zero or interpenetrate, so anything further apart is not a joint.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import _joints  # noqa: E402

CONTACT_MM = 2.0
ROOT_PART = "case_outer_fwd"
PKG = "engine/parts"
UNIT = "mm"

CIRCUITS = [
    # ---- the pressure vessel and its walls
    ("the outer case is one vessel, inlet to nozzle",
     ["inlet_case", "flange_inlet", "case_fan", "flange_fan_aft",
      "case_outer_fwd", "flange_outer_mid", "case_outer_aft",
      "flange_outer_aft", "swivel_fixed_ring"]),
    ("the fan frame ties hub, splitter and outer case together",
     ["fan_frame_hub", "fan_frame_struts", "intermediate_case"]),
    ("and carries the forward mounts",
     ["fan_frame_struts", "mount_trunnions"]),
    ("the core casings run unbroken from splitter to mixer",
     ["core_splitter", "case_hpc", "case_combustor", "case_turbine",
      "mixer"]),
    ("the core cowl closes the bypass duct over the compressor",
     ["core_splitter", "core_cowl", "case_combustor"]),
    ("the service struts tie the core to the outer case at the back",
     ["case_turbine", "service_struts", "case_outer_aft"]),
    ("the thrust lug is on the rear case", ["case_outer_aft", "mount_aft_lug"]),

    # ---- the LP spool, from the spinner to the bearings to the frame
    ("the LP rotor is one piece: spinner, fan, shaft, turbine",
     ["spinner", "fan_blisk_1", "shaft_lp", "lpt_disc", "blades_lpt_r"]),
    ("the second fan stage rides on the first",
     ["fan_blisk_1", "fan_drum", "fan_blisk_2"]),
    ("the fan runs in bearings 1 and 2, hung from the fan frame",
     ["shaft_lp", "brg_1_lp_roller", "sump_front", "fan_frame_hub"]),
    ("and bearing 2", ["shaft_lp", "brg_2_lp_ball", "sump_front"]),
    ("the LP turbine runs in bearing 5, hung from the mid-turbine frame",
     ["shaft_lp", "brg_5_lp_roller", "sump_rear", "vanes_mtf",
      "case_turbine"]),

    # ---- the HP spool
    ("the HP rotor is one piece: CDFS, drums, compressor, shaft, turbine",
     ["cdfs_blisk", "hp_front_drum", "hpc_drum", "shaft_hp", "hpt_disc",
      "blades_hpt_r"]),
    ("the CDFS is carried on the HP shaft", ["cdfs_blisk", "shaft_hp"]),
    ("every compressor rotor is on the drum",
     ["hpc_drum", "blades_hpc_r1"]),
    ("", ["hpc_drum", "blades_hpc_r6"]),
    ("the HP spool runs in bearing 3 at the front",
     ["shaft_hp", "brg_3_hp_ball", "sump_front"]),
    ("and bearing 4 at the back",
     ["shaft_hp", "brg_4_hp_roller", "sump_rear"]),

    # ---- stators hang from their casings
    ("fan stators in the fan case", ["case_fan", "vanes_fan_s1"]),
    ("", ["case_fan", "vanes_fan_s2", "fan_frame_hub"]),
    ("the CDFS stator in the splitter wall",
     ["intermediate_case", "vanes_cdfs", "vanes_hpc_igv"]),
    ("compressor stators in the case", ["case_hpc", "vanes_hpc_s1"]),
    ("", ["case_hpc", "vanes_hpc_s5"]),
    ("exit guide vanes between the cases",
     ["case_combustor", "diffuser", "combustor_inner_case"]),
    ("the turbine nozzle between the inner case and the turbine case",
     ["combustor_inner_case", "vanes_hpt_ngv", "case_turbine"]),

    # ---- combustor
    ("the liners hang on pins from both cases",
     ["case_combustor", "combustor_mount_pins", "combustor_liner_outer",
      "combustor_dome", "combustor_liner_inner", "combustor_mount_pins",
      "combustor_inner_case"]),
    ("the swirlers are held in the dome", ["combustor_dome", "swirlers"]),
    ("fuel: pump, metering unit, line, manifold, nozzle, swirler",
     ["fuel_pump", "gearbox", "fuel_metering_unit", "fuel_lines",
      "fuel_manifold", "fuel_nozzles", "swirlers"]),
    ("ignition reaches the liner", ["igniters", "combustor_liner_outer"]),

    # ---- augmentor and nozzle
    ("the mixer and augmentor hang off the turbine case",
     ["case_turbine", "mixer"]),
    ("", ["intermediate_case", "augmentor_case", "augmentor_liner"]),
    ("the flameholder's radial gutters hold the tail cone",
     ["augmentor_liner", "flameholder", "tailcone"]),
    ("reheat fuel reaches every spray ring through the reheat control",
     ["fuel_lines", "ab_fuel_control", "ab_fuel_manifold", "ab_spray_rings"]),
    ("and zones 2 and 3 through their spraybars",
     ["ab_fuel_manifold", "ab_spraybars", "ab_spray_rings"]),
    ("the reheat igniter is in the case", ["case_outer_aft", "ab_igniter"]),
    ("the reheat control is on the case", ["case_outer_aft", "ab_fuel_control"]),
    ("the swivel ducts run on from the outer case, bearing to bearing",
     ["case_outer_aft", "flange_outer_aft", "swivel_fixed_ring",
      "swivel_bearing_1", "swivel_duct_fwd", "swivel_bearing_2",
      "swivel_duct_mid", "swivel_bearing_3", "swivel_duct_aft",
      "nozzle_static_ring"]),
    ("each bearing's motor is in mesh with its ring gear",
     ["case_outer_aft", "swivel_drive_1", "swivel_bearing_1"]),
    ("", ["swivel_duct_fwd", "swivel_drive_2", "swivel_bearing_2"]),
    ("", ["swivel_duct_mid", "swivel_drive_3", "swivel_bearing_3"]),
    ("the flaps are hinged on the static ring and at the throat",
     ["nozzle_static_ring", "nozzle_hinges", "nozzle_conv_flaps",
      "nozzle_div_flaps"]),
    ("", ["nozzle_hinges", "nozzle_ext_flaps"]),
    ("the seals lie on the flaps",
     ["nozzle_conv_flaps", "nozzle_conv_seals"]),
    ("", ["nozzle_div_flaps", "nozzle_div_seals"]),
    ("the external flaps are held on the divergent flaps",
     ["nozzle_div_flaps", "nozzle_div_links", "nozzle_ext_flaps"]),
    ("the actuators turn the unison ring, which sets the convergent flaps",
     ["swivel_duct_aft", "nozzle_actuators", "nozzle_unison_ring",
      "nozzle_conv_flaps"]),

    # ---- accessories
    ("the gearbox is driven off the HP spool",
     ["shaft_hp", "towershaft", "gearbox"]),
    ("and hung from the case", ["gearbox", "gearbox_mounts", "case_fan"]),
    ("", ["gearbox", "gearbox_mounts", "case_outer_fwd"]),
    ("it drives the generators", ["gearbox", "generator_l"]),
    ("", ["gearbox", "generator_r"]),
    ("oil: tank to gearbox to the front sump",
     ["oil_tank", "oil_lines", "sump_front"]),
    ("and the scavenge from the rear sump",
     ["sump_rear", "oil_lines", "oil_tank"]),
    ("the FADECs stand on the case and are wired to the gearbox",
     ["case_outer_fwd", "fadec_a", "harnesses", "gearbox"]),
    ("", ["case_outer_fwd", "fadec_b", "harnesses"]),
    ("and each reads its probes on the case through its own loom",
     ["fadec_a", "harness_looms", "sensor_probes", "case_outer_aft"]),
    ("", ["fadec_b", "harness_looms", "sensor_probes", "case_outer_fwd"]),
    ("the igniters are fired from exciters on the case, powered off the looms",
     ["harness_looms", "ignition_leads", "ignition_exciters", "case_outer_fwd"]),
    ("", ["ignition_exciters", "ignition_leads", "igniters"]),
    ("", ["ignition_exciters", "ignition_leads", "ab_igniter"]),
    ("the third stream: mode valve, heat exchanger, coolant out",
     ["intermediate_case", "mode_valve"]),
    ("", ["intermediate_case", "tms_hx", "coolant_lines"]),
    ("the mode valve is actuated from outside the case",
     ["case_outer_fwd", "mode_valve_actuators"]),
    ("the swivel's motors are fed from the gearbox's pump",
     ["gearbox", "hydraulic_pump", "hydraulic_lines", "swivel_drive_1"]),
    ("", ["hydraulic_lines", "swivel_rotary_union", "case_outer_aft"]),
    ("the outer case is stiffened", ["case_outer_fwd", "case_ribs",
                                     "case_outer_aft"]),
    ("the variable vanes are ganged",
     ["vsv_actuation", "vanes_hpc_igv"]),
    ("", ["vsv_actuation", "vanes_hpc_s2"]),
]


def main():
    parts, collisions, cut_owner, built_by, failures = _joints.load(ROOT, PKG)
    bad = []
    print(f"\n{len(parts)} parts from {len(set(built_by.values()))} modules")

    print("\nMODULES")
    for name, why in failures:
        print(f"  x   {name:26s} did not build: {why}")
        bad.append(f"{name} did not build")
    for key, first, second in collisions:
        print(f"  x   {key:26s} built by both {first} and {second}")
        bad.append(f"{key} is built twice")
    for target, owners in sorted(cut_owner.items()):
        for owner in owners:
            if target not in built_by:
                print(f"  x   {target:26s} cut declared by {owner}, and nothing"
                      f" builds it")
                bad.append(f"{target} cutter has no target")
    if not bad:
        print("  ok  every part name is built once and every cutter has a target")

    print(f"\nASSEMBLY  (contact within {CONTACT_MM:g} {UNIT})")
    graph = _joints.contact_graph(parts, CONTACT_MM)
    groups = _joints.components(graph)
    main_group = next((g for g in groups if ROOT_PART in g), set())
    loose = [g for g in groups if g is not main_group]
    if not loose:
        print(f"  ok  all {len(main_group)} parts hang together off {ROOT_PART}")
    for g in loose:
        names = ", ".join(sorted(g))
        print(f"  x   detached: {names}")
        bad.append(f"detached: {names}")

    print("\nCIRCUITS")
    last = ""
    for label, chain in CIRCUITS:
        label = label or last
        last = label
        breaks = _joints.broken_links(parts, graph, chain)
        if not breaks:
            print(f"  ok  {label}: {' -> '.join(chain)}" if len(chain) <= 3
                  else f"  ok  {label}")
            continue
        for (_i, a, b, why) in breaks:
            extra = ""
            if why == "no contact":
                A, B = _joints.match(parts, a), _joints.match(parts, b)
                d = min(_joints.gap(parts[x], parts[y]) for x in A for y in B)
                extra = f" ({d:.1f} {UNIT} apart)"
            print(f"  x   {label}: {a} -> {b}, {why}{extra}")
            bad.append(f"{label}: {a} -> {b} {why}")

    print()
    if not bad:
        print("PASS  it is one assembly and every circuit is joined")
        return 0
    print(f"FAIL  {len(bad)} joints are not made")
    return 1


if __name__ == "__main__":
    sys.exit(main())
