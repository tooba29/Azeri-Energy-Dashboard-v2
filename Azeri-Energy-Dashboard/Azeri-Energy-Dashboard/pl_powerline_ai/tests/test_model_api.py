"""Test script to debug model API connection."""

from pathlib import Path
from src.utils.io import load_yaml
from src.utils.model_api import ModelAPI
import cv2
import numpy as np

# Load config
config = load_yaml('configs/model.yaml')

print("Testing model API connection...")
print(f"API Key: {config['api_key'][:10]}...")
print(f"Model ID: {config['model_id']}")
print(f"Endpoint will be: https://detect.roboflow.com/{config['model_id']}")
print()

# Initialize API
api = ModelAPI(
    api_key=config['api_key'],
    model_id=config['model_id'],
    api_url=config.get('api_url', 'https://serverless.roboflow.com')
)

print(f"Using model package with workspace: {api.workspace}, project: {api.project_name}, version: {api.version}")
print()

# Create a test image (small 100x100 image)
test_image = np.zeros((100, 100, 3), dtype=np.uint8)
cv2.rectangle(test_image, (20, 20), (80, 80), (255, 255, 255), -1)

print("Testing with a small test image...")
try:
    result = api.predict(test_image, confidence=0.25)
    print("SUCCESS!")
    print(f"Response keys: {list(result.keys())}")
    if 'predictions' in result:
        print(f"Number of predictions: {len(result['predictions'])}")
    print(f"Full response: {result}")
except Exception as e:
    print(f"ERROR: {e}")
    print()
    print("Trying to get more details...")
    import requests
    import base64
    
    # Encode test image
    _, buffer = cv2.imencode('.jpg', test_image)
    image_base64 = base64.b64encode(buffer).decode('utf-8')
    
    params = {"api_key": config['api_key'], "confidence": 0.25}
    
    print(f"Endpoint: {api.endpoint}")
    print(f"Params: {params}")
    print(f"Image size (base64): {len(image_base64)} chars")
    
    response = requests.post(
        api.endpoint,
        params=params,
        data=image_base64,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Text: {response.text[:500]}")
