"""Build docs/dataset_episodes.json: every dataset trial for the full gallery.

Enumerates all 2,610 episodes across the three source subsets (re-homed to
allegro/inspire), recording per episode: camera serials, executed-grasp status,
and whether an interactive-3D GLB exists. This is the full-dataset analogue of
the curated experiments.json.

    python scripts/build_dataset_manifest.py
"""
import json
import os

D = "/home/mingi/shared_data/autodex_dataset"
GLB_ROOT = "/home/mingi/shared_data/AutoDex/interactive_3d"
OUT = "/home/mingi/autodex-gallery/docs/dataset_episodes.json"
SUBSETS = {
    "selected_100": "allegro",
    "corl_selected_100": "allegro",
    "selected_100_inspire": "inspire",
}


def episode_cameras(ep):
    vdir = os.path.join(ep, "videos")
    if not os.path.isdir(vdir):
        return []
    return sorted(f[:-4] for f in os.listdir(vdir) if f.endswith(".avi"))


EXPERIMENTS = "/home/mingi/autodex-gallery/docs/experiments.json"


def load_status_map():
    """(hand, obj, timestamp) -> 'success'|'fail' from the curated experiments.json.

    The raw dataset's executed_grasp/meta.json success is usually null (untracked);
    the tracked outcome lives in experiments.json keyed by dir_idx (= timestamp)."""
    m = {}
    try:
        d = json.load(open(EXPERIMENTS))
    except Exception:
        return m
    for hand, objs in d.items():
        for obj, ranks in (objs or {}).items():
            for _, exp in (ranks or {}).items():
                ts = exp.get("dir_idx")
                st = exp.get("status")
                if ts and st in ("success", "fail"):
                    m[(hand, obj, str(ts))] = st
    return m


def main():
    status_map = load_status_map()
    manifest = {"allegro": {}, "inspire": {}}
    counts = {"allegro": 0, "inspire": 0}
    for src, hand in SUBSETS.items():
        droot = os.path.join(D, src)
        if not os.path.isdir(droot):
            continue
        for obj in sorted(os.listdir(droot)):
            oroot = os.path.join(droot, obj)
            if not os.path.isdir(oroot):
                continue
            for ts in sorted(os.listdir(oroot)):
                ep = os.path.join(oroot, ts)
                if not os.path.isdir(ep):
                    continue
                cams = episode_cameras(ep)
                if not cams:
                    continue  # skip episodes with no video (nothing to browse)
                ovdir = os.path.join(ep, "object_overlay")
                entry = {
                    "ts": ts,
                    "cameras": cams,
                    "status": status_map.get((hand, obj, ts), "unknown"),
                    "has_glb": os.path.isdir(os.path.join(GLB_ROOT, hand, obj, ts)),
                    "has_overlay": os.path.isdir(ovdir) and bool(os.listdir(ovdir)),
                }
                manifest[hand].setdefault(obj, []).append(entry)
                counts[hand] += 1

    # stable order: episodes by timestamp within each object
    for hand in manifest:
        for obj in manifest[hand]:
            manifest[hand][obj].sort(key=lambda e: e["ts"])

    json.dump(manifest, open(OUT, "w"))
    total = counts["allegro"] + counts["inspire"]
    n_glb = sum(1 for h in manifest for o in manifest[h] for e in manifest[h][o] if e["has_glb"])
    print(f"wrote {OUT}")
    print(f"episodes: allegro={counts['allegro']} inspire={counts['inspire']} total={total}")
    print(f"with GLB: {n_glb}")


if __name__ == "__main__":
    main()
