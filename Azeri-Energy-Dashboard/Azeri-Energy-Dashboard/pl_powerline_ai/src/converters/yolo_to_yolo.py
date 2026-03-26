"""Convert YOLO format to unified YOLO format."""

from pathlib import Path
from typing import List, Tuple, Dict, Optional
from .common import (
    load_label_mapping, map_label, get_unified_class_id,
    validate_yolo_bbox, write_yolo_label
)
import yaml


def read_yolo_label(label_path: Path) -> List[Tuple[int, str, float, float, float, float]]:
    """
    Read YOLO format label file.
    
    Returns:
        List of (class_id, class_name, x_center, y_center, width, height) tuples
        Note: class_name is placeholder, will be resolved via mapping
    """
    annotations = []
    if not label_path.exists():
        return annotations
    
    with open(label_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 5:
                continue
            class_id = int(parts[0])
            x_center = float(parts[1])
            y_center = float(parts[2])
            width = float(parts[3])
            height = float(parts[4])
            annotations.append((class_id, "", x_center, y_center, width, height))
    
    return annotations


def convert_yolo_dataset(
    dataset_path: Path,
    images_dir: str,
    labels_dir: str,
    output_dir: Path,
    dataset_name: str,
    mapping_config_path: Path,
    components_config_path: Path,
    class_name_mapping: Optional[Dict[int, str]] = None,
    max_images: Optional[int] = None
) -> Dict[str, int]:
    """
    Convert YOLO format dataset to unified YOLO format.
    
    Args:
        dataset_path: Root path of source dataset
        images_dir: Relative path to images directory
        labels_dir: Relative path to labels directory
        output_dir: Output directory for converted dataset
        dataset_name: Name of dataset (for mapping lookup)
        mapping_config_path: Path to label_mapping.yaml
        components_config_path: Path to components.yaml
        class_name_mapping: Optional mapping from class_id to class_name (if available)
        max_images: Maximum number of images to process (None = all)
    
    Returns:
        Dictionary with conversion statistics
    """
    from ...utils.io import get_image_paths
    
    images_path = dataset_path / images_dir
    labels_path = dataset_path / labels_dir
    
    if not images_path.exists():
        raise ValueError(f"Images directory not found: {images_path}")
    if not labels_path.exists():
        raise ValueError(f"Labels directory not found: {labels_path}")
    
    # Load mappings
    label_mapping = load_label_mapping(mapping_config_path, dataset_name)
    
    # Get class name mapping if not provided
    if class_name_mapping is None:
        # Try to load from dataset if available, otherwise use empty dict
        class_name_mapping = {}
    
    # Get all images
    images = get_image_paths(images_path)
    if max_images:
        images = images[:max_images]
    
    stats = {
        'total_images': len(images),
        'converted_images': 0,
        'skipped_images': 0,
        'total_boxes': 0,
        'mapped_boxes': 0,
        'ignored_boxes': 0
    }
    
    for img_path in images:
        label_path = labels_path / f"{img_path.stem}.txt"
        
        if not label_path.exists():
            stats['skipped_images'] += 1
            continue
        
        # Read original annotations
        annotations = read_yolo_label(label_path)
        
        if not annotations:
            # Empty label file - create empty output file
            output_label_path = output_dir / f"{dataset_name}_{img_path.stem}.txt"
            output_label_path.parent.mkdir(parents=True, exist_ok=True)
            output_label_path.write_text("")
            stats['converted_images'] += 1
            continue
        
        # Convert annotations
        converted_annotations = []
        for orig_class_id, _, x_center, y_center, width, height in annotations:
            stats['total_boxes'] += 1
            
            # Get class name from mapping or use placeholder
            if orig_class_id in class_name_mapping:
                dataset_label = class_name_mapping[orig_class_id]
            else:
                # If no class name mapping, we can't map - skip
                stats['ignored_boxes'] += 1
                continue
            
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
            
            # Validate bbox
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
