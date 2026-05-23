"""
ARVE SUPER BRAIN v7.0 - CEREBRO DEFINITIVO
Integra: 2 Motores, 2 Servos (Pan+Tilt), 3 LEDs RGB, Sensor Color,
         2x Ultrasonido, RTX 3050 (YOLO TACO + COCO Personas), Escaneo 360°
Modelo: Usa arve_best.pt (entrenado TACO) y yolov8n.pt (COCO) simultaneamente
"""
import cv2
import numpy as np
from ultralytics import YOLO
import time
import threading
import urllib.request
import urllib.error
import torch
import os
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
URL_SERVO2 = f"http://{ESP32_IP}/servo2"
URL_BEEP   = f"http://{ESP32_IP}/beep"
URL_LED    = f"http://{ESP32_IP}/led"
URL_STATUS = f"http://{ESP32_IP}/status"

# Clases dinámicas TACO
TRASH_CLASSES = {
    0: ("Papel Aluminio", "METAL", (200,200,0)),
    1: ("Bateria", "PELIGROSO", (0,0,255)),
    2: ("Blister Aluminio", "METAL", (200,200,0)),
    3: ("Blister Carton", "CARTON", (255,200,0)),
    4: ("Otra botella plastico", "PLASTICO", (0,255,0)),
    5: ("Botella Plastico Transp.", "PLASTICO", (0,255,0)),
    6: ("Botella Vidrio", "VIDRIO", (0,255,128)),
    7: ("Tapa Plastica", "PLASTICO", (0,255,0)),
    8: ("Tapa Metalica", "METAL", (200,200,0)),
    9: ("Vidrio Roto", "PELIGROSO", (0,0,255)),
    10: ("Lata Comida", "METAL", (200,200,0)),
    11: ("Aerosol", "PELIGROSO", (0,0,255)),
    12: ("Lata Bebida", "METAL", (200,200,0)),
    13: ("Tubo Carton", "CARTON", (255,200,0)),
    14: ("Otro Carton", "CARTON", (255,200,0)),
    15: ("Carton Huevo", "CARTON", (255,200,0)),
    16: ("Carton Bebida", "CARTON", (255,200,0)),
    17: ("Carton Corrugado", "CARTON", (255,200,0)),
    18: ("Carton Comida", "CARTON", (255,200,0)),
    19: ("Caja Pizza", "CARTON", (255,200,0)),
    20: ("Vaso Papel", "PAPEL", (255,200,0)),
    21: ("Vaso Plastico Desc.", "PLASTICO", (0,255,0)),
    22: ("Vaso Espuma", "PLASTICO", (0,255,0)),
    23: ("Vaso Vidrio", "VIDRIO", (0,255,128)),
    24: ("Otro vaso plastico", "PLASTICO", (0,255,0)),
    25: ("Residuo Comida", "ORGANICO", (0,165,255)),
    26: ("Jarra Vidrio", "VIDRIO", (0,255,128)),
    27: ("Tapa Plastico", "PLASTICO", (0,255,0)),
    28: ("Tapa Metal", "METAL", (200,200,0)),
    29: ("Otro Plastico", "PLASTICO", (0,255,0)),
    30: ("Papel Revista", "PAPEL", (255,200,0)),
    31: ("Pañuelos", "PAPEL", (255,200,0)),
    32: ("Papel Envoltura", "PAPEL", (255,200,0)),
    33: ("Papel Normal", "PAPEL", (255,200,0)),
    34: ("Bolsa Papel", "PAPEL", (255,200,0)),
    35: ("Bolsa Papel Plastificada", "PLASTICO", (0,255,0)),
    36: ("Film Plastico", "PLASTICO", (0,255,0)),
    37: ("Anillos Six Pack", "PLASTICO", (0,255,0)),
    38: ("Bolsa Basura", "PLASTICO", (0,255,0)),
    39: ("Otra envoltura plastico", "PLASTICO", (0,255,0)),
    40: ("Bolsa Plastico Simple", "PLASTICO", (0,255,0)),
    41: ("Bolsa Polipropileno", "PLASTICO", (0,255,0)),
    42: ("Paquete Papas", "PLASTICO", (0,255,0)),
    43: ("Envase Untable", "PLASTICO", (0,255,0)),
    44: ("Tupperware", "PLASTICO", (0,255,0)),
    45: ("Envase Comida Desc.", "PLASTICO", (0,255,0)),
    46: ("Envase Comida Espuma", "PLASTICO", (0,255,0)),
    47: ("Otro Envase Plastico", "PLASTICO", (0,255,0)),
    48: ("Guantes Plastico", "PLASTICO", (0,255,0)),
    49: ("Utensilios Plastico", "PLASTICO", (0,255,0)),
    50: ("Chapa Lata", "METAL", (200,200,0)),
    51: ("Cuerdas", "RESIDUO", (180,180,0)),
    52: ("Chatarra Metal", "METAL", (200,200,0)),
    53: ("Zapato", "RESIDUO", (180,180,0)),
    54: ("Tubo Exprimible", "PLASTICO", (0,255,0)),
    55: ("Cañita Plastica", "PLASTICO", (0,255,0)),
    56: ("Cañita Papel", "PAPEL", (255,200,0)),
    57: ("Trozo Espuma", "PLASTICO", (0,255,0)),
    58: ("Basura sin Etiqueta", "RESIDUO", (180,180,0)),
    59: ("Cigarro", "RESIDUO", (180,180,0)),
}

