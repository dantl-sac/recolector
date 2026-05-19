"""
==============================================
PIPELINE COMPLETO DE ENTRENAMIENTO
Augmentación + Entrenamiento + Validación
==============================================
"""

import os
import cv2
import numpy as np
from pathlib import Path
import albumentations as A
from tqdm import tqdm
from ultralytics import YOLO
import torch
import matplotlib.pyplot as plt

class GeneradorDataAugmented:
    """Genera dataset aumentado con múltiples ángulos y condiciones"""
    
    def __init__(self, dataset_root='dataset_taco'):
        self.dataset_root = dataset_root
        self.train_imgs = Path(f"{dataset_root}/images/train")
        self.train_labels = Path(f"{dataset_root}/labels/train")
        self.output_dir = Path(f"{dataset_root}_augmented")
        self.output_dir.mkdir(exist_ok=True)
        
        # Crear estructura de carpetas
        (self.output_dir / "images" / "train").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "labels" / "train").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "images" / "val").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "labels" / "val").mkdir(parents=True, exist_ok=True)
    
    def crear_transformaciones(self):
        """Define augmentaciones avanzadas"""
        return A.Compose([
            # Rotaciones
            A.Rotate(limit=45, p=0.7, border_mode=cv2.BORDER_REFLECT),
            A.Perspective(scale=(0.05, 0.15), p=0.6),
            
            # Iluminación realista
            A.RandomBrightnessContrast(brightness_limit=0.4, contrast_limit=0.4, p=0.7),
            A.RandomGamma(p=0.3),
            A.RandomFog(p=0.3),
            A.RandomSunFlare(p=0.2),
            
            # Ruido y desenfoque
            A.GaussNoise(p=0.3),
            A.MotionBlur(blur_limit=7, p=0.3),
            A.GaussBlur(blur_limit=5, p=0.3),
            
            # Cambios de color (importante para detectar sin importar color)
            A.RandomRain(p=0.1),
            A.Equalize(p=0.2),
            A.CLAHE(p=0.3),
            
            # Zoom y escala
            A.ShiftScaleRotate(shift_limit=0.1, scale_limit=0.3, p=0.6),
            A.OpticalDistortion(distortion_limit=0.2, p=0.3),
            A.ElasticTransform(p=0.2),
            
            # Cambios de escala (múltiples tamaños de objeto)
            A.Downscale(scale_min=0.7, scale_max=0.99, p=0.2),
        ], bbox_params=A.BboxParams(format='yolo', min_visibility=0.2))
    
    def leer_anotaciones_yolo(self, archivo_txt):
        """Lee anotaciones en formato YOLO"""
        bboxes = []
        try:
            with open(archivo_txt, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        bboxes.append([float(x) for x in parts])
        except:
            pass
        return bboxes
    
    def guardar_anotaciones_yolo(self, archivo_txt, bboxes):
        """Guarda anotaciones en formato YOLO"""
        with open(archivo_txt, 'w') as f:
            for bbox in bboxes:
                f.write(' '.join(map(str, bbox)) + '\n')
    
    def aumentar_dataset(self, augmentaciones_por_imagen=3):
        """Genera dataset aumentado"""
        print(f"\n📈 Generando dataset aumentado...")
        print(f"   • Carpeta origen: {self.train_imgs}")
        print(f"   • Augmentaciones por imagen: {augmentaciones_por_imagen}")
        
        transform = self.crear_transformaciones()
        
        imagenes = list(self.train_imgs.glob("*.jpg")) + list(self.train_imgs.glob("*.png"))
        total = len(imagenes) * (1 + augmentaciones_por_imagen)
        
        pbar = tqdm(total=total, desc="Augmentando")
        
        for img_path in imagenes:
            label_path = self.train_labels / (img_path.stem + ".txt")
            
            # Leer imagen y anotaciones
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            
            bboxes = self.leer_anotaciones_yolo(label_path)
            
            # Guardar original
            out_img = self.output_dir / "images" / "train" / img_path.name
            out_label = self.output_dir / "labels" / "train" / label_path.name
            cv2.imwrite(str(out_img), img)
            self.guardar_anotaciones_yolo(str(out_label), bboxes)
            pbar.update(1)
            
            # Generar augmentaciones
            for i in range(augmentaciones_por_imagen):
                transformed = transform(image=img, bboxes=bboxes)
                aug_img = transformed['image']
                aug_bboxes = transformed['bboxes']
                
                # Guardar
                aug_name = f"{img_path.stem}_aug{i}"
                out_aug_img = self.output_dir / "images" / "train" / f"{aug_name}.jpg"
                out_aug_label = self.output_dir / "labels" / "train" / f"{aug_name}.txt"
                
                cv2.imwrite(str(out_aug_img), aug_img)
                self.guardar_anotaciones_yolo(str(out_aug_label), aug_bboxes)
                
                pbar.update(1)
        
        pbar.close()
        print(f"✅ Dataset augmentado guardado en {self.output_dir}")
        return self.output_dir

class EntrenadorProfesional:
    """Entrena YOLO con configuración profesional"""
    
    def __init__(self, dataset_yaml='dataset_taco_augmented/dataset.yaml'):
        self.dataset_yaml = dataset_yaml
        self.device = self._detectar_device()
    
    def _detectar_device(self):
        if torch.cuda.is_available():
            device = 0
            props = torch.cuda.get_device_properties(0)
            print(f"✓ GPU: {props.name}")
            print(f"  Memoria: {props.total_memory / 1e9:.1f} GB")
            return device
        else:
            print("⚠ Usando CPU (entrenamiento lento)")
            return "cpu"
    
    def entrenar_yolov8(self, epochs=300, imgsz=416):
        """Entrena YOLOv8 medium (mejor balance)"""
        
        print("\n" + "="*60)
        print("   ENTRENAMIENTO PROFESIONAL YOLOV8")
        print("="*60)
        
        model = YOLO('yolov8m.pt')  # Medium = mejor precisión/velocidad
        
        print(f"\n🚀 Iniciando entrenamiento...")
        print(f"   • Modelo: YOLOv8 Medium")
        print(f"   • Épocas: {epochs}")
        print(f"   • Tamaño imagen: {imgsz}x{imgsz}")
        print(f"   • Device: {'GPU' if isinstance(self.device, int) else 'CPU'}")
        
        results = model.train(
            data=self.dataset_yaml,
            epochs=epochs,
            imgsz=imgsz,
            device=self.device,
            
            # Optimización
            workers=4,
            batch=16,
            patience=50,
            
            # Data augmentation avanzada
            augment=True,
            mosaic=1.0,
            mixup=0.15,
            copy_paste=0.0,
            
            # Color augmentation
            hsv_h=0.015,
            hsv_s=0.7,
            hsv_v=0.4,
            
            # Geometric augmentation
            degrees=15,
            translate=0.1,
            scale=0.5,
            flipud=0.5,
            fliplr=0.5,
            perspective=0.0001,
            
            # Optimizer
            optimizer='SGD',
            lr0=0.01,
            lrf=0.01,
            momentum=0.937,
            weight_decay=0.0005,
            
            # Warmup
            warmup_epochs=3,
            warmup_momentum=0.8,
            
            # Loss weights
            box=7.5,
            cls=0.5,
            dfl=1.5,
            
            # Learning rate scheduler
            cos_lr=True,
            
            # Guardado y validación
            save=True,
            cache='ram',
            val=True,
            plots=True,
            save_json=True,
            verbose=True,
        )
        
        return results
    
    def entrenar_ensemble(self, epochs=200):
        """Entrena múltiples modelos para ensemble"""
        print("\n" + "="*60)
        print("   ENTRENAMIENTO ENSEMBLE (3 MODELOS)")
        print("="*60)
        
        modelos = ['yolov8n', 'yolov8m', 'yolov8l']  # Nano, Medium, Large
        resultados = {}
        
        for modelo in modelos:
            print(f"\n🔄 Entrenando {modelo}...")
            m = YOLO(f'{modelo}.pt')
            results = m.train(
                data=self.dataset_yaml,
                epochs=epochs,
                imgsz=416,
                device=self.device,
                workers=4,
                batch=16,
                patience=30,
                augment=True,
                mosaic=1.0,
                plots=True,
            )
            resultados[modelo] = results
        
        return resultados
    
    def validar_completo(self):
        """Valida con métricas detalladas"""
        print("\n" + "="*60)
        print("   VALIDACIÓN COMPLETA")
        print("="*60)
        
        model = YOLO('runs/detect/train/weights/best.pt')
        
        # Validación
        print("\n📊 Validando...")
        metrics = model.val(
            data=self.dataset_yaml,
            device=self.device,
            verbose=True,
            plots=True,
        )
        
        print(f"\n✅ RESULTADOS:")
        print(f"   • mAP@50:95  = {metrics.box.map:.3f}")
        print(f"   • mAP@50     = {metrics.box.map50:.3f}")
        print(f"   • mAP@75     = {metrics.box.map75:.3f}")
        print(f"   • Precisión  = {metrics.box.mp:.3f}")
        print(f"   • Recall     = {metrics.box.mr:.3f}")
        
        return metrics
    
    def exportar_optimizado(self):
        """Exporta modelo para ESP32"""
        print("\n📦 Exportando modelo optimizado para ESP32...")
        
        model = YOLO('runs/detect/train/weights/best.pt')
        
        # TensorFlow Lite (ideal para ESP32)
        print("  → Exportando a TFLite...")
        model.export(format='tflite', imgsz=320)
        
        print("✅ Modelos exportados")

def crear_dataset_yaml(output_dir='dataset_taco_augmented'):
    """Crea archivo dataset.yaml para augmented dataset"""
    
    yaml_content = f"""path: {Path(output_dir).absolute()}
train: images/train
val: images/val
nc: 60
names: ['Aluminium foil', 'Battery', 'Aluminium blister pack', 'Carded blister pack', 'Other plastic bottle', 'Clear plastic bottle', 'Glass bottle', 'Plastic bottle cap', 'Metal bottle cap', 'Broken glass', 'Food Can', 'Aerosol', 'Drink can', 'Toilet tube', 'Other carton', 'Egg carton', 'Drink carton', 'Corrugated carton', 'Meal carton', 'Pizza box', 'Paper cup', 'Disposable plastic cup', 'Foam cup', 'Glass cup', 'Other plastic cup', 'Food waste', 'Glass jar', 'Plastic lid', 'Metal lid', 'Other plastic', 'Magazine paper', 'Tissues', 'Wrapping paper', 'Normal paper', 'Paper bag', 'Plastified paper bag', 'Plastic film', 'Six pack rings', 'Garbage bag', 'Other plastic wrapper', 'Single-use carrier bag', 'Polypropylene bag', 'Crisp packet', 'Spread tub', 'Tupperware', 'Disposable food container', 'Foam food container', 'Other plastic container', 'Plastic glooves', 'Plastic utensils', 'Pop tab', 'Rope & strings', 'Scrap metal', 'Shoe', 'Squeezable tube', 'Plastic straw', 'Paper straw', 'Styrofoam piece', 'Unlabeled litter', 'Cigarette']
"""
    
    yaml_path = f"{output_dir}/dataset.yaml"
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)
    
    print(f"✓ Creado {yaml_path}")

