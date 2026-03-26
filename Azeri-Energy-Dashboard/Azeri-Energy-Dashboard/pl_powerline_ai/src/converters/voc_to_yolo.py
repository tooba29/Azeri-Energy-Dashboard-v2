"""Convert Pascal VOC format to unified YOLO format."""

from pathlib import Path
from typing import List, Tuple, Dict, Optional
import xml.etree.ElementTree as ET
from PIL import Image
from .common import (
    load_label_mapping, map_label, get_unified_class_id,
    normalize_bbox, validate_yolo_bbox, write_yolo_label
)


def parse_voc_xml(xml_path: Path) -> Tuple[str, int, int, List[Tuple[str, float, float, float, float]]]:
    """
    Parse Pascal VOC XML annotation file.
    
    Returns:
        (filename, width, height, [(class_name, x1, y1, x2, y2), ...])
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    filename = root.find('filename').text
    size = root.find('size')
    width = int(size.find('width').text)
    height = int(size.find('height').text)
    
    objects = []
    for obj in root.findall('object'):
        class_name = obj.find('name').text
        bbox = obj.find('bndbox')
        x1 = float(bbox.find('xmin').text)
        y1 = float(bbox.find('ymin').text)
        x2 = float(bbox.find('xmax').text)
        y2 = float(bbox.find('ymax').text)
        objects.append((class_name, x1, y1, x2, y2))
    
    return (filename, width, height, objects)


def convert_voc_dataset(
    dataset_path: Path,
    images_dir: str,
    ann_dir: str,
    output_dir: Path,
    dataset_name: str,
    mapping_config_path: Path,
    components_config_path: Path,
    max_images: Optional[int] = None
) -> Dict[str, int]:
    """
    Convert Pascal VOC format dataset to unified YOLO format.
    
    Args:
        dataset_path: Root path of source dataset
        images_dir: Relative path to images directory
        ann_dir: Relative path to annotations directory
        output_dir: Output directory for converted labels
        dataset_name: Name of dataset (for mapping lookup)
        mapping_config_path: Path to label_mapping.yaml
        components_config_path: Path to components.yaml
        max_images: Maximum number of images to process (None = all)
    
    Returns:
        Dictionary with conversion statistics
    """
    images_path = dataset_path / images_dir
    ann_path = dataset_path / ann_dir
    
    if not images_path.exists():
        raise ValueError(f"Images directory not found: {images_path}")
    if not ann_path.exists():
        raise ValueError(f"Annotations directory not found: {ann_path}")
    
    # Load label mapping
    label_mapping = load_label_mapping(mapping_config_path, dataset_name)
    
    # Get all XML files
    xml_files = sorted(list(ann_path.glob('*.xml')))
    if max_images:
        xml_files = xml_files[:max_images]
    
    stats = {
        'total_images': len(xml_files),
        'converted_images': 0,
        'skipped_images': 0,
        'total_boxes': 0,
        'mapped_boxes': 0,
        'ignored_boxes': 0
    }
    
    for xml_path in xml_files:
        try:
            filename, img_width, img_height, objects = parse_voc_xml(xml_path)
        except Exception as e:
            print(f"Warning: Failed to parse {xml_path}: {e}")
            stats['skipped_images'] += 1
            continue
        
        # Find corresponding image
        img_path = images_path / filename
        if not img_path.exists():
            # Try with different extensions
            found = False
            for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                alt_path = images_path / f"{xml_path.stem}{ext}"
                if alt_path.exists():
                    img_path = alt_path
                    found = True
                    break
            if not found:
                stats['skipped_images'] += 1
                continue
        
        # Convert annotations
        converted_annotations = []
        for class_name, x1, y1, x2, y2 in objects:
            stats['total_boxes'] += 1
            
            # Map to unified label
            unified_label = map_label(class_name, label_mapping)
            if unified_label is None:
                stats['ignored_boxes'] += 1
                continue
            
            # Get unified class ID
            unified_class_id = get_unified_class_id(unified_label, components_config_path)
            if unified_class_id is None:
                stats['ignored_boxes'] += 1
                continue
            
            # Normalize bbox to YOLO format
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
        output_label_path = output_dir / f"{dataset_name}_{xml_path.stem}.txt"
        write_yolo_label(output_label_path, converted_annotations)
        
        # Copy image with renamed filename
        output_img_path = output_dir.parent / "images" / f"{dataset_name}_{img_path.name}"
        output_img_path.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(img_path, output_img_path)
        
        stats['converted_images'] += 1
    
    return stats
