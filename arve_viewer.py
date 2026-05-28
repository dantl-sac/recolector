"""
ARVE VIEWER FINAL - GARANTIZADO QUE FUNCIONA
========================================================
Estrategia: 1 HTTP request por frame (mas lento pero CONFIABLE)
+ YOLO en RTX 3050
+ Control manual con teclado
+ Modo auto que decide que hacer (lo muestra en pantalla)

Uso:
    python arve_viewer.py --esp32-ip 192.168.137.128
    python arve_viewer.py --esp32-ip 192.168.137.128 --no-ai
    python arve_viewer.py --esp32-ip 192.168.137.128 --model arve_best.pt

Teclas:
    Q/ESC = salir       W/A/S/D = mover    ESPACIO = stop
    flechas = servos    M = AUTO/MANUAL    Y = toggle YOLO
    +/- = velocidad
"""

import argparse
import socket
import sys
import threading
import time
from collections import deque
from typing import Optional
from urllib.parse import urlparse

import cv2
import numpy as np
import requests


# ===================================================================
# CLIENTE HTTP DEL ESP32
# ===================================================================
class ESP32Client:
    def __init__(self, ip, port=80):
        self.base = f"http://{ip}:{port}"
        self.s = requests.Session()
        self.t = 0.4

    def _g(self, p, **kw):
        try:
            self.s.get(f"{self.base}{p}", params=kw, timeout=self.t)
            return True
        except requests.RequestException:
            return False

    def move(self, v1, v2):       self._g("/move", v1=v1, v2=v2)
    def stop(self):               self._g("/move", v1=0, v2=0)
    def servo_pan(self, a):       self._g("/servo", ang=a)
    def servo_tilt(self, a):      self._g("/servo2", ang=a)
    def mode(self, m):            self._g("/mode", m=m)
    def speed(self, b, t):        self._g("/speed", base=b, turn=t)
    def set_res(self, s):         self._g("/res", s=s)
    def set_quality(self, q):     self._g("/quality", q=q)
    def send_ai(self, x, dist, conf, cls):
        self._g("/ai", x=f"{x:.3f}", dist=dist, conf=f"{conf:.3f}", cls=cls)


# ===================================================================
# CAPTURA FRAME-POR-FRAME (metodo del ai_wifi_bridge original)
# ===================================================================
class FrameGrabber:
    """Captura UN frame por HTTP request. Mas lento pero IMPOSIBLE que falle."""

    def __init__(self, ip, port=81):
        self.url = f"http://{ip}:{port}"
        self.frame = None
        self.lock = threading.Lock()
        self.running = True
        self.connected = False
        self.frames_total = 0
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _get_one_frame(self) -> Optional[np.ndarray]:
        """Hace 1 HTTP request al stream usando socket crudo (mas confiable).
        Bypassa requests library (que parece bloqueada por McAfee).
        Mismo metodo que el test_conexion.py que SI funciono."""
        parsed = urlparse(self.url)
        host = parsed.hostname
        port = parsed.port or 80
        path = parsed.path or "/"

        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(8)
            sock.connect((host, port))

            req = (f"GET {path} HTTP/1.1\r\n"
                   f"Host: {host}\r\n"
                   f"Connection: close\r\n\r\n").encode()
            sock.sendall(req)

            buf = bytearray()
            headers_done = False
            t_start = time.time()

            while time.time() - t_start < 8:
                try:
                    chunk = sock.recv(8192)
                except socket.timeout:
                    break
                if not chunk:
                    break
                buf.extend(chunk)

                # Saltar headers HTTP
                if not headers_done:
                    idx = buf.find(b"\r\n\r\n")
                    if idx < 0:
                        continue
                    del buf[:idx + 4]
                    headers_done = True

                # Buscar JPEG completo
                s = buf.find(b'\xff\xd8')
                if s < 0:
                    continue
                e = buf.find(b'\xff\xd9', s + 2)
                if e < 0:
                    continue
                jpg = bytes(buf[s:e + 2])
                return cv2.imdecode(np.frombuffer(jpg, np.uint8),
                                    cv2.IMREAD_COLOR)
        except (socket.timeout, OSError) as e:
            if not hasattr(self, '_last_err') or self._last_err != str(e):
                self._last_err = str(e)
                print(f"[CAM] Socket: {str(e)[:80]}")
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
        return None

    def _loop(self):
        consecutive_fails = 0
        while self.running:
            img = self._get_one_frame()
            if img is None:
                consecutive_fails += 1
                self.connected = False
                if consecutive_fails == 1:
                    print("[CAM] esperando ESP32...")
                if consecutive_fails > 50:
                    consecutive_fails = 0  # log periodicamente
                time.sleep(0.2)
                continue
            consecutive_fails = 0
            self.connected = True
            self.frames_total += 1
            with self.lock:
                self.frame = img

    def read(self) -> Optional[np.ndarray]:
        with self.lock:
            if self.frame is None:
                return None
            return self.frame.copy()

    def release(self):
        self.running = False


