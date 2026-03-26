"""API integration for model inference."""

from pathlib import Path
from typing import Dict, List, Any, Optional
import cv2
import numpy as np
from roboflow import Roboflow
import tempfile
import os
import sys
import time
from contextlib import contextmanager
from io import StringIO


@contextmanager
def suppress_model_output():
    """Context manager to suppress model library print statements."""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    try:
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        yield
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


class ModelAPI:
    """Wrapper for model inference API."""
    
    def __init__(
        self,
        api_key: str,
        model_id: str,
        api_url: str = "https://serverless.roboflow.com"
    ):
        """
        Initialize API client.
        
        Args:
            api_key: Your API key
            model_id: Model ID in format "workspace/project/version"
            api_url: API URL (kept for compatibility)
        """
        self.api_key = api_key
        self.model_id = model_id
        
        # Parse model_id to extract workspace, project, version
        parts = model_id.split('/')
        if len(parts) == 3:
            workspace, project, version = parts
            self.workspace = workspace
            self.project_name = project
            self.version = int(version)
        else:
            raise ValueError(f"Invalid model_id format: {model_id}. Expected 'workspace/project/version'")
        
        # Suppress model library messages and show AzerEnerji branding instead
        print("loading AzerEnerji workspace...", flush=True)
        with suppress_model_output():
            self.rf = Roboflow(api_key=api_key)
        
        print("loading AzerEnerji project...", flush=True)
        with suppress_model_output():
            self.project = self.rf.workspace(self.workspace).project(self.project_name)
            self.model = self.project.version(self.version).model
    
    def predict(self, image: np.ndarray, confidence: float = 0.25, max_retries: int = 3) -> Dict[str, Any]:
        """
        Run inference on image array with retry logic for 502 errors.
        
        Args:
            image: Image as numpy array (BGR format from OpenCV)
            confidence: Confidence threshold (passed to model)
            max_retries: Maximum number of retry attempts for 502 errors
            
        Returns:
            Dictionary with predictions
        """
        # Save image to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            # Convert BGR to RGB for saving
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            cv2.imwrite(tmp_file.name, image_rgb)
            tmp_path = tmp_file.name
        
        try:
            # Use model package to predict
            # Model API expects confidence as percentage (0-100)
            # Ensure minimum of 1% to avoid rounding to 0
            if confidence <= 1.0:
                confidence_percent = max(1, int(round(confidence * 100)))
            else:
                confidence_percent = int(confidence)
            print(f"DEBUG ModelAPI: Calling predict with confidence={confidence_percent}% (from {confidence})")
            
            # Retry logic for 502 Bad Gateway errors
            last_error = None
            for attempt in range(max_retries):
                try:
                    result = self.model.predict(
                        tmp_path,
                        confidence=confidence_percent,
                        overlap=30
                    )
                    # If successful, break out of retry loop
                    break
                except Exception as e:
                    last_error = e
                    error_str = str(e).lower()
                    # Check if it's a 502 error or network issue
                    if "502" in error_str or "bad gateway" in error_str or "timeout" in error_str or "connection" in error_str:
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 2  # Exponential backoff: 2s, 4s, 6s
                            print(f"WARNING: model API error (attempt {attempt + 1}/{max_retries}): {e}")
                            print(f"Retrying in {wait_time} seconds...")
                            time.sleep(wait_time)
                            continue
                        else:
                            print(f"ERROR: model API failed after {max_retries} attempts: {e}")
                            # Return empty predictions instead of crashing
                            return {'predictions': []}
                    else:
                        # Non-retryable error, raise immediately
                        print(f"ERROR: model API error (non-retryable): {e}")
                        raise
            
            # If we exhausted retries, return empty predictions
            if last_error and ("502" in str(last_error).lower() or "bad gateway" in str(last_error).lower()):
                print(f"ERROR: model API returned 502 after {max_retries} retries. Returning empty predictions.")
                return {'predictions': []}
            
            # If result is still None after retries, return empty predictions
            if result is None:
                return {'predictions': []}
            
            # Convert to dictionary format
            if result is None:
                return {'predictions': []}
            
            # Check if result has json() method
            if hasattr(result, 'json'):
                json_result = result.json()
                print(f"DEBUG ModelAPI.predict_from_path: Got result from json() method, predictions count: {len(json_result.get('predictions', []))}")
            elif isinstance(result, dict):
                json_result = result
                print(f"DEBUG ModelAPI.predict_from_path: Result is dict, predictions count: {len(json_result.get('predictions', []))}")
            else:
                # Try to convert to dict
                try:
                    json_result = dict(result) if result else {}
                    print(f"DEBUG ModelAPI.predict_from_path: Converted result to dict, predictions count: {len(json_result.get('predictions', []))}")
                except Exception as e:
                    print(f"DEBUG ModelAPI.predict_from_path: Failed to convert result: {e}")
                    json_result = {'predictions': []}
            
            if json_result is None:
                print("DEBUG ModelAPI.predict_from_path: json_result is None")
                return {'predictions': []}
            
            # Ensure it has predictions key
            if 'predictions' not in json_result:
                print("DEBUG ModelAPI.predict_from_path: No 'predictions' key in result, adding empty list")
                json_result['predictions'] = []
            
            print(f"DEBUG ModelAPI.predict_from_path: Final predictions count: {len(json_result.get('predictions', []))}")
            if json_result.get('predictions'):
                print(f"DEBUG ModelAPI.predict_from_path: First prediction: {json_result['predictions'][0]}")
            return json_result
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def predict_from_path(self, image_path: Path, confidence: float = 0.25, max_retries: int = 3) -> Dict[str, Any]:
        """
        Run inference on image file with retry logic for 502 errors.
        
        Args:
            image_path: Path to image file
            confidence: Confidence threshold
            max_retries: Maximum number of retry attempts for 502 errors
            
        Returns:
            Dictionary with predictions
        """
        # Use model package to predict
        # Model API expects confidence as percentage (0-100)
        # For very low thresholds (like 0.01 = 1%), we'll pass 1% to model
        # But model might filter more aggressively, so let's use 0% to get all detections
        # and filter ourselves based on the actual confidence values
        if confidence <= 0.01:
            # For 1% or lower, request all detections from model (0% threshold)
            # We'll filter by confidence ourselves later
            confidence_percent = 0
            print(f"DEBUG ModelAPI: Low threshold ({confidence}), using 0% to get all detections from model")
        elif confidence <= 1.0:
            confidence_percent = max(1, int(round(confidence * 100)))
        else:
            confidence_percent = int(confidence)
        print(f"DEBUG ModelAPI: Calling predict_from_path with confidence={confidence_percent}% (from {confidence})")
        
        # Retry logic for 502 Bad Gateway errors
        last_error = None
        for attempt in range(max_retries):
            try:
                result = self.model.predict(
                    str(image_path),
                    confidence=confidence_percent,
                    overlap=30
                )
                # If successful, break out of retry loop
                break
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                # Check if it's a 502 error or network issue
                if "502" in error_str or "bad gateway" in error_str or "timeout" in error_str or "connection" in error_str:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2  # Exponential backoff: 2s, 4s, 6s
                        print(f"WARNING: model API error (attempt {attempt + 1}/{max_retries}): {e}")
                        print(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"ERROR: model API failed after {max_retries} attempts: {e}")
                        # Return empty predictions instead of crashing
                        return {'predictions': []}
                else:
                    # Non-retryable error, raise immediately
                    print(f"ERROR: model API error (non-retryable): {e}")
                    raise
        
        # If we exhausted retries, return empty predictions
        if last_error and ("502" in str(last_error).lower() or "bad gateway" in str(last_error).lower()):
            print(f"ERROR: model API returned 502 after {max_retries} retries. Returning empty predictions.")
            return {'predictions': []}
        
        # If result is None after retries, return empty predictions
        if result is None:
            return {'predictions': []}
        
        # Convert to dictionary format
        print(f"DEBUG ModelAPI.predict_from_path: result type={type(result)}, is None={result is None}")
        if result is None:
            print("DEBUG ModelAPI.predict_from_path: Result is None, returning empty predictions")
            return {'predictions': []}
        
        # Check if result has json() method
        if hasattr(result, 'json'):
            json_result = result.json()
            print(f"DEBUG ModelAPI.predict_from_path: Got result from json() method")
        elif isinstance(result, dict):
            json_result = result
            print(f"DEBUG ModelAPI.predict_from_path: Result is already a dict")
        else:
            # Try to convert to dict
            try:
                json_result = dict(result) if result else {}
                print(f"DEBUG ModelAPI.predict_from_path: Converted result to dict")
            except Exception as e:
                print(f"DEBUG ModelAPI.predict_from_path: Failed to convert result: {e}")
                json_result = {'predictions': []}
        
        if json_result is None:
            print("DEBUG ModelAPI.predict_from_path: json_result is None")
            return {'predictions': []}
        
        # Ensure it has predictions key
        if 'predictions' not in json_result:
            print("DEBUG ModelAPI.predict_from_path: No 'predictions' key in result, adding empty list")
            json_result['predictions'] = []
        
        pred_count = len(json_result.get('predictions', []))
        print(f"DEBUG ModelAPI.predict_from_path: Final predictions count: {pred_count}")
        if pred_count > 0:
            print(f"DEBUG ModelAPI.predict_from_path: First prediction sample: {json_result['predictions'][0]}")
        
        return json_result
    
    def parse_detection_results(self, api_response: Dict[str, Any], img_width: int, img_height: int) -> List[Dict[str, Any]]:
        """
        Parse detection API response into standardized format.
        
        Args:
            api_response: Raw API response
            img_width: Image width
            img_height: Image height
            
        Returns:
            List of detections in format:
            {
                'class': str,
                'confidence': float,
                'bbox_xyxy': [x1, y1, x2, y2],
            }
        """
        detections = []
        
        # Check if api_response is None
        if api_response is None:
            return detections
        
        # Model package returns predictions in 'predictions' key
        predictions = api_response.get('predictions', []) if isinstance(api_response, dict) else []
        print(f"DEBUG parse_detection_results: Found {len(predictions)} predictions in API response")
        
        if not isinstance(predictions, list):
            print(f"DEBUG parse_detection_results: predictions is not a list, type: {type(predictions)}")
            return detections
        
        for i, pred in enumerate(predictions):
            # Skip if pred is None
            if pred is None or not isinstance(pred, dict):
                print(f"DEBUG parse_detection_results: Skipping prediction {i} - None or not dict")
                continue
            
            # Extract bounding box (model returns x, y, width, height - center-based)
            x = pred.get('x', 0)
            y = pred.get('y', 0)
            width = pred.get('width', 0)
            height = pred.get('height', 0)
            conf = float(pred.get('confidence', 0.0))
            cls = pred.get('class', 'unknown')
            
            print(f"DEBUG parse_detection_results: Prediction {i}: class={cls}, confidence={conf:.3f}, x={x}, y={y}, w={width}, h={height}")
            
            # Convert center-based to xyxy format
            x1 = int(x - width / 2)
            y1 = int(y - height / 2)
            x2 = int(x + width / 2)
            y2 = int(y + height / 2)
            
            # Clamp to image bounds
            x1 = max(0, min(x1, img_width - 1))
            y1 = max(0, min(y1, img_height - 1))
            x2 = max(0, min(x2, img_width - 1))
            y2 = max(0, min(y2, img_height - 1))
            
            detection = {
                'class': cls,
                'confidence': conf,
                'bbox_xyxy': [x1, y1, x2, y2]
            }
            detections.append(detection)
            print(f"DEBUG parse_detection_results: Added detection {i}: class={cls}, conf={conf:.3f}, bbox=[{x1},{y1},{x2},{y2}]")
        
        print(f"DEBUG parse_detection_results: Returning {len(detections)} detections total")
        return detections
