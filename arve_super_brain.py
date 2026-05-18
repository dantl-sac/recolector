"""
ARVE SUPER BRAIN v6.0 - CEREBRO DEFINITIVO
Integra: Servo cámara, Buzzer, LED RGB, Sensor Color,
         2x Ultrasonido, RTX 3050 (YOLO TACO 60 clases), Búsqueda 360°
Modelo: Usa arve_best.pt (entrenado TACO) o yolov8n.pt como respaldo
"""
import cv2
import numpy as np
from ultralytics import YOLO
import time
import threading
import urllib.request
import urllib.error
import torch
import winsound
from collections import deque

# Optimización NVIDIA
torch.backends.cudnn.benchmark = True

# ==========================================
# CONFIGURACIÓN
# ==========================================
ESP32_IP   = "192.168.137.100"
URL_STREAM = f"http://{ESP32_IP}:81/"
URL_MOVE   = f"http://{ESP32_IP}/move"
URL_SERVO  = f"http://{ESP32_IP}/servo"
URL_BEEP   = f"http://{ESP32_IP}/beep"
URL_LED    = f"http://{ESP32_IP}/led"
URL_STATUS = f"http://{ESP32_IP}/status"

# Clases dinámicas (se definen dinámicamente al cargar el modelo)
TRASH_CLASSES = {}
DANGEROUS_CLASSES = set()
OBSTACLE_CLASSES = set()
PERSON_CLASS = 0

# Estados del robot
class Estado:
    BUSCANDO   = "MODO RADAR: BUSCANDO..."
    APUNTANDO  = "CALIBRANDO ANGULO..."
    AVANZANDO  = "OBJETIVO: AVANZANDO"
    ESQUIVANDO = "OBSTACULO: ESQUIVANDO"
    PELIGRO    = "PERSONA DETECTADA: STOP"
    ESCANEANDO = "ESCANEANDO MATERIAL..."

# ==========================================
# IA - RTX 3050
# ==========================================
import os
device = 'cuda' if torch.cuda.is_available() else 'cpu'
use_half = device != "cpu"

# Usar modelo TACO entrenado si existe, sino el base
MODELO_TACO = "arve_best.pt"
MODELO_BASE = "yolov8n.pt"
if os.path.exists(MODELO_TACO):
    print(f"[OK] Usando modelo TACO entrenado: {MODELO_TACO}")
    modelo_path = MODELO_TACO
else:
    print(f"[INFO] Modelo TACO no encontrado, usando base: {MODELO_BASE}")
    print(f"[INFO] Ejecuta 'lanzar_entrenamiento.py' para entrenar con 60 clases TACO")
    modelo_path = MODELO_BASE

print(f"[*] Cargando IA en: {device.upper()}")
model = YOLO(modelo_path).to(device)

# Mapeo dinámico de clases según el modelo
is_taco_model = False
if "Clear plastic bottle" in model.names.values() or len(model.names) == 60:
    is_taco_model = True
    print("[OK] Detectado modelo con clases TACO. Aplicando mapeo dinámico de TACO...")
    PERSON_CLASS = -1  # No hay persona en TACO
    TRASH_CLASSES = {
        4: ("Botella Plastico",   "PLASTICO",   (0,255,0)),
        5: ("Botella Plastico",   "PLASTICO",   (0,255,0)),
        6: ("Botella Vidrio",     "VIDRIO",     (0,255,128)),
        7: ("Tapa Plastica",      "PLASTICO",   (0,255,0)),
        8: ("Chapa Metalica",     "METAL",      (200,200,0)),
        10: ("Lata Comida",       "METAL",      (200,200,0)),
        11: ("Aerosol",           "METAL",      (200,200,0)),
        12: ("Lata Bebida",       "METAL",      (200,200,0)),
        20: ("Vaso Papel",        "PAPEL",      (255,200,0)),
        21: ("Vaso Plastico",     "PLASTICO",   (0,255,0)),
        22: ("Vaso Tecnopor",     "RESIDUO",    (180,180,0)),
        23: ("Vaso Vidrio",       "VIDRIO",     (0,255,128)),
        24: ("Vaso Plastico",     "PLASTICO",   (0,255,0)),
        25: ("Comida Organica",   "ORGANICO",   (0,165,255)),
        26: ("Jarra Vidrio",      "VIDRIO",     (0,255,128)),
        27: ("Tapa Plastica",     "PLASTICO",   (0,255,0)),
        28: ("Tapa Metalica",     "METAL",      (200,200,0)),
        29: ("Plastico",          "PLASTICO",   (0,255,0)),
        34: ("Bolsa Papel",       "PAPEL",      (255,200,0)),
        36: ("Envoltura",         "PLASTICO",   (0,255,0)),
        38: ("Bolsa Basura",      "PLASTICO",   (0,255,0)),
        40: ("Bolsa Plastico",    "PLASTICO",   (0,255,0)),
        44: ("Tupperware",        "PLASTICO",   (0,255,0)),
        45: ("Envase Alimento",   "PLASTICO",   (0,255,0)),
        55: ("Cañita Plastica",   "PLASTICO",   (0,255,0)),
        59: ("Colilla Cigarro",   "RESIDUO",    (180,180,0)),
    }
    DANGEROUS_CLASSES = {1}  # Batería
    OBSTACLE_CLASSES = set()
