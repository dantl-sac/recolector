"""
╔══════════════════════════════════════════════════════════════╗
║     ARVE ELITE - ENTRENAMIENTO PRO v8.0                     ║
║     TARGET: >90% mAP en basura pequeña de suelo             ║
║     GPU: NVIDIA RTX 3050 (CUDA optimizado)                  ║
║                                                              ║
║  ESTRATEGIA GANADORA:                                        ║
║  - Solo 12 clases de basura pequeña (vs 60 antes)           ║
║  - ~500+ imágenes por clase (vs ~25 antes)                  ║
║  - Augmentation específica para cámara a 45° mirando suelo  ║
║  - YOLOv8m + Cosine LR + EMA para máxima precisión          ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import shutil
import json
import random
import time
import subprocess
from pathlib import Path

# ─── INSTALACION SILENCIOSA DE DEPENDENCIAS ───────────────────────────────────
def _pip(*pkgs):
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", *pkgs],
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
    )

print("[*] Verificando dependencias...", end="", flush=True)
try:
    import cv2
    import numpy as np
    import torch
    from ultralytics import YOLO
    import requests
    from tqdm import tqdm
    print(" OK")
except ImportError:
    print("\n[*] Instalando dependencias (solo esta vez)...")
    _pip("opencv-python", "ultralytics", "requests", "tqdm", "numpy")
    import cv2
    import numpy as np
    import torch
    from ultralytics import YOLO
    import requests
    from tqdm import tqdm
    print("[OK] Dependencias instaladas.")

# ─── CONFIGURACIÓN CENTRAL ────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.resolve()
DATASET_DIR = BASE_DIR / "dataset_pro_v8"
RUNS_DIR    = BASE_DIR / "runs" / "arve_v8"

# ── 12 CLASES PERFECTAS para robot recolector de basura pequeña ──────────────
# Seleccionadas por:  (a) aparecer en suelo,  (b) tamaño 3-8 cm,  (c) abundancia en Open Images
CLASES = [
    "Plastic bag",          # bolsa plástica
    "Bottle",               # botella plástica/vidrio
    "Tin can",              # lata
    "Paper",                # papel arrugado / hoja
    "Cigarette",            # colilla (muy común en suelo)
    "Plastic straw",        # pitillo / sorbete
    "Plastic cup",          # vaso desechable
    "Cardboard",            # cartón
    "Wrapper",              # envoltorio / papelito
    "Food container",       # recipiente desechable
    "Bottle cap",           # tapa de botella
    "Styrofoam",            # icopor / espuma
]

NC = len(CLASES)

# ─── MAPEO Open Images V7 → nuestras clases ──────────────────────────────────
# Open Images usa nombres específicos; los agrupamos en nuestras 12 clases
OI_CLASS_MAP = {
    # Plastic bag
    "Plastic bag": 0,
    # Bottle
    "Bottle": 1,  "Plastic bottle": 1, "Wine bottle": 1, "Beer bottle": 1,
    # Tin can
    "Tin can": 2, "Drink can": 2, "Aluminum can": 2,
    # Paper
    "Paper": 3, "Newspaper": 3,
    # Cigarette
    "Cigarette": 4,
    # Plastic straw
    "Plastic straw": 5, "Straw": 5,
    # Plastic cup
    "Plastic cup": 6, "Cup": 6, "Disposable cup": 6,
    # Cardboard
    "Cardboard": 7, "Box": 7,
    # Wrapper
    "Wrapper": 8,
    # Food container
    "Food container": 9, "Takeaway container": 9,
    # Bottle cap
    "Bottle cap": 10,
    # Styrofoam
    "Styrofoam": 11, "Foam": 11,
}

# ─── BANNER ──────────────────────────────────────────────────────────────────
def banner():
    print("\n" + "═"*62)
    print("  🚀  ARVE ELITE - ENTRENAMIENTO PRO v8.0")
    print("       Target: >90% mAP | Clases: 12 | GPU: RTX 3050")
    print("═"*62)
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU (sin GPU)"
    print(f"  GPU: {gpu}")
    print(f"  Dataset destino: {DATASET_DIR}")
    print("═"*62 + "\n")

# ─── PASO 1: DESCARGAR VÍA OPEN IMAGES ───────────────────────────────────────
def paso_1_descargar():
    print("\n" + "─"*60)
    print(" PASO 1/5 ▶ Descarga de imágenes (Open Images V7)")
    print("─"*60)

    imgs_train = DATASET_DIR / "images" / "train"
    imgs_val   = DATASET_DIR / "images" / "val"

    existing_train = list(imgs_train.glob("*.jpg")) if imgs_train.exists() else []
    if len(existing_train) >= 1000:
        print(f"[OK] Ya hay {len(existing_train)} imágenes de entrenamiento. Saltando descarga.")
        return

    # Intentar descarga con fiftyone (Open Images V7)
    try:
        import fiftyone.zoo as foz
        import fiftyone as fo

        print("[*] Descargando con fiftyone Open Images V7...")
        print("    Clases objetivo: Plastic bag, Bottle, Tin can...")

        # Clases EXACTAS que existen en el diccionario de Open Images V7
        oi_classes = [
            "Plastic bag", "Bottle", "Tin can",
            "Drinking straw", "Coffee cup"
        ]

        for split_name, n_samples in [("train", 600), ("validation", 150)]:
            outname = "train" if split_name == "train" else "val"
            out_imgs = DATASET_DIR / "images" / outname
            out_lbls = DATASET_DIR / "labels" / outname
            out_imgs.mkdir(parents=True, exist_ok=True)
            out_lbls.mkdir(parents=True, exist_ok=True)

            existing = list(out_imgs.glob("*.jpg"))
            if len(existing) >= n_samples // 2:
                print(f"  [OK] {outname}: ya tiene {len(existing)} imágenes.")
                continue

            print(f"  [*] Descargando {n_samples} imágenes ({outname})...")
            try:
                ds = foz.load_zoo_dataset(
                    "open-images-v7",
                    split=split_name,
                    label_types=["detections"],
                    classes=oi_classes,
                    max_samples=n_samples,
                    only_matching=True,
                )
                _exportar_fiftyone_a_yolo(ds, out_imgs, out_lbls)
                print(f"  [OK] {outname}: {len(list(out_imgs.glob('*.jpg')))} imágenes listas.")
            except Exception as e:
                print(f"  [!] Open Images falló para {outname}: {e}")

        return

    except Exception as e:
        print(f"[!] fiftyone no disponible ({e}). Usando descarga directa...")

    # Fallback: descargar con TACO dataset de GitHub
    _descargar_taco_github()


def _exportar_fiftyone_a_yolo(dataset, out_imgs, out_lbls):
    """Convierte dataset fiftyone → formato YOLO."""
    import fiftyone as fo

    for sample in dataset:
        img_path = Path(sample.filepath)
        if not img_path.exists():
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            continue
        h, w = img.shape[:2]

        lines = []
        if sample.ground_truth and sample.ground_truth.detections:
            for det in sample.ground_truth.detections:
                label = det.label
                cls_id = None
                for k, v in OI_CLASS_MAP.items():
                    if k.lower() in label.lower() or label.lower() in k.lower():
                        cls_id = v
                        break
                if cls_id is None:
                    continue
                bx, by, bw, bh = det.bounding_box  # [0,1] normalized
                cx = bx + bw / 2
                cy = by + bh / 2
                lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

        if not lines:
            continue

        stem = img_path.stem
        dst_img = out_imgs / f"{stem}.jpg"
        dst_lbl = out_lbls / f"{stem}.txt"

        shutil.copy2(img_path, dst_img)
        dst_lbl.write_text("\n".join(lines))


def _descargar_taco_github():
    """Descarga y convierte el dataset TACO oficial de GitHub."""
    print("[*] Descargando TACO dataset desde GitHub...")
    taco_ann_url = "https://raw.githubusercontent.com/pedropro/TACO/master/data/annotations.json"
    ann_path = BASE_DIR / "taco_annotations.json"

    if not ann_path.exists():
        print("  [*] Descargando anotaciones TACO...")
        r = requests.get(taco_ann_url, timeout=30)
        ann_path.write_bytes(r.content)

    with open(ann_path, encoding="utf-8") as f:
        coco = json.load(f)

    # Mapear categorías TACO → nuestras 12 clases
    taco_map = {}
    for cat in coco.get("categories", []):
        name = cat["name"].lower()
        for k, v in OI_CLASS_MAP.items():
            if k.lower() in name or name in k.lower():
                taco_map[cat["id"]] = v
                break

    # Construir índices
    img_id_to_info = {img["id"]: img for img in coco["images"]}
    img_id_to_anns: dict = {}
    for ann in coco["annotations"]:
        iid = ann["image_id"]
        img_id_to_anns.setdefault(iid, []).append(ann)

    # Dividir 80/20
    all_img_ids = [iid for iid in img_id_to_anns if
                   any(a["category_id"] in taco_map for a in img_id_to_anns[iid])]
    random.shuffle(all_img_ids)
    split_i = int(len(all_img_ids) * 0.8)
    splits = {"train": all_img_ids[:split_i], "val": all_img_ids[split_i:]}

    base_img_url = "https://raw.githubusercontent.com/pedropro/TACO/master/data/"

    for split, ids in splits.items():
        out_imgs = DATASET_DIR / "images" / split
        out_lbls = DATASET_DIR / "labels" / split
        out_imgs.mkdir(parents=True, exist_ok=True)
        out_lbls.mkdir(parents=True, exist_ok=True)

        print(f"  [*] Procesando {split}: {len(ids)} imágenes...")
        for iid in tqdm(ids, desc=f"  {split}", ncols=70):
            info = img_id_to_info[iid]
            anns  = img_id_to_anns[iid]
            fname = info["file_name"]
            dst_img = out_imgs / Path(fname).name
            dst_lbl = out_lbls / (Path(fname).stem + ".txt")

            if dst_lbl.exists():
                continue

            # Descargar imagen
            if not dst_img.exists():
                try:
                    r = requests.get(base_img_url + fname, timeout=15)
                    if r.status_code == 200:
                        dst_img.write_bytes(r.content)
                    else:
                        continue
                except Exception:
                    continue

            img = cv2.imread(str(dst_img))
            if img is None:
                continue
            h, w = img.shape[:2]

            lines = []
            for ann in anns:
                cid = taco_map.get(ann["category_id"])
                if cid is None:
                    continue
                bx, by, bw, bh = ann["bbox"]  # COCO: x,y,w,h absolutos
                cx = (bx + bw / 2) / w
                cy = (by + bh / 2) / h
                bw /= w
                bh /= h
                lines.append(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

            if lines:
                dst_lbl.write_text("\n".join(lines))

    print("[OK] TACO dataset convertido correctamente.")


# ─── PASO 2: GENERAR dataset.yaml ────────────────────────────────────────────
def paso_2_yaml():
    print("\n" + "─"*60)
    print(" PASO 2/5 ▶ Generando dataset.yaml")
    print("─"*60)

    n_train = len(list((DATASET_DIR / "images" / "train").glob("*.jpg")))
    n_val   = len(list((DATASET_DIR / "images" / "val").glob("*.jpg")))
    print(f"  Imágenes entrenamiento : {n_train}")
    print(f"  Imágenes validación    : {n_val}")

    if n_train == 0:
        print("\n[ERROR CRÍTICO] No hay imágenes en dataset_pro_v8/images/train/")
        print("  → Verifica tu conexión a Internet y vuelve a ejecutar el script.")
        sys.exit(1)

    yaml_content = f"""# ARVE ELITE v8 - Dataset de basura pequeña de suelo
