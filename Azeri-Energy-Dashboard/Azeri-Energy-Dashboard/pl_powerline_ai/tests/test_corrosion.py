"""
Test script for Corrosion Detection Model
Usage: python test_corrosion.py <image_path>
"""

import sys
import requests
from pathlib import Path

def test_corrosion_detection(image_path: str):
    """Test corrosion detection on an image file"""
    
    if not Path(image_path).exists():
        print(f"ERROR: Image file not found: {image_path}")
        return
    
    print("\n" + "="*60)
    print("CORROSION DETECTION TEST")
    print("="*60)
    print(f"Image: {image_path}")
    print(f"Backend: http://localhost:8080/predict")
    print()
    
    try:
        # Prepare the file for upload
        with open(image_path, 'rb') as f:
            files = {'file': (Path(image_path).name, f, 'image/jpeg')}
            
            print("Sending image to backend...")
            response = requests.post(
                'http://localhost:8080/predict',
                files=files,
                timeout=60
            )
        
        if response.status_code == 200:
            result = response.json()
            
            print("\n" + "="*60)
            print("RESULTS")
            print("="*60)
            print(f"Image Size: {result.get('width')}x{result.get('height')}")
            print(f"Component Detections: {result.get('component_count', 0)}")
            print(f"Corrosion Detections: {result.get('corrosion_count', 0)}")
            print(f"Total Detections: {result.get('total_count', 0)}")
            print()
            
            # Show component detections
            component_detections = [d for d in result.get('detections', []) if d.get('detection_type') == 'component']
            if component_detections:
                print("COMPONENT DETECTIONS:")
                for i, det in enumerate(component_detections, 1):
                    print(f"  {i}. {det.get('component_class', 'unknown')}")
                    print(f"     Confidence: {det.get('component_conf', 0.0):.2%}")
                    print(f"     BBox: {det.get('bbox_xyxy', [])}")
                print()
            
            # Show corrosion detections
            corrosion_detections = [d for d in result.get('detections', []) if d.get('detection_type') == 'corrosion']
            if corrosion_detections:
                print("CORROSION DETECTIONS:")
                for i, det in enumerate(corrosion_detections, 1):
                    print(f"  {i}. Class: {det.get('corrosion_class', 'unknown')}")
                    print(f"     Confidence: {det.get('corrosion_conf', 0.0):.2%}")
                    print(f"     BBox: {det.get('bbox_xyxy', [])}")
                    print(f"     Original Class: {det.get('original_class', 'unknown')}")
                print()
            else:
                print("NO CORROSION DETECTED")
                print("(Note: Corrosion is filtered to only detect on component parts)")
                print()
            
            # Summary
            print("="*60)
            if corrosion_detections:
                print(f"SUCCESS: Found {len(corrosion_detections)} corrosion detection(s)")
            else:
                print("NO CORROSION DETECTED")
            print("="*60)
            
        else:
            print(f"ERROR: Backend returned status {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to backend server at http://localhost:8080")
        print("Make sure the backend server is running!")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_corrosion.py <image_path>")
        print("\nExample:")
        print("  python test_corrosion.py test_image.jpg")
        sys.exit(1)
    
    test_corrosion_detection(sys.argv[1])