else:
    print("[OK] Detectado modelo COCO estándar (yolov8n). Aplicando mapeo COCO...")
    PERSON_CLASS = 0
    TRASH_CLASSES = {
        39: ("Botella",        "PLASTICO",   (0,255,0)),
        41: ("Vaso/Taza",      "PLASTICO",   (0,255,0)),
        45: ("Recipiente",     "PLASTICO",   (0,200,0)),
        46: ("Botella Vino",   "VIDRIO",     (0,255,128)),
        47: ("Copa",           "VIDRIO",     (0,255,128)),
        48: ("Comida",         "ORGANICO",   (0,165,255)),
        49: ("Tenedor",        "METAL",      (200,200,0)),
        50: ("Cuchillo",       "PELIGROSO",  (0,0,255)),
        51: ("Cuchara",        "METAL",      (200,200,0)),
        52: ("Cascara",        "ORGANICO",   (0,165,255)),
        53: ("Fruta",          "ORGANICO",   (0,165,255)),
        54: ("Naranja",        "ORGANICO",   (0,165,255)),
        56: ("Sandwich",       "ORGANICO",   (0,165,255)),
        57: ("Pizza",          "ORGANICO",   (0,165,255)),
        58: ("Donut",          "ORGANICO",   (0,165,255)),
        59: ("Pastel",         "ORGANICO",   (0,165,255)),
        60: ("Lata/Bowl",      "METAL",      (200,200,0)),
        61: ("Bolsa",          "PLASTICO",   (0,255,0)),
        62: ("Silla",          "OBSTACULO",  (100,100,100)),
        67: ("Celular",        "ELECTRONICO",(255,0,255)),
        73: ("Libro/Papel",    "PAPEL",      (255,200,0)),
        76: ("Tijera",         "PELIGROSO",  (0,0,255)),
        77: ("Peluche",        "RESIDUO",    (180,180,0)),
        78: ("Secador",        "ELECTRONICO",(255,0,255)),
        79: ("Cepillo",        "RESIDUO",    (180,180,0)),
    }
    DANGEROUS_CLASSES = {50, 76}
    OBSTACLE_CLASSES = {62}

# Buffer de video (siempre el más reciente)
frame_buffer = deque(maxlen=1)

# Estado global
estado_actual = Estado.BUSCANDO
dist_frontal  = 100
emergencia    = False
running       = True

# Variables para maniobras temporizadas no bloqueantes
maniobra_tipo = None  # None, "esquivar", "rodear"
maniobra_inicio_t = 0.0

# Control de spam de errores de red
NET_ERROR_COOLDOWN = 5.0
last_net_error = 0.0

