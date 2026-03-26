# Model Integration Usage Guide

This project now uses **model API only** for inference. No local YOLO models are required.

## Setup

1. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

2. **Configure model:**
   - The config file is already set up at `configs/model.yaml`
   - Your API key and model ID are already configured
   - Update `class_mapping` if your model uses different class names

## Usage

### Command Line Inference

Process images using model API:

```powershell
python scripts/13_full_inference_export_json.py `
    --model-config configs/model.yaml `
    --source ./test_images `
    --output ./outputs/predictions
```

**Options:**
- `--model-config`: Path to model config YAML (default: `configs/model.yaml`)
- `--source`: Source directory or image file (required)
- `--output`: Output directory (default: `outputs/predictions`)
- `--components-config`: Components config path (default: `configs/components.yaml`)
- `--conf-threshold`: Confidence threshold (overrides config)
- `--no-annotated`: Skip saving annotated images
- `--no-json`: Skip saving JSON files
- `--no-csv`: Skip saving summary CSV

### API Server for Frontend

Start the FastAPI server:

```powershell
python api_server.py
```

The server will run on `http://localhost:8000`

**Endpoints:**
- `POST /predict` - Upload an image and get predictions
- `GET /health` - Health check

**Frontend Example (JavaScript):**

```javascript
const formData = new FormData();
formData.append('file', imageFile);

const response = await fetch('http://localhost:8000/predict', {
  method: 'POST',
  body: formData
});

const result = await response.json();
console.log(result);
```

**Response Format:**
```json
{
  "image_name": "image.jpg",
  "width": 1920,
  "height": 1080,
  "detections": [
    {
      "component_class": "glass_insulator",
      "component_class_id": 0,
      "component_conf": 0.95,
      "bbox_xyxy": [100, 200, 300, 400],
      "model_class": "glass_insulator"
    }
  ]
}
```

## Configuration

Edit `configs/model.yaml`:

```yaml
api_key: "your-api-key"
api_url: "https://serverless.roboflow.com"
model_id: "yeni-wbzkp/my-first-project-glnqx/1"

# Map model class names to your unified classes
class_mapping:
  "model_class_name": "unified_class_name"

confidence_threshold: 0.25
```

## Output Structure

After running inference, you'll get:

```
outputs/predictions/
├── annotated/          # Annotated images with bounding boxes
├── json/              # JSON file per image
├── summary.csv        # Summary statistics
└── summary.json       # Summary in JSON format
```

## Notes

- The system uses **only model API** - no local models needed
- Make sure you have internet connection for API calls
- **ALL classes** from model are used - no filtering or exclusion
- Class mapping in config allows you to map model classes to your unified class names
- If a class isn't mapped, it will use the model class name as-is and assign a dynamic class ID
- All detections are included in the output, regardless of whether they're in the mapping
