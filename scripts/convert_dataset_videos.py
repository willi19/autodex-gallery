"""Compress dataset camera videos (.avi -> web mp4) for the full-trial gallery.

For every episode across allegro/inspire, transcodes each 24-camera .avi into a
small H.264 mp4 (<=720p, CRF 30, no audio, faststart) written to a local staging
tree:  {STAGE}/{hand}/{object}/{timestamp}/{serial}.mp4

Existence-checked (resumable) and parallelized across CPU cores. Upload happens
separately (upload_dataset_video.py) after the raw-dataset upload finishes, to
avoid concurrent commits to the same HF repo.

    python scripts/convert_dataset_videos.py
"""
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

D = "/home/mingi/shared_data/autodex_dataset"
STAGE = "/home/mingi/shared_data/_dataset_video"
SUBSETS = {
    "selected_100": "allegro",
    "corl_selected_100": "allegro",
    "selected_100_inspire": "inspire",
}
WORKERS = 24


def build_jobs():
    jobs = []
    for src, hand in SUBSETS.items():
        droot = os.path.join(D, src)
        if not os.path.isdir(droot):
            continue
        for obj in sorted(os.listdir(droot)):
            oroot = os.path.join(droot, obj)
            if not os.path.isdir(oroot):
                continue
            for ts in sorted(os.listdir(oroot)):
                edir = os.path.join(oroot, ts)
                # camera videos: {serial}.avi -> {serial}.mp4
                vdir = os.path.join(edir, "videos")
                if os.path.isdir(vdir):
                    for f in os.listdir(vdir):
                        if f.endswith(".avi"):
                            cam = f[:-4]
                            jobs.append((os.path.join(vdir, f),
                                         os.path.join(STAGE, hand, obj, ts, cam + ".mp4")))
                # debug overlay videos: object_overlay/overlay_{serial}.mp4 -> overlay_{serial}.mp4
                ovdir = os.path.join(edir, "object_overlay")
                if os.path.isdir(ovdir):
                    for f in os.listdir(ovdir):
                        if f.endswith(".mp4"):
                            jobs.append((os.path.join(ovdir, f),
                                         os.path.join(STAGE, hand, obj, ts, f)))
    return jobs


def convert(job):
    src_avi, out = job
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return "skip"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".tmp.mp4"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", src_avi,
        "-vf", "scale=-2:'min(720,ih)'",
        "-c:v", "libx264", "-crf", "30", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart",
        tmp,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.replace(tmp, out)
        return "ok"
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        return "fail"


def main():
    jobs = build_jobs()
    total = len(jobs)
    print(f"videos to convert: {total} (workers={WORKERS})", flush=True)
    done = ok = fail = skip = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(convert, j) for j in jobs]
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if r == "ok":
                ok += 1
            elif r == "skip":
                skip += 1
            else:
                fail += 1
            if done % 500 == 0:
                print(f"{done}/{total}  ok={ok} skip={skip} fail={fail}", flush=True)
    print(f"DONE: {done}/{total}  ok={ok} skip={skip} fail={fail}", flush=True)


if __name__ == "__main__":
    main()