# Variables de búsqueda 360°
servo_pos     = 90   # Posición del servo (0=izq, 90=frente, 180=der)
servo_dir     = 1    # Dirección del barrido: 1=derecha, -1=izquierda
ultimo_objetivo_dir = None  # Recuerda donde vio basura por última vez
ultimo_barrido_t = 0.0

# ==========================================
# ESTRUCTURAS DE ESTADO ASÍNCRONO
# ==========================================
target_state = {
    "v1": 0,
    "v2": 0,
    "servo": 90,
    "led_r": 0,
    "led_g": 0,
    "led_b": 1,
    "beep": 0
}
target_state_lock = threading.Lock()

current_state = {
    "v1": None,
    "v2": None,
    "servo": None,
    "led_r": None,
    "led_g": None,
    "led_b": None
}

# ==========================================
# COMUNICACIÓN CON ESP32 (ASÍNCRONA)
# ==========================================
def _log_net_error(context, err):
    global last_net_error
    now = time.time()
    if now - last_net_error >= NET_ERROR_COOLDOWN:
        print(f"[WARN] {context}: {err}")
        last_net_error = now

# Funciones de control rápidas (actualizan el estado objetivo de inmediato sin bloquear)
def mover(v1, v2):
    with target_state_lock:
        target_state["v1"] = v1
        target_state["v2"] = v2

def servo(ang):
    with target_state_lock:
        target_state["servo"] = ang

def led(r, g, b):
    with target_state_lock:
        target_state["led_r"] = r
        target_state["led_g"] = g
        target_state["led_b"] = b

def beep(n=1):
    with target_state_lock:
        target_state["beep"] = n

def get_status():
    global dist_frontal, emergencia
    try:
        r = urllib.request.urlopen(URL_STATUS, timeout=0.3)
        import json
        data = json.loads(r.read())
        dist_frontal = data.get("dist_f", 100)
        emergencia   = data.get("emergencia", False)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        _log_net_error("No se pudo leer /status", e)

# Hilo de transmisión de comandos en segundo plano
def command_sender_thread():
    global running
    last_heartbeat = 0.0
    last_motor_send = 0.0
    last_servo_send = 0.0
    last_led_send = 0.0
    
    print("[*] Hilo de control de hardware asíncrono activo (Rate Limiting habilitado)...")
    while running:
        time.sleep(0.01)  # Bucle rápido de 10ms
        
        # 1. Beep prioritario
        beeps_to_send = 0
        with target_state_lock:
            if target_state["beep"] > 0:
                beeps_to_send = target_state["beep"]
                target_state["beep"] = 0
                
        if beeps_to_send > 0:
            url = f"{URL_BEEP}?n={beeps_to_send}"
            try:
                urllib.request.urlopen(url, timeout=0.5)
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                _log_net_error("Error enviando beep", e)
            continue
            
        # 2. Motores, Servo y LED
        with target_state_lock:
            t_v1, t_v2 = target_state["v1"], target_state["v2"]
            t_servo = target_state["servo"]
            t_r, t_g, t_b = target_state["led_r"], target_state["led_g"], target_state["led_b"]
            
        now = time.time()
        force_send = (now - last_heartbeat > 2.5)  # Latido de sincronización
        
        # A. Control de Motores (Limitado a una vez cada 80ms, excepto parada de emergencia)
        es_parada_emergencia = (t_v1 == 0 and t_v2 == 0 and (current_state["v1"] != 0 or current_state["v2"] != 0))
        if force_send or t_v1 != current_state["v1"] or t_v2 != current_state["v2"]:
            if es_parada_emergencia or (now - last_motor_send >= 0.08):
                url = f"{URL_MOVE}?v1={t_v1}&v2={t_v2}"
                try:
                    urllib.request.urlopen(url, timeout=0.08)
                    current_state["v1"], current_state["v2"] = t_v1, t_v2
                    last_motor_send = now
                    last_heartbeat = now
                except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                    _log_net_error("Error enviando movimiento", e)
                    
        # B. Control de Servo (Limitado a una vez cada 120ms)
        if force_send or t_servo != current_state["servo"]:
            if now - last_servo_send >= 0.12:
                url = f"{URL_SERVO}?ang={t_servo}"
                try:
                    urllib.request.urlopen(url, timeout=0.08)
                    current_state["servo"] = t_servo
                    last_servo_send = now
                    last_heartbeat = now
                except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                    _log_net_error("Error enviando angulo de servo", e)
                    
        # C. Control de LED (Limitado a una vez cada 200ms)
        if force_send or t_r != current_state["led_r"] or t_g != current_state["led_g"] or t_b != current_state["led_b"]:
            if now - last_led_send >= 0.20:
                url = f"{URL_LED}?r={t_r}&g={t_g}&b={t_b}"
                try:
                    urllib.request.urlopen(url, timeout=0.08)
                    current_state["led_r"], current_state["led_g"], current_state["led_b"] = t_r, t_g, t_b
                    last_led_send = now
                    last_heartbeat = now
                except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                    _log_net_error("Error enviando estado de LED", e)

