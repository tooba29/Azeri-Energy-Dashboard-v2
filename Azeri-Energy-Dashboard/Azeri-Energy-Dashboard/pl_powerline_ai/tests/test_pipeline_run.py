"""Test /api/pipeline/run endpoint directly"""
import requests
import base64
from pathlib import Path

image_path = Path(r"C:\Users\gana_\Downloads\TestData_POC-20260203T113026Z-3-001\TestData_POC\rust_bolt_3.png")

# Read and encode image
with open(image_path, 'rb') as f:
    image_bytes = f.read()
    rgb_base64 = base64.b64encode(image_bytes).decode('utf-8')

payload = {
    "rgb_base64": f"data:image/png;base64,{rgb_base64}",
    "tower_id": "TEST-001"
}

print("Sending request to /api/pipeline/run...")
response = requests.post('http://localhost:8080/api/pipeline/run', json=payload, timeout=120)

print(f"\nStatus: {response.status_code}")

if response.status_code == 200:
    result = response.json()
    print(f"\nRun ID: {result.get('run_id')}")
    print(f"Status: {result.get('status')}")
    print(f"Findings count: {result.get('findings_count', 0)}")
    print(f"Detections count: {len(result.get('detections', []))}")
    
    detections = result.get('detections', [])
    if detections:
        print(f"\nDetections:")
        for i, det in enumerate(detections[:5], 1):  # Show first 5
            print(f"  {i}. Type: {det.get('component_type', 'N/A')}, "
                  f"Defect: {det.get('defect_type', 'N/A')}, "
                  f"Confidence: {det.get('det_conf', 0):.2%}, "
                  f"BBox: {det.get('bbox', [])}")
    else:
        print("\nNo detections found!")
else:
    print(f"Error: {response.text}")
