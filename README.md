# 🤖 ARVE ELITE v7.0 — Robot Recolector de Basura Autónomo

Robot autónomo basado en **ESP32-CAM** con visión artificial (**YOLOv8**) capaz de detectar y recolectar basura pequeña (3–8 cm) del suelo con **+90% de precisión**, usando una **RTX 3050** para el procesamiento de IA.

---

## 📦 Componentes de Hardware

| # | Componente | Función |
|---|-----------|---------|
| 1 | ESP32-CAM (OV2640) | Cámara + Microcontrolador WiFi |
| 2 | Chasis 2WD + 2 Motores TT | Desplazamiento |
| 3 | Driver Motor TB6612FNG | Control de motores |
| 4 | PCA9685 (16 canales PWM) | Servos + LEDs vía I2C |
| 5 | 2× Servo SG90 | Pan (horizontal) + Tilt (vertical, 45° al suelo) |
| 6 | 2× HC-SR04 | Ultrasonido frontal y trasero |
| 7 | TCS3200 | Sensor de color (perfil alternativo) |
| 8 | LM2596 | Regulador Step-Down (3S → 5V) |
| 9 | 3× Batería 18650 Li-ion 3.7V | Alimentación (11.1V en serie) |
| 10 | 3× LED RGB | Estado, Material, Alerta |
| 11 | Buzzer 5V Activo | Alertas sonoras |

---

## 📁 Estructura del Proyecto

```
esp32-yolo-camera/
├── camera_server/
│   └── camera_server.ino       ← Firmware ESP32-CAM (subir con Arduino IDE)
├── arve_super_brain.py          ← Cerebro IA principal (ejecutar en PC)
├── entrenar_profesional_v7.py   ← Pipeline de entrenamiento RTX 3050
├── ai_wifi_bridge.py            ← Bridge WiFi PC ↔ ESP32
├── dataset.yaml                 ← Configuración 61 clases (60 TACO + persona)
└── dataset_taco/                ← Dataset local (no se sube a git)
    ├── images/train/
    ├── images/val/
    └── labels/
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
| CH 8-10 | LED RGB 1 — Estado |
| CH 11-13 | LED RGB 2 — Material |
| CH 14-15 | LED RGB 3 — Alerta |

| GPIO ESP32 | Componente |
|-----------|-----------|
| GPIO 2 | Buzzer 5V activo |
| GPIO 12 | I2C SCL → PCA9685 |
| GPIO 13 | I2C SDA → PCA9685 |
| GPIO 14 | HC-SR04 Frontal TRIG |
| GPIO 15 | HC-SR04 Frontal ECHO |

---

## 🚀 Uso

### 1. Subir Firmware al ESP32
Abrir `camera_server/camera_server.ino` en **Arduino IDE** y subir a la ESP32-CAM AI Thinker.

### 2. Entrenar la IA (RTX 3050)
```bash
python entrenar_profesional_v7.py
```
- Detecta automáticamente la GPU CUDA
- Usa **YOLOv8 Medium** con batch 16
- Target: **mAP50 ≥ 0.90**
- Al terminar copia el mejor modelo como `arve_best.pt`

### 3. Ejecutar el Robot Autónomo
```bash
python arve_super_brain.py
```
- Carga **2 modelos simultáneos**: TACO (basura) + COCO (personas)
- Escaneo 360° con patrón de serpentina (Pan 30°–150° + Tilt 60°–120°)
- Tilt por defecto a **135° (45° hacia el suelo)** para detectar basura de 3–8 cm
- LEDs dinámicos: Azul=buscando, Verde=avanzando, Rojo=peligro

### 4. Bridge WiFi (opcional)
```bash
python ai_wifi_bridge.py --esp32-ip 192.168.137.100
```

---

## 🎯 Clases Detectadas (TACO Dataset)
60 clases de basura: botellas plásticas, latas, cartón, papel, vidrio, colillas, bolsas, etc.  
+ 1 clase especial: **persona** (detención de seguridad automática).

---

## 📡 API HTTP del ESP32

| Endpoint | Parámetros | Descripción |
|---------|-----------|-------------|
| `/move` | `v1`, `v2` (-4095 a 4095) | Control de motores |
| `/servo` | `ang` (0–180) | Servo Pan |
| `/servo2` | `ang` (0–180) | Servo Tilt |
| `/led` | `n` (1-3), `r`,`g`,`b` (0–4095) | LED RGB individual |
| `/leds` | `l1r,l1g,l1b,l2r...` | Todos los LEDs |
| `/beep` | `n` (veces) | Buzzer |
| `/scan` | — | Iniciar escaneo 360° |
| `/mode` | `m=auto\|manual` | Cambiar modo |
| `/status` | — | Estado JSON del robot |
| `/ai` | `x,dist,conf,cls` | Inyectar datos de IA |

---

## 📊 Baterías
3× 18650 Li-ion 3.7V **en serie** = **11.1V**  
→ LM2596 regula a **5V** para alimentar ESP32 y PCA9685.

---

*ARVE ELITE v7.0 — Proyecto académico de robótica autónoma*
