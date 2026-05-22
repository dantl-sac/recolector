"""
PC -> ESP32 AI bridge (WiFi)
- Reads MJPEG stream from ESP32
- Runs YOLO on frames
- Sends best detection to ESP32 via /ai endpoint
"""

import argparse
import json
import time
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
import requests
from ultralytics import YOLO

# Valores por defecto extraidos del dataset.yaml (solo "basura")
DEFAULT_CLASSES = [
    "botella_plastico",
    "lata_aluminio",
    "carton",
    "papel",
]


def read_mjpeg_frame(url: str, timeout: float = 2.0) -> Optional[np.ndarray]:
    """Read a single JPEG frame from MJPEG stream."""
    try:
        r = requests.get(url, stream=True, timeout=timeout)
        if r.status_code != 200:
            return None
        bytes_buf = b""
        for chunk in r.iter_content(chunk_size=1024):
            bytes_buf += chunk
            a = bytes_buf.find(b"\xff\xd8")
            b = bytes_buf.find(b"\xff\xd9")
            if a != -1 and b != -1 and b > a:
                jpg = bytes_buf[a:b + 2]
                img = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                return img
    except requests.RequestException:
        return None
    return None


def estimate_distance_cm(box_w_px: float, focal_len: float, real_w_cm: float) -> int:
    if box_w_px <= 1:
        return 0
    return int((real_w_cm * focal_len) / box_w_px)


def pick_best_detection(result, class_allow: Optional[set]) -> Optional[Tuple[float, float, float, int]]:
    """Return (x_center, box_w_px, conf, cls_idx) of best detection."""
    if result is None or result.boxes is None or len(result.boxes) == 0:
        return None
    boxes = result.boxes
    confs = boxes.conf.cpu().numpy()
    classes = boxes.cls.cpu().numpy().astype(int)

    best_idx = -1
    best_conf = -1.0
    for i, conf in enumerate(confs):
        if class_allow is not None and i < len(classes):
            cls_name = result.names[classes[i]]
            if cls_name not in class_allow:
                continue
        if float(conf) > best_conf:
            best_conf = float(conf)
            best_idx = i

    if best_idx < 0:
        return None

    xyxy = boxes.xyxy[best_idx].cpu().numpy()
    conf = float(confs[best_idx])
    cls_idx = int(classes[best_idx])
    x1, y1, x2, y2 = xyxy
    box_w = max(1.0, x2 - x1)
    x_center = (x1 + x2) / 2.0
    return x_center, box_w, conf, cls_idx


def load_calibration(path: Optional[str]) -> Tuple[float, Dict[str, float]]:
    if not path:
        return 615.0, {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    focal = float(data.get("focal", 615.0))
    widths = {str(k): float(v) for k, v in data.get("class_widths_cm", {}).items()}
    return focal, widths


def main() -> None:
    parser = argparse.ArgumentParser(description="Send AI detections to ESP32 via WiFi")
    parser.add_argument("--esp32-ip", required=True, help="ESP32 IP (e.g., 192.168.137.100)")
    parser.add_argument("--model", default="arve_best.pt", help="YOLO model path")
    parser.add_argument("--stream-port", type=int, default=81, help="ESP32 MJPEG port")
    parser.add_argument("--conf", type=float, default=0.60, help="Min confidence")
    parser.add_argument("--focal", type=float, default=615.0, help="Focal length (fallback)")
    parser.add_argument("--real-w", type=float, default=7.0, help="Real object width (cm, fallback)")
    parser.add_argument("--classes", default="", help="Comma list of target classes (optional)")
    parser.add_argument("--calib", default="", help="Calibration JSON (focal and widths)")
    parser.add_argument("--interval", type=float, default=0.2, help="Seconds between sends")
    args = parser.parse_args()

    stream_url = f"http://{args.esp32_ip}:{args.stream_port}"
    ai_url = f"http://{args.esp32_ip}/ai"

    model = YOLO(args.model)
    focal, class_widths = load_calibration(args.calib)
    class_allow = None
    if args.classes.strip():
        class_allow = {c.strip() for c in args.classes.split(",") if c.strip()}
    else:
        # Si no se pasa --classes, usamos las clases "basura" por defecto
        class_allow = set(DEFAULT_CLASSES)

    last_send = 0.0
    while True:
        frame = read_mjpeg_frame(stream_url)
        if frame is None:
            time.sleep(0.2)
            continue

        results = model.predict(frame, conf=args.conf, verbose=False)
        best = pick_best_detection(results[0] if results else None, class_allow)

        if best and (time.time() - last_send) >= args.interval:
            x_center, box_w, conf, cls_idx = best
            cls_name = results[0].names.get(cls_idx, "unknown") if results else "unknown"
            x_norm = x_center / frame.shape[1]
            real_w = class_widths.get(cls_name, args.real_w)
            dist_cm = estimate_distance_cm(box_w, focal, real_w)

            params = {
                "x": f"{x_norm:.3f}",
                "dist": str(dist_cm),
                "conf": f"{conf:.3f}",
                "cls": cls_name,
            }
            try:
                requests.get(ai_url, params=params, timeout=0.6)
                last_send = time.time()
            except requests.RequestException:
                pass

        time.sleep(0.02)


if __name__ == "__main__":
    main()
