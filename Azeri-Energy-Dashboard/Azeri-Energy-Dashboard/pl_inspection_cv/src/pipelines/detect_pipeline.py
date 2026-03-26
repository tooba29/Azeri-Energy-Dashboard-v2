"""Detection pipeline for Stage A."""

from pathlib import Path
from typing import List, Tuple, Optional
from ultralytics import YOLO
import numpy as np


class DetectionPipeline:
    """Pipeline for component detection (Stage A)."""
    
    def __init__(self, model_path: Path, conf_threshold: float = 0.25, iou_threshold: float = 0.45):
        """
        Initialize detection pipeline.
        
        Args:
            model_path: Path to trained YOLO detector weights
            conf_threshold: Confidence threshold for detections
            iou_threshold: IoU threshold for NMS
        """
        self.model = YOLO(str(model_path))
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
    
    def predict(self, image_path: Path) -> List[Tuple[int, Tuple[int, int, int, int], float]]:
        """
        Run detection on single image.
        
        Args:
            image_path: Path to image
        
        Returns:
            List of (class_id, (x1, y1, x2, y2), confidence) tuples
        """
        results = self.model.predict(
            str(image_path),
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            verbose=False
        )
        
        detections = []
        for result in results:
            boxes = result.boxes
            for box in boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                bbox = box.xyxy[0].cpu().numpy().astype(int)
                bbox_tuple = (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
                detections.append((class_id, bbox_tuple, confidence))
        
        return detections
    
    def predict_batch(self, image_paths: List[Path]) -> List[List[Tuple[int, Tuple[int, int, int, int], float]]]:
        """
        Run detection on batch of images.
        
        Args:
            image_paths: List of image paths
        
        Returns:
            List of detection lists (one per image)
        """
        all_detections = []
        for img_path in image_paths:
            detections = self.predict(img_path)
            all_detections.append(detections)
        return all_detections
