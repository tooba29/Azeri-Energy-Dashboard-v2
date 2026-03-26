"""Script 12: Full inference pipeline - Stage A + Stage B with JSON export (CRITICAL)."""

import argparse
from pathlib import Path
from src.utils.io import load_yaml
from src.pipelines.full_inference_pipeline import FullInferencePipeline


def main():
    parser = argparse.ArgumentParser(
        description='Run full inference pipeline: Stage A (detection) -> Stage B (classification) -> Export JSON. '
                    'This is the main inference script for production use.'
    )
    parser.add_argument('--detector-weights', type=str, required=True,
                        help='Path to Stage A detector weights (.pt file)')
    parser.add_argument('--classifier-weights', type=str, required=True,
                        help='Path to Stage B classifier weights (.pt file)')
    parser.add_argument('--source', type=str, required=True,
                        help='Source directory or file (images/videos)')
    parser.add_argument('--output', type=str, default='./outputs/predictions',
                        help='Output directory (default: ./outputs/predictions)')
    parser.add_argument('--components-config', type=str, default='./configs/components.yaml',
                        help='Path to components config YAML (default: ./configs/components.yaml)')
    parser.add_argument('--defects-config', type=str, default='./configs/defects.yaml',
                        help='Path to defects config YAML (default: ./configs/defects.yaml)')
    parser.add_argument('--conf-threshold', type=float, default=0.25,
                        help='Detection confidence threshold (default: 0.25)')
    parser.add_argument('--iou-threshold', type=float, default=0.45,
                        help='Detection IoU threshold for NMS (default: 0.45)')
    parser.add_argument('--padding-ratio', type=float, default=0.1,
                        help='Padding ratio for crops (default: 0.1)')
    parser.add_argument('--no-annotated', action='store_true',
                        help='Skip saving annotated images')
    parser.add_argument('--no-json', action='store_true',
                        help='Skip saving JSON per image')
    parser.add_argument('--no-csv', action='store_true',
                        help='Skip saving summary CSV')
    
    args = parser.parse_args()
    
    detector_weights = Path(args.detector_weights)
    classifier_weights = Path(args.classifier_weights)
    source_path = Path(args.source)
    
    if not detector_weights.exists():
        print(f"Error: Detector weights not found: {detector_weights}")
        return 1
    
    if not classifier_weights.exists():
        print(f"Error: Classifier weights not found: {classifier_weights}")
        return 1
    
    if not source_path.exists():
        print(f"Error: Source path does not exist: {source_path}")
        return 1
    
    # Load configs
    components_config = load_yaml(args.components_config)
    defects_config = load_yaml(args.defects_config)
    
    component_class_names = components_config['names']
    defect_class_names = defects_config['names']
    
    # Initialize pipeline
    pipeline = FullInferencePipeline(
        detector_model_path=detector_weights,
        classifier_model_path=classifier_weights,
        component_class_names=component_class_names,
        defect_class_names=defect_class_names,
        conf_threshold=args.conf_threshold,
        iou_threshold=args.iou_threshold,
        padding_ratio=args.padding_ratio
    )
    
    print(f"Running full inference pipeline:")
    print(f"  Detector: {detector_weights}")
    print(f"  Classifier: {classifier_weights}")
    print(f"  Source: {source_path}")
    print(f"  Output: {args.output}")
    
    # Process
    output_dir = Path(args.output)
    
    if source_path.is_file():
        # Single file
        print(f"\nProcessing single file: {source_path.name}")
        result = pipeline.process_image(source_path)
        
        # Save results
        if not args.no_json:
            json_dir = output_dir / 'json'
            json_dir.mkdir(parents=True, exist_ok=True)
            from src.utils.io import save_json
            json_path = json_dir / f"{source_path.stem}.json"
            save_json(result, json_path)
            print(f"JSON saved to: {json_path}")
        
        if not args.no_annotated:
            annotated_dir = output_dir / 'annotated'
            annotated_dir.mkdir(parents=True, exist_ok=True)
            annotated_img = pipeline._annotate_image(source_path, result)
            annotated_path = annotated_dir / source_path.name
            import cv2
            cv2.imwrite(str(annotated_path), annotated_img)
            print(f"Annotated image saved to: {annotated_path}")
        
        print(f"\nDetections: {len(result['detections'])}")
    
    else:
        # Directory
        print(f"\nProcessing directory: {source_path}")
        summary_stats = pipeline.process_directory(
            source_dir=source_path,
            output_dir=output_dir,
            save_annotated=not args.no_annotated,
            save_json=not args.no_json,
            save_csv=not args.no_csv
        )
        
        # Print summary
        print(f"\n=== Inference Summary ===")
        print(f"Total images processed: {summary_stats['total_images']}")
        print(f"Total detections: {summary_stats['total_detections']}")
        print(f"\nDefect counts:")
        for defect, count in sorted(summary_stats['defect_counts'].items()):
            print(f"  {defect}: {count}")
        print(f"\nComponent counts:")
        for component, count in sorted(summary_stats['component_counts'].items()):
            print(f"  {component}: {count}")
        
        print(f"\nResults saved to: {output_dir}")
        if not args.no_annotated:
            print(f"  Annotated images: {output_dir / 'annotated'}")
        if not args.no_json:
            print(f"  JSON files: {output_dir / 'json'}")
        if not args.no_csv:
            print(f"  Summary CSV: {output_dir / 'summary.csv'}")
        print(f"  Summary JSON: {output_dir / 'summary.json'}")
    
    print("\nInference completed!")
    return 0


if __name__ == '__main__':
    exit(main())
