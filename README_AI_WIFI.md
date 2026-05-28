# IA por WiFi (PC -> ESP32)

La PC ejecuta YOLO y le envía las detecciones al ESP32 por WiFi.
El script encargado de esto es **`arve_viewer.py`** (visor + control + envío de IA).

## Cómo funciona
1) El ESP32 transmite video MJPEG en el puerto 81.
2) La PC lee el stream y corre YOLO (en la RTX 3050 si hay CUDA).
3) La PC envía al ESP32: centro-x (0–1), distancia estimada, confianza y clase.
4) El ESP32 usa esos datos en modo AUTO para perseguir el objeto.

## Ejecutar
Desde la carpeta del proyecto:

```bash
python arve_viewer.py --esp32-ip 192.168.137.100 --model arve_best.pt
```

Si solo quieres ver el video sin IA:

```bash
python arve_viewer.py --esp32-ip 192.168.137.100 --no-ai
```

## Opciones útiles (flags reales)
| Flag | Default | Descripción |
|------|---------|-------------|
| `--esp32-ip` | (obligatorio) | IP del ESP32-CAM |
| `--model` | `yolov8n.pt` | Modelo YOLO (usa `arve_best.pt` para basura) |
| `--conf` | `0.40` | Umbral de confianza |
| `--no-ai` | — | Solo video, sin YOLO |
| `--device` | `cuda` | `cuda` o `cpu` |
| `--imgsz` | `416` | Tamaño de inferencia |
| `--skip` | `2` | Corre YOLO cada N frames (rendimiento) |
| `--start-res` | `qvga` | Resolución de cámara (`qqvga`/`qvga`/`hvga`/`vga`) |
| `--quality` | `20` | Calidad JPEG (5–60) |

## Notas
- La distancia es una **estimación simple** a partir del ancho de la caja:
  `dist_cm ≈ 15000 / ancho_en_px` (más ancho = más cerca).
- El modo AUTO se activa con la tecla `M` o enviando `/mode?m=auto`.

## Endpoints del ESP32 que usa
- `/ai?x=0.50&dist=35&conf=0.82&cls=Bottle`  ← inyecta la detección
- `/mode?m=auto` / `/mode?m=manual`
- `/move?v1=..&v2=..`
- `/servo?ang=..` / `/servo2?ang=..`
- `/status`
