# extract_frames.py  --  Phase 1.5, slices 1 + 2 + 3 (complete).
# Slice 1: score every frame. Slice 2: pick sharpest per window. Slice 3: write keepers to disk.

import cv2
import numpy as np
import os

VIDEO_PATH = r"C:\odm\datasets\tyco_house\trimmedGX010063.MP4"  # <-- your path
OUTPUT_DIR = r"C:\odm\datasets\tyco_house\images"                # where JPGs go
WINDOW_SECONDS = 0.5

# ---------- slice 1: score every frame ----------
cap = cv2.VideoCapture(VIDEO_PATH)
if not cap.isOpened():
    raise SystemExit(f"Could not open video: {VIDEO_PATH}")

fps = cap.get(cv2.CAP_PROP_FPS)

scores = []
while True:
    ok, frame = cap.read()
    if not ok:
        break
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    scores.append(cv2.Laplacian(gray, cv2.CV_64F).var())
cap.release()
scores = np.array(scores)

# ---------- slice 2: pick the sharpest frame per window ----------
window_frames = max(1, int(round(WINDOW_SECONDS * fps)))

keepers = []
for start in range(0, len(scores), window_frames):
    window = scores[start:start + window_frames]
    keepers.append(int(start + window.argmax()))   # int() strips the np.int64 wrapper

# ---------- slice 3: write the keeper frames to disk ----------

# Make the output folder. exist_ok=True means re-running won't error if it's there.
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Convert keepers to a set for fast "is this index a keeper?" membership tests.
keeper_set = set(keepers)

# Re-read the video from the start, in order (the reliable way, see notes above).
cap = cv2.VideoCapture(VIDEO_PATH)
if not cap.isOpened():
    raise SystemExit(f"Could not reopen video: {VIDEO_PATH}")

frame_index = 0   # counts every frame we read, matching the indices in keeper_set
written = 0       # counts how many we actually saved, for the final report
while True:
    ok, frame = cap.read()
    if not ok:
        break

    # Only write this frame if its index is one we selected.
    if frame_index in keeper_set:
        # :04d -> pad the number to 4 digits with leading zeros, so filenames
        # sort in capture order as text (frame_0044 before frame_1140).
        filename = f"frame_{frame_index:04d}.jpg"
        out_path = os.path.join(OUTPUT_DIR, filename)   # join folder + filename, OS-correct
        success = cv2.imwrite(out_path, frame)
        if not success:
            print(f"WARNING: failed to write {out_path}")
        else:
            written += 1

    frame_index += 1

cap.release()

# ---------- report ----------
print(f"keepers selected: {len(keepers)}")
print(f"frames written:   {written}")
print(f"output folder:    {OUTPUT_DIR}")