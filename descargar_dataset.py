"""
DESCARGADOR DE DATASET DE BASURA - ARVE ELITE
Descarga el dataset TACO (Trash Annotations in Context)
Miles de imágenes reales de basura ya etiquetadas para YOLO.
"""
import os
import shutil
import subprocess
import sys

DATASET_DIR = os.path.join(os.path.dirname(__file__), "dataset")

def instalar_dependencias():
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fiftyone", "-q"])

def descargar_con_fiftyone():
    import fiftyone.zoo as foz
    
    print("[1/3] Descargando dataset COCO con clases de basura (bottle, cup, bag)...")
    dataset = foz.load_zoo_dataset(
        "coco-2017",
        split="train",
        label_types=["detections"],
        classes=["bottle", "cup", "bowl"],
        max_samples=3000,
    )
    print(f"[*] Descargadas {len(dataset)} imágenes con basura.")
    return dataset

def descargar_taco_directo():
    """Descarga el dataset TACO directo desde GitHub."""
    print("[1/3] Clonando repositorio TACO (dataset oficial de basura)...")
    if not os.path.exists("TACO"):
        subprocess.check_call(["git", "clone", "--depth=1", "https://github.com/pedropro/TACO.git"])
    
    print("[2/3] Instalando dependencias TACO...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pycocotools", "-q"])
    
    print("[3/3] Descargando imágenes...")
    os.chdir("TACO")
    subprocess.check_call([sys.executable, "download.py"])
    os.chdir("..")
    print("[!] TACO descargado exitosamente en la carpeta TACO/data/")

def descargar_roboflow_publico():
    """
    Descarga dataset público de detección de basura desde Roboflow Universe.
    Este dataset tiene +5000 imágenes de botellas, latas, papel, cartón.
    """
    from roboflow import Roboflow
    
    print("[1/3] Conectando a Roboflow Universe (público, sin API key)...")
    rf = Roboflow(api_key="YOUR_API_KEY") # Necesita API key gratuita
    
    project = rf.workspace("divyanshu-joshi").project("garbage-detection-h7ygb")
    version = project.version(5)
    
    print("[2/3] Descargando imágenes...")
    dataset = version.download("yolov8", location=DATASET_DIR)
    
    print(f"[3/3] Dataset listo en: {DATASET_DIR}")
    return dataset

def crear_dataset_manual():
    """
    Crea la estructura de carpetas lista para que el usuario pegue sus fotos.
    """
    carpetas = [
        os.path.join(DATASET_DIR, "images", "train"),
        os.path.join(DATASET_DIR, "images", "val"),
        os.path.join(DATASET_DIR, "labels", "train"),
        os.path.join(DATASET_DIR, "labels", "val"),
    ]
    for c in carpetas:
        os.makedirs(c, exist_ok=True)
    print(f"[!] Estructura creada en: {DATASET_DIR}")
    print("     Pon tus fotos de basura en: dataset/images/train/")
    print("     Pon tus etiquetas en:       dataset/labels/train/")

if __name__ == "__main__":
    print("="*50)
    print("  ARVE ELITE - DESCARGADOR DE DATASET DE BASURA")
    print("="*50)
    print("\nOpciones:")
    print("  1. Descargar TACO (Dataset oficial de basura - GitHub)")
    print("  2. Solo crear la estructura de carpetas (para pegar fotos manualmente)")
    
    opcion = input("\nElige una opción (1 o 2): ").strip()
    
    if opcion == "1":
        descargar_taco_directo()
    else:
        crear_dataset_manual()
        
    print("\n[OK] Listo. Ahora puedes correr 'entrenar_ia.py' para que la IA aprenda.")
