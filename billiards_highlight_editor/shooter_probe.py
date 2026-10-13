"""
Person probe for the turn filter. Runs in the detection virtualenv (OpenCV 4.x, which can still read the Caffe
MobileNet-SSD person detector that OpenCV 5 dropped):

  .venv_detect\\Scripts\\python.exe -m billiards_highlight_editor.shooter_probe --video V.mp4 --times times.json --out people.json

times.json: list of seconds. people.json: for each time the persons found around the table:
  {"t": 12.3, "people": [{"box": [x, y, w, h], "conf": 0.97, "torso": [h, s, v]}]}
`torso` is the mean HSV (OpenCV scale 0-179 / 0-255 / 0-255) of the shirt area, used later to tell the two players apart.
The detector is weak on small people far from the camera, so a missing person means "unknown", never "absent".
"""

import argparse
import json
import os
import sys
from typing import List, Tuple

import cv2
import numpy as np

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
PERSON_CLASS = 15
ZONE_Y0, ZONE_Y1 = 380, 1080           # the band of the 1080p frame that holds the table and the people around it
CROP_XS = (330, 640, 960)


def load_net():
    proto = os.path.join(MODEL_DIR, "deploy.prototxt")
    weights = os.path.join(MODEL_DIR, "mobilenet_iter_73000.caffemodel")
    if not (os.path.exists(proto) and os.path.exists(weights)):
        raise FileNotFoundError(f"person detector files missing in {MODEL_DIR}")
    return cv2.dnn.readNetFromCaffe(proto, weights)


def _nms(boxes: List[Tuple[float, float, float, float, float]]):
    boxes = sorted(boxes, key=lambda b: -b[4])
    keep = []
    for b in boxes:
        dup = False
        for k in keep:
            ix = max(0.0, min(b[0] + b[2], k[0] + k[2]) - max(b[0], k[0]))
            iy = max(0.0, min(b[1] + b[3], k[1] + k[3]) - max(b[1], k[1]))
            if ix * iy / (min(b[2] * b[3], k[2] * k[3]) + 1e-6) > 0.5:
                dup = True
                break
        if not dup:
            keep.append(b)
    return keep


def detect_people(net, frame: np.ndarray, conf: float = 0.35):
    """Boxes (x, y, w, h, conf) in frame pixels. The 1080p frame is scanned with three overlapping square crops
    because SSD works on 300x300 and people far from the camera would otherwise be only a few pixels tall."""
    h, w = frame.shape[:2]
    sx, sy = w / 1920.0, h / 1080.0
    y0, y1 = int(ZONE_Y0 * sy), int(ZONE_Y1 * sy)
    size = y1 - y0
    boxes = []
    for cx in CROP_XS:
        x0 = int(cx * sx)
        crop = frame[y0:y1, x0:x0 + size]
        if crop.shape[1] < size // 2:
            continue
        blob = cv2.dnn.blobFromImage(cv2.resize(crop, (300, 300)), 0.007843, (300, 300), 127.5)
        net.setInput(blob)
        out = net.forward()
        for i in range(out.shape[2]):
            if int(out[0, 0, i, 1]) == PERSON_CLASS and float(out[0, 0, i, 2]) >= conf:
                bx = out[0, 0, i, 3:7] * np.array([size, size, size, size])
                boxes.append((x0 + bx[0], y0 + bx[1], bx[2] - bx[0], bx[3] - bx[1], float(out[0, 0, i, 2])))
    return _nms(boxes)


def torso_color(frame: np.ndarray, box) -> List[float]:
    """Mean HSV of the shirt: upper-middle of the person box (roughly shoulders to waist, narrowed to skip the arms)."""
    x, y, w, h = [int(round(v)) for v in box[:4]]
    x0, x1 = x + int(w * 0.25), x + int(w * 0.75)
    y0, y1 = y + int(h * 0.18), y + int(h * 0.55)
    H, W = frame.shape[:2]
    x0, x1, y0, y1 = max(0, x0), min(W, x1), max(0, y0), min(H, y1)
    if x1 <= x0 or y1 <= y0:
        return [0.0, 0.0, 0.0]
    hsv = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float32)
    return [round(float(v), 1) for v in np.median(hsv, axis=0)]


def probe(video: str, times: List[float]):
    net = load_net()
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {video}")
    result = []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(t)) * 1000.0)
        ok, frame = cap.read()
        people = []
        if ok:
            for (x, y, w, h, c) in detect_people(net, frame):
                people.append({"box": [round(x, 1), round(y, 1), round(w, 1), round(h, 1)], "conf": round(c, 3),
                               "torso": torso_color(frame, (x, y, w, h))})
        result.append({"t": float(t), "people": people})
    cap.release()
    return result


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--times", required=True, help="JSON file with a list of seconds")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    with open(args.times, encoding="utf-8") as f:
        times = json.load(f)
    res = probe(args.video, times)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f)
    print(f"{len(res)} frames, {sum(len(r['people']) for r in res)} people")


if __name__ == "__main__":
    main()
