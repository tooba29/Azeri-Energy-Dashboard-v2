"""Full inference pipeline combining Stage A and Stage B."""

from pathlib import Path
from typing import List, Dict, Any
import cv2
import csv
from .detect_pipeline import DetectionPipeline
from .cls_pipeline import ClassificationPipeline
from ..utils.crops import crop_component
from ..utils.viz import draw_bbox, COMPONENT_COLORS, DEFECT_COLORS
from ..utils.io import get_image_paths, ensure_dir, save_json


class FullInferencePipeline:
    """End-to-end pipeline: Detection -> Classification -> Export."""
    
    def __init__(
        self,
        detector_model_path: Path,
        classifier_model_path: Path,
        component_class_names: List[str],
        defect_class_names: List[str],
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        padding_ratio: float = 0.1
    ):
        """
        Initialize full inference pipeline.
        
        Args:
            detector_model_path: Path to Stage A detector weights
            classifier_model_path: Path to Stage B classifier weights
            component_class_names: List of component class names
            defect_class_names: List of defect class names
            conf_threshold: Detection confidence threshold
            iou_threshold: Detection IoU threshold
            padding_ratio: Padding ratio for crops
        """
        self.detector = DetectionPipeline(detector_model_path, conf_threshold, iou_threshold)
        self.classifier = ClassificationPipeline(classifier_model_path)
        self.component_class_names = component_class_names
        self.defect_class_names = defect_class_names
        self.padding_ratio = padding_ratio
    
    def process_image(self, image_path: Path) -> Dict[str, Any]:
        """
        Process single image through both stages.
        
        Args:
            image_path: Path to input image
        
        Returns:
            Dictionary with detection and classification results
        """
        # Load image
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        h, w = img.shape[:2]
        
        # Stage A: Detection
        detections = self.detector.predict(image_path)
        
        # Stage B: Classification for each detection
        results = []
        for class_id, bbox, component_conf in detections:
            # Crop component
            crop = crop_component(img, bbox, self.padding_ratio, min_size=32)
            if crop is None:
                continue
            
            # Classify defect
            defect_class_id, defect_conf = self.classifier.predict(crop)
            
            results.append({
                'component_class': self.component_class_names[class_id] if class_id < len(self.component_class_names) else f'class_{class_id}',
                'component_class_id': class_id,
                'component_conf': float(component_conf),
                'bbox_xyxy': [int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])],
                'defect_class': self.defect_class_names[defect_class_id] if defect_class_id < len(self.defect_class_names) else f'class_{defect_class_id}',
                'defect_class_id': defect_class_id,
                'defect_conf': float(defect_conf)
            })
        
        return {
            'image_name': image_path.name,
            'width': w,
            'height': h,
            'detections': results
        }
    
    def process_directory(
        self,
        source_dir: Path,
        output_dir: Path,
        save_annotated: bool = True,
        save_json: bool = True,
        save_csv: bool = True
    ) -> Dict[str, Any]:
        """
        Process all images in directory.
        
        Args:
            source_dir: Directory with input images
            output_dir: Output directory for results
            save_annotated: Whether to save annotated images
            save_json: Whether to save JSON per image
            save_csv: Whether to save summary CSV
        
        Returns:
            Summary statistics
        """
        ensure_dir(output_dir)
        
        if save_annotated:
            annotated_dir = output_dir / 'annotated'
            ensure_dir(annotated_dir)
        
        if save_json:
            json_dir = output_dir / 'json'
            ensure_dir(json_dir)
        
        # Get all images
        images = get_image_paths(source_dir)
        
        all_results = []
        summary_stats = {
            'total_images': len(images),
            'total_detections': 0,
            'defect_counts': {name: 0 for name in self.defect_class_names},
            'component_counts': {name: 0 for name in self.component_class_names}
        }
        
        for img_path in images:
            # Process image
            result = self.process_image(img_path)
            all_results.append(result)
            
            # Update stats
            summary_stats['total_detections'] += len(result['detections'])
            for det in result['detections']:
                defect_class = det['defect_class']
                component_class = det['component_class']
                if defect_class in summary_stats['defect_counts']:
                    summary_stats['defect_counts'][defect_class] += 1
                if component_class in summary_stats['component_counts']:
                    summary_stats['component_counts'][component_class] += 1
            
            # Save annotated image
            if save_annotated:
                annotated_img = self._annotate_image(img_path, result)
                annotated_path = annotated_dir / img_path.name
                cv2.imwrite(str(annotated_path), annotated_img)
            
            # Save JSON
            if save_json:
                json_path = json_dir / f"{img_path.stem}.json"
                save_json(result, json_path)
        
        # Save summary CSV
        if save_csv:
            csv_path = output_dir / 'summary.csv'
            self._save_summary_csv(csv_path, all_results, summary_stats)
        
        # Save summary JSON
        summary_json_path = output_dir / 'summary.json'
        save_json(summary_stats, summary_json_path)
        
        return summary_stats
    
    def _annotate_image(self, image_path: Path, result: Dict[str, Any]) -> cv2.typing.MatLike:
        """Annotate image with detections and classifications."""
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        for det in result['detections']:
            bbox = det['bbox_xyxy']
            component_class = det['component_class']
            component_conf = det['component_conf']
            defect_class = det['defect_class']
            defect_conf = det['defect_conf']
            
            # Use component color for box
            component_id = det['component_class_id']
            color = COMPONENT_COLORS[component_id % len(COMPONENT_COLORS)]
            
            # Label includes both component and defect
            label = f"{component_class} ({defect_class})"
            if component_conf < 1.0:  # Only show confidence if not GT
                label += f" {component_conf:.2f}"
            
            img = draw_bbox(img, tuple(bbox), label, color, None)
        
        return img
    
    def _save_summary_csv(self, csv_path: Path, all_results: List[Dict], summary_stats: Dict):
        """Save summary CSV report."""
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow(['Image', 'Component', 'Defect', 'Confidence'])
            
            # Data rows
            for result in all_results:
                for det in result['detections']:
                    writer.writerow([
                        result['image_name'],
                        det['component_class'],
                        det['defect_class'],
                        f"{det['defect_conf']:.3f}"
                    ])
            
            # Summary section
            writer.writerow([])
            writer.writerow(['Summary'])
            writer.writerow(['Total Images', summary_stats['total_images']])
            writer.writerow(['Total Detections', summary_stats['total_detections']])
            writer.writerow([])
            writer.writerow(['Defect Counts'])
            for defect, count in summary_stats['defect_counts'].items():
                writer.writerow([defect, count])
            writer.writerow([])
            writer.writerow(['Component Counts'])
            for component, count in summary_stats['component_counts'].items():
                writer.writerow([component, count])