def main():
    print("\n" + "="*60)
    print("   PIPELINE PROFESIONAL DE ENTRENAMIENTO")
    print("   ARVE ELITE v6.0")
    print("="*60)
    
    # Paso 1: Augmentar dataset
    print("\n1️⃣  AUGMENTACIÓN DE DATOS")
    generador = GeneradorDataAugmented()
    generador.aumentar_dataset(augmentaciones_por_imagen=5)
    
    # Crear dataset.yaml para datos aumentados
    crear_dataset_yaml()
    
    # Paso 2: Entrenar
    print("\n2️⃣  ENTRENAMIENTO")
    entrenador = EntrenadorProfesional(
        dataset_yaml='dataset_taco_augmented/dataset.yaml'
    )
    entrenador.entrenar_yolov8(epochs=300, imgsz=416)
    
    # Paso 3: Validar
    print("\n3️⃣  VALIDACIÓN")
    entrenador.validar_completo()
    
    # Paso 4: Exportar
    print("\n4️⃣  EXPORTACIÓN")
    entrenador.exportar_optimizado()
    
    print("\n" + "="*60)
    print("✅ PIPELINE COMPLETADO")
    print("   Tu modelo está listo para usar en ARVE ELITE")
    print("="*60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⛔ Entrenamiento cancelado")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
