"""
==============================================
CLIENTE ARVE ELITE v6.0 - CONTROL BLUETOOTH
==============================================
Controlador profesional para ESP32-CAM con:
- Comunicación Bluetooth estable
- Detección de objetos con profundidad
- Interfaz en tiempo real
- Grabación de datos
"""

import bluetooth
import json
import time
import threading
from collections import deque
from datetime import datetime
import numpy as np
from ultralytics import YOLO

class ClienteARVEElite:
    def __init__(self, device_name="ARVE-ELITE-v6.0"):
        """Inicializa cliente Bluetooth"""
        self.device_name = device_name
        self.socket = None
        self.conectado = False
        self.buffer_rx = deque(maxlen=100)
        self.modelo_yolo = YOLO('runs/detect/train/weights/best.pt')
        self.telemetria = {}
        
        # Parámetros de calibración
        self.focal_length = 615
        self.tamaños_objetos = {
            'Food Can': 6.5, 'Drink can': 6.5, 'Battery': 2.5,
            'Bottle': 7.0, 'Other plastic bottle': 7.0, 'Clear plastic bottle': 7.0,
            'Glass bottle': 7.5, 'Aluminium foil': 3.0, 'Metal bottle cap': 1.2,
            'Plastic bottle cap': 1.2, 'Aerosol': 8.0, 'Food waste': 10.0,
        }
    
    def buscar_dispositivo(self):
        """Busca dispositivos Bluetooth disponibles"""
        print("🔍 Buscando dispositivos Bluetooth...")
        devices = bluetooth.discover_devices(duration=8, lookup_names=True)
        
        if not devices:
            print("❌ No se encontraron dispositivos Bluetooth")
            return None
        
        print(f"\n📱 {len(devices)} dispositivos encontrados:\n")
        for i, (addr, name) in enumerate(devices, 1):
            print(f"   {i}. {name} ({addr})")
            if self.device_name in name:
                print(f"      ✓ ARVE ELITE encontrado!")
        
        return devices
    
    def conectar(self, direccion=None):
        """Conecta al dispositivo Bluetooth"""
        if not direccion:
            devices = self.buscar_dispositivo()
            if not devices:
                return False
            
            # Buscar ARVE-ELITE
            for addr, name in devices:
                if self.device_name in name:
                    direccion = addr
                    break
            
            if not direccion:
                print(f"❌ No se encontró {self.device_name}")
                return False
        
        print(f"\n🔗 Conectando a {direccion}...")
        try:
            self.socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self.socket.connect((direccion, 1))
            self.conectado = True
            print("✅ Conectado a ARVE ELITE")
            
            # Recibir mensajes de bienvenida
            time.sleep(1)
            self._recibir_loop_bg()
            
            return True
        
        except Exception as e:
            print(f"❌ Error al conectar: {e}")
            self.conectado = False
            return False
    
    def _recibir_loop_bg(self):
        """Ejecuta recepción en segundo plano"""
        def loop():
            while self.conectado:
                try:
                    data = self.socket.recv(256)
                    if data:
                        mensaje = data.decode('utf-8', errors='ignore').strip()
                        self.buffer_rx.append(mensaje)
                        print(f"[RX] {mensaje}")
                except Exception as e:
                    print(f"[RX ERROR] {e}")
                time.sleep(0.05)
        
        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
    
    def enviar_comando(self, comando):
        """Envía comando a ARVE ELITE"""
        if not self.conectado:
            print("❌ No conectado a ARVE ELITE")
            return False
        
        try:
            self.socket.send(comando + "\n")
            print(f"[TX] {comando}")
            return True
        except Exception as e:
            print(f"❌ Error al enviar: {e}")
            self.conectado = False
            return False
    
    # ===== COMANDOS =====
    def mover(self, motor, velocidad):
        """Mueve un motor (1-2) con velocidad (-4095 a 4095)"""
        velocidad = max(-4095, min(4095, velocidad))
        return self.enviar_comando(f"MOVE {motor} {velocidad}")
    
    def servo(self, angulo):
        """Mueve servo a ángulo (0-180)"""
        angulo = max(0, min(180, angulo))
        return self.enviar_comando(f"SERVO {angulo}")
    
    def led(self, r, g, b):
        """Controla LED RGB (0-1)"""
        return self.enviar_comando(f"LED {int(r)} {int(g)} {int(b)}")
    
    def beep(self, veces):
        """Suena buzzer n veces"""
        return self.enviar_comando(f"BEEP {veces}")
    
    def status(self):
        """Obtiene estado del sistema"""
        self.enviar_comando("STATUS")
        time.sleep(0.2)
        return self.buffer_rx[-1] if self.buffer_rx else None
    
    def modo(self, nuevo_modo):
        """Cambia modo (MANUAL, AUTO)"""
        return self.enviar_comando(f"MODE {nuevo_modo}")
    
    def ayuda(self):
        """Muestra comandos disponibles"""
        return self.enviar_comando("HELP")
    
    # ===== DETECCIÓN =====
    def detectar_objetos(self, imagen_path):
        """Detecta objetos con distancia real"""
        print(f"\n🔍 Detectando objetos en {imagen_path}...")
        
        results = self.modelo_yolo.predict(imagen_path, conf=0.5, verbose=False)
        detecciones = []
        
        for result in results:
            for box, cls, conf in zip(result.boxes.xyxy, result.boxes.cls, result.boxes.conf):
                x1, y1, x2, y2 = box.cpu().numpy()
                clase_id = int(cls)
                clase_nombre = result.names[clase_id]
                confianza = float(conf)
                
                ancho_px = x2 - x1
                ancho_real = self.tamaños_objetos.get(clase_nombre, 7.0)
                distancia_cm = (ancho_real * self.focal_length) / ancho_px if ancho_px > 0 else 0
                
                detecciones.append({
                    'clase': clase_nombre,
                    'confianza': round(confianza, 3),
                    'ancho_px': int(ancho_px),
                    'distancia_cm': round(distancia_cm, 1),
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                })
        
        print(f"\n✅ {len(detecciones)} objetos detectados:\n")
        for i, det in enumerate(detecciones, 1):
            print(f"   {i}. {det['clase']}")
            print(f"      • Confianza: {det['confianza']*100:.1f}%")
            print(f"      • Distancia: {det['distancia_cm']:.1f} cm")
            print(f"      • Ancho: {det['ancho_px']} px")
            print()
        
        return detecciones
    
    def escanear_automatico(self):
        """Escanea automáticamente girando la cámara"""
        print("\n🔄 Iniciando escaneo automático...")
        
        # Mueve servo en diferentes ángulos
        angulos = [45, 90, 135]
        
        for angulo in angulos:
            print(f"\n→ Escaneando en ángulo {angulo}°...")
            self.servo(angulo)
            time.sleep(1)  # Espera a que se estabilice
            
            # Aquí capturar imagen del stream y detectar
            print(f"  ✓ Escaneado a {angulo}°")

