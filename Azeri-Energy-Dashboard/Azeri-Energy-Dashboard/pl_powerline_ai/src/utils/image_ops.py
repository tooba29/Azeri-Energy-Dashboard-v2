"""Image operations utilities."""

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image


def load_image(path: Path) -> Optional[np.ndarray]:
    """Load image as BGR numpy array."""
    img = cv2.imread(str(path))
    return img


def get_image_size(path: Path) -> Optional[Tuple[int, int]]:
    """Get image dimensions (width, height) without loading full image."""
    try:
        with Image.open(path) as img:
            return img.size  # (width, height)
    except Exception:
        return None


def is_valid_image(path: Path) -> bool:
    """Check if image file is valid and can be loaded."""
    try:
        img = load_image(path)
        return img is not None and img.size > 0
    except Exception:
        return False


def crop_roi(
    img: np.ndarray,
    bbox: Tuple[int, int, int, int],
    padding_ratio: float = 0.1,
    min_size: int = 32
) -> Optional[np.ndarray]:
    """
    Crop region of interest from image with padding.
    
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
