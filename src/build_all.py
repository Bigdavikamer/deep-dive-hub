"""Run every phase in order, then validate.

ORDER MATTERS, and not only because later phases supersede earlier ones.
Several phases write state that a later phase reads and that nothing else
reproduces:

  - Phases 3, 4b, 5, 6 and 7c each call lib.mood.mark_glass on the lanterns
    they build, which sets per-polygon material indices. Phase 8 paints those
    slots. Running Phase 8 against a scene where an earlier phase has not run
    since the indices were last disturbed paints a lantern with no glass.
  - Phase 7b instances the Phase 7a kit by linked mesh data, so 7a must exist
    before 7b runs, and 7b must re-run whenever 7a rebuilds or the instances
    point at orphaned datablocks.
  - Phase 7c sits on top of 7b's placement and purges by site token, so it
    always follows 7b.

Running the phases piecemeal is fine while iterating on one of them; this is
the script that proves the whole thing still builds from nothing.

Usage inside Blender:  exec(open(".../build_all.py").read())
or headless:           blender --background --python src/build_all.py
"""
import importlib
import os
import sys
import time

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

PHASES = [
    ("p1_greybox", "Greybox"),
    ("p2_terrain", "Terrain shell"),
    ("p3_shop", "Shop + spire"),
    ("p4_plaza", "Plaza, paths, leaderboard"),
    ("p4b_merchant", "Merchant Row + enclosure"),
    ("p5_plots", "Plots"),
    ("p6_gate", "Ocean gate + harbour works"),
    ("p7a_kit", "Prop kit"),
    ("p7b_scatter", "Zones, lanes, vignettes"),
    ("p7c_story", "Hand-placed storytelling"),
    ("p8_materials", "Materials + manifest"),
]


def build_all(verbose=True):
    import bpy

    started = time.time()
    for mod_name, label in PHASES:
        t0 = time.time()
        mod = importlib.import_module(mod_name)
        importlib.reload(mod)
        if verbose:
            print(f"\n=== {mod_name}: {label} ===")
        mod.build()
        bpy.context.view_layer.update()
        if verbose:
            print(f"    ({time.time() - t0:.1f}s)")
    print(f"\nbuild_all: {len(PHASES)} phases in {time.time() - started:.1f}s")


def validate():
    import validate as dd_validate
    importlib.reload(dd_validate)
    return dd_validate.main()


if __name__ == "__main__":
    build_all()
    sys.exit(validate())
