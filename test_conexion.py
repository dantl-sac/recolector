"""
Test de conexion bruta al ESP32-CAM.
Prueba TCP, HTTP y MJPEG paso a paso.
Sirve para diagnosticar si es McAfee/Firewall.
"""
import socket
import sys
import time

IP = "192.168.137.189"  # CAMBIA SI HACE FALTA

print("=" * 60)
print(f"DIAGNOSTICO DE CONEXION A {IP}")
print("=" * 60)

# Test 1: TCP socket crudo al puerto 80
print("\n[Test 1] TCP socket directo al puerto 80...")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    t0 = time.time()
    s.connect((IP, 80))
    print(f"  OK conectado en {(time.time()-t0)*1000:.0f}ms")
    s.close()
except Exception as e:
    print(f"  FALLO: {e}")

# Test 2: TCP socket crudo al puerto 81
print("\n[Test 2] TCP socket directo al puerto 81...")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    t0 = time.time()
    s.connect((IP, 81))
    print(f"  OK conectado en {(time.time()-t0)*1000:.0f}ms")
    s.close()
except Exception as e:
    print(f"  FALLO: {e}")

# Test 3: HTTP GET manual al puerto 80
print("\n[Test 3] HTTP GET manual al puerto 80 (la pagina web)...")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect((IP, 80))
    req = f"GET / HTTP/1.1\r\nHost: {IP}\r\nConnection: close\r\n\r\n"
    s.sendall(req.encode())
    data = b""
    t0 = time.time()
    while time.time() - t0 < 5:
        chunk = s.recv(4096)
        if not chunk:
            break
        data += chunk
        if len(data) > 500:
            break
    s.close()
    if data:
        print(f"  OK recibi {len(data)} bytes")
        head = data[:200].decode('utf-8', errors='replace')
        print(f"  Primeros bytes: {head[:100]}...")
    else:
        print("  FALLO: no llegaron datos")
except Exception as e:
    print(f"  FALLO: {e}")

# Test 4: HTTP GET manual al puerto 81 (stream)
print("\n[Test 4] HTTP GET manual al puerto 81 (stream MJPEG)...")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    s.connect((IP, 81))
    req = f"GET / HTTP/1.1\r\nHost: {IP}\r\nConnection: close\r\n\r\n"
    s.sendall(req.encode())
    data = b""
    t0 = time.time()
    while time.time() - t0 < 8:
        try:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
            if len(data) > 5000:
                break
        except socket.timeout:
            break
    s.close()
    if data:
        print(f"  OK recibi {len(data)} bytes del stream!")
        head = data[:300].decode('utf-8', errors='replace')
        print(f"  Headers: {head[:200]}")
        # Buscar marcador JPEG
        if b'\xff\xd8' in data:
            print("  OK encontre marcador JPEG -> stream funcionando!")
        else:
            print("  WARN no encontre JPEG en primeros 5KB")
    else:
        print("  FALLO: el ESP32 acepto la conexion pero no envia datos")
        print("  Esto suele ser McAfee/Firewall bloqueando")
except Exception as e:
    print(f"  FALLO: {e}")

print("\n" + "=" * 60)
print("INTERPRETACION:")
print("=" * 60)
print("""
  Si Test 1 y 2 funcionan pero Test 3 y 4 fallan:
    -> McAfee Firewall esta bloqueando el HTTP de Python.

  Si TODO falla:
    -> ESP32 no responde, revisa IP y reset.

  Si TODO funciona:
    -> Tu arve_viewer.py deberia funcionar tambien.
""")
