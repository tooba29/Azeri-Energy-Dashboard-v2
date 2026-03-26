"""Direct API test to see raw response"""
import requests
from pathlib import Path

image_path = Path(r"C:\Users\gana_\Downloads\TestData_POC-20260203T113026Z-3-001\TestData_POC\rust_bolt_3.png")

with open(image_path, 'rb') as f:
    files = {'file': (image_path.name, f, 'image/png')}
    response = requests.post('http://localhost:8080/predict', files=files, timeout=60)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    result = response.json()
    print(f"\nCorrosion count: {result.get('corrosion_count', 0)}")
    print(f"Component count: {result.get('component_count', 0)}")
    print(f"Total count: {result.get('total_count', 0)}")
    
    detections = result.get('detections', [])
    corrosion_dets = [d for d in detections if d.get('detection_type') == 'corrosion']
    print(f"\nCorrosion detections: {len(corrosion_dets)}")
    for i, det in enumerate(corrosion_dets, 1):
        print(f"  {i}. {det}")
else:
    print(f"Error: {response.text}")
