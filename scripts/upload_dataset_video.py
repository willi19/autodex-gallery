"""Upload compressed browser videos to willi19/autodex-gallery-video.

Uploads {STAGE}/{hand}/{object}/{timestamp}/{serial}.mp4 (from
convert_dataset_videos.py) into a SEPARATE HF repo so it runs concurrently with
the raw-dataset upload without commit conflicts.

Per EPISODE: an episode uploads as soon as all its cameras (per
dataset_episodes.json) are converted. Loops, re-scanning for newly-finished
episodes, until every episode is uploaded — so it can run alongside the ongoing
conversion.

    python scripts/upload_dataset_video.py
"""
import json
import os
import time

os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
os.environ.setdefault("HF_XET_HIGH_PERFORMANCE", "1")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")

from huggingface_hub import HfApi

REPO_ID = "willi19/autodex-gallery-video"
REPO_TYPE = "dataset"
STAGE = "/home/mingi/shared_data/_dataset_video"
MANIFEST = "/home/mingi/autodex-gallery/docs/dataset_episodes.json"
LEDGER = "/home/mingi/shared_data/_video_upload_done.txt"
MAX_RETRIES = 4
IDLE_SLEEP = 90          # wait between rescans when nothing new is ready
MAX_IDLE_ROUNDS = 40     # give up after ~1h of no progress (conversion done/stalled)


def load_ledger():
    if not os.path.exists(LEDGER):
        return set()
    with open(LEDGER) as f:
        return set(l.strip() for l in f if l.strip())


def main():
    api = HfApi()
    manifest = json.load(open(MANIFEST))
    episodes = []
    for hand, objs in manifest.items():
        for obj, eps in objs.items():
            for e in eps:
                episodes.append((hand, obj, e["ts"], len(e["cameras"])))
    total = len(episodes)
    print(f"episodes to upload: {total}", flush=True)

    done = load_ledger()
    idle_rounds = 0
    while len(done) < total:
        progressed = 0
        for hand, obj, ts, ncam in episodes:
            key = f"{hand}/{obj}/{ts}"
            if key in done:
                continue
            edir = os.path.join(STAGE, hand, obj, ts)
            if not os.path.isdir(edir):
                continue
            have = sum(1 for f in os.listdir(edir) if f.endswith(".mp4"))
            if have < ncam:
                continue  # still converting
            ok = False
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    api.upload_folder(folder_path=edir, path_in_repo=key,
                                      repo_id=REPO_ID, repo_type=REPO_TYPE,
                                      commit_message=f"Add browser videos {key}")
                    ok = True
                    break
                except Exception as e:  # noqa: BLE001
                    print(f"{key} attempt {attempt} {type(e).__name__}: {str(e)[:70]}", flush=True)
                    time.sleep(4)
            if ok:
                with open(LEDGER, "a") as f:
                    f.write(key + "\n")
                done.add(key)
                progressed += 1
                if len(done) % 50 == 0:
                    print(f"uploaded {len(done)}/{total}", flush=True)
        if progressed == 0:
            idle_rounds += 1
            if idle_rounds >= MAX_IDLE_ROUNDS:
                print("no progress for a while; stopping (rerun to resume)", flush=True)
                break
            time.sleep(IDLE_SLEEP)
        else:
            idle_rounds = 0
    print(f"DONE video upload: {len(load_ledger())}/{total}", flush=True)


if __name__ == "__main__":
    main()
