"""
Direct test of Corrosion Model via model API
This bypasses all filtering to test the raw model output
"""

import sys
from pathlib import Path
from src.utils.io import load_yaml
from src.utils.model_api import ModelAPI
import cv2

def test_corrosion_direct(image_path: str):
    """Test corrosion model directly via model API"""
    
    if not Path(image_path).exists():
        print(f"ERROR: Image file not found: {image_path}")
        return
    
    print("\n" + "="*60)
    print("DIRECT CORROSION MODEL TEST")
    print("="*60)
    print(f"Image: {image_path}")
    print()
    
    # Load config
    corrosion_config = load_yaml('configs/corrosion.yaml')
    
    print("Configuration:")
    print(f"  Model ID: {corrosion_config['model_id']}")
    print(f"  API Key: {corrosion_config['api_key'][:10]}...")
    print(f"  Confidence Threshold: {corrosion_config.get('confidence_threshold', 0.05)}")
    print()
    
    # Initialize API
    print("Initializing model API...")
    corrosion_api = ModelAPI(
        api_key=corrosion_config['api_key'],
        model_id=corrosion_config['model_id'],
        api_url=corrosion_config.get('api_url', 'https://serverless.roboflow.com')
    )
    
    # Load image
    img = cv2.imread(image_path)
    if img is None:
        print(f"ERROR: Could not load image: {image_path}")
        return
    
    h, w = img.shape[:2]
    print(f"Image loaded: {w}x{h}")
    print()
    
    # Test with different confidence thresholds
    thresholds = [0.01, 0.05, 0.10, 0.25]
    
    for conf_thresh in thresholds:
        print(f"Testing with confidence threshold: {conf_thresh} ({conf_thresh*100}%)")
        print("-" * 60)
        
        try:
            # Call model API directly
            api_response = corrosion_api.predict_from_path(
                Path(image_path), 
                confidence=conf_thresh
            )
            
            if api_response is None:
                print("  API returned None")
                print()
                continue
            
            # Parse results
            detections = corrosion_api.parse_detection_results(api_response, w, h)
            
            print(f"  Raw API Response Keys: {list(api_response.keys())}")
            if 'predictions' in api_response:
                print(f"  Number of predictions in response: {len(api_response['predictions'])}")
            
            print(f"  Parsed Detections: {len(detections)}")
            
            if detections:
                print("  Detections:")
                for i, det in enumerate(detections, 1):
                    print(f"    {i}. Class: {det.get('class', 'unknown')}")
                    print(f"       Confidence: {det.get('confidence', 0.0):.2%}")
                    print(f"       BBox: {det.get('bbox_xyxy', [])}")
            else:
                print("  No detections found")
            
            print()
            
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            print()
    
    print("="*60)
    print("Test Complete")
    print("="*60)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_corrosion_direct.py <image_path>")
        sys.exit(1)
    
    test_corrosion_direct(sys.argv[1])
