"""Upload experiment videos to HuggingFace dataset.

Uses setcover rank (from scene_info -> setcover_order.json) as directory index.
For each object:
1. Copy AVIs from NAS to local
2. Convert AVI -> MP4
3. Upload per object
4. Cleanup

Usage:
    python scripts/upload_experiments.py                     # All
    python scripts/upload_experiments.py --hand allegro       # One hand
    python scripts/upload_experiments.py --obj banana apple   # Specific objects
    python scripts/upload_experiments.py --dry-run            # Preview only
"""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from huggingface_hub import HfApi


REPO_ID = "willi19/autodex-gallery"
REPO_TYPE = "dataset"
EXP_BASE = Path.home() / "shared_data" / "AutoDex" / "experiment" / "selected_100"
ORDER_BASE = Path.home() / "AutoDex" / "order"
LOCAL_TMP = Path("/tmp/exp_convert")


def convert_avi_to_mp4(avi_path, mp4_path):
    subprocess.run([
        "ffmpeg", "-i", str(avi_path),
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-an", "-y", str(mp4_path)
    ], capture_output=True)


def load_scene_to_rank(hand, obj):
    """Load setcover_order.json and build scene_info -> rank mapping."""
    order_path = ORDER_BASE / hand / "v3" / obj / "setcover_order.json"
    if not order_path.exists():
        return {}
    order = json.load(open(order_path))
    mapping = {}
    for rank, entry in enumerate(order):
        key = (entry[1], str(entry[2]), str(entry[3]))
        mapping[key] = rank
    return mapping


def get_best_trials(summary_path, scene_to_rank):
    """Pick one best trial per setcover rank (prefer success)."""
    trials = json.load(open(summary_path))

    by_rank = {}
    for t in trials:
        si = t.get("scene_info")
        if not si:
            continue
        key = (si[0], str(si[1]), str(si[2]))
        rank = scene_to_rank.get(key)
        if rank is None:
            continue
        if rank not in by_rank:
            by_rank[rank] = []
        by_rank[rank].append(t)

    selected = {}
    for rank, rank_trials in by_rank.items():
        best = next((t for t in rank_trials if t.get("success")), rank_trials[0])
        selected[rank] = best
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hand", nargs="+", default=["allegro", "inspire"])
    parser.add_argument("--obj", nargs="+", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api = HfApi()
    if not args.dry_run:
        api.create_repo(REPO_ID, repo_type=REPO_TYPE, exist_ok=True)

    obj_tasks = []
    for hand in args.hand:
        hand_dir = EXP_BASE / hand
        if not hand_dir.exists():
            continue
        objects = args.obj if args.obj else sorted([
            d for d in os.listdir(hand_dir) if (hand_dir / d).is_dir()
        ])
        for obj in objects:
            summary_path = hand_dir / obj / "summary.json"
            if not summary_path.exists():
                continue
            scene_to_rank = load_scene_to_rank(hand, obj)
            if not scene_to_rank:
                continue
            selected = get_best_trials(summary_path, scene_to_rank)
            if not selected:
                continue
            # Filter to only those with videos
            valid = {}
            for rank, trial in selected.items():
                vdir = hand_dir / obj / trial["dir_idx"] / "videos"
                if vdir.exists() and list(vdir.glob("*.avi")):
                    valid[rank] = trial
            if valid:
                obj_tasks.append((hand, obj, valid))

    total_grasps = sum(len(v) for _, _, v in obj_tasks)
    total_cams = sum(
        len(list((EXP_BASE / h / o / t["dir_idx"] / "videos").glob("*.avi")))
        for h, o, trials in obj_tasks for t in trials.values()
    )
    print(f"Found {len(obj_tasks)} objects, {total_grasps} grasps, {total_cams} videos")

    if args.dry_run:
        for hand, obj, trials in obj_tasks:
            print(f"\n{hand}/{obj}: {len(trials)} grasps")
            for rank, trial in sorted(trials.items()):
                n = len(list((EXP_BASE / hand / obj / trial["dir_idx"] / "videos").glob("*.avi")))
                status = "OK" if trial.get("success") else "FAIL"
                print(f"  setcover_rank={rank:3d} ({status}) scene={trial.get('scene_info')} ({n} cams)")
        return

    for oi, (hand, obj, trials) in enumerate(obj_tasks):
        print(f"\n[{oi+1}/{len(obj_tasks)}] {hand}/{obj} ({len(trials)} grasps)")

        mp4_dir = LOCAL_TMP / "mp4" / hand / obj

        for rank, trial in sorted(trials.items()):
            rank_str = f"{rank:03d}"
            nas_videos = EXP_BASE / hand / obj / trial["dir_idx"] / "videos"
            local_avi = LOCAL_TMP / "avi" / hand / obj / rank_str
            out_dir = mp4_dir / rank_str

            # Copy from NAS
            local_avi.mkdir(parents=True, exist_ok=True)
            avis = sorted(nas_videos.glob("*.avi"))
            print(f"  Copying rank {rank_str}/ ({len(avis)} files)...")
            for avi in avis:
                shutil.copy2(avi, local_avi / avi.name)

            # Convert
            out_dir.mkdir(parents=True, exist_ok=True)
            print(f"  Converting rank {rank_str}/...")
            for avi in sorted(local_avi.glob("*.avi")):
                convert_avi_to_mp4(avi, out_dir / f"{avi.stem}.mp4")

            # Metadata
            meta = {
                "setcover_rank": rank,
                "success": trial.get("success", False),
                "scene_info": trial.get("scene_info"),
                "dir_idx": trial["dir_idx"],
                "cameras": [avi.stem for avi in avis],
            }
            with open(out_dir / "meta.json", "w") as f:
                json.dump(meta, f, indent=2)

            # Cleanup AVI
            shutil.rmtree(local_avi, ignore_errors=True)

        # Upload
        print(f"  Uploading {hand}/{obj}...")
        api.upload_folder(
            repo_id=REPO_ID,
            repo_type=REPO_TYPE,
            folder_path=str(mp4_dir),
            path_in_repo=f"experiments/{hand}/{obj}",
        )
        print(f"  Done: {hand}/{obj}")

        # Cleanup MP4
        shutil.rmtree(mp4_dir, ignore_errors=True)

    shutil.rmtree(LOCAL_TMP, ignore_errors=True)
    print("\nAll done!")


if __name__ == "__main__":
    main()
