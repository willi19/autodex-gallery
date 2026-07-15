"""Deferred pass: upload the debug-only object_overlay/ videos.

Run AFTER upload_dataset.py has finished the video-first main pass. Uploads
{hand}/{object}/{timestamp}/object_overlay/ for the ~420 episodes that have it,
using its own ledger so it is independently resumable.

    python scripts/upload_overlay.py
"""
import os

os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
os.environ.setdefault("HF_XET_HIGH_PERFORMANCE", "1")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")

import time

from huggingface_hub import HfApi

REPO_ID = "willi19/autodex-gallery"
REPO_TYPE = "dataset"
D = "/home/mingi/shared_data/autodex_dataset"
SUBSETS = {
    "selected_100": "allegro",
    "corl_selected_100": "allegro",
    "selected_100_inspire": "inspire",
}
LEDGER = "/home/mingi/shared_data/_overlay_upload_done.txt"
MAX_RETRIES = 4


def load_ledger():
    if not os.path.exists(LEDGER):
        return set()
    with open(LEDGER) as f:
        return set(line.strip() for line in f if line.strip())


def mark_done(key):
    with open(LEDGER, "a") as f:
        f.write(key + "\n")


def main():
    api = HfApi()
    done = load_ledger()

    tasks = []
    for src, hand in SUBSETS.items():
        droot = os.path.join(D, src)
        if not os.path.isdir(droot):
            continue
        for obj in sorted(os.listdir(droot)):
            oroot = os.path.join(droot, obj)
            if not os.path.isdir(oroot):
                continue
            for ts in sorted(os.listdir(oroot)):
                ov = os.path.join(oroot, ts, "object_overlay")
                if os.path.isdir(ov) and os.listdir(ov):
                    tasks.append((hand, obj, ts, ov))

    total = len(tasks)
    print(f"episodes with object_overlay: {total} | already in ledger: {len(done)}", flush=True)
    uploaded = 0
    for i, (hand, obj, ts, ov) in enumerate(tasks, 1):
        key = f"{hand}/{obj}/{ts}"
        if key in done:
            continue
        ok = False
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                api.upload_folder(
                    folder_path=ov,
                    path_in_repo=f"{key}/object_overlay",
                    repo_id=REPO_ID,
                    repo_type=REPO_TYPE,
                    commit_message=f"Add object_overlay {key}",
                )
                ok = True
                break
            except Exception as e:  # noqa: BLE001
                print(f"[{i}/{total}] {key} attempt {attempt} {type(e).__name__}: {str(e)[:80]}", flush=True)
                time.sleep(5)
        if ok:
            mark_done(key)
            uploaded += 1
        else:
            print(f"[{i}/{total}] {key} FAILED (retry next run)", flush=True)

    print(f"DONE overlay run: {uploaded} uploaded; ledger now {len(load_ledger())}/{total}", flush=True)


if __name__ == "__main__":
    main()
