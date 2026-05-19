# 🤖 ARVE ELITE v6.0 - SISTEMA PROFESIONAL DE VISIÓN AVANZADA

## 📋 Descripción General

**ARVE ELITE** es un robot de detección y clasificación de basura con:
- **Visión Avanzada**: YOLOv8 entrenado con 60 clases de objetos
- **Detección de Profundidad**: Triangulación para medir distancia real
- **Comunicación Bluetooth**: Conexión estable sin interferencias WiFi
- **Deep Learning**: Redes neuronales profesionales
- **Data Augmentation**: 5 variaciones por imagen de entrenamiento

---

## 🚀 Inicio Rápido

### 1. Instalación de Dependencias

```bash
pip install -r requirements.txt
```

### 2. Cargar Código en ESP32

```bash
# En Arduino IDE:
1. Abre: esp32-yolo-camera/camera_server/camera_server_bluetooth.ino
2. Selecciona placa: "AI Thinker ESP32-CAM"
3. Carga el código
```

### 3. Entrenar Modelo (IMPORTANTE)

Este paso mejora la precisión exponencialmente:

```bash
python pipeline_entrenamiento_completo.py
```

**¿Qué hace?**
- ✓ Aumenta dataset con 5 variaciones por imagen (rotaciones, iluminación, ángulos)
- ✓ Entrena YOLOv8 Medium durante 300 épocas
- ✓ Valida con métricas detalladas (mAP, Precisión, Recall)
- ✓ Exporta modelo optimizado para ESP32

**Tiempo estimado**: 2-4 horas (con GPU: 30-60 minutos)

---

## 💻 Scripts Disponibles

### `entrenamiento_profesional.py` - Entrenamiento Avanzado
Características:
- YOLOv8 Medium (mejor precisión que Nano)
- Data Augmentation profesional (45+ transformaciones)
- Red neuronal para detección de profundidad
- Validación automática

```bash
python entrenamiento_profesional.py
```

### `pipeline_entrenamiento_completo.py` - Pipeline Completo
Automático de principio a fin:
1. Augmenta dataset
2. Entrena modelo
3. Valida resultados
4. Exporta optimizado

```bash
python pipeline_entrenamiento_completo.py
```

### `cliente_bluetooth.py` - Control Remoto
Interfaz para controlar ARVE ELITE por Bluetooth:

```bash
python cliente_bluetooth.py
```

**Opciones disponibles:**
- ✓ Conectar/Desconectar
- ✓ Control manual de motores
- ✓ Detección de objetos con profundidad
- ✓ Escaneo automático
- ✓ Ver telemetría en tiempo real

---

## 📱 Uso de Bluetooth

### Conectar Dispositivo

```python
from cliente_bluetooth import ClienteARVEElite

cliente = ClienteARVEElite()
cliente.conectar()  # Busca automáticamente ARVE-ELITE-v6.0
```

### Comandos Disponibles

```
MOVE <motor> <velocidad>  - Motor (1-2), velocidad (-4095 a 4095)
SERVO <angulo>            - Mueve servo (0-180°)
LED <r> <g> <b>           - LED RGB (0=off, 1=on)
BEEP <n>                  - Buzzer (n veces)
STATUS                    - Estado del sistema
MODE <MANUAL|AUTO>        - Cambiar modo
HELP                      - Ver comandos
```

### Ejemplo: Detección de Objetos

```python
# Detecta objetos en una imagen
detecciones = cliente.detectar_objetos("imagen.jpg")

# Resultado incluye:
# - Clase del objeto
# - Confianza (0-100%)
# - Distancia en cm (calculada por triangulación)
# - Bounding box en píxeles
```

---

## 🔧 Configuración de Pines ESP32-CAM

### Cámara (No modificar)
```
GPIO0: XCLK
GPIO5: Y2
GPIO18-27: Datos de cámara
GPIO32: PWDN
GPIO34-36: Más datos
GPIO39: Y7
```

### Periféricos Disponibles
```
GPIO12-13: I2C (PCA9685)
GPIO14-15: Ultrasónico
GPIO2, 4, 16, 17, 33: Sensor de Color TCS3200
```

### PCA9685 (Canales)
```
0-5:   Motores TB6612FNG
6:     Servo SG90
7-9:   LED RGB
10:    Buzzer 5V
```

---

## 📊 Detección de Profundidad

### Algoritmo de Triangulación

```
Distancia = (Ancho_Real × Focal_Length) / Ancho_Píxeles

Donde:
- Ancho_Real = tamaño conocido del objeto (ej: 6.5cm para lata)
- Focal_Length = parámetro calibrado de la cámara (615)
- Ancho_Píxeles = ancho del objeto detectado en la imagen
```

