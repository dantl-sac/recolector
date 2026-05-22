"""
==============================================
SCRIPT DE CONFIGURACIÓN INICIAL
Prepara el proyecto ARVE ELITE v6.0
==============================================
"""

import os
import sys
from pathlib import Path
import subprocess
import json

class ConfiguradorProyecto:
    def __init__(self):
        self.proyecto_dir = Path(__file__).parent
        self.pasos_completados = []
    
    def crear_estructura_carpetas(self):
        """Crea estructura de carpetas necesarias"""
        print("\n📁 Creando estructura de carpetas...")
        
        carpetas = [
            "dataset_taco/images/train",
            "dataset_taco/images/val",
            "dataset_taco/labels/train",
            "dataset_taco/labels/val",
            "dataset_taco_augmented/images/train",
            "dataset_taco_augmented/images/val",
            "dataset_taco_augmented/labels/train",
            "dataset_taco_augmented/labels/val",
            "models",
            "resultados_entrenamiento",
            "calibracion",
            "logs",
        ]
        
        for carpeta in carpetas:
            ruta = self.proyecto_dir / carpeta
            ruta.mkdir(parents=True, exist_ok=True)
            print(f"   ✓ {carpeta}")
    
    def instalar_dependencias(self):
        """Instala dependencias de Python"""
        print("\n📦 Instalando dependencias...")
        
        try:
            # Instalar requirements
            requirements = self.proyecto_dir / "requirements.txt"
            if requirements.exists():
                print("   → Instalando paquetes (esto puede tardar...)")
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(requirements)],
                    check=True
                )
                print("   ✓ Dependencias instaladas")
            else:
                print("   ⚠ requirements.txt no encontrado")
        
        except Exception as e:
            print(f"   ❌ Error: {e}")
            print("   → Instala manualmente: pip install -r requirements.txt")
    
    def verificar_dataset(self):
        """Verifica si hay dataset disponible"""
        print("\n📊 Verificando dataset...")
        
        train_dir = self.proyecto_dir / "dataset_taco" / "images" / "train"
        archivos_train = list(train_dir.glob("*.jpg")) + list(train_dir.glob("*.png"))
        
        if archivos_train:
            print(f"   ✓ Se encontraron {len(archivos_train)} imágenes de entrenamiento")
            return True
        else:
            print("   ⚠ Sin imágenes de entrenamiento")
            print("   → Copia imágenes a: dataset_taco/images/train/")
            print("   → Copia etiquetas a: dataset_taco/labels/train/")
            return False
    
    def descargar_modelos_base(self):
        """Descarga modelos YOLO base"""
        print("\n🤖 Descargando modelos YOLO...")
        
        try:
            from ultralytics import YOLO
            
            modelos = ['yolov8n.pt', 'yolov8m.pt']
            
            for modelo in modelos:
                print(f"   → Descargando {modelo}...")
                YOLO(modelo)
                print(f"   ✓ {modelo} listo")
        
        except Exception as e:
            print(f"   ❌ Error: {e}")
            print("   Los modelos se descargarán automáticamente al entrenar")
    
    def crear_config_inicial(self):
        """Crea archivo de configuración inicial"""
        print("\n⚙️  Creando configuración...")
        
        config = {
            "proyecto": "ARVE ELITE v6.0",
            "version": "6.0",
            "descripcion": "Sistema profesional de visión para detección de basura",
            "pines": {
                "i2c_sda": 13,
                "i2c_scl": 12,
                "trig_f": 14,
                "echo_f": 15,
                "trig_r": 16,
                "echo_r": 4,
                "tcs3200_opcional": False,
                "nota": "ESP32-CAM no permite 2 HC-SR04 + TCS3200 a la vez sin expansor de pines",
            },
            "camara": {
                "modelo": "AI Thinker ESP32-CAM",
                "resolucion": "320x240",
                "fps": 30,
            },
            "yolo": {
                "version": "yolov8m",
                "clases": 60,
                "epocas_recomendadas": 300,
                "tamaño_imagen": 416,
            },
            "wifi": {
                "ssid": "ARVE-07",
                "password": "12345678",
                "ip": "192.168.137.100",
            },
            "calibracion": {
                "focal_length": 615,
                "escala_distancia": "cm",
            }
        }
        
        config_file = self.proyecto_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"   ✓ Configuración guardada en config.json")
    
    def crear_guia_inicio_rapido(self):
        """Crea guía de inicio rápido"""
        print("\n📝 Creando guía de inicio...")
        
        guia = """
# 🚀 INICIO RÁPIDO - ARVE ELITE v6.0

## 5 Pasos para Empezar

### 1️⃣ Instalar Dependencias (1 minuto)
```bash
pip install -r requirements.txt
```

### 2️⃣ Preparar Datos (5 minutos)
```
1. Coloca imágenes en: dataset_taco/images/train/
2. Coloca etiquetas en: dataset_taco/labels/train/
   (Formato YOLO: class_id x_center y_center width height)
```

### 3️⃣ Entrenar Modelo (30 min - 4 horas según GPU)
```bash
python pipeline_entrenamiento_completo.py
```

### 4️⃣ Subir Codigo a ESP32
```
1. Abre Arduino IDE
2. Archivo -> Ejemplos -> ESP32 -> Camera -> Camera Server
3. Cambia a: camera_server/camera_server.ino
4. Sube el codigo
```

### 5️⃣ Controlar por WiFi
```
http://IP_DEL_ESP32/status
http://IP_DEL_ESP32/move?v1=2000&v2=2000
http://IP_DEL_ESP32/servo?ang=90
http://IP_DEL_ESP32/led?r=0&g=1&b=0
http://IP_DEL_ESP32/beep?n=2
```

## Scripts Principales

| Script | Propósito |
|--------|-----------|
| `pipeline_entrenamiento_completo.py` | Entrenamiento de principio a fin |
| `herramientas_calibracion.py` | Calibracion de camara |
| `entrenamiento_profesional.py` | Entrenamiento avanzado |

## Endpoints HTTP disponibles

```
/move?v1=2000&v2=2000
/servo?ang=90
/led?r=0&g=1&b=0
/beep?n=2
/status
```

## Solucion rapida de problemas

**No conecta WiFi:**
→ Revisa SSID y password en el firmware
→ Verifica que el router acepte 2.4GHz

**Baja precisión:**
→ Aumentar épocas de entrenamiento
→ Agregar más imágenes de entrenamiento
→ Usar modelo más grande (yolov8l)

**Distancia incorrecta:**
→ Calibrar con herramientas_calibracion.py
→ Usar objetos de tamaño conocido

## Documentación Completa

Ver: README_PROFESIONAL.md

---
¡Éxito! 🎉
"""
        
        guia_file = self.proyecto_dir / "INICIO_RAPIDO.md"
        with open(guia_file, 'w') as f:
            f.write(guia)
        
        print(f"   ✓ Guía guardada en INICIO_RAPIDO.md")
    
    def ejecutar_configuracion(self):
        """Ejecuta toda la configuración"""
        print("\n" + "="*60)
        print("   CONFIGURACIÓN INICIAL - ARVE ELITE v6.0")
        print("="*60)
        
        self.crear_estructura_carpetas()
        self.descargar_modelos_base()
        self.crear_config_inicial()
        self.crear_guia_inicio_rapido()
        
        print("\n" + "="*60)
        print("   ✅ CONFIGURACIÓN COMPLETADA")
        print("="*60)
        print("""
✓ Estructura de carpetas creada
✓ Modelos YOLO descargados
✓ Configuración guardada
✓ Guía de inicio creada

📖 Próximos pasos:
1. Lee: INICIO_RAPIDO.md
2. Coloca imágenes en dataset_taco/images/train/
3. Ejecuta: python pipeline_entrenamiento_completo.py
4. Carga código en ESP32
5. Controla por WiFi usando los endpoints HTTP

¡Éxito! 🚀
""")

