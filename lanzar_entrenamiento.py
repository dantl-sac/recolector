from ultralytics import YOLO
import torch

# ==========================================
# LANZADOR DE ENTRENAMIENTO ARVE ELITE
# Dataset: TACO - 60 clases de basura real
# ==========================================

# En Windows es OBLIGATORIO este guard para multiprocessing
if __name__ == '__main__':

    print("=" * 50)
    print("  ARVE ELITE - ENTRENAMIENTO IA")
    print("=" * 50)

    # Verificar GPU
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        print(f"[OK] GPU detectada: {gpu_name}")
        device = 0
    else:
        print("[WARN] Sin GPU, usando CPU")
        device = "cpu"

    print("[OK] Dataset: 60 clases de basura real (TACO)")
    print("[OK] Epocas: 50 | Imagenes: 320x320 | Batch: 16")
    print("")
    print("Iniciando entrenamiento... (30-45 min aprox)")
    print("")

    # Cargar modelo base YOLOv8 Nano
    model = YOLO("yolov8n.pt")

    # Entrenar con RTX 3050
    results = model.train(
        data="dataset_taco/dataset.yaml",
        epochs=50,
        imgsz=320,
        batch=16,
        device=device,
        workers=2,       # Reducido a 2 para evitar conflictos en Windows
        patience=10,
        save=True,
        project="runs/arve_trash",
        name="taco_v1",
        exist_ok=True,
        amp=True,        # Precision mixta RTX 3050 = mas rapido
        verbose=True,
        plots=True,
    )

    print("")
    print("=" * 50)
    print("  ENTRENAMIENTO COMPLETADO!")
    print("=" * 50)
    print("Modelo guardado en: runs/arve_trash/taco_v1/weights/best.pt")
    print("")
    print("Copia ese archivo a la carpeta principal y renombralo 'arve_best.pt'")
