"""Upload turntable videos to HuggingFace dataset.

Usage:
    python scripts/upload_turntable.py                    # Upload all
    python scripts/upload_turntable.py --hand allegro     # Only allegro
    python scripts/upload_turntable.py --obj apple banana # Specific objects
    python scripts/upload_turntable.py --dry-run          # Preview only
"""
import argparse
import os
from pathlib import Path

from huggingface_hub import HfApi


REPO_ID = "willi19/autodex-gallery"
REPO_TYPE = "dataset"
DATA_DIR = Path.home() / "AutoDex" / "data"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hand", nargs="+", default=["allegro", "inspire"])
    parser.add_argument("--obj", nargs="+", default=None, help="Specific objects")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api = HfApi()

    # Ensure repo exists
    if not args.dry_run:
        api.create_repo(REPO_ID, repo_type=REPO_TYPE, exist_ok=True)

    uploads = []
    for hand in args.hand:
        hand_dir = DATA_DIR / hand
        if not hand_dir.exists():
            print(f"Skipping {hand}: directory not found")
            continue

        objects = args.obj if args.obj else sorted(os.listdir(hand_dir))
        for obj in objects:
            obj_dir = hand_dir / obj
            if not obj_dir.is_dir():
                continue
            for rank_dir in sorted(obj_dir.iterdir()):
                mp4 = rank_dir / "turntable.mp4"
                if mp4.exists():
                    remote_path = f"turntable/{hand}/{obj}/{rank_dir.name}/turntable.mp4"
                    uploads.append((str(mp4), remote_path))

    print(f"Found {len(uploads)} videos to upload")

    if args.dry_run:
        for local, remote in uploads[:10]:
            print(f"  {local} -> {remote}")
        if len(uploads) > 10:
            print(f"  ... and {len(uploads) - 10} more")
        return

    # Upload in batches using folder upload for efficiency
    for hand in args.hand:
        hand_dir = DATA_DIR / hand
        if not hand_dir.exists():
            continue

        objects = args.obj if args.obj else sorted(os.listdir(hand_dir))
        for obj in objects:
            obj_dir = hand_dir / obj
            if not obj_dir.is_dir():
                continue

            print(f"Uploading {hand}/{obj}...")
            api.upload_folder(
                repo_id=REPO_ID,
                repo_type=REPO_TYPE,
                folder_path=str(obj_dir),
                path_in_repo=f"turntable/{hand}/{obj}",
                allow_patterns=["*/turntable.mp4"],
            )
            print(f"  Done: {hand}/{obj}")

    print("All uploads complete!")


if __name__ == "__main__":
    main()
