"""Crop generation utilities."""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from .yolo import yolo_to_xyxy
from .io import ensure_dir


def crop_component(
    img: np.ndarray,
    bbox: Tuple[int, int, int, int],
    padding_ratio: float = 0.1,
    min_size: int = 32
) -> Optional[np.ndarray]:
    """
    Crop component from image with padding.
    
    Args:
        img: Image array (BGR)
        bbox: (x1, y1, x2, y2) in absolute coordinates
        padding_ratio: Padding ratio (0.1 = 10% padding on each side)
        min_size: Minimum crop size in pixels
    
    Returns:
        Cropped image or None if too small
    """
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox
    
    # Calculate padding
    box_w = x2 - x1
    box_h = y2 - y1
    pad_w = int(box_w * padding_ratio)
    pad_h = int(box_h * padding_ratio)
    
    # Apply padding
    x1 = max(0, x1 - pad_w)
    y1 = max(0, y1 - pad_h)
    x2 = min(w, x2 + pad_w)
    y2 = min(h, y2 + pad_h)
    
    # Check minimum size
    if (x2 - x1) < min_size or (y2 - y1) < min_size:
        return None
    
    # Crop
    crop = img[y1:y2, x1:x2]
    return crop


def save_crop_with_metadata(
    crop: np.ndarray,
    output_path: Path,
    metadata: Dict
) -> None:
    """
    Save crop image with metadata in filename or sidecar JSON.
    
    Args:
        crop: Cropped image array
        output_path: Output path for crop
        metadata: Dictionary with metadata (original_image, component_class, bbox_xyxy, confidence)
    """
    ensure_dir(output_path.parent)
    cv2.imwrite(str(output_path), crop)
    
    # Save sidecar JSON with metadata
    json_path = output_path.with_suffix('.json')
    import json
    with open(json_path, 'w') as f:
        json.dump(metadata, f, indent=2)


def generate_crops_from_yolo_labels(
    images_dir: Path,
    labels_dir: Path,
    output_dir: Path,
    component_class_names: List[str],
    padding_ratio: float = 0.1,
    min_box_size: int = 32,
    balance_classes: bool = False
) -> Dict[str, int]:
    """
    Generate crops from YOLO ground-truth labels.
    
    Args:
        images_dir: Directory with images
        labels_dir: Directory with YOLO label files
        output_dir: Output directory for crops (organized by component class)
        component_class_names: List of component class names
        padding_ratio: Padding ratio for crops
        min_box_size: Minimum box size in pixels
        balance_classes: Whether to balance number of crops per class
    
    Returns:
        Dictionary with crop counts per component class
    """
    from .io import get_image_paths
    from .yolo import read_yolo_label
    import random
    
    output_dir = Path(output_dir)
    crop_counts = {name: 0 for name in component_class_names}
    
    # Create output directories for each component class
    for class_name in component_class_names:
        ensure_dir(output_dir / class_name)
    
    # Get all images
    images = get_image_paths(images_dir)
    
    # Collect all crops first (for balancing)
    all_crops = {name: [] for name in component_class_names}
    
    for img_path in images:
        label_path = labels_dir / f"{img_path.stem}.txt"
        if not label_path.exists():
            continue
        
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        
        h, w = img.shape[:2]
        annotations = read_yolo_label(label_path)
        
        for class_id, x_center, y_center, width, height in annotations:
            if class_id >= len(component_class_names):
                continue
            
            component_class = component_class_names[class_id]
            bbox = yolo_to_xyxy(x_center, y_center, width, height, w, h)
            
            # Check minimum size
            box_w = bbox[2] - bbox[0]
            box_h = bbox[3] - bbox[1]
            if box_w < min_box_size or box_h < min_box_size:
                continue
            
            crop = crop_component(img, bbox, padding_ratio, min_box_size)
            if crop is None:
                continue
            
            # Store crop info
            crop_info = {
                'crop': crop,
                'output_name': f"{img_path.stem}_{class_id}_{crop_counts[component_class]}.jpg",
                'metadata': {
                    'original_image': str(img_path),
                    'component_class': component_class,
                    'component_class_id': class_id,
                    'bbox_xyxy': bbox,
                    'confidence': 1.0  # GT has 100% confidence
                }
            }
            all_crops[component_class].append(crop_info)
    
    # Balance classes if requested
    if balance_classes:
        min_count = min(len(crops) for crops in all_crops.values() if crops)
        for class_name in all_crops:
            if len(all_crops[class_name]) > min_count:
                all_crops[class_name] = random.sample(all_crops[class_name], min_count)
    
    # Save crops
    for component_class, crops in all_crops.items():
        for crop_info in crops:
            output_path = output_dir / component_class / crop_info['output_name']
            save_crop_with_metadata(
                crop_info['crop'],
                output_path,
                crop_info['metadata']
            )
            crop_counts[component_class] += 1
    
    return crop_counts


