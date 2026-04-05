"""Upload experiment videos to HuggingFace dataset.

For each object, picks one successful trial per candidate_idx,
converts AVI to MP4, and uploads everything in a single commit.

Usage:
    python scripts/upload_experiments.py                     # All
    python scripts/upload_experiments.py --hand allegro       # One hand
    python scripts/upload_experiments.py --obj banana apple   # Specific objects
    python scripts/upload_experiments.py --dry-run            # Preview only
"""
import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi


REPO_ID = "willi19/autodex-gallery"
REPO_TYPE = "dataset"
EXP_BASE = Path.home() / "shared_data" / "AutoDex" / "experiment" / "selected_100"


def convert_avi_to_mp4(avi_path, mp4_path):
    subprocess.run([
        "ffmpeg", "-i", str(avi_path),
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-an", "-y", str(mp4_path)
    ], capture_output=True)


def get_successful_trials(summary_path):
    with open(summary_path) as f:
        trials = json.load(f)
    selected = {}
    for trial in trials:
        cidx = trial.get("candidate_idx")
        if cidx is None or cidx in selected:
            continue
        if trial.get("success"):
            selected[cidx] = trial
    return selected


def collect_tasks(args):
    """Collect all (hand, obj, cidx, trial) tuples to process."""
    tasks = []
    for hand in args.hand:
        hand_dir = EXP_BASE / hand
        if not hand_dir.exists():
            print(f"Skipping {hand}: not found")
            continue
        objects = args.obj if args.obj else sorted([
            d for d in os.listdir(hand_dir)
            if (hand_dir / d).is_dir()
        ])
        for obj in objects:
            summary_path = hand_dir / obj / "summary.json"
            if not summary_path.exists():
                continue
            selected = get_successful_trials(summary_path)
            if not selected:
                continue
            for cidx, trial in sorted(selected.items()):
                videos_dir = hand_dir / obj / trial["dir_idx"] / "videos"
                if not videos_dir.exists() or not list(videos_dir.glob("*.avi")):
                    continue
                tasks.append((hand, obj, cidx, trial))
    return tasks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hand", nargs="+", default=["allegro", "inspire"])
    parser.add_argument("--obj", nargs="+", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tasks = collect_tasks(args)
    total_cams = sum(
        len(list((EXP_BASE / h / o / t["dir_idx"] / "videos").glob("*.avi")))
        for h, o, _, t in tasks
    )
    print(f"Found {len(tasks)} grasps, {total_cams} videos to convert")

    if args.dry_run:
        cur_obj = None
        for hand, obj, cidx, trial in tasks:
            key = f"{hand}/{obj}"
            if key != cur_obj:
                cur_obj = key
                count = sum(1 for h, o, _, _ in tasks if f"{h}/{o}" == key)
                print(f"\n{key}: {count} grasps")
            n = len(list((EXP_BASE / hand / obj / trial["dir_idx"] / "videos").glob("*.avi")))
            print(f"  candidate #{cidx} -> rank {cidx:03d}/ ({n} cameras)")
        return

    api = HfApi()
    api.create_repo(REPO_ID, repo_type=REPO_TYPE, exist_ok=True)

    tmpdir = Path(tempfile.mkdtemp())
    operations = []

    for i, (hand, obj, cidx, trial) in enumerate(tasks):
        rank = f"{cidx:03d}"
        videos_dir = EXP_BASE / hand / obj / trial["dir_idx"] / "videos"
        out_dir = tmpdir / hand / obj / rank
        out_dir.mkdir(parents=True, exist_ok=True)

        avis = sorted(videos_dir.glob("*.avi"))
        print(f"[{i+1}/{len(tasks)}] {hand}/{obj}/{rank} ({len(avis)} cameras)")

        for avi in avis:
            serial = avi.stem
            mp4_path = out_dir / f"{serial}.mp4"
            convert_avi_to_mp4(avi, mp4_path)
            operations.append(CommitOperationAdd(
                path_in_repo=f"experiments/{hand}/{obj}/{rank}/{serial}.mp4",
                path_or_fileobj=str(mp4_path),
            ))

        meta = {
            "candidate_idx": cidx,
            "success": trial["success"],
            "scene_info": trial.get("scene_info"),
            "dir_idx": trial["dir_idx"],
            "cameras": [avi.stem for avi in avis],
        }
        meta_path = out_dir / "meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
        operations.append(CommitOperationAdd(
            path_in_repo=f"experiments/{hand}/{obj}/{rank}/meta.json",
            path_or_fileobj=str(meta_path),
        ))

    print(f"\nUploading {len(operations)} files in 1 commit...")
    api.create_commit(
        repo_id=REPO_ID,
        repo_type=REPO_TYPE,
        operations=operations,
        commit_message=f"Add {len(operations)} experiment files",
    )
    print(f"Done! {len(operations)} files uploaded.")


if __name__ == "__main__":
    main()
