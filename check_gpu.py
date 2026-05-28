"""
Verifica que PyTorch detecte tu RTX 3050 con CUDA.
Uso:
    python check_gpu.py
"""
import sys

def main():
    print("=" * 60)
    print("DIAGNOSTICO GPU / CUDA")
    print("=" * 60)

    try:
        import torch
    except ImportError:
        print("[X] PyTorch no instalado. Ejecuta:")
        print("    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121")
        sys.exit(1)

    print(f"[OK] PyTorch version    : {torch.__version__}")
    print(f"[..] CUDA disponible    : {torch.cuda.is_available()}")

    if not torch.cuda.is_available():
        print()
        print("[X] CUDA NO esta disponible. Posibles causas:")
        print("    1. Instalaste PyTorch CPU-only.")
        print("       Solucion: pip uninstall torch torchvision -y")
        print("       Luego:    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121")
        print("    2. No tienes drivers NVIDIA actualizados.")
        print("       Solucion: descarga GeForce Game Ready Driver desde nvidia.com")
        sys.exit(1)

    print(f"[OK] CUDA version       : {torch.version.cuda}")
    print(f"[OK] cuDNN version      : {torch.backends.cudnn.version()}")
    print(f"[OK] GPUs detectadas    : {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        vram_gb = props.total_memory / (1024 ** 3)
        print(f"     - GPU {i}: {props.name} ({vram_gb:.1f} GB VRAM)")

    # Prueba rapida de tensor en GPU
    print()
    print("[..] Probando calculo en GPU...")
    x = torch.randn(1000, 1000, device="cuda")
    y = torch.randn(1000, 1000, device="cuda")
    z = x @ y
    print(f"[OK] Multiplicacion matricial en GPU OK. Resultado shape: {z.shape}")

    # Probar Ultralytics si esta instalado
    try:
        from ultralytics import YOLO
        print(f"[OK] Ultralytics       : importado correctamente")
    except ImportError:
        print("[X] Ultralytics NO instalado. Ejecuta:")
        print("    pip install ultralytics")
        sys.exit(1)

    print()
    print("=" * 60)
    print("TODO LISTO - Tu RTX puede correr YOLO")
    print("=" * 60)


if __name__ == "__main__":
    main()