# ==========================================
# HILO DE VIDEO
# ==========================================
def video_thread():
    global running
    print(f"[*] Conectando al stream de video...")
    while running:
        try:
            stream = urllib.request.urlopen(URL_STREAM, timeout=5)
            buf = b''
            while running:
                buf += stream.read(4096)
                a = buf.find(b'\xff\xd8')
                b = buf.find(b'\xff\xd9')
                if a != -1 and b != -1:
                    if b > a:
                        jpg = buf[a:b+2]
                        buf = buf[b+2:]
                        if len(jpg) > 0:
                            img = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                            if img is not None:
                                frame_buffer.append(img)
                    else:
                        # Si el marcador de fin está antes del de inicio, limpiamos el residuo corrupto
                        buf = buf[a:]
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            print(f"[Video] Reconectando... ({e})")
            time.sleep(1)

# ==========================================
# HILO DE TELEMETRÍA
# ==========================================
def telemetry_thread():
    while running:
        get_status()
        time.sleep(0.15)

# ==========================================
# LÓGICA DE BÚSQUEDA 360° (Radar Visual - No Bloqueante)
# ==========================================
def buscar_con_radar():
    global servo_pos, servo_dir, ultimo_objetivo_dir, ultimo_barrido_t
    ahora = time.time()
    # Realizar barrido de servo cada 200ms
    if ahora - ultimo_barrido_t >= 0.20:
        ultimo_barrido_t = ahora
        servo_pos += servo_dir * 15
        if servo_pos >= 150:
            servo_pos = 150
            servo_dir = -1
        elif servo_pos <= 30:
            servo_pos = 30
            servo_dir = 1
        servo(servo_pos)