def generate_crops_from_predictions(
    images_dir: Path,
    detector_model_path: Path,
    output_dir: Path,
    component_class_names: List[str],
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    padding_ratio: float = 0.1,
    min_box_size: int = 32,
    balance_classes: bool = False
) -> Dict[str, int]:
    """
    Generate crops from detector predictions.
    
    Args:
        images_dir: Directory with images
        detector_model_path: Path to trained YOLO detector weights
        output_dir: Output directory for crops
        component_class_names: List of component class names
        conf_threshold: Confidence threshold for detections
        iou_threshold: IoU threshold for NMS
        padding_ratio: Padding ratio for crops
        min_box_size: Minimum box size in pixels
        balance_classes: Whether to balance number of crops per class
    
    Returns:
        Dictionary with crop counts per component class
    """
    from ultralytics import YOLO
    from .io import get_image_paths
    import random
    
    output_dir = Path(output_dir)
    crop_counts = {name: 0 for name in component_class_names}
    
    # Create output directories
    for class_name in component_class_names:
        ensure_dir(output_dir / class_name)
    
    # Load detector
    model = YOLO(str(detector_model_path))
    
    # Get all images
    images = get_image_paths(images_dir)
    
    # Collect all crops first (for balancing)
    all_crops = {name: [] for name in component_class_names}
    
    for img_path in images:
        results = model.predict(
            str(img_path),
            conf=conf_threshold,
            iou=iou_threshold,
            verbose=False
        )
        
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                class_id = int(box.cls[0])
                if class_id >= len(component_class_names):
                    continue
                
                component_class = component_class_names[class_id]
                confidence = float(box.conf[0])
                bbox = box.xyxy[0].cpu().numpy().astype(int)
                bbox = (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
                
                # Check minimum size
                box_w = bbox[2] - bbox[0]
                box_h = bbox[3] - bbox[1]
                if box_w < min_box_size or box_h < min_box_size:
                    continue
                
                crop = crop_component(img, bbox, padding_ratio, min_box_size)
                if crop is None:
                    continue
                
                # Store crop info
                crop_info = {
                    'crop': crop,
                    'output_name': f"{img_path.stem}_{class_id}_{crop_counts[component_class]}.jpg",
                    'metadata': {
                        'original_image': str(img_path),
                        'component_class': component_class,
                        'component_class_id': class_id,
                        'bbox_xyxy': bbox,
                        'confidence': confidence
                    }
                }
                all_crops[component_class].append(crop_info)
    
    # Balance classes if requested
    if balance_classes:
        min_count = min(len(crops) for crops in all_crops.values() if crops)
        for class_name in all_crops:
            if len(all_crops[class_name]) > min_count:
                all_crops[class_name] = random.sample(all_crops[class_name], min_count)
    
    # Save crops
    for component_class, crops in all_crops.items():
        for crop_info in crops:
            output_path = output_dir / component_class / crop_info['output_name']
            save_crop_with_metadata(
                crop_info['crop'],
                output_path,
                crop_info['metadata']
            )
            crop_counts[component_class] += 1
    
    return crop_counts