class InterfazARVEElite:
    def __init__(self):
        self.cliente = None
        self.conectado = False
    
    def menu_principal(self):
        """Muestra menú principal"""
        while True:
            print("\n" + "="*60)
            print("   ARVE ELITE v6.0 - CONTROL REMOTO PROFESIONAL")
            print("="*60)
            print("\n1️⃣  Conectar a ARVE ELITE")
            print("2️⃣  Control Manual")
            print("3️⃣  Detección de Objetos")
            print("4️⃣  Escaneo Automático")
            print("5️⃣  Ver Ayuda")
            print("6️⃣  Desconectar")
            print("0️⃣  Salir")
            
            opcion = input("\n▶ Elige opción: ").strip()
            
            if opcion == "1":
                self.conectar()
            elif opcion == "2" and self.conectado:
                self.control_manual()
            elif opcion == "3" and self.conectado:
                self.menu_deteccion()
            elif opcion == "4" and self.conectado:
                self.cliente.escanear_automatico()
            elif opcion == "5" and self.conectado:
                self.cliente.ayuda()
            elif opcion == "6":
                self.desconectar()
            elif opcion == "0":
                print("\n👋 ¡Hasta luego!")
                break
            else:
                print("❌ Opción no válida")
    
    def conectar(self):
        """Conecta al dispositivo"""
        self.cliente = ClienteARVEElite()
        if self.cliente.conectar():
            self.conectado = True
            time.sleep(2)
    
    def desconectar(self):
        """Desconecta del dispositivo"""
        if self.cliente and self.cliente.socket:
            self.cliente.socket.close()
            self.cliente.conectado = False
            self.conectado = False
            print("✓ Desconectado")
    
    def control_manual(self):
        """Control manual de motores"""
        print("\n" + "="*60)
        print("   CONTROL MANUAL")
        print("="*60)
        print("Escribe comandos (ej: 'move 1 2000', 'servo 90', 'led 1 0 0')")
        print("Escribe 'salir' para volver al menú\n")
        
        while True:
            cmd = input("▶ ").strip()
            if cmd.lower() == 'salir':
                break
            elif cmd:
                self.cliente.enviar_comando(cmd)
            time.sleep(0.2)
    
    def menu_deteccion(self):
        """Menú de detección"""
        print("\n" + "="*60)
        print("   DETECCIÓN DE OBJETOS")
        print("="*60)
        
        ruta = input("📁 Ruta de imagen: ").strip()
        if ruta:
            detecciones = self.cliente.detectar_objetos(ruta)
            
            # Guardar resultados
            resultado = {
                'timestamp': datetime.now().isoformat(),
                'imagen': ruta,
                'detecciones': detecciones,
            }
            
            archivo = f"detecciones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(archivo, 'w') as f:
                json.dump(resultado, f, indent=2)
            
            print(f"\n💾 Guardado en {archivo}")

def main():
    print("\n" + "="*60)
    print("    BIENVENIDO A ARVE ELITE v6.0")
    print("   Sistema Profesional de Visión por Computadora")
    print("="*60)
    
    interfaz = InterfazARVEElite()
    interfaz.menu_principal()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⛔ Interrumpido por usuario")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
