"""Convert COCO format to unified YOLO format."""

from pathlib import Path
from typing import List, Tuple, Dict, Optional
import json
from PIL import Image
from .common import (
    load_label_mapping, map_label, get_unified_class_id,
    normalize_bbox, validate_yolo_bbox, write_yolo_label
)


def convert_coco_dataset(
    dataset_path: Path,
    images_dir: str,
    ann_path: str,
    output_dir: Path,
    dataset_name: str,
    mapping_config_path: Path,
    components_config_path: Path,
    max_images: Optional[int] = None
) -> Dict[str, int]:
    """
    Convert COCO format dataset to unified YOLO format.
    
    Args:
        dataset_path: Root path of source dataset
        images_dir: Relative path to images directory
        ann_path: Relative path to COCO JSON annotation file
        output_dir: Output directory for converted labels
        dataset_name: Name of dataset (for mapping lookup)
        mapping_config_path: Path to label_mapping.yaml
        components_config_path: Path to components.yaml
        max_images: Maximum number of images to process (None = all)
    
    Returns:
        Dictionary with conversion statistics
    """
    images_path = dataset_path / images_dir
    ann_file_path = dataset_path / ann_path
    
    if not images_path.exists():
        raise ValueError(f"Images directory not found: {images_path}")
    if not ann_file_path.exists():
        raise ValueError(f"Annotation file not found: {ann_file_path}")
    
    # Load COCO annotations
    with open(ann_file_path, 'r', encoding='utf-8') as f:
        coco_data = json.load(f)
    
    # Build mappings
    categories = {cat['id']: cat['name'] for cat in coco_data.get('categories', [])}
    images_dict = {img['id']: img for img in coco_data.get('images', [])}
    annotations_dict = {}
    for ann in coco_data.get('annotations', []):
        image_id = ann['image_id']
        if image_id not in annotations_dict:
            annotations_dict[image_id] = []
        annotations_dict[image_id].append(ann)
    
    # Load label mapping
    label_mapping = load_label_mapping(mapping_config_path, dataset_name)
    
    stats = {
        'total_images': len(images_dict),
        'converted_images': 0,
        'skipped_images': 0,
        'total_boxes': 0,
        'mapped_boxes': 0,
        'ignored_boxes': 0
    }
    
    # Process images
    image_list = list(images_dict.values())
    if max_images:
        image_list = image_list[:max_images]
    
    for img_info in image_list:
        image_id = img_info['id']
        img_filename = img_info['file_name']
        img_width = img_info['width']
        img_height = img_info['height']
        
        img_path = images_path / img_filename
        if not img_path.exists():
            stats['skipped_images'] += 1
            continue
        
        # Get annotations for this image
        annotations = annotations_dict.get(image_id, [])
        
        # Convert annotations
        converted_annotations = []
        for ann in annotations:
            stats['total_boxes'] += 1
            
            # Get category
            category_id = ann['category_id']
            if category_id not in categories:
                stats['ignored_boxes'] += 1
                continue
            
            dataset_label = categories[category_id]
            
            # Map to unified label
            unified_label = map_label(dataset_label, label_mapping)
            if unified_label is None:
                stats['ignored_boxes'] += 1
                continue
            
            # Get unified class ID
            unified_class_id = get_unified_class_id(unified_label, components_config_path)
            if unified_class_id is None:
                stats['ignored_boxes'] += 1
                continue
            
            # Convert bbox from COCO format [x, y, width, height] to YOLO format
            bbox = ann['bbox']  # [x, y, width, height]
            x1 = bbox[0]
            y1 = bbox[1]
            x2 = x1 + bbox[2]
            y2 = y1 + bbox[3]
            
            # Normalize to YOLO format
            x_center, y_center, width, height = normalize_bbox(
                x1, y1, x2, y2, img_width, img_height
            )
            
            # Validate
            if not validate_yolo_bbox(x_center, y_center, width, height):
                stats['ignored_boxes'] += 1
                continue
            
            converted_annotations.append((unified_class_id, x_center, y_center, width, height))
            stats['mapped_boxes'] += 1
        
        # Write converted label
        output_label_path = output_dir / f"{dataset_name}_{img_path.stem}.txt"
        write_yolo_label(output_label_path, converted_annotations)
        
        # Copy image with renamed filename
        output_img_path = output_dir.parent / "images" / f"{dataset_name}_{img_path.name}"
        output_img_path.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(img_path, output_img_path)
        
        stats['converted_images'] += 1
    
    return stats