DANGEROUS_CLASSES = {1, 9, 11} # Bateria, Vidrio Roto, Aerosol

# Estados del robot
class Estado:
    BUSCANDO   = "MODO RADAR: BUSCANDO..."
    APUNTANDO  = "CALIBRANDO ANGULO..."
    AVANZANDO  = "OBJETIVO: AVANZANDO"
    ESQUIVANDO = "OBSTACULO: ESQUIVANDO"
    PELIGRO    = "PERSONA DETECTADA: STOP"
    ESCANEANDO = "ESCANEANDO MATERIAL..."

# ==========================================
# IA - RTX 3050 (Modelos Duales)
# ==========================================
device = 'cuda' if torch.cuda.is_available() else 'cpu'
use_half = device != "cpu"

print(f"[*] Cargando IA en: {device.upper()}")

# Modelo 1: TACO (Basura)
MODELO_TACO = "arve_best.pt"
if os.path.exists(MODELO_TACO):
    print(f"[OK] Cargando modelo TACO entrenado: {MODELO_TACO}")
    model_taco = YOLO(MODELO_TACO).to(device)
else:
    print(f"[WARN] Modelo TACO no encontrado. Usa 'entrenar_profesional_v7.py' para entrenarlo.")
    model_taco = YOLO("yolov8n.pt").to(device) # fallback

# Modelo 2: COCO (Personas)
print(f"[OK] Cargando modelo COCO base para personas: yolov8n.pt")
model_coco = YOLO("yolov8n.pt").to(device)
PERSON_CLASS = 0

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

# Variables de búsqueda 360° (Pan y Tilt)
servo_pan_pos  = 90   # 0=izq, 90=frente, 180=der
servo_tilt_pos = 135  # 90=frente, 135=45 grados hacia abajo (ideal para el suelo)
scan_pan_dir   = 1
scan_tilt_dir  = 1
ultimo_barrido_t = 0.0

# ==========================================
# ESTRUCTURAS DE ESTADO ASÍNCRONO
# ==========================================
target_state = {
    "v1": 0,
    "v2": 0,
    "servo_pan": 90,
    "servo_tilt": 135,
    "led1": (0, 0, 4095), # Estado (Azul)
    "led2": (0, 0, 0),    # Material (Apagado)
    "led3": (0, 4095, 0), # Alerta (Verde)
    "beep": 0
}
target_state_lock = threading.Lock()