### Calibración

Si la distancia no es exacta:

```python
# En cliente_bluetooth.py, línea ~45
self.focal_length = 615  # Aumenta para distancias más cortas

# O actualiza tamaños de objetos:
self.tamaños_objetos['Food Can'] = 6.5  # En cm
```

---

## 🎓 Cómo Mejorar el Modelo

### Opción 1: Más Épocas
```python
entrenador.entrenar_yolov8(epochs=500)  # Más entrenamiento
```

### Opción 2: Imágenes de Diferentes Ángulos
Coloca en `dataset_taco/images/train/`:
- ✓ Frente
- ✓ Arriba/Abajo (±45°)
- ✓ Lateral izquierdo/derecho
- ✓ Diferentes iluminaciones
- ✓ Con obstáculos de fondo

El pipeline generará 5 variaciones de cada una.

### Opción 3: Ensemble de Modelos
```python
entrenador.entrenar_ensemble(epochs=200)
# Entrena Nano, Medium y Large juntos
# Aumenta precisión pero usa más RAM
```

### Opción 4: Transfer Learning Avanzado
```python
from ultralytics import YOLO
model = YOLO('yolov8x.pt')  # Extra Large (máxima precisión)
results = model.train(data='dataset.yaml', epochs=300)
```

---

## 🐛 Solución de Problemas

### "No se conecta por Bluetooth"
```bash
# Verificar que está disponible:
python -c "import bluetooth; bluetooth.discover_devices()"

# Asegurar que el nombre en código coincide:
# device_name="ARVE-ELITE-v6.0"
```

### "Modelo tarda mucho en entrenar"
```bash
# Usar modelo más pequeño:
model = YOLO('yolov8n.pt')  # Nano (rápido, menos preciso)
model = YOLO('yolov8s.pt')  # Small (balance)
model = YOLO('yolov8m.pt')  # Medium (recomendado)
model = YOLO('yolov8l.pt')  # Large (más preciso, más lento)
```

### "Baja precisión en detección"
1. Aumentar épocas de entrenamiento
2. Agregar más imágenes de entrenamiento
3. Capturar imágenes en diferentes condiciones de luz
4. Usar modelo más grande (L o X)

### "Distancia incorrecta"
1. Calibrar `focal_length`
2. Actualizar tamaños de objetos en `tamaños_objetos`
3. Entrenar con múltiples ángulos

---

## 📈 Métricas de Éxito

Después del entrenamiento, deberías ver:

| Métrica | Target | Descripción |
|---------|--------|-------------|
| mAP@50-95 | >0.70 | Precisión general |
| mAP@50 | >0.85 | Detección precisa |
| Precisión | >0.80 | Pocos falsos positivos |
| Recall | >0.75 | Pocas detecciones perdidas |

---

## 🎯 Casos de Uso

### Clasificación Automática de Basura
```python
# Robot se mueve, detecta objetos y clasifica
cliente.modo("AUTO")
cliente.servo(90)  # Apunta al frente
detecciones = cliente.detectar_objetos(foto_live)
```

### Control Manual
```python
cliente.modo("MANUAL")
cliente.mover(1, 2000)   # Motor 1 a velocidad 2000
cliente.servo(45)         # Gira cámara 45°
```

### Telemetría
```python
status = cliente.status()
# {"status":"ok","dist":25,"servo":90,"emerg":false,"color":1}
```

---

## 📦 Estructura del Proyecto

```
esp32-yolo-camera/
├── camera_server/
│   ├── camera_server.ino (WiFi original)
│   ├── camera_server_bluetooth.ino (RECOMENDADO - Bluetooth)
│   └── camera_pins.h
├── dataset_taco/
│   ├── images/train/
│   ├── labels/train/
│   └── dataset.yaml
├── entrenamiento_profesional.py
├── pipeline_entrenamiento_completo.py
├── cliente_bluetooth.py
├── requirements.txt
└── README.md (este archivo)
```

---

## 🔐 Seguridad

- **Bluetooth PIN**: `1234` (cambiable en código)
- **Velocidad máxima motor**: 4095
- **Ángulo máximo servo**: 180°
- **Emergencia automática**: <20cm de distancia

---

## 📞 Soporte

Para problemas:
1. Verifica logs en Serial Monitor (115200 baud)
2. Revisa comandos en `cliente_bluetooth.py`
3. Calibra distancias con objetos conocidos

---

## 🎉 ¡Éxito!

Tu ARVE ELITE está listo para:
✓ Detectar 60 tipos de basura
✓ Medir distancias reales
✓ Operar por Bluetooth estable
✓ Ser totalmente autónomo

**¡A detectar basura como un profesional!** 🚀