# ===================================================================
# YOLO
# ===================================================================
def load_yolo(model_path, device="cuda"):
    try:
        from ultralytics import YOLO
        import torch
    except ImportError as e:
        print(f"[ERROR] Falta dependencia: {e}")
        sys.exit(1)

    if device == "cuda" and not torch.cuda.is_available():
        print("[WARN] CUDA no disponible -> CPU")
        device = "cpu"
    if device == "cuda":
        print(f"[OK] YOLO en GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("[OK] YOLO en CPU")

    model = YOLO(model_path)
    model.to(device)
    classes = list(model.names.values())
    print(f"[OK] Modelo: {model_path}")
    print(f"[OK] {len(model.names)} clases: {classes[:5]}{'...' if len(classes) > 5 else ''}")
    print("[..] Calentando YOLO...")
    dummy = np.zeros((320, 320, 3), dtype=np.uint8)
    _ = model.predict(dummy, verbose=False, imgsz=320)
    print("[OK] YOLO listo")
    return model, device


# ===================================================================
# DIBUJO Y LOGICA AUTONOMA
# ===================================================================
def draw_detections(frame, dets):
    best = None
    best_c = -1.0
    h, w = frame.shape[:2]
    for d in dets:
        x1, y1, x2, y2 = d["x1"], d["y1"], d["x2"], d["y2"]
        c = d["conf"]
        name = d["name"]
        color = (60, 220, 80) if c > 0.7 else (80, 180, 255)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        label = f"{name} {c*100:.0f}%"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x1, max(0, y1 - th - 6)),
                      (x1 + tw + 6, y1), color, -1)
        cv2.putText(frame, label, (x1 + 3, max(12, y1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        if c > best_c:
            best_c = c
            xc = (x1 + x2) / 2.0
            best = {"x_norm": xc / w, "box_w": max(1, x2 - x1),
                    "conf": c, "cls": name, "x_px": xc, "frame_w": w}
    return best


def decide_action(best, vel_base=1800, vel_giro=1400):
    """Cerebro autonomo: decide que hacer segun la deteccion."""
    if best is None:
        return "BUSCAR", "girar lento", -vel_giro // 2, vel_giro // 2
    x = best["x_norm"]
    if x < 0.40:
        return f"OBJETO {best['cls']} A LA IZQUIERDA", "girar izq", -vel_giro, vel_giro
    elif x > 0.60:
        return f"OBJETO {best['cls']} A LA DERECHA", "girar der", vel_giro, -vel_giro
    else:
        # Centrado, avanzar
        if best["box_w"] > 150:
            return f"BASURA {best['cls']} CERCA", "RECOGER", 0, 0
        return f"OBJETO {best['cls']} EN FRENTE", "avanzar", vel_base, vel_base


def draw_hud(frame, fps, yolo_on, dev, pan, tilt, vel, modo,
             ndet, conn, accion, motors):
    h, w = frame.shape[:2]
    bar = 28
    ov = frame.copy()
    cv2.rectangle(ov, (0, 0), (w, bar), (0, 0, 0), -1)
    cv2.rectangle(ov, (0, h - bar), (w, h), (0, 0, 0), -1)
    frame[:] = cv2.addWeighted(ov, 0.7, frame, 0.3, 0)

    state_color = (60, 220, 80) if conn else (60, 60, 220)
    top = f"FPS:{fps:4.1f} | YOLO:{'ON' if yolo_on else 'OFF'}({dev}) | DET:{ndet} | PAN:{pan} TILT:{tilt}"
    cv2.putText(frame, top, (6, 19), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, state_color, 1, cv2.LINE_AA)

    bot = f"MODO:{modo} | VEL:{vel} | {accion[:50]}"
    cv2.putText(frame, bot, (6, h - 8), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, (240, 240, 240), 1, cv2.LINE_AA)


# ===================================================================
# MAIN
# ===================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp32-ip", required=True)
    ap.add_argument("--stream-port", type=int, default=81)
    ap.add_argument("--http-port", type=int, default=80)
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--conf", type=float, default=0.40)
    ap.add_argument("--no-ai", action="store_true")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--skip", type=int, default=2)
    ap.add_argument("--imgsz", type=int, default=416)
    ap.add_argument("--start-res", default="qvga")
    ap.add_argument("--quality", type=int, default=20)
    args = ap.parse_args()

    esp = ESP32Client(args.esp32_ip, args.http_port)
    print(f"[..] Configurando ESP32: res={args.start_res} q={args.quality}")
    esp.set_res(args.start_res)
    esp.set_quality(args.quality)
    time.sleep(0.4)

    print(f"[..] Iniciando captura desde http://{args.esp32_ip}:{args.stream_port}")
    print(f"[..] Metodo: 1 HTTP request por frame (lento pero confiable)")
    cap = FrameGrabber(args.esp32_ip, args.stream_port)

    print("[..] Esperando primer frame (max 30s)...")
    t0 = time.time()
    while cap.read() is None and time.time() - t0 < 30:
        time.sleep(0.3)
    if cap.read() is None:
        print("[ERROR] No llegan frames. Revisa:")
        print("  1. Que el ESP32 este corriendo y conectado a WiFi")
        print("  2. Que tu hotspot ARVE-07 este activo en 2.4 GHz")
        print("  3. Que no haya navegador con la IP abierta")
        print("  4. Que la IP sea correcta")
        cap.release()
        sys.exit(1)
    print(f"[OK] Stream activo - frames recibidos: {cap.frames_total}")

    yolo_on = not args.no_ai
    model, device = (None, "cpu")
    if yolo_on:
        model, device = load_yolo(args.model, args.device)

    pan, tilt = 90, 90
    vel = 1800
    modo = "MANUAL"
    dets = []
    fcnt = 0
    fps_buf = deque(maxlen=20)
    t_prev = time.time()
    last_ai_send = 0.0
    last_auto = 0.0
    accion_actual = "Esperando..."
    motors = (0, 0)

    cv2.namedWindow("ARVE", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("ARVE", 900, 700)

    print()
    print("=" * 60)
    print("CONTROLES:")
    print("  W/A/S/D     - mover (delante/izq/atras/der)")
    print("  ESPACIO     - STOP de emergencia")
    print("  flechas     - servos pan/tilt")
    print("  M           - cambiar MANUAL <-> AUTO")
    print("  +/-         - subir/bajar velocidad")
    print("  Y           - prender/apagar YOLO")
    print("  Q o ESC     - salir")
    print("=" * 60)
    print()

    try:
        while True:
            frame = cap.read()
            if frame is None:
                time.sleep(0.05)
                continue

            best = None
            if yolo_on and model is not None:
                if fcnt % args.skip == 0:
                    res = model.predict(frame, conf=args.conf, verbose=False,
                                        device=device, imgsz=args.imgsz)
                    dets = []
                    if res and res[0].boxes is not None:
                        r = res[0]
                        confs = r.boxes.conf.cpu().numpy()
                        cls = r.boxes.cls.cpu().numpy().astype(int)
                        xy = r.boxes.xyxy.cpu().numpy()
                        for i in range(len(confs)):
                            x1, y1, x2, y2 = map(int, xy[i])
                            dets.append({
                                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                                "conf": float(confs[i]),
                                "name": r.names.get(int(cls[i]), str(cls[i]))
                            })
                fcnt += 1
                best = draw_detections(frame, dets)
            else:
                dets = []

            now = time.time()

            # Modo AUTO: decide que hacer cada 300ms
            if modo == "AUTO" and (now - last_auto) >= 0.3:
                accion_actual, sub, m1, m2 = decide_action(best, vel, int(vel*0.78))
                motors = (m1, m2)
                esp.move(m1, m2)
                last_auto = now

            # Enviar deteccion al ESP32 (rate limited)
            if best and (now - last_ai_send) >= 0.15:
                d_cm = max(5, int(15000 / max(1, best["box_w"])))
                esp.send_ai(best["x_norm"], d_cm, best["conf"], best["cls"])
                last_ai_send = now

            # FPS
            dt = now - t_prev
            t_prev = now
            if dt > 0:
                fps_buf.append(1.0 / dt)
            fps = sum(fps_buf) / len(fps_buf) if fps_buf else 0.0

            # En modo MANUAL, mostrar accion = "manual"
            if modo == "MANUAL":
                accion_actual = "control manual"

            draw_hud(frame, fps, yolo_on, device, pan, tilt, vel,
                     modo, len(dets), cap.connected, accion_actual, motors)

            cv2.imshow("ARVE", frame)
            k = cv2.waitKeyEx(5)
            if k == -1:
                continue
            if k in (27, ord('q'), ord('Q')):
                break
            elif k in (ord('w'), ord('W')): esp.move(vel, vel); accion_actual = "AVANZAR"
            elif k in (ord('s'), ord('S')): esp.move(-vel, -vel); accion_actual = "ATRAS"
            elif k in (ord('a'), ord('A')): esp.move(-int(vel*0.7), int(vel*0.7)); accion_actual = "GIRAR IZQ"
            elif k in (ord('d'), ord('D')): esp.move(int(vel*0.7), -int(vel*0.7)); accion_actual = "GIRAR DER"
            elif k == ord(' '): esp.stop(); accion_actual = "STOP"
            elif k == 2424832: pan = max(0, pan-5);   esp.servo_pan(pan)
            elif k == 2555904: pan = min(180, pan+5); esp.servo_pan(pan)
            elif k == 2490368: tilt = min(180, tilt+5); esp.servo_tilt(tilt)
            elif k == 2621440: tilt = max(0, tilt-5);   esp.servo_tilt(tilt)
            elif k in (ord('m'), ord('M')):
                modo = "AUTO" if modo == "MANUAL" else "MANUAL"
                esp.mode(modo.lower())
                print(f"[INFO] Modo: {modo}")
            elif k in (ord('+'), ord('=')):
                vel = min(4095, vel+200); esp.speed(vel, int(vel*0.78))
            elif k in (ord('-'), ord('_')):
                vel = max(500, vel-200);  esp.speed(vel, int(vel*0.78))
            elif k in (ord('y'), ord('Y')):
                yolo_on = not yolo_on
                if yolo_on and model is None:
                    model, device = load_yolo(args.model, args.device)
                print(f"[INFO] YOLO {'ON' if yolo_on else 'OFF'}")

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        esp.stop()
        print(f"\n[OK] Cerrado. Frames totales: {cap.frames_total}")


if __name__ == "__main__":
    main()
