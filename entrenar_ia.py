from ultralytics import YOLO
import torch

# ==========================================
# SCRIPT DE ENTRENAMIENTO ARVE ELITE
# ==========================================

def entrenar():
    if torch.cuda.is_available():
        device = 0
        gpu_name = torch.cuda.get_device_name(0)
        print(f"[OK] GPU detectada: {gpu_name}")
    else:
        device = "cpu"
        print("[WARN] Sin GPU, usando CPU (entrenamiento más lento)")

    # Cargamos el modelo base (Nano) para que sea rápido
    model = YOLO('yolov8n.pt')

    print("[*] Iniciando entrenamiento con tus imágenes...")
    
    # Entrenar por 50 épocas (puedes subirlo a 100 para más precisión)
    # imgsz=320 para que coincida con la velocidad del ESP32
    model.train(
        data='dataset.yaml', 
        epochs=50, 
        imgsz=320, 
        device=device,
        workers=2,
        plots=True,
    )

    print("[!] Entrenamiento completado. El nuevo cerebro está en 'runs/detect/train/weights/best.pt'")

if __name__ == "__main__":
    entrenar()