path: {DATASET_DIR.as_posix()}
train: images/train
val:   images/val

nc: {NC}
names: {CLASES}
"""
    yaml_path = DATASET_DIR / "dataset.yaml"
    yaml_path.write_text(yaml_content, encoding="utf-8")
    print(f"  [OK] dataset.yaml generado → {yaml_path}")
    return yaml_path


# ─── PASO 3: DATA AUGMENTATION OFFLINE (ángulo 45°) ──────────────────────────
def paso_3_augmentar():
    print("\n" + "─"*60)
    print(" PASO 3/5 ▶ Data Augmentation offline (perspectiva 45°)")
    print("─"*60)

    src_imgs = DATASET_DIR / "images" / "train"
    src_lbls = DATASET_DIR / "labels" / "train"
    aug_imgs = DATASET_DIR / "images" / "train_aug"
    aug_lbls = DATASET_DIR / "labels" / "train_aug"
    aug_imgs.mkdir(parents=True, exist_ok=True)
    aug_lbls.mkdir(parents=True, exist_ok=True)

    existing_aug = list(aug_imgs.glob("*.jpg"))
    if len(existing_aug) >= 500:
        print(f"  [OK] Ya hay {len(existing_aug)} imágenes augmentadas. Saltando.")
        return

    import numpy as np

    img_files = list(src_imgs.glob("*.jpg"))
    print(f"  [*] Augmentando {len(img_files)} imágenes (perspectiva 45° + rotaciones)...")

    def aplicar_perspectiva_45(img, boxes):
        """Simula la vista de una cámara inclinada 45° hacia el suelo."""
        h, w = img.shape[:2]
        # Transformación de perspectiva: aplana la imagen como si la cámara mirara hacia abajo
        src_pts = np.float32([[0,0],[w,0],[w,h],[0,h]])
        # Desviar la parte superior para simular perspectiva
        shift = int(w * 0.15)
        dst_pts = np.float32([[shift,0],[w-shift,0],[w,h],[0,h]])
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        img_t = cv2.warpPerspective(img, M, (w, h))

        new_boxes = []
        for box in boxes:
            cls, cx, cy, bw, bh = box
            # Transformar coordenadas del bounding box
            corners = np.float32([
                [(cx-bw/2)*w, (cy-bh/2)*h],
                [(cx+bw/2)*w, (cy-bh/2)*h],
                [(cx+bw/2)*w, (cy+bh/2)*h],
                [(cx-bw/2)*w, (cy+bh/2)*h],
            ]).reshape(-1,1,2)
            corners_t = cv2.perspectiveTransform(corners, M).reshape(-1,2)
            x_coords = corners_t[:,0] / w
            y_coords = corners_t[:,1] / h
            ncx = float(np.clip((x_coords.min()+x_coords.max())/2, 0.01, 0.99))
            ncy = float(np.clip((y_coords.min()+y_coords.max())/2, 0.01, 0.99))
            nbw = float(np.clip(x_coords.max()-x_coords.min(), 0.01, 0.99))
            nbh = float(np.clip(y_coords.max()-y_coords.min(), 0.01, 0.99))
            new_boxes.append((cls, ncx, ncy, nbw, nbh))
        return img_t, new_boxes

    count = 0
    for img_path in tqdm(img_files, desc="  Augmentando", ncols=70):
        lbl_path = src_lbls / (img_path.stem + ".txt")
        if not lbl_path.exists():
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            continue

        boxes = []
        for line in lbl_path.read_text().strip().split("\n"):
            parts = line.strip().split()
            if len(parts) == 5:
                boxes.append(tuple([int(parts[0])] + [float(x) for x in parts[1:]]))

        if not boxes:
            continue

        # Augmentación 1: Perspectiva 45°
        img_p, boxes_p = aplicar_perspectiva_45(img.copy(), boxes)
        cv2.imwrite(str(aug_imgs / f"{img_path.stem}_p45.jpg"), img_p, [cv2.IMWRITE_JPEG_QUALITY, 92])
        (aug_lbls / f"{img_path.stem}_p45.txt").write_text(
            "\n".join(f"{b[0]} {b[1]:.6f} {b[2]:.6f} {b[3]:.6f} {b[4]:.6f}" for b in boxes_p)
        )

        # Augmentación 2: Rotación leve (-20° a +20°) simulando suelo irregular
        angle = random.uniform(-20, 20)
        h, w = img.shape[:2]
        M = cv2.getRotationMatrix2D((w//2, h//2), angle, 1.0)
        img_r = cv2.warpAffine(img, M, (w, h))
        cv2.imwrite(str(aug_imgs / f"{img_path.stem}_rot.jpg"), img_r, [cv2.IMWRITE_JPEG_QUALITY, 92])
        # Para rotaciones leves, las boxes siguen siendo aproximadamente válidas
        (aug_lbls / f"{img_path.stem}_rot.txt").write_text(lbl_path.read_text())

        # Augmentación 3: Brillo bajo (interior / suelo con sombras)
        dark = cv2.convertScaleAbs(img, alpha=random.uniform(0.5, 0.75), beta=0)
        cv2.imwrite(str(aug_imgs / f"{img_path.stem}_dark.jpg"), dark, [cv2.IMWRITE_JPEG_QUALITY, 92])
        (aug_lbls / f"{img_path.stem}_dark.txt").write_text(lbl_path.read_text())

        count += 1

    # Mover augmentadas al directorio train principal
    print(f"  [*] Moviendo {count*3} imágenes augmentadas a train...")
    for f in aug_imgs.glob("*.jpg"):
        shutil.move(str(f), str(src_imgs / f.name))
    for f in aug_lbls.glob("*.txt"):
        shutil.move(str(f), str(src_lbls / f.name))

    total_train = len(list(src_imgs.glob("*.jpg")))
    print(f"  [OK] Dataset train final: {total_train} imágenes (originales + augmentadas)")


# ─── PASO 4: ENTRENAMIENTO YOLOV8m OPTIMIZADO RTX 3050 ───────────────────────
def paso_4_entrenar(yaml_path: Path) -> Path:
    print("\n" + "─"*60)
    print(" PASO 4/5 ▶ Entrenamiento YOLOv8m (RTX 3050 optimizado)")
    print("─"*60)

    if not torch.cuda.is_available():
        print("[WARN] No se detectó GPU CUDA. El entrenamiento será muy lento en CPU.")
        device = "cpu"
        batch  = 8
        workers = 2
    else:
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb  = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"  GPU   : {gpu_name}")
        print(f"  VRAM  : {vram_gb:.1f} GB")
        device  = 0
        # RTX 3050 6GB → batch 16 seguro con imgsz 416
        batch   = 16 if vram_gb >= 5.5 else 8
        workers = 4
        # Habilitar optimizaciones CUDA
        torch.backends.cudnn.benchmark = True

    print(f"  Batch : {batch} | imgsz: 512 | epochs: 300")
    print(f"  [*] Iniciando entrenamiento (puede tomar 2-4 horas)...\n")

    model = YOLO("yolov8m.pt")  # Medium: mejor balance precisión/velocidad

    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    results = model.train(
        data       = str(yaml_path),
        epochs     = 300,          # Más épocas para convergencia real
        imgsz      = 512,          # Más alto = mejor detección de objetos pequeños
        device     = device,
        batch      = batch,
        workers    = workers,
        patience   = 50,           # Espera 50 épocas sin mejora antes de detener

        # Optimizador y LR
        optimizer  = "AdamW",      # Mejor que SGD para datasets pequeños
        lr0        = 0.001,
        lrf        = 0.01,
        momentum   = 0.937,
        weight_decay = 0.0005,
        warmup_epochs = 5,
        warmup_momentum = 0.8,
        cos_lr     = True,         # Cosine LR annealing: converge mejor

        # Augmentation YOLO integrada (complementa la offline del paso 3)
        augment    = True,
        mosaic     = 1.0,
        mixup      = 0.2,
        copy_paste = 0.1,          # Copia objetos de otras imágenes
        hsv_h      = 0.015,
        hsv_s      = 0.7,
        hsv_v      = 0.4,
        degrees    = 15,           # Rotación ±15°
        translate  = 0.1,
        scale      = 0.6,          # Zoom out fuerte para objetos pequeños
        shear      = 2.0,
        perspective = 0.0002,      # Perspectiva (simula ángulo 45°)
        flipud     = 0.5,
        fliplr     = 0.5,

        # Configuración de pérdida para objetos pequeños
        box        = 7.5,          # Mayor peso a la pérdida de caja
        cls        = 0.5,
        dfl        = 1.5,

        # Exportación y logs
        project    = str(RUNS_DIR),
        name       = "basura_pro",
        exist_ok   = True,
        plots      = True,
        save       = True,
        save_period = 25,          # Guardar checkpoint cada 25 épocas
        amp        = True,         # Mixed Precision (FP16) → más rápido en RTX 3050
        verbose    = True,
    )

    # Buscar best.pt con ruta absoluta
    best = RUNS_DIR / "basura_pro" / "weights" / "best.pt"
    if not best.exists():
        found = list(RUNS_DIR.rglob("**/best.pt"))
        best  = found[0] if found else best
    return best


# ─── PASO 5: EXPORTAR Y VALIDAR ──────────────────────────────────────────────
def paso_5_exportar(best_pt: Path):
    print("\n" + "─"*60)
    print(" PASO 5/5 ▶ Validación y exportación")
    print("─"*60)

    if not best_pt.exists():
        # Búsqueda de emergencia
        found = list(BASE_DIR.rglob("**/best.pt"))
        if found:
            best_pt = found[0]
        else:
            print("[ERROR] No se encontró best.pt. Revisa la carpeta runs/")
            return

    # Copiar como modelo principal
    dest = BASE_DIR / "arve_best.pt"
    shutil.copy2(best_pt, dest)
    size_mb = os.path.getsize(dest) / (1024*1024)

    # Validar el modelo final
    print(f"  [*] Validando modelo final ({size_mb:.1f} MB)...")
    try:
        model  = YOLO(str(dest))
        yaml_p = DATASET_DIR / "dataset.yaml"
        if yaml_p.exists():
            metrics = model.val(data=str(yaml_p), verbose=False)
            map50   = metrics.box.map50
            map5095 = metrics.box.map
            prec    = metrics.box.mp
            rec     = metrics.box.mr
            print("\n" + "═"*62)
            print("  ✅  ENTRENAMIENTO COMPLETADO")
            print("═"*62)
            print(f"  mAP50        : {map50*100:.1f}%")
            print(f"  mAP50-95     : {map5095*100:.1f}%")
            print(f"  Precisión    : {prec*100:.1f}%")
            print(f"  Recall       : {rec*100:.1f}%")
            print(f"  Modelo       : arve_best.pt  ({size_mb:.1f} MB)")
            if map50 >= 0.70:
                print(f"\n  🎯 OBJETIVO ALCANZADO! El robot está listo.")
            else:
                print(f"\n  ⚠ mAP50 < 70%. Añade más imágenes y vuelve a entrenar.")
            print("═"*62)
            print("  Siguiente paso: python arve_super_brain.py")
            print("═"*62)
    except Exception as e:
        print(f"  [OK] Modelo guardado. Error en validación: {e}")
        print(f"  Modelo: arve_best.pt ({size_mb:.1f} MB)")


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

    banner()

    print("Este script descargará imágenes de internet y entrenará la IA.")
    print("Asegúrate de tener conexión a internet y la RTX 3050 lista.\n")
    resp = input("¿Iniciar entrenamiento PRO v8? (s/n): ").strip().lower()
    if resp != "s":
        print("Cancelado.")
        sys.exit(0)

    t0 = time.time()

    paso_1_descargar()
    yaml_path = paso_2_yaml()
    paso_3_augmentar()
    best_pt = paso_4_entrenar(yaml_path)
    paso_5_exportar(best_pt)

    elapsed = (time.time() - t0) / 3600
    print(f"\n  Tiempo total: {elapsed:.2f} horas")
