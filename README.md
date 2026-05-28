# 🤖 ARVE ELITE v7.0 — Robot Recolector de Basura Autónomo

Robot autónomo basado en **ESP32-CAM** con visión artificial (**YOLOv8**) capaz de detectar y recolectar basura pequeña (3–8 cm) del suelo con **+90% de precisión**, usando una **RTX 3050** para el procesamiento de IA.

---

## 📦 Componentes de Hardware

| # | Componente | Función |
|---|-----------|---------|
| 1 | ESP32-CAM (OV2640) | Cámara + Microcontrolador WiFi |
| 2 | Chasis 2WD + 2 Motores DC | Desplazamiento |
| 3 | Driver Motor TB6612FNG | Control de los 2 motores DC |
| 4 | PCA9685 (16 canales PWM) | Servos + motores vía I2C |
| 5 | 2× Micro Servo TS90A (9g) | Pan (horizontal) + Tilt (vertical, 45° al suelo) |
| 6 | HC-SR04 | Ultrasonido frontal (anti-choque) |
| 7 | LM2596 | Regulador Step-Down a 5V |
| 8 | Batería Li-ion | Alimentación (entra al LM2596) |

---

## 📁 Estructura del Proyecto

```
esp32-yolo-camera/
├── camera_server/
│   └── camera_server.ino       ← Firmware ESP32-CAM (subir con Arduino IDE)
├── arve_super_brain_v8.py       ← Cerebro IA autónomo (ejecutar en PC)
├── arve_viewer.py               ← Visor + control manual/auto por teclado
├── entrenar_v8_pro.py           ← Pipeline de entrenamiento RTX 3050 (12 clases)
├── check_gpu.py                 ← Verifica CUDA / RTX
├── test_conexion.py             ← Diagnóstico de red al ESP32
├── dataset_pro_v8/              ← Dataset local 12 clases (no se sube a git)
│   └── dataset.yaml
└── arve_best.pt                 ← Modelo entrenado (no se sube a git)
```

---

## ⚡ Mapa de Pines ESP32-CAM → PCA9685

| Canal PCA | Componente |
|-----------|-----------|
| CH 0 | Motor 1 — PWM |
| CH 1 | Motor 1 — IN1 |
| CH 2 | Motor 1 — IN2 |
| CH 3 | Motor 2 — PWM |
| CH 4 | Motor 2 — IN1 |
| CH 5 | Motor 2 — IN2 |
| CH 6 | Servo Pan (horizontal) |
| CH 7 | Servo Tilt (vertical, default 135° = 45° al suelo) |

| GPIO ESP32 | Componente |
|-----------|-----------|
| GPIO 12 | HC-SR04 Frontal TRIG |
| GPIO 13 | HC-SR04 Frontal ECHO |
| GPIO 14 | I2C SDA → PCA9685 |
| GPIO 15 | I2C SCL → PCA9685 |

---

## 🚀 Uso

### 1. Subir Firmware al ESP32
Abrir `camera_server/camera_server.ino` en **Arduino IDE** y subir a la ESP32-CAM AI Thinker.

### 2. Entrenar la IA (RTX 3050)
```bash
python entrenar_v8_pro.py
```
- Detecta automáticamente la GPU CUDA
- Usa **YOLOv8 Medium** con 12 clases de basura pequeña
- Al terminar copia el mejor modelo como `arve_best.pt`

### 3. Ejecutar el Robot Autónomo
```bash
python arve_super_brain_v8.py
```
- Carga **2 modelos simultáneos**: TACO (basura) + COCO (personas)
- Escaneo 360° con patrón de serpentina (Pan 30°–150° + Tilt 60°–120°)
- Tilt por defecto a **135° (45° hacia el suelo)** para detectar basura de 3–8 cm
- El estado se muestra en la ventana de la PC (buscando / avanzando / persona)

> **Nota:** la IP del ESP32 está fija en `arve_super_brain_v8.py` (variable `ESP32_IP`). Cámbiala por la IP real de tu ESP32.

### 4. Visor + control manual (opcional)
```bash
python arve_viewer.py --esp32-ip 192.168.137.100
```
- Control por teclado: `W/A/S/D` mover, flechas servos, `M` auto/manual, `Y` YOLO on/off, `+/-` velocidad

---

## 🎯 Clases Detectadas (12 clases)
Bolsa plástica, botella, lata, papel, colilla, pitillo/sorbete, vaso plástico, cartón, envoltorio, recipiente de comida, tapa de botella, icopor/espuma.  
+ **persona** (vía modelo COCO, detención de seguridad automática).

---

## 📡 API HTTP del ESP32

| Endpoint | Parámetros | Descripción |
|---------|-----------|-------------|
| `/move` | `v1`, `v2` (-4095 a 4095) | Control de motores |
| `/servo` | `ang` (0–180) | Servo Pan |
| `/servo2` | `ang` (0–180) | Servo Tilt |
| `/mode` | `m=auto\|manual` | Cambiar modo |
| `/speed` | `base`, `turn` (500–4095) | Velocidad base / de giro |
| `/ai` | `x`, `dist`, `conf`, `cls` | Inyectar datos de IA |
| `/status` | — | Estado JSON del robot |
| `/res` | `s=qqvga\|qvga\|hvga\|vga` | Resolución de cámara |
| `/quality` | `q` (5–60) | Calidad JPEG |

---

## 📊 Baterías
3× 18650 Li-ion 3.7V **en serie** = **11.1V**  
→ LM2596 regula a **5V** para alimentar ESP32 y PCA9685.

---

*ARVE ELITE v7.0 — Proyecto académico de robótica autónoma*
