"""Visualization utilities."""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import random


# Color palette for component classes (BGR format for OpenCV)
COMPONENT_COLORS = [
    (255, 0, 0),      # blue - glass_insulator
    (0, 255, 0),      # green - polymer_insulator
    (0, 0, 255),      # red - yoke_suspension
    (255, 255, 0),    # cyan - clamp
    (255, 0, 255),    # magenta - vari_grip
    (0, 255, 255),    # yellow - lightning_rod_suspension
]

# Color palette for defect classes (BGR format)
DEFECT_COLORS = [
    (0, 255, 0),      # green - normal
    (0, 0, 255),      # red - rust
    (255, 0, 0),      # blue - broken
    (128, 128, 128),  # gray - missing_part
    (0, 165, 255),    # orange - pollution_flashover
]


def draw_bbox(
    img: np.ndarray,
    bbox: Tuple[int, int, int, int],
    label: str,
    color: Tuple[int, int, int],
    confidence: Optional[float] = None,
    thickness: int = 2
) -> np.ndarray:
    """
    Draw bounding box on image.
    
    Args:
        img: Image array (BGR)
        bbox: (x1, y1, x2, y2)
        label: Text label
        color: BGR color tuple
        confidence: Optional confidence score
        thickness: Line thickness
    
    Returns:
        Annotated image
    """
    img = img.copy()
    x1, y1, x2, y2 = bbox
    
    # Draw rectangle
    cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)
    
    # Prepare label text
    if confidence is not None:
        label_text = f"{label} {confidence:.2f}"
    else:
        label_text = label
    
    # Get text size
    (text_width, text_height), baseline = cv2.getTextSize(
        label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
    )
    
    # Draw label background
    cv2.rectangle(
        img,
        (x1, y1 - text_height - baseline - 5),
        (x1 + text_width, y1),
        color,
        -1
    )
    
    # Draw label text
    cv2.putText(
        img,
        label_text,
        (x1, y1 - baseline - 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
        cv2.LINE_AA
    )
    
    return img


def visualize_detections(
    img_path: Path,
    detections: List[Tuple[int, Tuple[int, int, int, int], Optional[float]]],
    class_names: List[str],
    colors: List[Tuple[int, int, int]],
    output_path: Optional[Path] = None
) -> np.ndarray:
    """
    Visualize detection boxes on image.
    
    Args:
        img_path: Path to image
        detections: List of (class_id, (x1, y1, x2, y2), confidence)
        class_names: List of class names
        colors: List of BGR color tuples
        output_path: Optional path to save annotated image
    
    Returns:
        Annotated image array
    """
    img = cv2.imread(str(img_path))
    if img is None:
        raise ValueError(f"Could not load image: {img_path}")
    
    for class_id, bbox, confidence in detections:
        if class_id >= len(class_names):
            continue
        label = class_names[class_id]
        color = colors[class_id % len(colors)]
        img = draw_bbox(img, bbox, label, color, confidence)
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), img)
    
    return img


def visualize_classification_samples(
    dataset_dir: Path,
    output_dir: Path,
    samples_per_class: int = 5,
    grid_cols: int = 5
) -> None:
    """
    Create a grid visualization of classification samples.
    
    Args:
        dataset_dir: Directory with class subdirectories
        output_dir: Output directory for visualization
        samples_per_class: Number of samples per class
        grid_cols: Number of columns in grid
    """
    from .io import get_image_paths, ensure_dir
    
    output_dir = Path(output_dir)
    ensure_dir(output_dir)
    
    class_dirs = sorted([d for d in dataset_dir.iterdir() if d.is_dir()])
    
    for class_dir in class_dirs:
        class_name = class_dir.name
        images = get_image_paths(class_dir)
        
        if not images:
            continue
        
        # Sample images
        sample_images = random.sample(images, min(samples_per_class, len(images)))
        
        # Create grid
        grid_rows = (len(sample_images) + grid_cols - 1) // grid_cols
        grid_height = 224 * grid_rows
        grid_width = 224 * grid_cols
        grid_img = np.zeros((grid_height, grid_width, 3), dtype=np.uint8)
        
        for idx, img_path in enumerate(sample_images):
            row = idx // grid_cols
            col = idx % grid_cols
            
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            
            # Resize to 224x224
            img_resized = cv2.resize(img, (224, 224))
            
            # Place in grid
            y1 = row * 224
            y2 = y1 + 224
            x1 = col * 224
            x2 = x1 + 224
            grid_img[y1:y2, x1:x2] = img_resized
        
        # Add class name label
        cv2.putText(
            grid_img,
            class_name,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )
        
        # Save grid
        output_path = output_dir / f"{class_name}_samples.jpg"
        cv2.imwrite(str(output_path), grid_img)
        print(f"Saved visualization: {output_path}")