current_state = {
    "v1": None,
    "v2": None,
    "servo_pan": None,
    "servo_tilt": None,
    "led1": None,
    "led2": None,
    "led3": None
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

def mover(v1, v2):
    with target_state_lock:
        target_state["v1"] = v1
        target_state["v2"] = v2

def servo_pan(ang):
    with target_state_lock:
        target_state["servo_pan"] = ang

def servo_tilt(ang):
    with target_state_lock:
        target_state["servo_tilt"] = ang

def led(n, r, g, b):
    with target_state_lock:
        if n == 1: target_state["led1"] = (r, g, b)
        elif n == 2: target_state["led2"] = (r, g, b)
        elif n == 3: target_state["led3"] = (r, g, b)

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

# Hilo de transmisión de comandos
def command_sender_thread():
    global running
    last_heartbeat = 0.0
    last_motor_send = 0.0
    last_servo_send = 0.0
    last_led_send = 0.0
    
    print("[*] Hilo de control de hardware asíncrono activo...")
    while running:
        time.sleep(0.01)
        
        # 1. Beep prioritario
        beeps_to_send = 0
        with target_state_lock:
            if target_state["beep"] > 0:
                beeps_to_send = target_state["beep"]
                target_state["beep"] = 0
                
        if beeps_to_send > 0:
            try:
                urllib.request.urlopen(f"{URL_BEEP}?n={beeps_to_send}", timeout=0.5)
            except: pass
            continue
            
        with target_state_lock:
            t_v1, t_v2 = target_state["v1"], target_state["v2"]
            t_span = target_state["servo_pan"]
            t_stilt = target_state["servo_tilt"]
            t_l1 = target_state["led1"]
            t_l2 = target_state["led2"]
            t_l3 = target_state["led3"]
            
        now = time.time()
        force_send = (now - last_heartbeat > 2.5)
        
        # A. Motores
        es_parada = (t_v1 == 0 and t_v2 == 0 and (current_state["v1"] != 0 or current_state["v2"] != 0))
        if force_send or t_v1 != current_state["v1"] or t_v2 != current_state["v2"]:
            if es_parada or (now - last_motor_send >= 0.08):
                try:
                    urllib.request.urlopen(f"{URL_MOVE}?v1={t_v1}&v2={t_v2}", timeout=0.08)
                    current_state["v1"], current_state["v2"] = t_v1, t_v2
                    last_motor_send = last_heartbeat = now
                except Exception as e: _log_net_error("Move error", e)
                    
        # B. Servos
        if force_send or t_span != current_state["servo_pan"] or t_stilt != current_state["servo_tilt"]:
            if now - last_servo_send >= 0.12:
                try:
                    if t_span != current_state["servo_pan"]:
                        urllib.request.urlopen(f"{URL_SERVO}?ang={t_span}", timeout=0.08)
                        current_state["servo_pan"] = t_span
                    if t_stilt != current_state["servo_tilt"]:
                        urllib.request.urlopen(f"{URL_SERVO2}?ang={t_stilt}", timeout=0.08)
                        current_state["servo_tilt"] = t_stilt
                    last_servo_send = last_heartbeat = now
                except Exception as e: _log_net_error("Servo error", e)
                    
        # C. LEDs (todos juntos con /leds)
        if force_send or t_l1 != current_state["led1"] or t_l2 != current_state["led2"] or t_l3 != current_state["led3"]:
            if now - last_led_send >= 0.20:
                try:
                    url = f"http://{ESP32_IP}/leds?l1r={t_l1[0]}&l1g={t_l1[1]}&l1b={t_l1[2]}&l2r={t_l2[0]}&l2g={t_l2[1]}&l2b={t_l2[2]}&l3r={t_l3[0]}&l3g={t_l3[1]}"
                    urllib.request.urlopen(url, timeout=0.08)
                    current_state["led1"] = t_l1
                    current_state["led2"] = t_l2
                    current_state["led3"] = t_l3
                    last_led_send = last_heartbeat = now
                except Exception as e: _log_net_error("LED error", e)

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
                        buf = buf[a:]
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            time.sleep(1)

# ==========================================
# HILO DE TELEMETRÍA
# ==========================================
def telemetry_thread():
    while running:
        get_status()
        time.sleep(0.15)

# ==========================================
# LÓGICA DE BÚSQUEDA 360°
# ==========================================
def buscar_con_radar():
    global servo_pan_pos, servo_tilt_pos, scan_pan_dir, scan_tilt_dir, ultimo_barrido_t
    ahora = time.time()
    
    # Realizar barrido de servo cada 150ms
    if ahora - ultimo_barrido_t >= 0.15:
        ultimo_barrido_t = ahora
        
        # Movimiento horizontal (pan)
        servo_pan_pos += scan_pan_dir * 15
        
        if servo_pan_pos >= 150:
            servo_pan_pos = 150
            scan_pan_dir = -1
            # Bajar un poco la mirada al llegar al extremo
            servo_tilt_pos -= 15
        elif servo_pan_pos <= 30:
            servo_pan_pos = 30
            scan_pan_dir = 1
            # Bajar un poco la mirada al llegar al extremo
            servo_tilt_pos -= 15
            
        if servo_tilt_pos < 60:
            servo_tilt_pos = 120 # Resetear mirada arriba
            # Al completar un barrido vertical, girar el robot
            mover(1200, -1200)
            time.sleep(0.3)
            mover(0, 0)
            
        servo_pan(servo_pan_pos)
        servo_tilt(servo_tilt_pos)

# ==========================================
# CEREBRO PRINCIPAL
# ==========================================
def brain_loop():
    global running, estado_actual, maniobra_tipo, maniobra_inicio_t

    cv2.namedWindow("ARVE ELITE v7.0", cv2.WINDOW_AUTOSIZE)
    prev_time = time.time()
    beep_dado = False

    while running:
        if not frame_buffer:
            time.sleep(0.01)
            continue

        frame = frame_buffer[-1].copy()
        h, w = frame.shape[:2]
        centro_x = w // 2

        # --- CONTROL DE MANIOBRA TEMPORIZADA ---
        ahora = time.time()
        if maniobra_tipo is not None:
            if maniobra_tipo == "esquivar":
                duracion = ahora - maniobra_inicio_t
                if duracion < 0.3:
                    estado_actual = "OBSTACULO: RETROCEDIENDO..."
                    mover(-1200, -1200)
                    led(1, 4095, 0, 0) # LED1 Rojo
                elif duracion < 0.6:
                    estado_actual = "OBSTACULO: EVITANDO..."
                    mover(1200, -1200)
                else:
                    maniobra_tipo = None
            elif maniobra_tipo == "rodear":
                duracion = ahora - maniobra_inicio_t
                if duracion < 0.3:
                    estado_actual = "⚠ PELIGROSO: RETROCEDIENDO..."
                    mover(-1000, -1000)
                    led(3, 4095, 0, 0) # LED3 Rojo (Alerta)
                elif duracion < 0.6:
                    estado_actual = "⚠ PELIGROSO: EVITANDO..."
                    mover(1500, -1500)
                else:
                    maniobra_tipo = None

            # Render HUD durante maniobra
            curr_time = time.time()
            fps = 1.0 / max((curr_time - prev_time), 0.001)
            prev_time = curr_time
            cv2.rectangle(frame, (0,h-40), (w,h), (15,15,15), -1)
            cv2.putText(frame, estado_actual, (8, h-15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,255,0), 1)
            cv2.imshow("ARVE ELITE v7.0", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'): running = False
            continue

        # --- IA DUAL ---
        # 1. Detectar Personas (COCO)
        results_coco = model_coco.predict(frame, verbose=False, conf=0.50, imgsz=320, half=use_half, device=device)
        hay_persona = False
        
        for box in results_coco[0].boxes:
            if int(box.cls[0]) == PERSON_CLASS:
                hay_persona = True
                c = box.xyxy[0].cpu().numpy().astype(int)
                cv2.rectangle(frame, (c[0],c[1]), (c[2],c[3]), (0,0,255), 3)
                cv2.putText(frame, "⚠ PERSONA - STOP", (c[0], c[1]-8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
                break

        # 2. Detectar Basura (TACO) - Resolución 416 para detectar cosas pequeñas (3cm-8cm)
        results_taco = model_taco.predict(frame, verbose=False, conf=0.35, imgsz=416, half=use_half, device=device)
        
        mejor_basura = None
        mayor_area = 0

        for box in results_taco[0].boxes:
            cls = int(box.cls[0])
            if cls in TRASH_CLASSES:
                c = box.xyxy[0].cpu().numpy().astype(int)
                area = (c[2]-c[0]) * (c[3]-c[1])
                if area > mayor_area:
                    mayor_area = area
                    nombre, material, color_rgb = TRASH_CLASSES[cls]
                    es_peligroso = cls in DANGEROUS_CLASSES
                    mejor_basura = ((c[0]+c[2])//2, area, nombre, material, color_rgb, c, es_peligroso)
                    
                color_bgr = (color_rgb[2], color_rgb[1], color_rgb[0])
                cv2.rectangle(frame, (c[0],c[1]), (c[2],c[3]), color_bgr, 2)
                etiqueta = f"{TRASH_CLASSES[cls][0]} [{TRASH_CLASSES[cls][1]}]"
                cv2.putText(frame, etiqueta, (c[0], c[1]-8), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color_bgr, 2)

        # ================================================
        # TOMA DE DECISIONES
        # ================================================
        if hay_persona:
            estado_actual = Estado.PELIGRO
            mover(0, 0)
            servo_pan(90)
            servo_tilt(90)
            led(1, 4095, 0, 0) # LED1 Rojo (Estado: Peligro)
            led(3, 4095, 0, 0) # LED3 Rojo (Alerta)
            beep_dado = False

        elif mejor_basura:
            tx, area, nombre, material, color_rgb, coords, es_peligroso = mejor_basura
            error_x = tx - centro_x

            # Ajustar servo pan
            nuevo_pan = int(servo_pan_pos + (-error_x / w) * 60)
            servo_pan(max(30, min(150, nuevo_pan)))
            
            # Ajustar servo tilt basado en el centro Y de la deteccion (simplificado)
            # Para apuntar la camara hacia abajo a medida que se acerca
            
            # Actualizar LEDs
            led(1, 0, 4095, 0) # LED1 Verde (Avanzando)
            # Mapear color a LED2 (R, G, B de 0 a 4095)
            # Si material es PLASTICO -> verde, VIDRIO -> azul, METAL -> amarillo, etc.
            if material == "PLASTICO": led(2, 0, 4095, 0)
            elif material == "VIDRIO": led(2, 0, 0, 4095)
            elif material == "METAL": led(2, 4095, 4095, 0)
            elif material == "PAPEL" or material == "CARTON": led(2, 4095, 2000, 0) # Naranja
            elif material == "ORGANICO": led(2, 4095, 1000, 0)
            else: led(2, 4095, 4095, 4095) # Blanco

            if es_peligroso:
                estado_actual = "⚠ OBJETO PELIGROSO: RODEANDO"
                led(3, 4095, 0, 0) # LED3 Rojo
                if not beep_dado:
                    beep(3)
                    beep_dado = True
                maniobra_tipo = "rodear"
                maniobra_inicio_t = time.time()

            elif emergencia or (0 < dist_frontal < 20):
                estado_actual = f"LLEGÓ: {nombre}"
                mover(0, 0)
                led(3, 0, 4095, 0) # LED3 Verde
                if not beep_dado:
                    beep(2)
                    beep_dado = True

            elif abs(error_x) < 40:
                estado_actual = f"AVANZANDO → {nombre}"
                mover(1800, 1800)
                led(3, 0, 4095, 0)
                beep_dado = False

            elif error_x > 0:
                estado_actual = f"GIRANDO DER → {nombre}"
                mover(1600, -1600)
            else:
                estado_actual = f"GIRANDO IZQ → {nombre}"
                mover(-1600, 1600)

        else:
            estado_actual = Estado.BUSCANDO
            beep_dado = False
            led(1, 0, 0, 4095) # LED1 Azul (Buscando)
            led(2, 0, 0, 0)    # LED2 Apagado
            led(3, 0, 4095, 0) # LED3 Verde

            if emergencia or (0 < dist_frontal < 25):
                estado_actual = Estado.ESQUIVANDO
                maniobra_tipo = "esquivar"
                maniobra_inicio_t = time.time()
            else:
                buscar_con_radar()
                mover(600, -600)

        # ================================================
        # HUD PROFESIONAL
        # ================================================
        curr_time = time.time()
        fps = 1.0 / max((curr_time - prev_time), 0.001)
        prev_time = curr_time

        cv2.rectangle(frame, (0,0), (w,38), (15,15,15), -1)
        color_fps = (0,255,0) if fps > 10 else (0,165,255)
        cv2.putText(frame, f"FPS: {int(fps)}", (8,25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_fps, 2)
        cv2.putText(frame, f"RTX 3050 | CUDA: {str(device).upper()}", (105,25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,255,255), 1)

        cv2.rectangle(frame, (0, h-50), (w, h), (15, 15, 15), -1)
        cv2.putText(frame, estado_actual, (8, h-30), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 0), 1)
        cv2.putText(frame, f"DIST: {dist_frontal}cm | PAN: {servo_pan_pos}° TILT: {servo_tilt_pos}°", (8, h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 255, 0), 1)

        cv2.line(frame, (centro_x-15, h//2), (centro_x+15, h//2), (255,255,255), 1)
        cv2.line(frame, (centro_x, h//2-15), (centro_x, h//2+15), (255,255,255), 1)

        cv2.imshow("ARVE ELITE v7.0", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            running = False
            mover(0, 0)
            break

if __name__ == "__main__":
    print("=" * 50)
    print("  ARVE ELITE v7.0 - SISTEMA AUTÓNOMO ACTIVO")
    print("=" * 50)
    print(f"  IA Device  : {device.upper()}")
    print(f"  ESP32 IP   : {ESP32_IP}")
    print(f"  Presiona Q : salir")
    print("=" * 50)

    threading.Thread(target=video_thread,          daemon=True).start()
    threading.Thread(target=telemetry_thread,      daemon=True).start()
    threading.Thread(target=command_sender_thread, daemon=True).start()
    try:
        brain_loop()
    except KeyboardInterrupt:
        pass
    finally:
        running = False
        mover(0, 0)
        led(1,0,0,0); led(2,0,0,0); led(3,0,0,0)
        cv2.destroyAllWindows()
        print("[!] Sistema ARVE apagado.")
