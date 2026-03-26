"""Common utilities for format converters."""

from pathlib import Path
from typing import List, Tuple, Dict, Optional
import json
import yaml


def load_label_mapping(mapping_config_path: Path, dataset_name: str) -> Dict[str, Optional[str]]:
    """
    Load label mapping for a specific dataset.
    
    Args:
        mapping_config_path: Path to label_mapping.yaml
        dataset_name: Name of the dataset
    
    Returns:
        Dictionary mapping dataset labels to unified labels (or None to ignore)
    """
    with open(mapping_config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    mappings = config.get('mappings', {})
    return mappings.get(dataset_name, {})


def map_label(
    dataset_label: str,
    mapping: Dict[str, Optional[str]],
    case_sensitive: bool = False
) -> Optional[str]:
    """
    Map a dataset label to unified label.
    
    Args:
        dataset_label: Original label from dataset
        mapping: Label mapping dictionary
        case_sensitive: Whether mapping is case-sensitive
    
    Returns:
        Unified label name or None if label should be ignored
    """
    if case_sensitive:
        return mapping.get(dataset_label)
    else:
        # Case-insensitive lookup
        dataset_label_lower = dataset_label.lower()
        for key, value in mapping.items():
            if key.lower() == dataset_label_lower:
                return value
        return None


def normalize_bbox(
    x1: float, y1: float, x2: float, y2: float,
    img_width: int, img_height: int
) -> Tuple[float, float, float, float]:
    """
    Normalize bounding box coordinates to [0, 1] range.
    
    Args:
        x1, y1, x2, y2: Bounding box coordinates (absolute pixels)
        img_width, img_height: Image dimensions
    
    Returns:
        (x_center, y_center, width, height) normalized to [0, 1]
    """
    # Clamp to image bounds
    x1 = max(0, min(x1, img_width - 1))
    y1 = max(0, min(y1, img_height - 1))
    x2 = max(0, min(x2, img_width - 1))
    y2 = max(0, min(y2, img_height - 1))
    
    # Calculate center and dimensions
    width = abs(x2 - x1)
    height = abs(y2 - y1)
    x_center = (x1 + x2) / 2.0
    y_center = (y1 + y2) / 2.0
    
    # Normalize
    x_center_norm = x_center / img_width
    y_center_norm = y_center / img_height
    width_norm = width / img_width
    height_norm = height / img_height
    
    return (x_center_norm, y_center_norm, width_norm, height_norm)


def validate_yolo_bbox(
    x_center: float, y_center: float, width: float, height: float
) -> bool:
    """
    Validate YOLO format bounding box coordinates.
    
    Args:
        x_center, y_center, width, height: Normalized coordinates [0, 1]
    
    Returns:
        True if valid, False otherwise
    """
    if not (0 <= x_center <= 1):
        return False
    if not (0 <= y_center <= 1):
        return False
    if not (0 < width <= 1):
        return False
    if not (0 < height <= 1):
        return False
    if not (0 <= x_center - width/2):
        return False
    if not (x_center + width/2 <= 1):
        return False
    if not (0 <= y_center - height/2):
        return False
    if not (y_center + height/2 <= 1):
        return False
    return True


def get_unified_class_id(
    unified_label: str,
    components_config_path: Path
) -> Optional[int]:
    """
    Get unified class ID for a label.
    
    Args:
        unified_label: Unified label name
        components_config_path: Path to components.yaml
    
    Returns:
        Class ID (0-indexed) or None if not found
    """
    with open(components_config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    names = config.get('names', [])
    try:
        return names.index(unified_label)
    except ValueError:
        return None


def write_yolo_label(
    label_path: Path,
    annotations: List[Tuple[int, float, float, float, float]]
) -> None:
    """
    Write YOLO format label file.
    
    Args:
        label_path: Output label file path
        annotations: List of (class_id, x_center, y_center, width, height) tuples
    """
    label_path.parent.mkdir(parents=True, exist_ok=True)
    with open(label_path, 'w') as f:
        for class_id, x_center, y_center, width, height in annotations:
            f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
