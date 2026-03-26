import React, { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import axios from 'axios'
import './Home.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function Home() {
  const [uploading, setUploading] = useState(false)
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  // Helper function to create thumbnail
  const createThumbnail = (imageData, maxWidth = 200) => {
    return new Promise((resolve) => {
      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement('canvas')
        const scale = Math.min(maxWidth / img.width, maxWidth / img.height)
        canvas.width = img.width * scale
        canvas.height = img.height * scale
        const ctx = canvas.getContext('2d')
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
        resolve(canvas.toDataURL('image/jpeg', 0.7)) // Compressed thumbnail
      }
      img.onerror = () => resolve(imageData) // Fallback to original if thumbnail fails
      img.src = imageData
    })
  }

  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0]
    if (!file) return

    // Create preview
    const reader = new FileReader()
    reader.onload = () => setPreview(reader.result)
    reader.readAsDataURL(file)

    // Upload and predict
    setUploading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await axios.post(`${API_URL}/predict`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      // Create thumbnail to save space
      const fullImageData = reader.result
      const thumbnail = await createThumbnail(fullImageData)

      // Store result in localStorage
      const imageId = Date.now().toString()
      const result = {
        id: imageId,
        imageName: file.name,
        imageData: thumbnail, // Store thumbnail instead of full image
        predictions: response.data,
        timestamp: new Date().toISOString(),
      }

      // Save to history with error handling
      try {
        const history = JSON.parse(localStorage.getItem('inspectionHistory') || '[]')
        history.unshift(result)
        // Reduce to last 20 items to save space
        const limitedHistory = history.slice(0, 20)
        localStorage.setItem('inspectionHistory', JSON.stringify(limitedHistory))
      } catch (storageError) {
        if (storageError.name === 'QuotaExceededError' || storageError.code === 22) {
          // Clear old items and try again
          const history = JSON.parse(localStorage.getItem('inspectionHistory') || '[]')
          const reducedHistory = history.slice(0, 10) // Keep only 10 most recent
          reducedHistory.unshift(result)
          localStorage.setItem('inspectionHistory', JSON.stringify(reducedHistory))
          console.warn('Storage quota exceeded. Reduced history to 10 items.')
        } else {
          throw storageError
        }
      }

      // Navigate to results
      navigate(`/results/${imageId}`)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to process image')
      console.error('Error:', err)
    } finally {
      setUploading(false)
    }
  }, [navigate])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png', '.bmp', '.tiff']
    },
    multiple: false
  })

  return (
    <div className="home-container">
      <div className="home-header">
        <h1>Powerline Component Detection</h1>
        <p>Upload an image to detect and classify powerline components using AI</p>
        <div className="upload-mode-switch">
          <button
            onClick={() => navigate('/bulk')}
            className="bulk-mode-button"
          >
            📦 Switch to Bulk Upload Mode
          </button>
        </div>
      </div>

      <div className="upload-section">
        <div
          {...getRootProps()}
          className={`dropzone ${isDragActive ? 'active' : ''} ${uploading ? 'uploading' : ''}`}
        >
          <input {...getInputProps()} />
          {uploading ? (
            <div className="upload-content">
              <div className="spinner"></div>
              <p>Processing image...</p>
            </div>
          ) : preview ? (
            <div className="preview-container">
              <img src={preview} alt="Preview" className="preview-image" />
              <p className="preview-text">Click or drag to upload a different image</p>
            </div>
          ) : (
            <div className="upload-content">
              <div className="upload-icon">📤</div>
              <p className="upload-text">
                {isDragActive
                  ? 'Drop the image here'
                  : 'Drag & drop an image here, or click to select'}
              </p>
              <p className="upload-hint">Supports: JPEG, PNG, BMP, TIFF</p>
            </div>
          )}
        </div>

        {error && (
          <div className="error-message">
            <span className="error-icon">⚠️</span>
            <span>{error}</span>
          </div>
        )}
      </div>

      <div className="info-section">
        <h2>How it works</h2>
        <div className="info-cards">
          <div className="info-card">
            <div className="info-icon">1️⃣</div>
            <h3>Upload Image</h3>
            <p>Upload a powerline inspection image</p>
          </div>
          <div className="info-card">
            <div className="info-icon">2️⃣</div>
            <h3>AI Detection</h3>
            <p>AI detects all components</p>
          </div>
          <div className="info-card">
            <div className="info-icon">3️⃣</div>
            <h3>View Results</h3>
            <p>See detected components with bounding boxes</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Home