def verificar_entorno():
    """Verifica que todo esté instalado correctamente"""
    print("\n🔍 Verificando entorno...")
    
    modulos = {
        'torch': 'PyTorch',
        'cv2': 'OpenCV',
        'numpy': 'NumPy',
        'ultralytics': 'YOLOv8',
        'albumentations': 'Albumentations',
    }
    
    faltan = []
    
    for modulo, nombre in modulos.items():
        try:
            __import__(modulo)
            print(f"   ✓ {nombre}")
        except ImportError:
            print(f"   ❌ {nombre}")
            faltan.append(modulo)
    
    if faltan:
        print(f"\n⚠️  Faltan instalar: {', '.join(faltan)}")
        print(f"Ejecuta: pip install -r requirements.txt")
        return False
    else:
        print(f"\n✅ Entorno listo")
        return True

def main():
    print("""
    ╔═════════════════════════════════════════╗
    ║  ARVE ELITE v6.0 - CONFIGURACIÓN INICIAL║
    ║   Sistema Profesional de Visión         ║
    ╚═════════════════════════════════════════╝
    """)
    
    # Verificar entorno
    if not verificar_entorno():
        respuesta = input("\n¿Instalar dependencias ahora? (s/n): ").strip().lower()
        if respuesta == 's':
            configurador = ConfiguradorProyecto()
            configurador.instalar_dependencias()
        else:
            print("⚠️  Por favor instala manualmente: pip install -r requirements.txt")
            return
    
    # Ejecutar configuración
    configurador = ConfiguradorProyecto()
    configurador.ejecutar_configuracion()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⛔ Cancelado")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
