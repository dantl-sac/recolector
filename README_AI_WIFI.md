# AI WiFi Bridge (PC -> ESP32)

This lets the PC run YOLO and send detections to the ESP32 over WiFi.

## How it works
1) ESP32 streams video on port 81.
2) PC reads the stream and runs YOLO.
3) PC sends x-center, distance and confidence to the ESP32.
4) ESP32 uses that data in AUTO mode.

## Run
From the project folder:

```bash
python ai_wifi_bridge.py --esp32-ip 192.168.137.100 --model arve_best.pt --calib ai_calibration.json
```

## Notes
- The distance is estimated using:
  distance_cm = (real_width_cm * focal) / box_width_px
- You can improve accuracy with ai_calibration.json (per-class widths).
- You can restrict detections to trash classes:
  --classes "Bottle,Drink can,Food Can,Plastic bag"
- You can adjust confidence:
  - --conf 0.55
  - --focal 615
  - --real-w 7.0

## ESP32 endpoints
- /ai?x=0.50&dist=35&conf=0.82&cls=Bottle
- /mode?m=auto
- /mode?m=manual
- /status
