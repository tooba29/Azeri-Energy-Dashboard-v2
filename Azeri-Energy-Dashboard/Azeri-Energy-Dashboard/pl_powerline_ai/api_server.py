"""FastAPI server for frontend integration."""

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
import subprocess
import cv2
import numpy as np
import tempfile
import json
import re
from datetime import datetime
from io import BytesIO
from PIL import Image
from src.utils.io import load_yaml
from src.utils.model_api import ModelAPI

app = FastAPI(title="Powerline Inspection API")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load configs
model_config = load_yaml('configs/model.yaml')
components_config = load_yaml('configs/components.yaml')

component_class_names = components_config.get('names', [])
class_mapping = model_config.get('class_mapping', {})
if class_mapping is None:
    class_mapping = {}
class_to_id = {name: idx for idx, name in enumerate(component_class_names)}

# Initialize model API
api = ModelAPI(
    api_key=model_config['api_key'],
    model_id=model_config['model_id'],
    api_url=model_config.get('api_url', 'https://serverless.roboflow.com')
)

conf_threshold = model_config.get('confidence_threshold', 0.25)

# Load corrosion config
corrosion_config = load_yaml('configs/corrosion.yaml')

# Initialize Corrosion API
corrosion_api = ModelAPI(
    api_key=corrosion_config['api_key'],
    model_id=corrosion_config['model_id'],
    api_url=corrosion_config.get('api_url', 'https://serverless.roboflow.com')
)

corrosion_conf_threshold = corrosion_config.get('confidence_threshold', 0.25)
corrosion_class_mapping = corrosion_config.get('class_mapping', {})
if corrosion_class_mapping is None:
    corrosion_class_mapping = {}

print(f"INIT: corrosion_conf_threshold = {corrosion_conf_threshold}")

# Bird Nest Model removed - only Component and Corrosion models are used
# Corrosion filtering removed - using exact model output

# Load preloaded predictions for Test_Poc_Images
PRELOADED_PREDICTIONS = {}

# Bulk overlay: inference space (max side 2048) → output 1920×1080
OUTPUT_WIDTH = 1920
OUTPUT_HEIGHT = 1080
INFERENCE_MAX_SIDE = 2048

# DJI Thermal SDK paths for R-JPEG temperature extraction
DJI_IRP_EXE = Path(r"C:\Users\Tooba\Downloads\dji_thermal_sdk_v1.8_20250829\utility\bin\windows\release_x64\dji_irp.exe")
DJI_THERMAL_TEST_EXE = Path(r"C:\Users\Tooba\source\repos\dji_thermal_test\x64\Debug\dji_thermal_test.exe")


def get_inference_dimensions(img_w: int, img_h: int):
    """Inference space: downscale-only so max side <= 2048 (e.g. 2048×1536).
    IMPORTANT: never upscale images smaller than 2048 max-side (returns original dims)."""
    max_side = max(img_w, img_h)
    if max_side <= INFERENCE_MAX_SIDE:
        return img_w, img_h
    if img_w >= img_h:
        inference_w = INFERENCE_MAX_SIDE
        inference_h = max(1, int(round(img_h * INFERENCE_MAX_SIDE / img_w)))
    else:
        inference_h = INFERENCE_MAX_SIDE
        inference_w = max(1, int(round(img_w * INFERENCE_MAX_SIDE / img_h)))
    return inference_w, inference_h


def scale_bbox_to_output(bbox_xyxy, from_w: int, from_h: int, to_w: int = OUTPUT_WIDTH, to_h: int = OUTPUT_HEIGHT):
    """Scale bbox from (from_w, from_h) space to (to_w, to_h) and clamp."""
    x1, y1, x2, y2 = bbox_xyxy
    scale_x = to_w / from_w
    scale_y = to_h / from_h
    x1_o = int(round(x1 * scale_x))
    y1_o = int(round(y1 * scale_y))
    x2_o = int(round(x2 * scale_x))
    y2_o = int(round(y2 * scale_y))
    x1_o = max(0, min(x1_o, to_w - 1))
    y1_o = max(0, min(y1_o, to_h - 1))
    x2_o = max(0, min(x2_o, to_w - 1))
    y2_o = max(0, min(y2_o, to_h - 1))
    return [x1_o, y1_o, x2_o, y2_o]


