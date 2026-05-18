"""
Convierte el dataset TACO (formato COCO) a formato YOLO
y luego entrena YOLOv8n con la RTX 3050.
"""
import json
import os
import shutil
import random
from pathlib import Path
import sys

BASE_DIR   = Path(__file__).parent
TACO_DIR   = BASE_DIR / "TACO" / "data"
ANNOT_FILE = TACO_DIR / "annotations.json"
OUT_DIR    = BASE_DIR / "dataset_taco"

# =============================================
# PASO 1: CARGAR ANOTACIONES
# =============================================
print("[1/4] Cargando anotaciones TACO...")
if not ANNOT_FILE.exists():
    print(f"[ERROR] No se encontró: {ANNOT_FILE}")
    print("[INFO] Descarga el dataset TACO primero con 'descargar_dataset.py' (opción 1).")
    sys.exit(1)
with open(ANNOT_FILE, "r") as f:
    coco = json.load(f)

categorias = {cat["id"]: cat["name"] for cat in coco["categories"]}
imagenes   = {img["id"]: img for img in coco["images"]}

print(f"      Imágenes:   {len(imagenes)}")
print(f"      Categorías: {len(categorias)}")
print(f"      Clases: {list(categorias.values())[:10]}...")

# Mapear categorías TACO a índices YOLO (0-based)
cat_ids  = sorted(categorias.keys())
cat_map  = {cid: idx for idx, cid in enumerate(cat_ids)}
nombres  = [categorias[cid] for cid in cat_ids]

# =============================================
# PASO 2: CREAR ESTRUCTURA DE CARPETAS
# =============================================
print("\n[2/4] Creando estructura de carpetas...")
for split in ["train", "val"]:
    (OUT_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

# Agrupar anotaciones por imagen
anots_por_img = {}
for ann in coco["annotations"]:
    iid = ann["image_id"]
    if iid not in anots_por_img:
        anots_por_img[iid] = []
    anots_por_img[iid].append(ann)

# Dividir en train (85%) y val (15%)
img_ids = list(imagenes.keys())
random.shuffle(img_ids)
split_idx = int(len(img_ids) * 0.85)
train_ids = set(img_ids[:split_idx])
val_ids   = set(img_ids[split_idx:])

print(f"      Train: {len(train_ids)} imágenes")
print(f"      Val:   {len(val_ids)} imágenes")

# =============================================
# PASO 3: CONVERTIR A FORMATO YOLO
# =============================================
print("\n[3/4] Convirtiendo anotaciones a formato YOLO...")
copiadas = 0
errores  = 0

for img_id, img_info in imagenes.items():
    split  = "train" if img_id in train_ids else "val"
    
    # Buscar la imagen en los batches
    fname  = img_info["file_name"]  # Ej: "batch_1/000000.jpg"
    src    = TACO_DIR / fname
    
    if not src.exists():
        errores += 1
        continue
    
    # Copiar imagen
    dst_img = OUT_DIR / "images" / split / src.name
    shutil.copy2(src, dst_img)
    
    # Crear etiqueta YOLO
    anots = anots_por_img.get(img_id, [])
    iw, ih = img_info["width"], img_info["height"]
    
    dst_lbl = OUT_DIR / "labels" / split / (src.stem + ".txt")
    with open(dst_lbl, "w") as f:
        for ann in anots:
            if ann.get("bbox") and ann["category_id"] in cat_map:
                x, y, bw, bh = ann["bbox"]
                # Convertir a YOLO (cx, cy, w, h) normalizado
                cx = (x + bw / 2) / iw
                cy = (y + bh / 2) / ih
                nw = bw / iw
                nh = bh / ih
                cls_idx = cat_map[ann["category_id"]]
                f.write(f"{cls_idx} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}\n")
    
    copiadas += 1
    if copiadas % 100 == 0:
        print(f"      Procesadas: {copiadas}/{len(imagenes)}")

print(f"      Completado: {copiadas} imágenes | Errores: {errores}")

# =============================================
# PASO 4: CREAR dataset.yaml
# =============================================
yaml_path = OUT_DIR / "dataset.yaml"
with open(yaml_path, "w") as f:
    f.write(f"path: {OUT_DIR.as_posix()}\n")
    f.write(f"train: images/train\n")
    f.write(f"val: images/val\n")
    f.write(f"nc: {len(nombres)}\n")
    f.write(f"names: {nombres}\n")

print(f"\n[4/4] dataset.yaml creado en: {yaml_path}")
print("\n" + "="*50)
print("  CONVERSIÓN COMPLETADA")
print("="*50)

# =============================================
# PASO 5: ENTRENAR CON RTX 3050
# =============================================
respuesta = input("\n¿Iniciar entrenamiento con la RTX 3050 ahora? (s/n): ").strip().lower()
if respuesta == "s":
    from ultralytics import YOLO
    print("\n[*] Iniciando entrenamiento YOLOv8n con RTX 3050...")
    print("    Esto tardará ~30-45 minutos. Puedes ver el progreso abajo.")
    model = YOLO("yolov8n.pt")
    model.train(
        data    = str(yaml_path),
        epochs  = 50,
        imgsz   = 320,
        device  = 0,          # RTX 3050
        batch   = 16,
        workers = 4,
        name    = "arve_trash_model",
        project = str(BASE_DIR / "esp32-yolo-camera"),
        patience= 15,
        plots   = True,
    )
    print("\n[!] Entrenamiento completado!")
    best = BASE_DIR / "esp32-yolo-camera" / "arve_trash_model" / "weights" / "best.pt"
    print(f"[*] Modelo listo en: {best}")
    print("[*] Copia 'best.pt' al proyecto y cambia 'yolov8n.pt' por 'best.pt' en arve_super_brain.py")
else:
    print("OK. Puedes entrenar después ejecutando 'entrenar_ia.py'")
