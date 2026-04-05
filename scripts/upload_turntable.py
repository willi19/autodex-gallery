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

    # Stage all files, single commit
    print("Uploading all in one commit...")
    operations = []
    from huggingface_hub import CommitOperationAdd
    for local, remote in uploads:
        operations.append(CommitOperationAdd(path_in_repo=remote, path_or_fileobj=local))

    api.create_commit(
        repo_id=REPO_ID,
        repo_type=REPO_TYPE,
        operations=operations,
        commit_message=f"Add {len(uploads)} turntable videos",
    )
    print(f"Done! Uploaded {len(uploads)} videos in 1 commit.")


if __name__ == "__main__":
    main()