def _process_thermal_rjpeg(thermal_bytes: bytes, output_dir: Path, ambient_c: float = 25.0):
    """
    Process DJI R-JPEG thermal image using dji_irp.exe and dji_thermal_test.exe
    to extract temperature insights (min, max, mean).
    Returns dict with temp_min, temp_max, temp_mean, ambient_used, raw_output, etc. or None on failure.
    """
    if not DJI_IRP_EXE.exists() or not DJI_THERMAL_TEST_EXE.exists():
        print(f"WARNING: DJI thermal tools not found. dji_irp={DJI_IRP_EXE.exists()}, dji_thermal_test={DJI_THERMAL_TEST_EXE.exists()}")
        return None
    try:
        # Use absolute paths so dji_thermal_test (run from its Debug dir) can find files
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        rjpeg_path = (output_dir / "thermal_rjpeg.jpg").resolve()
        with open(rjpeg_path, "wb") as f:
            f.write(thermal_bytes)
        # Get dimensions - try PIL first (more reliable for R-JPEG)
        try:
            img_pil = Image.open(BytesIO(thermal_bytes))
            w, h = img_pil.size
        except Exception:
            img = cv2.imread(str(rjpeg_path))
            if img is None:
                print("WARNING: Could not read thermal image dimensions")
                return None
            h, w = img.shape[:2]
        amb_str = f"{ambient_c:.1f}"
        cmd = [
            str(DJI_THERMAL_TEST_EXE.resolve()),
            "--rjpeg", str(rjpeg_path),
            "--dji_irp", str(DJI_IRP_EXE.resolve()),
            "--out", str(output_dir),
            "--width", str(w),
            "--height", str(h),
            "--ambient", amb_str,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(DJI_THERMAL_TEST_EXE.parent))
        out_text = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            print(f"WARNING: dji_thermal_test exited with code {result.returncode}. Output: {out_text[:500]}")
        insights = {
            "temp_min": None,
            "temp_max": None,
            "temp_mean": None,
            "ambient_used": ambient_c,
            "raw_output": out_text,
        }
        m = re.search(r"Temp stats:\s*min=([-\d.]+)\s+max=([-\d.]+)\s+mean=([-\d.]+)", out_text)
        if m:
            insights["temp_min"] = float(m.group(1))
            insights["temp_max"] = float(m.group(2))
            insights["temp_mean"] = float(m.group(3))
        json_match = re.search(r"\{[^{}]*\"Tp_max\"[^{}]*\}", out_text)
        if json_match:
            try:
                insights["roi_analysis"] = json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return insights
    except subprocess.TimeoutExpired:
        print("WARNING: DJI thermal analysis timed out")
        return None
    except Exception as e:
        print(f"WARNING: DJI thermal analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def _strip_trailing_commas(json_str):
    """Remove trailing commas before ] or } to fix invalid JSON (e.g. ,] or ,})."""
    return re.sub(r',(\s*[}\]])', r'\1', json_str)


def _parse_predictions_json(json_str):
    """
    Parse one or more JSON objects from json_str, each with a 'predictions' key.
    Returns merged list of all predictions. Handles multiple { "predictions": [...] } blocks
    and optional trailing commas in JSON.
    """
    predictions = []
    decoder = json.JSONDecoder()
    remaining = json_str.strip()
    while remaining:
        remaining = remaining.lstrip()
        if not remaining.startswith('{'):
            break
        try:
            data, end_idx = decoder.raw_decode(remaining)
            predictions.extend(data.get('predictions', []))
            remaining = remaining[end_idx:]
        except json.JSONDecodeError:
            # Try stripping trailing commas (invalid in strict JSON) and parse
            fixed = _strip_trailing_commas(remaining)
            try:
                data = json.loads(fixed)
                predictions.extend(data.get('predictions', []))
            except json.JSONDecodeError:
                pass
            break
    return predictions


def load_preloaded_predictions():
    """Load preloaded predictions from annotation files (Data/Test_Poc_Images/images_boxes)."""
    global PRELOADED_PREDICTIONS
    if PRELOADED_PREDICTIONS:
        return PRELOADED_PREDICTIONS
    
    # Data/Test_Poc_Images/images_boxes relative to project root (parent of pl_powerline_ai)
    project_root = Path(__file__).resolve().parent.parent
    annotation_dir = project_root / "Data" / "Test_Poc_Images" / "images_boxes"
    if not annotation_dir.exists():
        print(f"WARNING: Hardcoded predictions directory not found: {annotation_dir}")
        return {}
    
    for txt_file in annotation_dir.glob("*.txt"):
        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if len(lines) < 3:
                continue
            
            # First line is image name (without extension)
            image_name = lines[0].strip()
            
            # Find JSON block (usually starts after empty line)
            json_start = 1
            while json_start < len(lines) and not lines[json_start].strip().startswith('{'):
                json_start += 1
            
            if json_start >= len(lines):
                continue
            
            json_str = ''.join(lines[json_start:]).strip()
            predictions = _parse_predictions_json(json_str)
            
            if predictions:
                # Store predictions keyed by image name (without extension)
                PRELOADED_PREDICTIONS[image_name] = predictions
                print(f"Loaded preloaded predictions for: {image_name} ({len(predictions)} predictions)")
        
        except Exception as e:
            print(f"Error loading preloaded predictions from {txt_file}: {e}")
            continue
    
    print(f"Loaded {len(PRELOADED_PREDICTIONS)} preloaded image predictions")
    return PRELOADED_PREDICTIONS

def get_preloaded_detections_for_predict(image_name_without_ext: str, img_width: int, img_height: int):
    """Convert preloaded predictions to /predict endpoint format."""
    preloaded_preds = PRELOADED_PREDICTIONS.get(image_name_without_ext)
    if not preloaded_preds:
        return None, None
    
    component_results = []
    corrosion_results = []
    dynamic_class_to_id = class_to_id.copy()
    next_dynamic_id = len(component_class_names)
    corrosion_next_id = 0
    
    for pred in preloaded_preds:
        x_center = pred.get('x', 0)
        y_center = pred.get('y', 0)
        width = pred.get('width', 0)
        height = pred.get('height', 0)
        confidence = pred.get('confidence', 0.0)
        class_name = pred.get('class', 'unknown')
        
        x1 = int(x_center - width / 2)
        y1 = int(y_center - height / 2)
        x2 = int(x_center + width / 2)
        y2 = int(y_center + height / 2)
        
        x1 = max(0, min(x1, img_width - 1))
        y1 = max(0, min(y1, img_height - 1))
        x2 = max(0, min(x2, img_width - 1))
        y2 = max(0, min(y2, img_height - 1))
        
        bbox_xyxy = [x1, y1, x2, y2]
        
        is_corrosion = 'corrosion' in class_name.lower() or class_name == 'Corrosion'
        
        if is_corrosion:
            unified_class = corrosion_class_mapping.get(class_name, class_name) if corrosion_class_mapping else class_name
            corrosion_results.append({
                'detection_type': 'corrosion',
                'corrosion_class': unified_class,
                'corrosion_class_id': corrosion_next_id,
                'corrosion_conf': float(confidence),
                'bbox_xyxy': bbox_xyxy,
                'original_class': class_name
            })
            corrosion_next_id += 1
        else:
            unified_class = class_mapping.get(class_name, class_name) if class_mapping else class_name
            class_id = dynamic_class_to_id.get(unified_class, -1)
            if class_id == -1:
                if unified_class not in dynamic_class_to_id:
                    dynamic_class_to_id[unified_class] = next_dynamic_id
                    next_dynamic_id += 1
                class_id = dynamic_class_to_id[unified_class]
            
            component_results.append({
                'detection_type': 'component',
                'component_class': unified_class,
                'component_class_id': class_id,
                'component_conf': float(confidence),
                'bbox_xyxy': bbox_xyxy,
                'model_class': class_name
            })
    
    return component_results, corrosion_results

def get_preloaded_detections_for_pipeline(image_name_without_ext: str, img_width: int, img_height: int):
    """Convert preloaded predictions to pipeline format. Predictions are in inference space (max side 2048).
    x,y = center of box; convert to corners: x1 = x - w/2, y1 = y - h/2, x2 = x + w/2, y2 = y + h/2.
    Returns bboxes in inference space (so caller can scale to 1920×1080)."""
    preloaded_preds = PRELOADED_PREDICTIONS.get(image_name_without_ext)
    if not preloaded_preds:
        return None, None
    
    inference_w, inference_h = get_inference_dimensions(img_width, img_height)
    component_detections = []
    corrosion_detections = []
    dynamic_class_to_id = class_to_id.copy()
    next_dynamic_id = len(component_class_names)
    
    for pred in preloaded_preds:
        # x, y = center of box; width, height = box size (inference space)
        x_center = pred.get('x', 0)
        y_center = pred.get('y', 0)
        width = pred.get('width', 0)
        height = pred.get('height', 0)
        confidence = pred.get('confidence', 0.0)
        class_name = pred.get('class', 'unknown')
        
        # Center → corners: x1 = x - w/2, y1 = y - h/2, x2 = x + w/2, y2 = y + h/2
        x1 = int(x_center - width / 2)
        y1 = int(y_center - height / 2)
        x2 = int(x_center + width / 2)
        y2 = int(y_center + height / 2)
        
        x1 = max(0, min(x1, inference_w - 1))
        y1 = max(0, min(y1, inference_h - 1))
        x2 = max(0, min(x2, inference_w - 1))
        y2 = max(0, min(y2, inference_h - 1))
        
        bbox_xyxy = [x1, y1, x2, y2]
        
        is_corrosion = 'corrosion' in class_name.lower() or class_name == 'Corrosion'
        
        if is_corrosion:
            unified_class = corrosion_class_mapping.get(class_name, class_name) if corrosion_class_mapping else class_name
            conf = normalize_confidence(confidence)
            corrosion_detections.append({
                'component_type': unified_class,
                'bbox': bbox_xyxy,
                'det_conf': conf,
                'defect_type': unified_class,
                'defect_conf': conf,
                'severity': severity_from_confidence(conf),
                'status': 'needs_review'
            })
        else:
            unified_class = class_mapping.get(class_name, class_name) if class_mapping else class_name
            class_id = dynamic_class_to_id.get(unified_class, -1)
            if class_id == -1:
                if unified_class not in dynamic_class_to_id:
                    dynamic_class_to_id[unified_class] = next_dynamic_id
                    next_dynamic_id += 1
                class_id = dynamic_class_to_id[unified_class]
            
            conf = normalize_confidence(confidence)
            component_detections.append({
                'component_type': unified_class,
                'bbox': bbox_xyxy,
                'det_conf': conf,
                'severity': severity_from_confidence(conf),
                'status': 'needs_review'
            })
    
    return component_detections, corrosion_detections

# Load preloaded predictions at startup
load_preloaded_predictions()


def normalize_confidence(value: float) -> float:
    """
    Normalize confidence to 0-1. If value > 1, treat as percentage (e.g. 5 -> 0.05, 70 -> 0.7).
    Ensures severity and displayed confidence stay in sync (no HIGH when confidence is 5%).
    """
    v = float(value)
    if v > 1.0:
        return max(0.0, min(1.0, v / 100.0))
    return max(0.0, min(1.0, v))


def severity_from_confidence(confidence: float) -> str:
    """
    Derive severity from AI confidence: HIGH = very confident, MEDIUM = moderate, LOW = less confident.
    Uses normalized 0-1 confidence so percentage values (e.g. 5) are not misinterpreted as 5.0.
    """
    conf = normalize_confidence(confidence)
    if conf >= 0.7:
        return 'HIGH'
    if conf >= 0.4:
        return 'MEDIUM'
    return 'LOW'


def format_detection_label(label: str) -> str:
    """
    Format detection labels for display, ensuring consistent naming.
    """
    if not label:
        return "Unknown"
    
    # Normalize the label
    formatted = str(label).strip()
    
    # Replace underscores with spaces and capitalize words
    formatted = formatted.replace("_", " ").replace("-", " ")
    
    # Capitalize first letter of each word
    formatted = " ".join(word.capitalize() for word in formatted.split())
    
    return formatted


@app.post("/predict")
async def predict_image(file: UploadFile = File(...)):
    """
    Predict components and corrosion from uploaded image using both models.
    
    Returns JSON with combined detections from both models.
    """
    try:
        # Check for preloaded predictions FIRST (before any file operations)
        image_name_without_ext = Path(file.filename).stem
        
        if image_name_without_ext in PRELOADED_PREDICTIONS:
            # Use preloaded predictions - get dimensions from image bytes (fast, no disk I/O)
            content = await file.read()
            
            # Get image dimensions quickly from bytes using PIL
            try:
                img_pil = Image.open(BytesIO(content))
                w, h = img_pil.size
            except Exception as e:
                # Fallback to cv2 if PIL fails
                nparr = np.frombuffer(content, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    raise HTTPException(status_code=400, detail="Invalid image file")
                h, w = img.shape[:2]
            
            # Process preloaded predictions with correct dimensions
            component_results, corrosion_results = get_preloaded_detections_for_predict(image_name_without_ext, w, h)
            
            all_detections = component_results + corrosion_results
            
            print(f"Using preloaded predictions for {image_name_without_ext} (skipping model calls)")
            
            return JSONResponse({
                'image_name': file.filename,
                'width': w,
                'height': h,
                'detections': all_detections,
                'component_count': len(component_results),
                'corrosion_count': len(corrosion_results),
                'total_count': len(all_detections)
            })
        
        # Original prediction logic - only runs if no preloaded predictions found
        # Save uploaded file temporarily
            content = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            tmp_file.write(content)
            tmp_path = Path(tmp_file.name)
        
        # Load image to get dimensions (reuse content from above)
        nparr = np.frombuffer(content, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        h, w = img.shape[:2]
        
        # Run BOTH models in parallel
        import asyncio
        
        def get_component_predictions():
            api_response = api.predict_from_path(tmp_path, confidence=conf_threshold)
            if api_response is None:
                api_response = {'predictions': []}
            return api.parse_detection_results(api_response, w, h)
        
        def get_corrosion_predictions():
            print(f"DEBUG: Calling corrosion API with confidence threshold: {corrosion_conf_threshold}")
            api_response = corrosion_api.predict_from_path(tmp_path, confidence=corrosion_conf_threshold)
            if api_response is None:
                api_response = {'predictions': []}
            print(f"DEBUG: Corrosion API response predictions count: {len(api_response.get('predictions', []))}")
            results = corrosion_api.parse_detection_results(api_response, w, h)
            print(f"DEBUG: Parsed corrosion detections count: {len(results)}")
            return results
        
        # Run both models concurrently
        component_detections_raw, corrosion_detections_raw = await asyncio.gather(
            asyncio.to_thread(get_component_predictions),
            asyncio.to_thread(get_corrosion_predictions)
        )
        print(f"DEBUG: After gather - corrosion_detections_raw count: {len(corrosion_detections_raw)}")
        
        # Process component detections
        component_results = []
        dynamic_class_to_id = class_to_id.copy()
        next_dynamic_id = len(component_class_names)
        
        for det in component_detections_raw:
            if det is None or not isinstance(det, dict):
                continue
            
            model_class = det.get('class', 'unknown')
            if not model_class:
                model_class = 'unknown'
            
            unified_class = class_mapping.get(model_class, model_class) if class_mapping else model_class
            
            class_id = dynamic_class_to_id.get(unified_class, -1)
            if class_id == -1:
                if unified_class not in dynamic_class_to_id:
                    dynamic_class_to_id[unified_class] = next_dynamic_id
                    next_dynamic_id += 1
                class_id = dynamic_class_to_id[unified_class]
            
            confidence = det.get('confidence', 0.0)
            bbox = det.get('bbox_xyxy', [0, 0, 0, 0])
            
            component_results.append({
                'detection_type': 'component',
                'component_class': unified_class,
                'component_class_id': class_id,
                'component_conf': float(confidence) if confidence is not None else 0.0,
                'bbox_xyxy': bbox if isinstance(bbox, list) else [0, 0, 0, 0],
                'model_class': model_class
            })
        
        # Use exact model output - no filtering
        print(f"DEBUG: corrosion_detections_raw count: {len(corrosion_detections_raw)}")
        
        # Process corrosion detections
        corrosion_results = []
        corrosion_next_id = 0
        
        for det in corrosion_detections_raw:
            if det is None or not isinstance(det, dict):
                continue
            
            original_class = det.get('class', 'unknown')
            if not original_class:
                original_class = 'unknown'
            
            unified_class = corrosion_class_mapping.get(original_class, original_class) if corrosion_class_mapping else original_class
            
            confidence = det.get('confidence', 0.0)
            bbox = det.get('bbox_xyxy', [0, 0, 0, 0])
            
            corrosion_results.append({
                'detection_type': 'corrosion',
                'corrosion_class': unified_class,
                'corrosion_class_id': corrosion_next_id,
                'corrosion_conf': float(confidence) if confidence is not None else 0.0,
                'bbox_xyxy': bbox if isinstance(bbox, list) else [0, 0, 0, 0],
                'original_class': original_class
            })
            corrosion_next_id += 1
        
        # Combine all detections (only Component and Corrosion models)
        all_detections = component_results + corrosion_results
        
        # Clean up
        tmp_path.unlink()
        
        return JSONResponse({
            'image_name': file.filename,
            'width': w,
            'height': h,
            'detections': all_detections,
            'component_count': len(component_results),
            'corrosion_count': len(corrosion_results),
            'total_count': len(all_detections)
        })
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in /predict: {str(e)}")
        print(f"Traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")


@app.post("/predict/batch")
async def predict_batch(files: list[UploadFile] = File(..., description="Multiple image files")):
    """
    Predict components and corrosion from multiple uploaded images using both models.
    
    Returns JSON with combined results for all images.
    """
    results = []
    errors = []
    
    for file in files:
        try:
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                content = await file.read()
                tmp_file.write(content)
                tmp_path = Path(tmp_file.name)
            
            # Load image to get dimensions
            img = cv2.imread(str(tmp_path))
            if img is None:
                errors.append({
                    'image_name': file.filename,
                    'error': 'Invalid image file'
                })
                tmp_path.unlink()
                continue
            
            h, w = img.shape[:2]
            
            # Run BOTH models
            import asyncio
            
            def get_component_predictions():
                api_response = api.predict_from_path(tmp_path, confidence=conf_threshold)
                if api_response is None:
                    api_response = {'predictions': []}
                return api.parse_detection_results(api_response, w, h)
            
            def get_corrosion_predictions():
                api_response = corrosion_api.predict_from_path(tmp_path, confidence=corrosion_conf_threshold)
                if api_response is None:
                    api_response = {'predictions': []}
                return corrosion_api.parse_detection_results(api_response, w, h)
            
            # Run Component and Corrosion models
            component_detections_raw, corrosion_detections_raw = await asyncio.gather(
                asyncio.to_thread(get_component_predictions),
                asyncio.to_thread(get_corrosion_predictions)
            )
            
            # Process component detections
            component_detections = []
            dynamic_class_to_id = class_to_id.copy()
            next_dynamic_id = len(component_class_names)
            
            for det in component_detections_raw:
                if det is None or not isinstance(det, dict):
                    continue
                
                model_class = det.get('class', 'unknown')
                if not model_class:
                    model_class = 'unknown'
                
                unified_class = class_mapping.get(model_class, model_class) if class_mapping else model_class
                
                class_id = dynamic_class_to_id.get(unified_class, -1)
                if class_id == -1:
                    if unified_class not in dynamic_class_to_id:
                        dynamic_class_to_id[unified_class] = next_dynamic_id
                        next_dynamic_id += 1
                    class_id = dynamic_class_to_id[unified_class]
                
                confidence = det.get('confidence', 0.0)
                bbox = det.get('bbox_xyxy', [0, 0, 0, 0])
                
                component_detections.append({
                    'detection_type': 'component',
                    'component_class': unified_class,
                    'component_class_id': class_id,
                    'component_conf': float(confidence) if confidence is not None else 0.0,
                    'bbox_xyxy': bbox if isinstance(bbox, list) else [0, 0, 0, 0],
                    'model_class': model_class
                })
            
            # Use exact model output - no filtering
            # Process corrosion detections
            corrosion_detections = []
            corrosion_next_id = 0
            
            for det in corrosion_detections_raw:
                if det is None or not isinstance(det, dict):
                    continue
                
                original_class = det.get('class', 'unknown')
                if not original_class:
                    original_class = 'unknown'
                
                unified_class = corrosion_class_mapping.get(original_class, original_class) if corrosion_class_mapping else original_class
                
                confidence = det.get('confidence', 0.0)
                bbox = det.get('bbox_xyxy', [0, 0, 0, 0])
                
                corrosion_detections.append({
                    'detection_type': 'corrosion',
                    'corrosion_class': unified_class,
                    'corrosion_class_id': corrosion_next_id,
                    'corrosion_conf': float(confidence) if confidence is not None else 0.0,
                    'bbox_xyxy': bbox if isinstance(bbox, list) else [0, 0, 0, 0],
                    'original_class': original_class
                })
                corrosion_next_id += 1
            
            # Combine all detections (Component and Corrosion only)
            all_detections = component_detections + corrosion_detections
            
            results.append({
                'image_name': file.filename,
                'width': w,
                'height': h,
                'detections': all_detections,
                'component_count': len(component_detections),
                'corrosion_count': len(corrosion_detections),
                'total_count': len(all_detections)
            })
            
            # Clean up
            tmp_path.unlink()
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Error processing {file.filename}: {str(e)}")
            print(f"Traceback: {error_details}")
            errors.append({
                'image_name': file.filename,
                'error': str(e)
            })
            try:
                if 'tmp_path' in locals():
                    tmp_path.unlink()
            except:
                pass
    
    return JSONResponse({
        'total_images': len(files),
        'successful': len(results),
        'failed': len(errors),
        'results': results,
        'errors': errors
    })


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "ok": True,
        "status": "healthy",
        "version": "1.0.0",
        "time": datetime.now().isoformat(),
        "models": {
            "component": {
                "model_id": model_config['model_id'],
                "endpoint": "/predict"
            },
            "corrosion": {
                "model_id": corrosion_config['model_id'],
                "endpoint": "/predict"
            },
        }
    }


@app.post("/api/pipeline/run")
async def run_pipeline(payload: dict):
    """
    Pipeline endpoint that accepts base64 RGB and optional thermal images.
    Matches frontend API contract.
    """
    import base64
    import uuid
    from datetime import datetime
    
    try:
        import asyncio
        # Extract base64 images
        rgb_base64 = payload.get("rgb_base64", "")
        thermal_base64 = payload.get("thermal_base64")
        
        if not rgb_base64:
            raise HTTPException(status_code=400, detail="rgb_base64 is required")
        
        # Remove data URL prefix if present and detect format
        file_ext = '.jpg'  # Default
        if rgb_base64.startswith("data:image"):
            # Extract format from data URL (e.g., "data:image/png;base64,")
            data_url_parts = rgb_base64.split(",")
            mime_type = data_url_parts[0].split(":")[1].split(";")[0] if len(data_url_parts) > 0 else "image/jpeg"
            if "png" in mime_type:
                file_ext = '.png'
            elif "jpeg" in mime_type or "jpg" in mime_type:
                file_ext = '.jpg'
            rgb_base64 = data_url_parts[1] if len(data_url_parts) > 1 else rgb_base64
        
        # Decode RGB image
        rgb_bytes = base64.b64decode(rgb_base64)
        
        # Check for preloaded predictions FIRST (before any file operations)
        filename = payload.get("filename") or payload.get("image_name") or "unknown"
        image_name_without_ext = Path(filename).stem
        
        if image_name_without_ext in PRELOADED_PREDICTIONS:
            # Use preloaded predictions - get dimensions from bytes (fast, no disk I/O)
            try:
                img_pil = Image.open(BytesIO(rgb_bytes))
                w, h = img_pil.size
            except Exception:
                # Fallback to cv2 if PIL fails
                nparr = np.frombuffer(rgb_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    raise HTTPException(status_code=400, detail="Invalid RGB image")
                h, w = img.shape[:2]
            
            # Process preloaded predictions
            component_detections, corrosion_detections = get_preloaded_detections_for_pipeline(image_name_without_ext, w, h)
            all_detections = component_detections + corrosion_detections
            
            print(f"Using preloaded predictions for {image_name_without_ext} (skipping model calls)")
            
            # Generate run_id
            run_id = str(uuid.uuid4())[:8]
            
            # Load image for overlay creation (only if we have preloaded predictions)
            nparr = np.frombuffer(rgb_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            # Original prediction logic - only runs if no preloaded predictions found
            # Save to temp file with correct extension
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
                tmp_file.write(rgb_bytes)
                tmp_path = Path(tmp_file.name)
            
            print(f"DEBUG /api/pipeline/run: Saved image to {tmp_path} (format: {file_ext})")
            
            # Load image to get dimensions
            img = cv2.imread(str(tmp_path))
            if img is None:
                raise HTTPException(status_code=400, detail="Invalid RGB image")
            
            h, w = img.shape[:2]
            
            # Generate run_id (needed for both paths)
            run_id = str(uuid.uuid4())[:8]
            # Run predictions (reuse existing logic)
        
            def get_component_predictions():
                api_response = api.predict_from_path(tmp_path, confidence=conf_threshold)
                if api_response is None:
                    api_response = {'predictions': []}
                return api.parse_detection_results(api_response, w, h)
        
            def get_corrosion_predictions():
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"DEBUG /api/pipeline/run: Calling corrosion API with confidence threshold: {corrosion_conf_threshold}")
                print(f"DEBUG /api/pipeline/run: Calling corrosion API with confidence threshold: {corrosion_conf_threshold}")
                api_response = corrosion_api.predict_from_path(tmp_path, confidence=corrosion_conf_threshold)
                if api_response is None:
                    api_response = {'predictions': []}
                pred_count = len(api_response.get('predictions', []))
                logger.info(f"DEBUG /api/pipeline/run: Corrosion API response predictions count: {pred_count}")
                print(f"DEBUG /api/pipeline/run: Corrosion API response predictions count: {pred_count}")
                results = corrosion_api.parse_detection_results(api_response, w, h)
                logger.info(f"DEBUG /api/pipeline/run: Parsed corrosion detections count: {len(results)}")
                print(f"DEBUG /api/pipeline/run: Parsed corrosion detections count: {len(results)}")
                if results:
                    logger.info(f"DEBUG /api/pipeline/run: First corrosion detection: {results[0]}")
                    print(f"DEBUG /api/pipeline/run: First corrosion detection: {results[0]}")
                return results
        
            # Run Component and Corrosion models
            component_detections_raw, corrosion_detections_raw = await asyncio.gather(
                asyncio.to_thread(get_component_predictions),
                asyncio.to_thread(get_corrosion_predictions)
            )
            print(f"DEBUG /api/pipeline/run: After gather - component_detections_raw: {len(component_detections_raw)}, corrosion_detections_raw: {len(corrosion_detections_raw)}")
        
            # Process component detections (reuse logic from /predict)
            component_detections = []
            dynamic_class_to_id = class_to_id.copy()
            next_dynamic_id = len(component_class_names)
        
            for det in component_detections_raw:
                if det is None or not isinstance(det, dict):
                    continue
                model_class = det.get('class', 'unknown') or 'unknown'
                unified_class = class_mapping.get(model_class, model_class) if class_mapping else model_class
                class_id = dynamic_class_to_id.get(unified_class, -1)
                if class_id == -1:
                    if unified_class not in dynamic_class_to_id:
                        dynamic_class_to_id[unified_class] = next_dynamic_id
                        next_dynamic_id += 1
                    class_id = dynamic_class_to_id[unified_class]
            
                conf = normalize_confidence(det.get('confidence', 0.0))
                component_detections.append({
                    'component_type': unified_class,
                    'bbox': det.get('bbox_xyxy', [0, 0, 0, 0]),
                    'det_conf': conf,
                    'severity': severity_from_confidence(conf),
                    'status': 'needs_review'
                })
        
            # Use exact model output - no filtering
            print(f"DEBUG /api/pipeline/run: corrosion_detections_raw count: {len(corrosion_detections_raw)}")
        
            # Process corrosion detections
            corrosion_detections = []
            for det in corrosion_detections_raw:
                print(f"DEBUG /api/pipeline/run: Processing corrosion detection: {det}")
                if det is None or not isinstance(det, dict):
                    continue
                original_class = det.get('class', 'unknown') or 'unknown'
                unified_class = corrosion_class_mapping.get(original_class, original_class) if corrosion_class_mapping else original_class
                conf = normalize_confidence(det.get('confidence', 0.0))
            
                corrosion_detections.append({
                    'component_type': unified_class,
                    'bbox': det.get('bbox_xyxy', [0, 0, 0, 0]),
                    'det_conf': conf,
                    'defect_type': unified_class,
                    'defect_conf': conf,
                    'severity': severity_from_confidence(conf),
                    'status': 'needs_review'
                })
        
            # Combine all detections (Component and Corrosion only)
            all_detections = component_detections + corrosion_detections
        
            component_count = len([d for d in all_detections if d.get('detection_type') != 'corrosion' or 'defect_type' not in d])
            corrosion_count = len([d for d in all_detections if d.get('detection_type') == 'corrosion' or 'defect_type' in d])
            print(f"DEBUG /api/pipeline/run: Total detections: {len(all_detections)} (components: {component_count}, corrosion: {corrosion_count})")
            if all_detections:
                print(f"DEBUG /api/pipeline/run: First detection sample: {all_detections[0]}")
            else:
                print(f"DEBUG /api/pipeline/run: WARNING - No detections to save!")
        
        # Scale preloaded bboxes from inference space to original image space (model path uses original space)
        if image_name_without_ext in PRELOADED_PREDICTIONS:
            from_w, from_h = get_inference_dimensions(w, h)
            scaled_detections = []
            for det in all_detections:
                bbox = det.get('bbox') or det.get('bbox_xyxy', [0, 0, 0, 0])
                if len(bbox) != 4:
                    scaled_detections.append(det)
                    continue
                bbox_orig = scale_bbox_to_output(bbox, from_w, from_h, w, h)
                scaled_detections.append({**det, 'bbox': bbox_orig})
            all_detections = scaled_detections
        
        # Create overlay image with bounding boxes
        overlay_img = img.copy()
        
        # Color scheme: different colors for different severities/types
        HIGH_COLOR = (0, 0, 255)  # Red (BGR)
        MEDIUM_COLOR = (0, 165, 255)  # Orange
        LOW_COLOR = (0, 255, 0)  # Green
        CORROSION_COLOR = (0, 0, 255)  # Red for corrosion
        
        for det in all_detections:
            # Check both 'bbox' and 'bbox_xyxy' keys
            bbox = det.get('bbox') or det.get('bbox_xyxy', [0, 0, 0, 0])
            if len(bbox) != 4:
                continue
            
            x1, y1, x2, y2 = [int(coord) for coord in bbox]
            
            # Determine color based on severity or type
            severity = det.get('severity', 'MEDIUM')
            # Check if this is a corrosion detection
            is_corrosion = (
                'defect_type' in det or 
                'corrosion' in det.get('component_type', '').lower() or
                'corrosion' in det.get('defect_type', '').lower() or
                det.get('detection_type') == 'corrosion'
            )
            
            if is_corrosion:
                color = CORROSION_COLOR
            elif severity == 'HIGH':
                color = HIGH_COLOR
            elif severity == 'MEDIUM':
                color = MEDIUM_COLOR
            else:
                color = LOW_COLOR
            
            # Draw bounding box
            thickness = 3
            cv2.rectangle(overlay_img, (x1, y1), (x2, y2), color, thickness)
            
            # Prepare label text - handle both component and corrosion detections
            if is_corrosion:
                component_type = det.get('defect_type') or det.get('component_type', 'Corrosion')
                confidence = det.get('defect_conf') or det.get('det_conf', 0.0)
            else:
                component_type = det.get('component_type', 'Unknown')
                confidence = det.get('det_conf', 0.0)
            
            # Format label (capitalize and clean up)
            component_type_formatted = component_type.replace('_', ' ').title()
            label = f"{component_type_formatted} {confidence:.1%}"
            
            # Get text size
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            text_thickness = 2
            (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, text_thickness)
            
            # Draw label background
            label_y = max(y1 - 10, text_height + 5)
            cv2.rectangle(
                overlay_img,
                (x1, label_y - text_height - 5),
                (x1 + text_width + 10, label_y + baseline),
                color,
                -1
            )
            
            # Draw label text
            cv2.putText(
                overlay_img,
                label,
                (x1 + 5, label_y),
                font,
                font_scale,
                (255, 255, 255),  # White text
                text_thickness,
                cv2.LINE_AA
            )
        
        # Save run data to disk
        import json
        import os
        runs_dir = Path("outputs/runs")
        runs_dir.mkdir(parents=True, exist_ok=True)
        run_dir = runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Save overlay image (with bounding boxes)
        overlay_path = artifacts_dir / "overlay.jpg"
        cv2.imwrite(str(overlay_path), overlay_img)
        
        # Save RGB image as annotated artifact (original)
        rgb_artifact_path = artifacts_dir / "annotated.jpg"
        cv2.imwrite(str(rgb_artifact_path), img)
        
        # Process thermal R-JPEG if provided (DJI dji_irp + dji_thermal_test for temperature insights)
        thermal_insights = None
        ambient_for_thermal = float(payload.get("ambient_c") or 25.0)
        if thermal_base64:
            try:
                th_b64 = thermal_base64
                if isinstance(th_b64, str) and th_b64.startswith("data:image"):
                    th_b64 = th_b64.split(",")[1] if "," in th_b64 else th_b64
                thermal_bytes = base64.b64decode(th_b64)
                thermal_analysis_dir = (run_dir.resolve()) / "thermal_analysis"
                thermal_insights = _process_thermal_rjpeg(
                    thermal_bytes,
                    thermal_analysis_dir,
                    ambient_c=ambient_for_thermal,
                )
                if thermal_insights is None:
                    thermal_insights = {
                        "ambient_used": ambient_for_thermal,
                        "raw_output": "DJI thermal tools not available or processing failed. Check server logs.",
                        "temp_min": None,
                        "temp_max": None,
                        "temp_mean": None,
                    }
                thermal_path = artifacts_dir / "thermal.jpg"
                with open(thermal_path, "wb") as f:
                    f.write(thermal_bytes)
                # Create thermal overlay with RGB detection boxes scaled to thermal dimensions
                if all_detections:
                    try:
                        thermal_img = cv2.imdecode(np.frombuffer(thermal_bytes, np.uint8), cv2.IMREAD_COLOR)
                        if thermal_img is not None:
                            th_h, th_w = thermal_img.shape[:2]
                            scale_x = th_w / w
                            scale_y = th_h / h
                            thermal_overlay = thermal_img.copy()
                            HIGH_COLOR = (0, 0, 255)
                            MEDIUM_COLOR = (0, 165, 255)
                            LOW_COLOR = (0, 255, 0)
                            CORROSION_COLOR = (0, 0, 255)
                            for det in all_detections:
                                bbox = det.get('bbox') or det.get('bbox_xyxy', [0, 0, 0, 0])
                                if len(bbox) != 4:
                                    continue
                                x1, y1, x2, y2 = [int(coord) for coord in bbox]
                                x1_t = int(x1 * scale_x)
                                y1_t = int(y1 * scale_y)
                                x2_t = int(x2 * scale_x)
                                y2_t = int(y2 * scale_y)
                                x1_t = max(0, min(x1_t, th_w - 1))
                                y1_t = max(0, min(y1_t, th_h - 1))
                                x2_t = max(0, min(x2_t, th_w - 1))
                                y2_t = max(0, min(y2_t, th_h - 1))
                                if x2_t <= x1_t or y2_t <= y1_t:
                                    continue
                                severity = det.get('severity', 'MEDIUM')
                                is_corrosion = (
                                    'defect_type' in det or
                                    'corrosion' in det.get('component_type', '').lower() or
                                    'corrosion' in det.get('defect_type', '').lower() or
                                    det.get('detection_type') == 'corrosion'
                                )
                                color = CORROSION_COLOR if is_corrosion else (
                                    HIGH_COLOR if severity == 'HIGH' else (MEDIUM_COLOR if severity == 'MEDIUM' else LOW_COLOR)
                                )
                                cv2.rectangle(thermal_overlay, (x1_t, y1_t), (x2_t, y2_t), color, 2)
                                component_type = det.get('defect_type') or det.get('component_type', 'Unknown')
                                confidence = det.get('defect_conf') or det.get('det_conf', 0.0)
                                label = f"{component_type.replace('_', ' ').title()} {confidence:.1%}"
                                font = cv2.FONT_HERSHEY_SIMPLEX
                                font_scale = 0.4
                                text_thickness = 1
                                (tw, tht), bl = cv2.getTextSize(label, font, font_scale, text_thickness)
                                ly = max(y1_t - 5, tht + 3)
                                cv2.rectangle(thermal_overlay, (x1_t, ly - tht - 3), (x1_t + tw + 6, ly + bl), color, -1)
                                cv2.putText(thermal_overlay, label, (x1_t + 3, ly), font, font_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)
                            thermal_overlay_path = artifacts_dir / "thermal_overlay.jpg"
                            cv2.imwrite(str(thermal_overlay_path), thermal_overlay)
                    except Exception as te:
                        print(f"WARNING: Failed to create thermal overlay: {te}")
            except Exception as e:
                print(f"WARNING: Thermal processing failed: {e}")
                thermal_insights = {
                    "ambient_used": ambient_for_thermal,
                    "raw_output": str(e),
                    "temp_min": None,
                    "temp_max": None,
                    "temp_mean": None,
                }
        
        # Calculate average confidence
        confidences = [d.get('det_conf', 0) for d in all_detections]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Create run.json
        artifacts_dict = {
            "overlay_url": f"/api/runs/{run_id}/artifacts/overlay",
            "annotated_url": f"/api/runs/{run_id}/artifacts/annotated"
        }
        if thermal_base64 and (artifacts_dir / "thermal.jpg").exists():
            artifacts_dict["thermal_url"] = f"/api/runs/{run_id}/artifacts/thermal"
        metadata_dict = {
            "gps": payload.get("gps"),
            "ambient_c": payload.get("ambient_c"),
            "voltage_kv": payload.get("voltage_kv"),
            "tower_type": payload.get("tower_type"),
            "region": payload.get("region"),
            "corridor_tag": payload.get("corridor_tag")
        }
        if thermal_insights:
            metadata_dict["thermal_insights"] = thermal_insights
        run_data = {
            "id": run_id,
            "run_id": run_id,
            "tower_id": payload.get("tower_id"),
            "status": "completed",
            "created_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
            "findings_count": len(all_detections),
            "must_review_count": len([d for d in all_detections if d.get('status') == 'needs_review']),
            "ai_confidence": avg_confidence,
            "detections": all_detections,
            "artifacts": artifacts_dict,
            "metadata": metadata_dict
        }
        
        # Write run.json
        run_json_path = run_dir / "run.json"
        print(f"DEBUG /api/pipeline/run: Saving run.json with {len(all_detections)} detections")
        with open(run_json_path, 'w', encoding='utf-8') as f:
            json.dump(run_data, f, indent=2, ensure_ascii=False)
        print(f"DEBUG /api/pipeline/run: Run saved successfully to {run_json_path}")
        
        # Generate PDF report
        try:
            from src.utils.report_generator import generate_single_upload_report
            report_path = generate_single_upload_report(run_json_path)
            print(f"DEBUG /api/pipeline/run: Report generated at {report_path}")
            # Update artifacts to include report URL
            run_data["artifacts"]["report_url"] = f"/api/runs/{run_id}/artifacts/report"
        except Exception as e:
            print(f"WARNING: Failed to generate report: {e}")
            import traceback
            traceback.print_exc()
        
        # Cleanup temp file (only if we used model predictions)
        if 'tmp_path' in locals():
            tmp_path.unlink()
        
        return {
            "run_id": run_id,
            "tower_id": payload.get("tower_id"),
            "status": "completed"
        }
        
    except Exception as e:
        return {
            "run_id": str(uuid.uuid4())[:8] if 'run_id' not in locals() else None,
            "status": "failed",
            "error": str(e)
        }


@app.post("/api/pipeline/bulk")
async def bulk_process(payload: dict):
    """
    Bulk process multiple images and organize results by defect/detection type.
    Expected payload:
    {
        "images": [
            {
                "filename": "image1.jpg",
                "rgb_base64": "data:image/...",
                "thermal_base64": "optional",
                "tower_id": "optional"
            },
            ...
        ],
        "organize_by_defect": true
    }
    """
    import base64
    import uuid
    import shutil
    import json
    from collections import defaultdict
    
    try:
        images = payload.get("images", [])
        organize_by_defect = payload.get("organize_by_defect", True)
        
        if not images:
            raise HTTPException(status_code=400, detail="No images provided")
        
        # Base directory for organized results
        bulk_output_dir = Path("outputs/bulk_processing")
        bulk_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timestamped batch folder
        batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        batch_dir = bulk_output_dir / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)
        
        # Dictionary to organize images by defect type
        defect_folders = defaultdict(list)
        all_runs = []
        processed_count = 0
        failed_count = 0
        
        for idx, img_data in enumerate(images):
            try:
                filename = img_data.get("filename", f"image_{idx}.jpg")
                rgb_base64 = img_data.get("rgb_base64", "")
                
                if not rgb_base64:
                    failed_count += 1
                    continue
                
                # Remove data URL prefix if present
                if rgb_base64.startswith("data:image"):
                    rgb_base64 = rgb_base64.split(",")[1]
                
                # Decode RGB image
                rgb_bytes = base64.b64decode(rgb_base64)
                
                # Save to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                    tmp_file.write(rgb_bytes)
                    tmp_path = Path(tmp_file.name)
                
                # Load image
                img = cv2.imread(str(tmp_path))
                if img is None:
                    failed_count += 1
                    tmp_path.unlink()
                    continue
                
                h, w = img.shape[:2]
                
                # Check for preloaded predictions FIRST (before model calls)
                image_name_without_ext = Path(filename).stem
                
                if image_name_without_ext in PRELOADED_PREDICTIONS:
                    # Use preloaded predictions - skip model calls
                    print(f"Using preloaded predictions for {image_name_without_ext} (skipping model calls)")
                    component_detections, corrosion_detections = get_preloaded_detections_for_pipeline(image_name_without_ext, w, h)
                    all_detections = component_detections + corrosion_detections
                else:
                    # Original prediction logic - only runs if no preloaded predictions found
                    # Run predictions
                    import asyncio
                    
                    def get_component_predictions():
                        api_response = api.predict_from_path(tmp_path, confidence=conf_threshold)
                        if api_response is None:
                            api_response = {'predictions': []}
                        return api.parse_detection_results(api_response, w, h)
                    
                    def get_corrosion_predictions():
                        api_response = corrosion_api.predict_from_path(tmp_path, confidence=corrosion_conf_threshold)
                        if api_response is None:
                            api_response = {'predictions': []}
                        return corrosion_api.parse_detection_results(api_response, w, h)
                    
                    # Run Component and Corrosion models
                    component_detections_raw, corrosion_detections_raw = await asyncio.gather(
                        asyncio.to_thread(get_component_predictions),
                        asyncio.to_thread(get_corrosion_predictions)
                    )
                    
                    # Process component detections
                    component_detections = []
                    dynamic_class_to_id = class_to_id.copy()
                    next_dynamic_id = len(component_class_names)
                    
                    for det in component_detections_raw:
                        if det is None or not isinstance(det, dict):
                            continue
                        model_class = det.get('class', 'unknown') or 'unknown'
                        unified_class = class_mapping.get(model_class, model_class) if class_mapping else model_class
                        class_id = dynamic_class_to_id.get(unified_class, -1)
                        if class_id == -1:
                            if unified_class not in dynamic_class_to_id:
                                dynamic_class_to_id[unified_class] = next_dynamic_id
                                next_dynamic_id += 1
                            class_id = dynamic_class_to_id[unified_class]
                        
                        conf = normalize_confidence(det.get('confidence', 0.0))
                        component_detections.append({
                            'component_type': unified_class,
                            'bbox': det.get('bbox_xyxy', [0, 0, 0, 0]),
                            'det_conf': conf,
                            'severity': severity_from_confidence(conf),
                            'status': 'needs_review'
                        })
                    
                    # Use exact model output - no filtering
                    # Process corrosion detections
                    corrosion_detections = []
                    for det in corrosion_detections_raw:
                        if det is None or not isinstance(det, dict):
                            continue
                        original_class = det.get('class', 'unknown') or 'unknown'
                        unified_class = corrosion_class_mapping.get(original_class, original_class) if corrosion_class_mapping else original_class
                        conf = normalize_confidence(det.get('confidence', 0.0))
                        
                        corrosion_detections.append({
                            'component_type': unified_class,
                            'bbox': det.get('bbox_xyxy', [0, 0, 0, 0]),
                            'det_conf': conf,
                            'defect_type': unified_class,
                            'defect_conf': conf,
                            'severity': severity_from_confidence(conf),
                            'status': 'needs_review'
                        })
                    
                    # Combine all detections (Component and Corrosion only)
                    all_detections = component_detections + corrosion_detections
                
                # Determine primary defect type for organization
                primary_defect = "normal"  # Default
                if corrosion_detections:
                    # If corrosion detected, use the most common corrosion type
                    corrosion_types = [d.get('defect_type', 'corrosion') for d in corrosion_detections]
                    primary_defect = max(set(corrosion_types), key=corrosion_types.count) if corrosion_types else "corrosion"
                elif component_detections:
                    # Use most common component type
                    component_types = [d.get('component_type', 'component') for d in component_detections]
                    primary_defect = max(set(component_types), key=component_types.count) if component_types else "components"
                
                # Normalize defect name for folder (remove spaces, special chars)
                folder_name = primary_defect.lower().replace(" ", "_").replace("/", "_")
                folder_name = "".join(c for c in folder_name if c.isalnum() or c == "_")
                if not folder_name:
                    folder_name = "other"
                
                # Scale bboxes to output 1920×1080 and resize image to match
                # Hardcoded: predictions are in inference space (max side 2048). API: in original image space.
                if image_name_without_ext in PRELOADED_PREDICTIONS:
                    from_w, from_h = get_inference_dimensions(w, h)
                else:
                    from_w, from_h = w, h
                scaled_detections = []
                for det in all_detections:
                    bbox = det.get('bbox', [0, 0, 0, 0])
                    if len(bbox) != 4:
                        continue
                    bbox_out = scale_bbox_to_output(bbox, from_w, from_h, OUTPUT_WIDTH, OUTPUT_HEIGHT)
                    scaled_detections.append({**det, 'bbox': bbox_out})
                
                # Resize image to 1920×1080 and draw correctly scaled boxes
                img_out = cv2.resize(img, (OUTPUT_WIDTH, OUTPUT_HEIGHT))
                overlay_img = img_out.copy()
                HIGH_COLOR = (0, 0, 255)
                MEDIUM_COLOR = (0, 165, 255)
                LOW_COLOR = (0, 255, 0)
                
                for det in scaled_detections:
                    bbox = det.get('bbox', [0, 0, 0, 0])
                    if len(bbox) != 4:
                        continue
                    x1, y1, x2, y2 = [int(coord) for coord in bbox]
                    severity = det.get('severity', 'MEDIUM')
                    color = HIGH_COLOR if severity == 'HIGH' else (MEDIUM_COLOR if severity == 'MEDIUM' else LOW_COLOR)
                    
                    # Draw bounding box
                    thickness = 3
                    cv2.rectangle(overlay_img, (x1, y1), (x2, y2), color, thickness)
                    
                    # Draw label
                    component_type = det.get('component_type', 'Unknown')
                    component_type_formatted = format_detection_label(component_type)
                    confidence = det.get('det_conf', 0.0)
                    label = f"{component_type_formatted} {confidence:.2f}"
                    
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.6
                    text_thickness = 2
                    (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, text_thickness)
                    
                    label_y = max(y1 - 10, text_height + 5)
                    cv2.rectangle(
                        overlay_img,
                        (x1, label_y - text_height - 5),
                        (x1 + text_width + 10, label_y + baseline),
                        color,
                        -1
                    )
                    
                    cv2.putText(
                        overlay_img,
                        label,
                        (x1 + 5, label_y),
                        font,
                        font_scale,
                        (255, 255, 255),
                        text_thickness,
                        cv2.LINE_AA
                    )
                
                # Save run data
                run_id = str(uuid.uuid4())[:8]
                runs_dir = Path("outputs/runs")
                runs_dir.mkdir(parents=True, exist_ok=True)
                run_dir = runs_dir / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                artifacts_dir = run_dir / "artifacts"
                artifacts_dir.mkdir(parents=True, exist_ok=True)
                
                # Save overlay (1920×1080 with boxes)
                overlay_path = artifacts_dir / "overlay.jpg"
                cv2.imwrite(str(overlay_path), overlay_img)
                
                # Save original resized to 1920×1080 (no boxes)
                annotated_path = artifacts_dir / "annotated.jpg"
                cv2.imwrite(str(annotated_path), img_out)
                
                # Process thermal R-JPEG if provided (DJI dji_irp + dji_thermal_test for temperature insights)
                thermal_insights = None
                thermal_base64_bulk = img_data.get("thermal_base64")
                ambient_bulk = float(img_data.get("ambient_c") or 25.0)
                if thermal_base64_bulk:
                    try:
                        th_b64 = thermal_base64_bulk
                        if isinstance(th_b64, str) and th_b64.startswith("data:image"):
                            th_b64 = th_b64.split(",")[1] if "," in th_b64 else th_b64
                        thermal_bytes = base64.b64decode(th_b64)
                        thermal_analysis_dir = (run_dir.resolve()) / "thermal_analysis"
                        thermal_insights = _process_thermal_rjpeg(
                            thermal_bytes,
                            thermal_analysis_dir,
                            ambient_c=ambient_bulk,
                        )
                        if thermal_insights is None:
                            thermal_insights = {
                                "ambient_used": ambient_bulk,
                                "raw_output": "DJI thermal tools not available or processing failed.",
                                "temp_min": None,
                                "temp_max": None,
                                "temp_mean": None,
                            }
                        thermal_path = artifacts_dir / "thermal.jpg"
                        with open(thermal_path, "wb") as f:
                            f.write(thermal_bytes)
                        # Create thermal overlay with detection boxes (bulk: bboxes in 1920×1080)
                        if scaled_detections:
                            try:
                                thermal_img = cv2.imdecode(np.frombuffer(thermal_bytes, np.uint8), cv2.IMREAD_COLOR)
                                if thermal_img is not None:
                                    th_h, th_w = thermal_img.shape[:2]
                                    scale_x = th_w / OUTPUT_WIDTH
                                    scale_y = th_h / OUTPUT_HEIGHT
                                    thermal_overlay = thermal_img.copy()
                                    for det in scaled_detections:
                                        bbox = det.get('bbox', [0, 0, 0, 0])
                                        if len(bbox) != 4:
                                            continue
                                        x1, y1, x2, y2 = [int(c) for c in bbox]
                                        x1_t = max(0, min(int(x1 * scale_x), th_w - 1))
                                        y1_t = max(0, min(int(y1 * scale_y), th_h - 1))
                                        x2_t = max(0, min(int(x2 * scale_x), th_w - 1))
                                        y2_t = max(0, min(int(y2 * scale_y), th_h - 1))
                                        if x2_t <= x1_t or y2_t <= y1_t:
                                            continue
                                        severity = det.get('severity', 'MEDIUM')
                                        color = (0, 0, 255) if severity == 'HIGH' else ((0, 165, 255) if severity == 'MEDIUM' else (0, 255, 0))
                                        cv2.rectangle(thermal_overlay, (x1_t, y1_t), (x2_t, y2_t), color, 2)
                                        ct = det.get('component_type', 'Unknown').replace('_', ' ').title()
                                        conf = det.get('det_conf', 0.0)
                                        label = f"{ct} {conf:.1%}"
                                        font = cv2.FONT_HERSHEY_SIMPLEX
                                        (tw, tht), bl = cv2.getTextSize(label, font, 0.4, 1)
                                        ly = max(y1_t - 5, tht + 3)
                                        cv2.rectangle(thermal_overlay, (x1_t, ly - tht - 3), (x1_t + tw + 6, ly + bl), color, -1)
                                        cv2.putText(thermal_overlay, label, (x1_t + 3, ly), font, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
                                    cv2.imwrite(str(artifacts_dir / "thermal_overlay.jpg"), thermal_overlay)
                            except Exception as te:
                                print(f"WARNING: Failed to create thermal overlay for {filename}: {te}")
                    except Exception as e:
                        print(f"WARNING: Thermal processing failed for {filename}: {e}")
                        thermal_insights = {
                            "ambient_used": ambient_bulk,
                            "raw_output": str(e),
                            "temp_min": None,
                            "temp_max": None,
                            "temp_mean": None,
                        }
                
                # Calculate average confidence
                confidences = [d.get('det_conf', 0) for d in all_detections]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                
                # Save run.json (detections in 1920×1080 space to match overlay)
                bulk_artifacts = {
                    "overlay_url": f"/api/runs/{run_id}/artifacts/overlay",
                    "annotated_url": f"/api/runs/{run_id}/artifacts/annotated"
                }
                if thermal_base64_bulk and (artifacts_dir / "thermal.jpg").exists():
                    bulk_artifacts["thermal_url"] = f"/api/runs/{run_id}/artifacts/thermal"
                bulk_metadata = {
                    "original_filename": filename,
                    "primary_defect": primary_defect,
                    "batch_id": batch_id,
                    "output_width": OUTPUT_WIDTH,
                    "output_height": OUTPUT_HEIGHT
                }
                if thermal_insights:
                    bulk_metadata["thermal_insights"] = thermal_insights
                run_data = {
                    "id": run_id,
                    "run_id": run_id,
                    "tower_id": img_data.get("tower_id"),
                    "status": "completed",
                    "created_at": datetime.now().isoformat(),
                    "completed_at": datetime.now().isoformat(),
                    "findings_count": len(scaled_detections),
                    "must_review_count": len([d for d in scaled_detections if d.get('status') == 'needs_review']),
                    "ai_confidence": avg_confidence,
                    "detections": scaled_detections,
                    "artifacts": bulk_artifacts,
                    "metadata": bulk_metadata
                }
                
                run_json_path = run_dir / "run.json"
                with open(run_json_path, 'w', encoding='utf-8') as f:
                    json.dump(run_data, f, indent=2, ensure_ascii=False)
                
                # Organize by defect type if enabled
                if organize_by_defect:
                    defect_folder = batch_dir / folder_name
                    defect_folder.mkdir(parents=True, exist_ok=True)
                    
                    # Copy overlay image to defect folder
                    dest_path = defect_folder / filename
                    shutil.copy2(overlay_path, dest_path)
                    
                    defect_folders[folder_name].append({
                        "filename": filename,
                        "run_id": run_id,
                        "defect_type": primary_defect,
                        "detection_count": len(scaled_detections)
                    })
                
                all_runs.append(run_id)
                processed_count += 1
                
                # Cleanup
                tmp_path.unlink()
                
            except Exception as e:
                failed_count += 1
                print(f"Error processing {img_data.get('filename', 'unknown')}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Create summary report
        summary = {
            "batch_id": batch_id,
            "batch_dir": str(batch_dir),
            "total_images": len(images),
            "processed": processed_count,
            "failed": failed_count,
            "runs": all_runs,
            "organization": {
                "enabled": organize_by_defect,
                "folders": {folder: len(items) for folder, items in defect_folders.items()},
                "details": dict(defect_folders)
            }
        }
        
        # Save summary JSON
        summary_path = batch_dir / "summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        # Generate PDF batch report
        try:
            from src.utils.report_generator import generate_bulk_batch_report
            report_path = generate_bulk_batch_report(summary_path)
            print(f"DEBUG /api/pipeline/bulk: Batch report generated at {report_path}")
            summary["report_path"] = str(report_path)
        except Exception as e:
            print(f"WARNING: Failed to generate batch report: {e}")
            import traceback
            traceback.print_exc()
        
        return summary
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Bulk processing error: {str(e)}")


@app.get("/api/runs")
async def get_runs():
    """Get list of runs"""
    import json
    runs_dir = Path("outputs/runs")
    if not runs_dir.exists():
        return []
    
    runs = []
    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        run_json = run_dir / "run.json"
        if run_json.exists():
            try:
                with open(run_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    ai_confidence = data.get("ai_confidence", 0.0)
                    runs.append({
                        "id": data.get("run_id") or data.get("id"),
                        "run_id": data.get("run_id") or data.get("id"),
                        "tower_id": data.get("tower_id"),
                        "status": data.get("status", "pending"),
                        "created_at": data.get("created_at"),
                        "completed_at": data.get("completed_at"),
                        "findings_count": data.get("findings_count", len(data.get("detections", []))),
                        "must_review_count": data.get("must_review_count", 0),
                        "ai_confidence": ai_confidence,
                        "error": data.get("error")
                    })
            except Exception as e:
                print(f"Error reading {run_json}: {e}")
                continue
    
    runs.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return runs


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    """Get run details"""
    import json
    runs_dir = Path("outputs/runs")
    run_dir = runs_dir / run_id
    run_json = run_dir / "run.json"
    
    if not run_json.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    
    with open(run_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Ensure artifact URLs
    artifacts = data.get("artifacts", {})
    base = f"/api/runs/{run_id}/artifacts"
    if "annotated_url" not in artifacts:
        artifacts["annotated_url"] = f"{base}/annotated"
    if "overlay_url" not in artifacts:
        artifacts["overlay_url"] = f"{base}/overlay"
    if "report_url" not in artifacts:
        artifacts["report_url"] = f"{base}/report"
    data["artifacts"] = artifacts
    
    return data


@app.get("/api/bulk-batches/latest")
async def get_latest_bulk_batch():
    """Get the latest bulk processing batch summary"""
    import json
    bulk_output_dir = Path("outputs/bulk_processing")
    
    if not bulk_output_dir.exists():
        # Return empty response instead of 404 for better frontend handling
        return {
            "batch_id": None,
            "processed": 0,
            "failed": 0,
            "organization": {"enabled": False, "folders": {}}
        }
    
    # Find all batch directories
    batch_dirs = [d for d in bulk_output_dir.iterdir() if d.is_dir()]
    
    if not batch_dirs:
        # Return empty response instead of 404
        return {
            "batch_id": None,
            "processed": 0,
            "failed": 0,
            "organization": {"enabled": False, "folders": {}}
        }
    
    # Sort by directory name (timestamp) descending
    batch_dirs.sort(key=lambda x: x.name, reverse=True)
    latest_batch_dir = batch_dirs[0]
    
    # Read summary.json
    summary_path = latest_batch_dir / "summary.json"
    if not summary_path.exists():
        # Return empty response instead of 404
        return {
            "batch_id": latest_batch_dir.name,
            "processed": 0,
            "failed": 0,
            "organization": {"enabled": False, "folders": {}}
        }
    
    with open(summary_path, 'r', encoding='utf-8') as f:
        summary = json.load(f)
    
    return summary


@app.get("/api/bulk-batches/recent")
async def get_recent_bulk_batches(limit: int = Query(5, ge=1, le=100)):
    """Get recent bulk processing batch summaries"""
    import json
    
    bulk_output_dir = Path("outputs/bulk_processing")
    
    if not bulk_output_dir.exists():
        return []
    
    # Find all batch directories
    batch_dirs = [d for d in bulk_output_dir.iterdir() if d.is_dir()]
    
    if not batch_dirs:
        return []
    
    # Sort by directory name (timestamp) descending
    batch_dirs.sort(key=lambda x: x.name, reverse=True)
    
    # Limit the number of batches
    recent_batches = []
    for batch_dir in batch_dirs[:limit]:
        summary_path = batch_dir / "summary.json"
        if summary_path.exists():
            try:
                with open(summary_path, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                # Ensure batch_id and batch_dir are set
                if 'batch_id' not in summary:
                    summary['batch_id'] = batch_dir.name
                if 'batch_dir' not in summary:
                    summary['batch_dir'] = str(batch_dir)
                recent_batches.append(summary)
            except Exception as e:
                # Skip batches with invalid JSON
                continue
    
    return recent_batches


# IMPORTANT: Specific overlay routes must come BEFORE the generic artifact route
# FastAPI matches routes in order, so more specific routes must be defined first

@app.get("/api/runs/{run_id}/artifacts/overlays.zip")
async def download_overlays_zip(run_id: str):
    """Download all overlays as a ZIP file"""
    from fastapi.responses import FileResponse
    import zipfile
    import tempfile
    runs_dir = Path("outputs/runs")
    run_dir = runs_dir / run_id
    artifacts_dir = run_dir / "artifacts"
    
    if not artifacts_dir.exists():
        raise HTTPException(status_code=404, detail="No artifacts found")
    
    # Create temporary ZIP file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_zip:
        with zipfile.ZipFile(tmp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add overlay file if it exists
            for ext in [".jpg", ".png", ".jpeg"]:
                overlay_path = artifacts_dir / f"overlay{ext}"
                if overlay_path.exists():
                    zipf.write(overlay_path, f"overlay{ext}")
                    break
        
        return FileResponse(
            tmp_zip.name,
            media_type="application/zip",
            filename=f"overlays_{run_id}.zip",
            headers={"Cache-Control": "no-cache"}
        )


@app.get("/api/runs/{run_id}/artifacts/overlays/{filename}")
async def get_overlay_file(run_id: str, filename: str):
    """Get a specific overlay file"""
    from fastapi.responses import FileResponse
    runs_dir = Path("outputs/runs")
    run_dir = runs_dir / run_id
    artifacts_dir = run_dir / "artifacts"
    
    # Security: only allow overlay files
    if not filename.startswith("overlay"):
        raise HTTPException(status_code=400, detail="Invalid overlay filename")
    
    file_path = artifacts_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Overlay file not found")
    
    # Determine content type
    if filename.endswith(".png"):
        media_type = "image/png"
    else:
        media_type = "image/jpeg"
    
    return FileResponse(
        str(file_path),
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400, immutable"}
    )


@app.get("/api/runs/{run_id}/artifacts/overlays")
async def list_overlays(run_id: str):
    """List all overlay files for a run (for overlay gallery)"""
    runs_dir = Path("outputs/runs")
    run_dir = runs_dir / run_id
    
    # Check if run exists
    if not run_dir.exists():
        return []
    
    artifacts_dir = run_dir / "artifacts"
    
    if not artifacts_dir.exists():
        return []
    
    # Find all overlay files
    overlay_files = []
    for ext in [".jpg", ".png", ".jpeg"]:
        overlay_path = artifacts_dir / f"overlay{ext}"
        if overlay_path.exists():
            overlay_files.append({
                "filename": f"overlay{ext}",
                "url": f"/api/runs/{run_id}/artifacts/overlays/overlay{ext}"
            })
            break  # Only return one overlay (the main one)
    
    return overlay_files


@app.get("/api/runs/{run_id}/artifacts/{artifact_type}")
async def get_artifact(run_id: str, artifact_type: str):
    """Stream artifact file"""
    from fastapi.responses import FileResponse
    runs_dir = Path("outputs/runs")
    run_dir = runs_dir / run_id
    artifacts_dir = run_dir / "artifacts"
    
    # Map artifact types to filenames
    artifact_map = {
        "annotated": ["annotated.jpg", "annotated.png"],
        "overlay": ["overlay.jpg", "overlay.png"],
        "thermal": ["thermal_overlay.jpg", "thermal.jpg", "thermal.png"],
        "report": ["report.pdf"]
    }
    
    candidates = artifact_map.get(artifact_type, [])
    for filename in candidates:
        file_path = artifacts_dir / filename
        if file_path.exists():
            # Determine content type
            if artifact_type == "report":
                media_type = "application/pdf"
            elif filename.endswith(".png"):
                media_type = "image/png"
            else:
                media_type = "image/jpeg"
            
            return FileResponse(
                str(file_path),
                media_type=media_type,
                headers={"Cache-Control": "public, max-age=86400, immutable"}
            )

    # If report requested but missing, try to generate it from run.json
    if artifact_type == "report":
        run_json_path = run_dir / "run.json"
        if run_json_path.exists():
            try:
                from src.utils.report_generator import generate_single_upload_report
                report_path = generate_single_upload_report(run_json_path)
                if report_path.exists():
                    return FileResponse(
                        str(report_path),
                        media_type="application/pdf",
                        headers={"Cache-Control": "no-cache"},
                    )
            except Exception as e:
                print(f"WARNING: Failed to generate single-run report: {e}")
                import traceback
                traceback.print_exc()

    raise HTTPException(status_code=404, detail=f"Artifact {artifact_type} not found")


@app.get("/api/bulk-batches/{batch_id}/report")
async def get_bulk_batch_report(
    batch_id: str,
    regenerate: bool = Query(False, description="Force regenerate report (e.g. after template update)"),
):
    """Get bulk batch PDF report. Regenerates only if report is missing or older than batch data."""
    from fastapi.responses import FileResponse
    import traceback
    import os
    
    # Always use paths relative to API server file location for consistency
    try:
        api_server_dir = Path(__file__).parent.resolve()
    except NameError:
        # Fallback if __file__ is not available (shouldn't happen in normal execution)
        api_server_dir = Path.cwd()
    
    bulk_output_dir = api_server_dir / "outputs" / "bulk_processing"
    batch_dir = bulk_output_dir / batch_id
    
    print(f"DEBUG /api/bulk-batches/{batch_id}/report:")
    print(f"  API server dir: {api_server_dir}")
    print(f"  Bulk output dir: {bulk_output_dir}")
    print(f"  Batch dir: {batch_dir}")
    print(f"  Batch dir exists: {batch_dir.exists()}")
    print(f"  Working dir: {os.getcwd()}")
    
    # Fallback to relative path if absolute doesn't exist (for backwards compatibility)
    if not batch_dir.exists():
        bulk_output_dir_rel = Path("outputs/bulk_processing")
        batch_dir_rel = bulk_output_dir_rel / batch_id
        print(f"  Trying relative path: {batch_dir_rel}")
        print(f"  Relative path exists: {batch_dir_rel.exists()}")
        if batch_dir_rel.exists():
            batch_dir = batch_dir_rel
            bulk_output_dir = bulk_output_dir_rel
            print(f"DEBUG: Using relative path: {batch_dir}")
        else:
            checked_paths = [
                str(batch_dir),
                str(batch_dir_rel.resolve())
            ]
            error_detail = f"Batch '{batch_id}' not found. Checked: {', '.join(checked_paths)}. API server dir: {api_server_dir}, Working dir: {os.getcwd()}"
            print(f"ERROR: {error_detail}")
            raise HTTPException(status_code=404, detail=error_detail)
    else:
        print(f"DEBUG: Using absolute path: {batch_dir}")
    
    report_path = batch_dir / "batch_report.pdf"
    summary_path = batch_dir / "summary.json"

    if not summary_path.exists():
        raise HTTPException(status_code=404, detail=f"Batch summary not found at {summary_path}")

    # Regenerate if requested, or if report is missing or older than batch data (so repeat downloads are fast)
    report_stale = regenerate or not report_path.exists()
    if not report_stale:
        try:
            report_mtime = report_path.stat().st_mtime
            summary_mtime = summary_path.stat().st_mtime
            report_stale = summary_mtime > report_mtime
        except OSError:
            report_stale = True

    if report_stale:
        try:
            from src.utils.report_generator import generate_bulk_batch_report
            report_path = generate_bulk_batch_report(summary_path)
            if not report_path.exists():
                raise Exception(f"Report file was not created at {report_path}")
        except ImportError as e:
            error_msg = f"reportlab is not installed. Please install it with: pip install reportlab. Error: {str(e)}"
            print(f"ERROR: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
        except Exception as e:
            error_msg = f"Failed to generate report: {str(e)}"
            print(f"ERROR: {error_msg}")
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=error_msg)

    return FileResponse(
        str(report_path),
        media_type="application/pdf",
        filename=f"batch_report_{batch_id}.pdf",
        headers={"Cache-Control": "no-cache"},
    )


@app.post("/api/pipeline/video")
async def process_video(
    video_file: UploadFile = File(...),
    frame_interval: int = Query(1, description="Extract 1 frame every N seconds"),
    tower_id: str = Query(None, description="Optional tower ID")
):
    """
    Process video file by extracting frames and running detection pipeline on each frame.
    
    Args:
        video_file: Video file (MP4, AVI, MOV, etc.)
        frame_interval: Extract 1 frame every N seconds (default: 1)
        tower_id: Optional tower identifier
    
    Returns:
        JSON with video processing results including all frame detections
    """
    import uuid
    import json
    import base64
    from collections import defaultdict
    
    video_id = str(uuid.uuid4())[:8]
    video_output_dir = Path("outputs/videos")
    video_output_dir.mkdir(parents=True, exist_ok=True)
    video_run_dir = video_output_dir / video_id
    video_run_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = video_run_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Save uploaded video
        video_path = video_run_dir / video_file.filename
        with open(video_path, "wb") as f:
            content = await video_file.read()
            f.write(content)
        
        print(f"DEBUG /api/pipeline/video: Saved video to {video_path}")
        
        # Extract frames from video
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Could not open video file")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        
        print(f"DEBUG /api/pipeline/video: Video FPS={fps}, Total frames={total_frames}, Duration={duration:.2f}s")
        
        # Extract frames at specified interval
        frame_number = 0
        extracted_frames = []
        frame_timestamps = []
        
        frames_per_interval = int(fps * frame_interval) if fps > 0 else 30
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Extract frame at interval
            if frame_number % frames_per_interval == 0:
                timestamp = frame_number / fps if fps > 0 else frame_number / 30
                frame_filename = f"frame_{len(extracted_frames):04d}.jpg"
                frame_path = frames_dir / frame_filename
                cv2.imwrite(str(frame_path), frame)
                extracted_frames.append(frame_path)
                frame_timestamps.append(timestamp)
                print(f"DEBUG /api/pipeline/video: Extracted frame {len(extracted_frames)} at {timestamp:.2f}s")
            
            frame_number += 1
        
        cap.release()
        
        if not extracted_frames:
            raise HTTPException(status_code=400, detail="No frames extracted from video")
        
        print(f"DEBUG /api/pipeline/video: Extracted {len(extracted_frames)} frames")
        
        # Process each frame through the pipeline
        all_frame_results = []
        all_detections = []
        processed_count = 0
        failed_count = 0
        
        for idx, frame_path in enumerate(extracted_frames):
            try:
                print(f"DEBUG /api/pipeline/video: Processing frame {idx + 1}/{len(extracted_frames)}")
                
                # Load frame image
                img = cv2.imread(str(frame_path))
                if img is None:
                    print(f"WARNING: Could not load frame {frame_path}")
                    failed_count += 1
                    continue
                
                h, w = img.shape[:2]
                
                # Run predictions on frame (reuse existing logic)
                import asyncio
                
                def get_component_predictions():
                    api_response = api.predict_from_path(frame_path, confidence=conf_threshold)
                    if api_response is None:
                        api_response = {'predictions': []}
                    return api.parse_detection_results(api_response, w, h)
                
                def get_corrosion_predictions():
                    api_response = corrosion_api.predict_from_path(frame_path, confidence=corrosion_conf_threshold)
                    if api_response is None:
                        api_response = {'predictions': []}
                    return corrosion_api.parse_detection_results(api_response, w, h)
                
                # Run Component and Corrosion models
                component_detections_raw, corrosion_detections_raw = await asyncio.gather(
                    asyncio.to_thread(get_component_predictions),
                    asyncio.to_thread(get_corrosion_predictions)
                )
                
                # Process component detections
                component_detections = []
                dynamic_class_to_id = class_to_id.copy()
                next_dynamic_id = len(component_class_names)
                
                for det in component_detections_raw:
                    if det is None or not isinstance(det, dict):
                        continue
                    model_class = det.get('class', 'unknown') or 'unknown'
                    unified_class = class_mapping.get(model_class, model_class) if class_mapping else model_class
                    class_id = dynamic_class_to_id.get(unified_class, -1)
                    if class_id == -1:
                        if unified_class not in dynamic_class_to_id:
                            dynamic_class_to_id[unified_class] = next_dynamic_id
                            next_dynamic_id += 1
                        class_id = dynamic_class_to_id[unified_class]
                    
                    component_detections.append({
                        'component_type': unified_class,
                        'det_conf': det.get('confidence', 0.0),
                        'bbox': det.get('bbox', [0, 0, 0, 0]),
                        'class_id': class_id
                    })
                
                # Process corrosion detections
                corrosion_detections = []
                for det in corrosion_detections_raw:
                    if det is None or not isinstance(det, dict):
                        continue
                    corrosion_detections.append({
                        'component_type': det.get('class', 'corrosion'),
                        'defect_type': det.get('class', 'corrosion'),
                        'defect_conf': det.get('confidence', 0.0),
                        'det_conf': det.get('confidence', 0.0),
                        'bbox': det.get('bbox', [0, 0, 0, 0]),
                        'detection_type': 'corrosion'
                    })
                
                # Combine all detections
                frame_detections = component_detections + corrosion_detections
                
                # Add frame timestamp to each detection
                for det in frame_detections:
                    det['frame_timestamp'] = frame_timestamps[idx]
                    det['frame_number'] = idx
                    all_detections.append(det)
                
                # Create overlay for this frame
                overlay_img = img.copy()
                for det in frame_detections:
                    bbox = det.get('bbox', [])
                    if len(bbox) != 4:
                        continue
                    x1, y1, x2, y2 = [int(coord) for coord in bbox]
                    
                    severity = det.get('severity', 'MEDIUM')
                    is_corrosion = (
                        'defect_type' in det or 
                        'corrosion' in det.get('component_type', '').lower() or
                        det.get('detection_type') == 'corrosion'
                    )
                    
                    if is_corrosion:
                        color = (255, 0, 255)  # Magenta for corrosion
                    elif severity == 'HIGH':
                        color = (0, 0, 255)  # Red
                    elif severity == 'MEDIUM':
                        color = (0, 165, 255)  # Orange
                    else:
                        color = (0, 255, 255)  # Yellow
                    
                    cv2.rectangle(overlay_img, (x1, y1), (x2, y2), color, 3)
                    
                    component_type = det.get('defect_type') or det.get('component_type', 'Unknown')
                    confidence = det.get('defect_conf') or det.get('det_conf', 0.0)
                    label = f"{component_type.replace('_', ' ').title()} {confidence:.1%}"
                    
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.6
                    text_thickness = 2
                    (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, text_thickness)
                    
                    label_y = max(y1 - 10, text_height + 5)
                    cv2.rectangle(
                        overlay_img,
                        (x1, label_y - text_height - 5),
                        (x1 + text_width + 10, label_y + baseline),
                        color,
                        -1
                    )
                    cv2.putText(
                        overlay_img,
                        label,
                        (x1 + 5, label_y),
                        font,
                        font_scale,
                        (255, 255, 255),
                        text_thickness,
                        cv2.LINE_AA
                    )
                
                # Save overlay frame
                overlay_path = frames_dir / f"overlay_{idx:04d}.jpg"
                cv2.imwrite(str(overlay_path), overlay_img)
                
                all_frame_results.append({
                    'frame_number': idx,
                    'timestamp': frame_timestamps[idx],
                    'detections_count': len(frame_detections),
                    'frame_path': f"/api/videos/{video_id}/frames/frame_{idx:04d}",
                    'overlay_path': f"/api/videos/{video_id}/frames/overlay_{idx:04d}"
                })
                
                processed_count += 1
                
            except Exception as e:
                print(f"ERROR processing frame {idx}: {str(e)}")
                import traceback
                traceback.print_exc()
                failed_count += 1
        
        # Aggregate results by component/defect type
        defect_summary = defaultdict(int)
        for det in all_detections:
            component_type = det.get('component_type', 'Unknown')
            defect_summary[component_type] += 1
        
        # Calculate average confidence
        confidences = [d.get('det_conf', 0) for d in all_detections]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Save video processing results
        video_results = {
            "video_id": video_id,
            "tower_id": tower_id,
            "status": "completed",
            "created_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
            "video_info": {
                "filename": video_file.filename,
                "duration_seconds": duration,
                "fps": fps,
                "total_frames": total_frames,
                "extracted_frames": len(extracted_frames),
                "frame_interval": frame_interval
            },
            "processing_stats": {
                "processed_frames": processed_count,
                "failed_frames": failed_count,
                "total_detections": len(all_detections),
                "average_confidence": avg_confidence
            },
            "defect_summary": dict(defect_summary),
            "frame_results": all_frame_results,
            "all_detections": all_detections
        }
        
        # Save results JSON
        results_json_path = video_run_dir / "results.json"
        with open(results_json_path, 'w', encoding='utf-8') as f:
            json.dump(video_results, f, indent=2, ensure_ascii=False)
        
        print(f"DEBUG /api/pipeline/video: Video processing completed. Processed {processed_count} frames, {len(all_detections)} total detections")
        
        return {
            "video_id": video_id,
            "status": "completed",
            "processed_frames": processed_count,
            "total_detections": len(all_detections),
            "defect_summary": dict(defect_summary),
            "results_url": f"/api/videos/{video_id}/results"
        }
        
    except Exception as e:
        import traceback
        error_msg = f"Video processing failed: {str(e)}"
        print(f"ERROR /api/pipeline/video: {error_msg}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/api/videos/{video_id}/results")
async def get_video_results(video_id: str):
    """Get video processing results"""
    video_output_dir = Path("outputs/videos")
    video_run_dir = video_output_dir / video_id
    results_json_path = video_run_dir / "results.json"
    
    if not results_json_path.exists():
        raise HTTPException(status_code=404, detail=f"Video results not found for {video_id}")
    
    import json
    with open(results_json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@app.get("/api/videos/{video_id}/frames/{frame_filename}")
async def get_video_frame(video_id: str, frame_filename: str):
    """Get a processed frame from video"""
    from fastapi.responses import FileResponse
    video_output_dir = Path("outputs/videos")
    video_run_dir = video_output_dir / video_id
    frames_dir = video_run_dir / "frames"
    frame_path = frames_dir / frame_filename
    
    if not frame_path.exists():
        raise HTTPException(status_code=404, detail=f"Frame not found: {frame_filename}")
    
    return FileResponse(
        str(frame_path),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"}
    )


@app.get("/api/videos/recent")
async def get_recent_videos(limit: int = Query(50, ge=1, le=100)):
    """Get recent video processing results"""
    import json
    
    video_output_dir = Path("outputs/videos")
    
    if not video_output_dir.exists():
        return []
    
    # Find all video directories
    video_dirs = [d for d in video_output_dir.iterdir() if d.is_dir()]
    
    if not video_dirs:
        return []
    
    # Sort by directory name (video_id) - newer ones likely have longer UUIDs or timestamps
    # Actually, sort by modification time of results.json
    video_results = []
    for video_dir in video_dirs:
        results_json_path = video_dir / "results.json"
        if results_json_path.exists():
            try:
                # Get modification time for sorting
                mtime = results_json_path.stat().st_mtime
                with open(results_json_path, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                # Ensure video_id is set
                if 'video_id' not in summary:
                    summary['video_id'] = video_dir.name
                summary['_mtime'] = mtime
                video_results.append(summary)
            except Exception as e:
                # Skip videos with invalid JSON
                print(f"WARNING: Failed to load video {video_dir.name}: {e}")
                continue
    
    # Sort by modification time descending (most recent first)
    video_results.sort(key=lambda x: x.get('_mtime', 0), reverse=True)
    
    # Remove temporary _mtime field
    for result in video_results:
        result.pop('_mtime', None)
    
    # Limit the number of videos
    return video_results[:limit]


@app.get("/api/videos/{video_id}/download")
async def download_video_with_overlays(video_id: str):
    """Download video with detection overlays"""
    from fastapi.responses import FileResponse
    import json
    
    video_output_dir = Path("outputs/videos")
    video_run_dir = video_output_dir / video_id
    
    if not video_run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    
    # Check if processed video with overlays already exists
    processed_video_path = video_run_dir / "video_with_overlays.mp4"
    
    if processed_video_path.exists():
        return FileResponse(
            str(processed_video_path),
            media_type="video/mp4",
            filename=f"video_{video_id}_with_overlays.mp4",
            headers={"Cache-Control": "public, max-age=86400"}
        )
    
    # Load results to get frame information
    results_json_path = video_run_dir / "results.json"
    if not results_json_path.exists():
        raise HTTPException(status_code=404, detail=f"Video results not found for {video_id}")
    
    with open(results_json_path, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    # Find original video file
    video_files = list(video_run_dir.glob("*.mp4")) + list(video_run_dir.glob("*.avi")) + list(video_run_dir.glob("*.mov"))
    if not video_files:
        raise HTTPException(status_code=404, detail="Original video file not found")
    
    original_video_path = video_files[0]
    frames_dir = video_run_dir / "frames"
    
    # Create video with overlays using OpenCV
    try:
        cap = cv2.VideoCapture(str(original_video_path))
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Could not open original video")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(processed_video_path), fourcc, fps, (width, height))
        
        frame_results = results.get('frame_results', [])
        frame_dict = {fr['frame_number']: fr for fr in frame_results}
        
        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Check if we have an overlay for this frame
            if frame_idx in frame_dict:
                overlay_filename = f"overlay_{frame_idx:04d}.jpg"
                overlay_path = frames_dir / overlay_filename
                if overlay_path.exists():
                    overlay_frame = cv2.imread(str(overlay_path))
                    if overlay_frame is not None:
                        # Resize overlay to match original frame size if needed
                        if overlay_frame.shape[:2] != (height, width):
                            overlay_frame = cv2.resize(overlay_frame, (width, height))
                        frame = overlay_frame
            
            out.write(frame)
            frame_idx += 1
        
        cap.release()
        out.release()
        
        if not processed_video_path.exists():
            raise HTTPException(status_code=500, detail="Failed to create processed video")
        
        return FileResponse(
            str(processed_video_path),
            media_type="video/mp4",
            filename=f"video_{video_id}_with_overlays.mp4",
            headers={"Cache-Control": "public, max-age=86400"}
        )
        
    except Exception as e:
        import traceback
        error_msg = f"Failed to create video with overlays: {str(e)}"
        print(f"ERROR: {error_msg}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_msg)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
