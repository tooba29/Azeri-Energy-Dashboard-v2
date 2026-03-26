"""YOLO format utilities."""

from pathlib import Path
from typing import List, Tuple, Optional
import numpy as np


def read_yolo_label(label_path: Path) -> List[Tuple[int, float, float, float, float]]:
    """
    Read YOLO format label file.
    
    Returns:
        List of (class_id, x_center, y_center, width, height) tuples (normalized 0-1)
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
            annotations.append((class_id, x_center, y_center, width, height))
    
    return annotations


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


def yolo_to_xyxy(
    x_center: float,
    y_center: float,
    width: float,
    height: float,
    img_width: int,
    img_height: int
) -> Tuple[int, int, int, int]:
    """
    Convert YOLO normalized format to absolute xyxy coordinates.
    
    Returns:
        (x1, y1, x2, y2) in absolute pixel coordinates
    """
    x1 = int((x_center - width / 2) * img_width)
    y1 = int((y_center - height / 2) * img_height)
    x2 = int((x_center + width / 2) * img_width)
    y2 = int((y_center + height / 2) * img_height)
    
    # Clamp to image bounds
    x1 = max(0, min(x1, img_width - 1))
    y1 = max(0, min(y1, img_height - 1))
    x2 = max(0, min(x2, img_width - 1))
    y2 = max(0, min(y2, img_height - 1))
    
    return (x1, y1, x2, y2)


def xyxy_to_yolo(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    img_width: int,
    img_height: int
) -> Tuple[float, float, float, float]:
    """
    Convert absolute xyxy coordinates to YOLO normalized format.
    
    Returns:
        (x_center, y_center, width, height) normalized 0-1
    """
    # Clamp to image bounds
    x1 = max(0, min(x1, img_width - 1))
    y1 = max(0, min(y1, img_height - 1))
    x2 = max(0, min(x2, img_width - 1))
    y2 = max(0, min(y2, img_height - 1))
    
    width = abs(x2 - x1)
    height = abs(y2 - y1)
    
    x_center = (x1 + x2) / 2.0 / img_width
    y_center = (y1 + y2) / 2.0 / img_height
    width_norm = width / img_width
    height_norm = height / img_height
    
    return (x_center, y_center, width_norm, height_norm)


def validate_yolo_coords(
    x_center: float,
    y_center: float,
    width: float,
    height: float
) -> bool:
    """Validate YOLO coordinates are within [0, 1] and dimensions > 0."""
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
