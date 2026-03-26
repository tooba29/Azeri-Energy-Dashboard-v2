"""Classification pipeline for Stage B."""

from pathlib import Path
from typing import Tuple
from ultralytics import YOLO
import cv2
import numpy as np


class ClassificationPipeline:
    """Pipeline for defect classification (Stage B)."""
    
    def __init__(self, model_path: Path):
        """
        Initialize classification pipeline.
        
        Args:
            model_path: Path to trained YOLO classifier weights
        """
        self.model = YOLO(str(model_path))
    
    def predict(self, crop_image: np.ndarray) -> Tuple[int, float]:
        """
        Classify defect in cropped component image.
        
        Args:
            crop_image: Cropped image array (BGR)
        
        Returns:
            (class_id, confidence) tuple
        """
        results = self.model.predict(crop_image, verbose=False)
        
        if not results or len(results) == 0:
            return (0, 0.0)  # Default to normal with 0 confidence
        
        result = results[0]
        if hasattr(result, 'probs') and result.probs is not None:
            class_id = int(result.probs.top1)
            confidence = float(result.probs.top1conf)
        else:
            # Fallback
            class_id = 0
            confidence = 0.0
        
        return (class_id, confidence)
    
    def predict_from_path(self, crop_path: Path) -> Tuple[int, float]:
        """
        Classify defect from image file path.
        
        Args:
            crop_path: Path to cropped image
        
        Returns:
            (class_id, confidence) tuple
        """
        img = cv2.imread(str(crop_path))
        if img is None:
            return (0, 0.0)
        return self.predict(img)
