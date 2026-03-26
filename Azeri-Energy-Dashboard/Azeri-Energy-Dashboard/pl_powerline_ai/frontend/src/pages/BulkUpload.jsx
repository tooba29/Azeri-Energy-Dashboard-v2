import React, { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import axios from 'axios'
import './BulkUpload.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function BulkUpload() {
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState({ current: 0, total: 0 })
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  const onDrop = useCallback((acceptedFiles) => {
    setFiles(acceptedFiles)
    setResults(null)
    setError(null)
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png', '.bmp', '.tiff']
    },
    multiple: true
  })

  const removeFile = (index) => {
    setFiles(files.filter((_, i) => i !== index))
  }

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

  const processBulk = async () => {
    if (files.length === 0) return

    setUploading(true)
    setError(null)
    setProgress({ current: 0, total: files.length })

    let processingInterval = null

    try {
      const formData = new FormData()
      files.forEach(file => {
        formData.append('files', file)
      })

      // Track upload progress (0-30% of total)
      const response = await axios.post(`${API_URL}/predict/batch`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const uploadPercent = progressEvent.loaded / progressEvent.total
            // Upload represents ~30% of total time, processing is ~70%
            const totalPercent = uploadPercent * 0.3
            setProgress({
              current: Math.min(
                files.length, 
                Math.max(1, Math.floor(totalPercent * files.length))
              ),
              total: files.length
            })
          }
        }
      })
      
      // Upload complete, now processing (30-100%)
      setProgress({
        current: Math.floor(files.length * 0.3),
        total: files.length
      })
      
      // Simulate processing progress (since we can't get real-time updates from server)
      processingInterval = setInterval(() => {
        setProgress(prev => {
          if (prev.current < prev.total * 0.95) {
            return {
              current: Math.min(prev.total, prev.current + 1),
              total: prev.total
            }
          }
          return prev
        })
      }, 500)

      // Store results in localStorage
      const history = JSON.parse(localStorage.getItem('inspectionHistory') || '[]')
      
      // Process all FileReader operations and create thumbnails
      const promises = response.data.results.map((result, index) => {
        const file = files[index]
        const imageId = `${Date.now()}-${index}`
        
        return new Promise(async (resolve) => {
          const reader = new FileReader()
          reader.onload = async (e) => {
            // Create thumbnail to save space
            const thumbnail = await createThumbnail(e.target.result)
            const resultItem = {
              id: imageId,
              imageName: result.image_name,
              imageData: thumbnail, // Store thumbnail instead of full image
              predictions: result,
              timestamp: new Date().toISOString(),
            }
            resolve(resultItem)
          }
          reader.readAsDataURL(file)
        })
      })

      // Wait for all FileReader operations to complete
      const resultItems = await Promise.all(promises)
      
      // Clear processing interval
      if (processingInterval) {
        clearInterval(processingInterval)
      }
      
      // Show 100% complete
      setProgress({
        current: files.length,
        total: files.length
      })
      
      // Save with error handling
      try {
        resultItems.forEach(item => history.unshift(item))
        // Keep only last 20 items to save space
        const limitedHistory = history.slice(0, 20)
        localStorage.setItem('inspectionHistory', JSON.stringify(limitedHistory))
      } catch (storageError) {
        if (storageError.name === 'QuotaExceededError' || storageError.code === 22) {
          // Clear old items and keep only 10 most recent
          const reducedHistory = history.slice(0, 10)
          resultItems.slice(0, Math.min(10 - reducedHistory.length, resultItems.length)).forEach(item => {
            reducedHistory.unshift(item)
          })
          localStorage.setItem('inspectionHistory', JSON.stringify(reducedHistory))
          console.warn('Storage quota exceeded. Reduced history to 10 items.')
        } else {
          throw storageError
        }
      }
      
      setResults(response.data)
      setUploading(false)

    } catch (err) {
      // Clear processing interval on error
      if (processingInterval) {
        clearInterval(processingInterval)
      }
      setError(err.response?.data?.detail || err.message || 'Failed to process images')
      setUploading(false)
      console.error('Error:', err)
    }
  }

  const viewResult = (imageName) => {
    const history = JSON.parse(localStorage.getItem('inspectionHistory') || '[]')
    const found = history.find(item => item.imageName === imageName)
    if (found) {
      navigate(`/results/${found.id}`)
    }
  }

  return (
    <div className="bulk-upload-container">
      <div className="bulk-header">
        <h1>Bulk Image Upload</h1>
        <p>Upload multiple images at once for batch processing</p>
        <div className="upload-mode-switch">
          <button
            onClick={() => navigate('/')}
            className="single-mode-button"
          >
            📷 Switch to Single Upload Mode
          </button>
        </div>
      </div>

      <div className="bulk-upload-section">
        <div
          {...getRootProps()}
          className={`bulk-dropzone ${isDragActive ? 'active' : ''} ${uploading ? 'uploading' : ''}`}
        >
          <input {...getInputProps()} />
          <div className="bulk-upload-content">
            <div className="bulk-upload-icon">📦</div>
            <p className="bulk-upload-text">
              {isDragActive
                ? 'Drop the images here'
                : 'Drag & drop multiple images here, or click to select'}
            </p>
            <p className="bulk-upload-hint">
              Select multiple images (JPEG, PNG, BMP, TIFF)
            </p>
          </div>
        </div>

        {files.length > 0 && (
          <div className="files-list">
            <div className="files-header">
              <h3>Selected Files ({files.length})</h3>
              <button
                onClick={() => setFiles([])}
                className="clear-files-button"
                disabled={uploading}
              >
                Clear All
              </button>
            </div>
            <div className="files-grid">
              {files.map((file, index) => (
                <div key={index} className="file-item">
                  <img
                    src={URL.createObjectURL(file)}
                    alt={file.name}
                    className="file-preview"
                  />
                  <div className="file-info">
                    <p className="file-name" title={file.name}>{file.name}</p>
                    <p className="file-size">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                  {!uploading && (
                    <button
                      onClick={() => removeFile(index)}
                      className="remove-file-button"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
            </div>
            {!uploading && (
              <button
                onClick={processBulk}
                className="process-button"
                disabled={files.length === 0}
              >
                Process {files.length} Image{files.length !== 1 ? 's' : ''}
              </button>
            )}
          </div>
        )}

        {uploading && (
          <div className="progress-section">
            <div className="progress-header">
              <h3>Processing Images...</h3>
              <span className="progress-text">
                {progress.current} / {progress.total}
              </span>
            </div>
            <div className="progress-bar-container">
              <div
                className="progress-bar"
                style={{ width: `${Math.min(100, (progress.current / progress.total) * 100)}%` }}
              ></div>
            </div>
            <div className="progress-percentage-container">
              <span className="progress-percentage-large">
                {progress.total > 0 
                  ? Math.round((progress.current / progress.total) * 100) 
                  : 0}%
              </span>
              <p className="progress-percentage-label">Complete</p>
            </div>
            <p className="progress-status">
              {progress.current === 0 
                ? 'Uploading images to server...' 
                : progress.current < progress.total
                ? `Processing image ${progress.current} of ${progress.total}...`
                : 'Finalizing results...'}
            </p>
          </div>
        )}

        {error && (
          <div className="error-message">
            <span className="error-icon">⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {results && (
          <div className="results-summary">
            <h2>Processing Complete</h2>
            <div className="summary-stats">
              <div className="summary-stat">
                <div className="stat-value">{results.total_images}</div>
                <div className="stat-label">Total Images</div>
              </div>
              <div className="summary-stat success">
                <div className="stat-value">{results.successful}</div>
                <div className="stat-label">Successful</div>
              </div>
              <div className="summary-stat error">
                <div className="stat-value">{results.failed}</div>
                <div className="stat-label">Failed</div>
              </div>
            </div>

            {results.results.length > 0 && (
              <div className="results-list">
                <h3>Processed Images</h3>
                <div className="results-grid">
                  {results.results.map((result, index) => (
                    <div key={index} className="result-card">
                      <div className="result-header">
                        <span className="result-name" title={result.image_name}>
                          {result.image_name}
                        </span>
                        <span className="result-count">
                          {result.detections.length} detections
                        </span>
                      </div>
                      <div className="result-actions">
                        <button
                          onClick={() => viewResult(result.image_name)}
                          className="view-result-button"
                        >
                          View Details
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {results.errors.length > 0 && (
              <div className="errors-list">
                <h3>Errors</h3>
                {results.errors.map((error, index) => (
                  <div key={index} className="error-item">
                    <span className="error-file">{error.image_name}</span>
                    <span className="error-message">{error.error}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="results-actions">
              <button
                onClick={() => navigate('/history')}
                className="view-history-button"
              >
                View All in History
              </button>
              <button
                onClick={() => {
                  setFiles([])
                  setResults(null)
                }}
                className="process-more-button"
              >
                Process More Images
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default BulkUpload
