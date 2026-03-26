# Powerline Inspection AI - Frontend

Modern React frontend for the Powerline Inspection AI System.

## Features

- 🖼️ **Image Upload** - Drag & drop or click to upload images
- 🔍 **Real-time Detection** - Get instant component detection results
- 📊 **Visual Results** - See bounding boxes and detection details
- 📚 **History** - View all previous inspections
- ⚙️ **Settings** - Configure API connection

## Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Start development server:**
   ```bash
   npm run dev
   ```

3. **Build for production:**
   ```bash
   npm run build
   ```

## Configuration

The frontend connects to the FastAPI server at `http://localhost:8000` by default.

To change the API URL:
1. Go to Settings page
2. Update the API URL
3. Click "Test Connection" to verify
4. Click "Save Settings"

Or set environment variable:
```bash
VITE_API_URL=http://your-api-url:8000 npm run dev
```

## Pages

- **Home** (`/`) - Upload images and get predictions
- **Results** (`/results/:id`) - View detailed detection results
- **History** (`/history`) - Browse inspection history
- **Settings** (`/settings`) - Configure API and view information

## Tech Stack

- React 18
- React Router DOM
- Axios
- React Dropzone
- Vite

## API Integration

The frontend communicates with the FastAPI backend:

- `POST /predict` - Upload image and get predictions
- `GET /health` - Check API health

All detected classes are displayed, including unmapped classes.
