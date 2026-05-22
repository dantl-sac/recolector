"""
==============================================
HERRAMIENTA DE CALIBRACIÓN Y DEMOSTRACIÓN
ARVE ELITE v6.0
==============================================
"""

import cv2
import numpy as np
import json
from pathlib import Path
from datetime import datetime

class CalibradorCamara:
    """Calibra parámetros de la cámara para detección de profundidad"""
    
    def __init__(self):
        self.medidas_calibracion = []
        self.focal_length = 615  # Valor inicial
        self.resultados = {}
    
    def medir_objeto_referencia(self, imagen_path, ancho_real_cm=6.5):
        """
        Mide un objeto conocido en una imagen
        
        Args:
            imagen_path: Ruta de la imagen
            ancho_real_cm: Ancho real del objeto (ej: lata = 6.5cm)
        """
        print(f"\n📐 Calibrando con objeto: {Path(imagen_path).name}")
        print(f"   Ancho real: {ancho_real_cm} cm")
        
        img = cv2.imread(imagen_path)
        if img is None:
            print("❌ No se pudo leer la imagen")
            return None
        
        # Mostrar imagen
        cv2.imshow("Imagen para calibración", img)
        print("\n   → Selecciona el objeto presionando 2 puntos (izquierda-derecha)")
        
        puntos = []
        
        def click_evento(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                puntos.append((x, y))
                cv2.circle(img, (x, y), 3, (0, 255, 0), -1)
                cv2.imshow("Imagen para calibración", img)
                
                if len(puntos) == 2:
                    ancho_px = abs(puntos[1][0] - puntos[0][0])
                    distancia_estimada = (ancho_real_cm * self.focal_length) / ancho_px
                    
                    print(f"\n   ✓ Ancho en píxeles: {ancho_px}")
                    print(f"   ✓ Ancho real: {ancho_real_cm} cm")
                    print(f"   ✓ Focal length usado: {self.focal_length}")
                    
                    # Pedir distancia actual
                    dist_real = float(input("   → ¿Cuál es la distancia real del objeto? (en cm): "))
                    
                    # Calcular focal length correcto
                    focal_correcto = (ancho_real_cm * self.focal_length) / dist_real
                    
                    print(f"\n   📊 Resultados de calibración:")
                    print(f"      • Ancho medido: {ancho_px} px")
                    print(f"      • Distancia real: {dist_real} cm")
                    print(f"      • Focal length actual: {self.focal_length}")
                    print(f"      • Focal length CORRECTO: {focal_correcto:.0f}")
                    
                    self.focal_length = focal_correcto
                    self.medidas_calibracion.append({
                        'imagen': Path(imagen_path).name,
                        'ancho_real': ancho_real_cm,
                        'ancho_px': ancho_px,
                        'distancia_real': dist_real,
                        'focal_length': focal_correcto,
                    })
                    
                    cv2.destroyAllWindows()
        
        cv2.setMouseCallback("Imagen para calibración", click_evento)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
        return self.focal_length
    
    def calibrar_multiples(self, directorio_calibracion='./imagenes_calibracion'):
        """Calibra con múltiples objetos para más precisión"""
        ruta = Path(directorio_calibracion)
        
        if not ruta.exists():
            print(f"⚠ Carpeta {directorio_calibracion} no existe")
            print("  Crear carpetas con imágenes de objetos conocidos")
            return
        
        imagenes = list(ruta.glob("*.jpg")) + list(ruta.glob("*.png"))
        
        if not imagenes:
            print(f"⚠ No hay imágenes en {directorio_calibracion}")
            return
        
        print(f"\n📏 CALIBRACIÓN MULTI-OBJETO")
        print(f"   Encontradas {len(imagenes)} imágenes")
        
        for img_path in imagenes:
            ancho = float(input(f"\n   Ancho real de {img_path.name} (cm): "))
            self.medir_objeto_referencia(str(img_path), ancho)
        
        # Promediar focal lengths
        focal_promedio = np.mean([m['focal_length'] for m in self.medidas_calibracion])
        print(f"\n✅ CALIBRACIÓN COMPLETADA")
        print(f"   Focal Length Promedio: {focal_promedio:.0f}")
        
        self.focal_length = focal_promedio
        return focal_promedio
    
    def guardar_calibracion(self, archivo='calibracion.json'):
        """Guarda parámetros calibrados"""
        config = {
            'focal_length': self.focal_length,
            'medidas': self.medidas_calibracion,
            'fecha': datetime.now().isoformat(),
        }
        
        with open(archivo, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"💾 Calibración guardada en {archivo}")
        print("\n   Usa este focal_length en tu cliente de deteccion o control.")
        print(f"   focal_length = {self.focal_length:.0f}")

class DemostradorArveElite:
    """Demostración completa de funcionalidades"""
    
    def __init__(self):
        self.calibrador = CalibradorCamara()
    
    def demo_deteccion(self, imagen_path=None):
        """Demo de detección con modelo YOLO"""
        print("\n" + "="*60)
        print("   DEMO: DETECCIÓN DE OBJETOS")
        print("="*60)
        
        if not imagen_path:
            imagen_path = input("\n📁 Ruta de imagen: ").strip()
        
        try:
            from ultralytics import YOLO
            
            print(f"\n🔍 Cargando modelo YOLO...")
            modelo = YOLO('runs/detect/train/weights/best.pt')
            
            print(f"🔍 Detectando objetos en {Path(imagen_path).name}...")
            results = modelo.predict(imagen_path, conf=0.5, verbose=False)
            
            print(f"\n✅ DETECCIONES ({len(results[0])} objetos):\n")
            
            for i, result in enumerate(results):
                for j, (box, cls, conf) in enumerate(zip(
                    result.boxes.xyxy, 
                    result.boxes.cls, 
                    result.boxes.conf
                )):
                    clase = result.names[int(cls)]
                    confianza = float(conf)
                    x1, y1, x2, y2 = box.cpu().numpy()
                    ancho = x2 - x1
                    
                    # Estimar distancia
                    tamaños = {
                        'Food Can': 6.5, 'Drink can': 6.5, 'Battery': 2.5,
                        'Bottle': 7.0, 'Other plastic bottle': 7.0,
                    }
                    ancho_real = tamaños.get(clase, 7.0)
                    distancia = (ancho_real * 615) / ancho if ancho > 0 else 0
                    
                    print(f"   {j+1}. {clase}")
                    print(f"      Confianza: {confianza*100:.1f}%")
                    print(f"      Distancia: {distancia:.1f} cm")
                    print(f"      BBox: ({int(x1)}, {int(y1)}) - ({int(x2)}, {int(y2)})\n")
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def demo_entrenamiento(self):
        """Demo rápida de entrenamiento"""
        print("\n" + "="*60)
        print("   DEMO: ENTRENAMIENTO (VERSIÓN RÁPIDA)")
        print("="*60)
        
        print("""
        Para entrenar el modelo (recomendado):
        
        python pipeline_entrenamiento_completo.py
        
        Esto hace:
        ✓ Augmenta dataset (5 variaciones por imagen)
        ✓ Entrena YOLOv8 Medium (300 épocas)
        ✓ Valida automáticamente
        ✓ Exporta modelo optimizado
        
        Tiempo: 2-4 horas con CPU
               30-60 minutos con GPU
        
        Para acelerar en GPU:
        - Instala CUDA: https://developer.nvidia.com/cuda-downloads
        - Instala PyTorch con CUDA: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
        """)

def menu_principal():
    """Menú interactivo"""
    demo = DemostradorArveElite()
    
    while True:
        print("\n" + "="*60)
        print("   ARVE ELITE v6.0 - HERRAMIENTAS PROFESIONALES")
        print("="*60)
        print("\n1️⃣  Calibración de Cámara")
        print("2️⃣  Demo: Detección de Objetos")
        print("3️⃣  Demo: Entrenamiento")
        print("4️⃣  Tutorial Completo")
        print("0️⃣  Salir")
        
        opcion = input("\n▶ Elige opción: ").strip()
        
        if opcion == "1":
            calibrador = CalibradorCamara()
            while True:
                print("\n📐 CALIBRACIÓN")
                print("1. Medir un objeto")
                print("2. Calibrar múltiples")
                print("3. Guardar calibración")
                print("0. Volver")
                
                sub = input("\n▶ ").strip()
                if sub == "1":
                    img = input("Ruta de imagen: ").strip()
                    ancho = float(input("Ancho real (cm): "))
                    calibrador.medir_objeto_referencia(img, ancho)
                elif sub == "2":
                    calibrador.calibrar_multiples()
                elif sub == "3":
                    calibrador.guardar_calibracion()
                elif sub == "0":
                    break
        
        elif opcion == "2":
            demo.demo_deteccion()
        
        elif opcion == "3":
            demo.demo_entrenamiento()
            input("\nPresiona Enter para continuar...")
        
        elif opcion == "4":
            print("\n" + "="*60)
            print("   TUTORIAL COMPLETO")
            print("="*60)
            print("""
            PASO 1: PREPARAR IMÁGENES
            ✓ Coloca imágenes en dataset_taco/images/train/
            ✓ Asegúrate de tener etiquetas en dataset_taco/labels/train/
            ✓ Mínimo 100 imágenes por clase
            
            PASO 2: ENTRENAR MODELO
            $ python pipeline_entrenamiento_completo.py
            
            PASO 3: CARGAR EN ESP32
            ✓ Abre Arduino IDE
            ✓ camera_server/camera_server.ino
            ✓ Selecciona: Board="AI Thinker ESP32-CAM"
            ✓ Puerto y velocidad correcta
            ✓ Sube el código
            
            PASO 4: CALIBRAR CÁMARA
            $ python herramientas_calibracion.py
            ✓ Opción 1: Calibración
            ✓ Medir objetos conocidos
            
            PASO 5: CONTROLAR POR WIFI
            ✓ Abre http://IP_DEL_ESP32/status
            ✓ Usa /move, /servo, /led, /beep
            
            PASO 6: MODO AUTONOMO
            ✓ Cambiar a MODE AUTO
            ✓ Robot detecta automáticamente
            ✓ Clasifica basura
            
            ¡Listo! 🎉
            """)
            input("\nPresiona Enter para continuar...")
        
        elif opcion == "0":
            print("\n👋 ¡Hasta luego!")
            break

if __name__ == "__main__":
    try:
        menu_principal()
    except KeyboardInterrupt:
        print("\n⛔ Cancelado")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
