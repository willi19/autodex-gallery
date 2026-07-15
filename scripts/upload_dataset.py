"""Upload the raw AutoDex dataset to willi19/autodex-gallery under clean names.

Source subsets are re-homed on HuggingFace by hand:
    selected_100, corl_selected_100  ->  allegro/
    selected_100_inspire             ->  inspire/

Uploads at the repo root as {hand}/{object}/{timestamp}/..., excluding the heavy
raw/ and init_capture/ dirs. Commits PER EPISODE (small enough to land before
network timeouts) and records completed episodes (by repo path) in a local
ledger for full resumability.

Must NOT run concurrently with any other upload to the same repo.

    python scripts/upload_dataset.py
"""
import os

# Speed/robustness tuning — must be set before importing huggingface_hub.
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")  # accelerated LFS path
os.environ.setdefault("HF_XET_HIGH_PERFORMANCE", "1")    # xet high-throughput uploads
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")   # fewer spurious ReadTimeouts

import time

from huggingface_hub import HfApi

REPO_ID = "willi19/autodex-gallery"
REPO_TYPE = "dataset"
D = "/home/mingi/shared_data/autodex_dataset"
# source dataset folder -> repo top-level hand folder
SUBSETS = {
    "selected_100": "allegro",
    "corl_selected_100": "allegro",
    "selected_100_inspire": "inspire",
}
# object_overlay is debug-only -> deferred to a separate later pass (upload_overlay.py)
IGNORE = ["raw/**", "init_capture/**", "raw/*", "init_capture/*",
          "object_overlay/**", "object_overlay/*"]
LEDGER = "/home/mingi/shared_data/_dataset_upload_done.txt"
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

    episodes = []
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
                if os.path.isdir(ep):
                    episodes.append((hand, obj, ts, ep))

    total = len(episodes)
    print(f"episodes: {total} | already in ledger: {len(done)}", flush=True)
    uploaded = 0
    for i, (hand, obj, ts, ep) in enumerate(episodes, 1):
        key = f"{hand}/{obj}/{ts}"
        if key in done:
            continue
        ok = False
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                api.upload_folder(
                    folder_path=ep,
                    path_in_repo=key,
                    repo_id=REPO_ID,
                    repo_type=REPO_TYPE,
                    ignore_patterns=IGNORE,
                    commit_message=f"Add dataset episode {key}",
                )
                ok = True
                break
            except Exception as e:  # noqa: BLE001 - retry incl. trailing ReadTimeout
                print(f"[{i}/{total}] {key} attempt {attempt} {type(e).__name__}: {str(e)[:80]}", flush=True)
                time.sleep(5)
        if ok:
            mark_done(key)
            uploaded += 1
            if uploaded % 25 == 0:
                print(f"[{i}/{total}] progress: {uploaded} uploaded this run", flush=True)
        else:
            print(f"[{i}/{total}] {key} FAILED after {MAX_RETRIES} attempts (retry next run)", flush=True)

    print(f"DONE run: {uploaded} uploaded; ledger now {len(load_ledger())}/{total}", flush=True)


if __name__ == "__main__":
    main()
