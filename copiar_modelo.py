"""
Copia el modelo TACO entrenado al archivo 'arve_best.pt'
Ejecutar DESPUES de que termine lanzar_entrenamiento.py
"""
import os
import shutil
from pathlib import Path

MODELO_FUENTE = Path("runs/detect/runs/arve_trash/taco_v1/weights/best.pt")
MODELO_DESTINO = Path("arve_best.pt")

if MODELO_FUENTE.exists():
    shutil.copy2(MODELO_FUENTE, MODELO_DESTINO)
    size_mb = MODELO_DESTINO.stat().st_size / 1024 / 1024
    print(f"[OK] Modelo copiado: {MODELO_DESTINO} ({size_mb:.1f} MB)")
    print(f"[OK] Ahora ejecuta: python arve_super_brain.py")
    print(f"[OK] El robot usara las 60 clases de basura real TACO!")
else:
    print(f"[ERROR] No se encontro el modelo en: {MODELO_FUENTE}")
    print(f"[INFO] Verifica que haya terminado el entrenamiento.")
    # Buscar en otras ubicaciones posibles
    for p in Path(".").rglob("best.pt"):
        print(f"[ENCONTRADO] {p}")