# ==========================================
# CEREBRO PRINCIPAL
# ==========================================
def brain_loop():
    global running, estado_actual, ultimo_objetivo_dir, maniobra_tipo, maniobra_inicio_t

    cv2.namedWindow("ARVE ELITE v6.0", cv2.WINDOW_AUTOSIZE)
    prev_time = time.time()
    beep_dado = False

    while running:
        if not frame_buffer:
            time.sleep(0.01)
            continue

        frame = frame_buffer[-1].copy()
        h, w = frame.shape[:2]
        centro_x = w // 2

        # --- CONTROL DE MANIOBRA TEMPORIZADA NO BLOQUEANTE ---
        ahora = time.time()
        if maniobra_tipo is not None:
            if maniobra_tipo == "esquivar":
                duracion = ahora - maniobra_inicio_t
                if duracion < 0.3:
                    estado_actual = "OBSTACULO: RETROCEDIENDO..."
                    mover(-1200, -1200)
                    led(1, 0, 0)
                elif duracion < 0.6:
                    estado_actual = "OBSTACULO: EVITANDO..."
                    mover(1200, -1200)
                    led(1, 0, 0)
                else:
                    maniobra_tipo = None  # Fin de la maniobra
            elif maniobra_tipo == "rodear":
                duracion = ahora - maniobra_inicio_t
                if duracion < 0.3:
                    estado_actual = "⚠ PELIGROSO: RETROCEDIENDO..."
                    mover(-1000, -1000)
                    led(1, 0, 1)
                elif duracion < 0.6:
                    estado_actual = "⚠ PELIGROSO: EVITANDO..."
                    mover(1500, -1500)
                    led(1, 0, 1)
                else:
                    maniobra_tipo = None  # Fin de la maniobra

            # Dibujar HUD y mostrar frame (nos saltamos la IA)
            curr_time = time.time()
            fps = 1.0 / max((curr_time - prev_time), 0.001)
            prev_time = curr_time
            cv2.rectangle(frame, (0,0), (w,38), (15,15,15), -1)
            color_fps = (0,255,0) if fps > 10 else (0,165,255)
            cv2.putText(frame, f"FPS: {int(fps)}", (8,25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_fps, 2)
            cv2.putText(frame, f"RTX 3050 | CUDA: {str(device).upper()}", (105,25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,255,255), 1)
            cv2.rectangle(frame, (0,h-40), (w,h), (15,15,15), -1)
            cv2.putText(frame, estado_actual, (8, h-15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,255,0), 1)
            cv2.putText(frame, f"DIST: {dist_frontal}cm | SERVO: {servo_pos}°", (w-180, h-15), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255,255,0), 1)
            cv2.line(frame, (centro_x-15, h//2), (centro_x+15, h//2), (255,255,255), 1)
            cv2.line(frame, (centro_x, h//2-15), (centro_x, h//2+15), (255,255,255), 1)
            cv2.imshow("ARVE ELITE v5.0", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                running = False
                mover(0, 0)
                led(0, 0, 0)
                break
            continue

        # --- IA ---
        results = model.predict(frame, verbose=False, conf=0.35,
                                imgsz=320, half=use_half, device=device)
        detecciones = results[0].boxes

        mejor_basura  = None  # (x_centro, area, nombre, coords)
        mayor_area    = 0
        hay_persona   = False

        for box in detecciones:
            cls  = int(box.cls[0])
            c    = box.xyxy[0].cpu().numpy().astype(int)
            area = (c[2]-c[0]) * (c[3]-c[1])

            if cls == PERSON_CLASS:
                hay_persona = True
                cv2.rectangle(frame, (c[0],c[1]), (c[2],c[3]), (0,0,255), 3)
                cv2.putText(frame, "⚠ PERSONA - STOP", (c[0], c[1]-8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)

            elif cls in TRASH_CLASSES and area > mayor_area:
                nombre, material, color = TRASH_CLASSES[cls]
                es_peligroso = cls in DANGEROUS_CLASSES
                mayor_area = area
                mejor_basura = ((c[0]+c[2])//2, area, nombre, material, color, c, es_peligroso)
                
                cv2.rectangle(frame, (c[0],c[1]), (c[2],c[3]), color, 2)
                etiqueta = f"{'⚠ PELIGROSO' if es_peligroso else nombre} [{material}]"
                cv2.putText(frame, etiqueta, (c[0], c[1]-8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        # ================================================
        # TOMA DE DECISIONES
        # ================================================
        if hay_persona:
            # PRIORIDAD 1: Persona detectada → STOP total
            estado_actual = Estado.PELIGRO
            mover(0, 0)
            servo(90)
            led(1, 0, 0)
            beep_dado = False

        elif mejor_basura:
            # PRIORIDAD 2: Hay basura → Analizar y actuar
            tx, area, nombre, material, color_det, coords, es_peligroso = mejor_basura
            ultimo_objetivo_dir = "derecha" if tx > centro_x else "izquierda"
            error_x = tx - centro_x

            # Ajustar servo de cámara hacia el objetivo
            servo_objetivo = int(servo_pos + (-error_x / w) * 60)
            servo_objetivo = max(30, min(150, servo_objetivo))
            servo(servo_objetivo)

            if es_peligroso:
                # Objeto peligroso (cuchillo, tijera) → Iniciar maniobra no bloqueante
                estado_actual = "⚠ OBJETO PELIGROSO: RODEANDO"
                led(1, 0, 1)  # Magenta = Peligro especial
                if not beep_dado:
                    beep(3)
                    beep_dado = True
                # Iniciar maniobra no bloqueante
                maniobra_tipo = "rodear"
                maniobra_inicio_t = time.time()

            elif emergencia or (0 < dist_frontal < 20):
                # Llegó al objetivo → detenerse
                estado_actual = f"LLEGÓ: {nombre} [{material}]"
                mover(0, 0)
                led(1, 1, 0)  # Amarillo = En el objetivo
                if not beep_dado:
                    beep(2)
                    beep_dado = True

            elif abs(error_x) < 40:
                # Centrado → avanzar directo
                estado_actual = f"AVANZANDO → {nombre} [{material}]"
                mover(1800, 1800)
                led(0, 1, 0)
                beep_dado = False

            elif error_x > 0:
                # Basura a la derecha → girar derecha
                estado_actual = f"GIRANDO DER → {nombre}"
                mover(1600, -1600)
                led(0, 0, 1)
            else:
                # Basura a la izquierda → girar izquierda
                estado_actual = f"GIRANDO IZQ → {nombre}"
                mover(-1600, 1600)
                led(0, 0, 1)

        else:
            # PRIORIDAD 3: No ve nada → Buscar con radar
            estado_actual = Estado.BUSCANDO
            beep_dado = False

            if emergencia or (0 < dist_frontal < 25):
                # Hay obstáculo → Iniciar maniobra no bloqueante
                estado_actual = Estado.ESQUIVANDO
                maniobra_tipo = "esquivar"
                maniobra_inicio_t = time.time()
            else:
                # Modo radar: mover servo y avanzar lentamente (no bloqueante)
                buscar_con_radar()
                mover(600, -600)     # Giro lento sobre su eje
                led(0, 0, 1)         # Azul = Buscando

        # ================================================
        # HUD PROFESIONAL
        # ================================================
        curr_time = time.time()
        fps = 1.0 / max((curr_time - prev_time), 0.001)
        prev_time = curr_time

        # Barra superior
        cv2.rectangle(frame, (0,0), (w,38), (15,15,15), -1)
        color_fps = (0,255,0) if fps > 10 else (0,165,255)
        cv2.putText(frame, f"FPS: {int(fps)}", (8,25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_fps, 2)
        cv2.putText(frame, f"RTX 3050 | CUDA: {str(device).upper()}", (105,25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,255,255), 1)

        # Barra inferior (diseño de doble línea profesional para evitar solapamiento)
        cv2.rectangle(frame, (0, h-50), (w, h), (15, 15, 15), -1)
        # Línea 1: Estado actual del robot
        cv2.putText(frame, estado_actual, (8, h-30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 0), 1)
        # Línea 2: Telemetría de sensores
        cv2.putText(frame, f"DIST: {dist_frontal}cm | SERVO: {servo_pos}°",
                    (8, h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 255, 0), 1)

        # Cruz central (mira de la cámara)
        cv2.line(frame, (centro_x-15, h//2), (centro_x+15, h//2), (255,255,255), 1)
        cv2.line(frame, (centro_x, h//2-15), (centro_x, h//2+15), (255,255,255), 1)

        cv2.imshow("ARVE ELITE v5.0", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            running = False
            mover(0, 0)
            led(0, 0, 0)
            break

# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    print("=" * 50)
    print("  ARVE ELITE v6.0 - SISTEMA AUTÓNOMO ACTIVO")
    print("=" * 50)
    print(f"  IA Device  : {device.upper()}")
    print(f"  Modelo IA  : {modelo_path}")
    print(f"  ESP32 IP   : {ESP32_IP}")
    print(f"  Presiona Q : salir")
    print("=" * 50)

    threading.Thread(target=video_thread,          daemon=True).start()
    threading.Thread(target=telemetry_thread,        daemon=True).start()
    threading.Thread(target=command_sender_thread, daemon=True).start()
    try:
        brain_loop()
    except KeyboardInterrupt:
        print("[WARN] Interrupción por teclado.")
    finally:
        running = False
        mover(0, 0)
        led(0, 0, 0)
        cv2.destroyAllWindows()
        print("[!] Sistema ARVE apagado.")
