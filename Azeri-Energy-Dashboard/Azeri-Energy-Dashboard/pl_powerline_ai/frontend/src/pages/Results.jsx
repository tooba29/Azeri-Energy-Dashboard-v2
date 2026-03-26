import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import './Results.css'

function Results() {
  const { imageId } = useParams()
  const navigate = useNavigate()
  const [result, setResult] = useState(null)
  const [selectedDetection, setSelectedDetection] = useState(null)
  // All hooks must be declared at the top, before any conditional returns
  const [imageDimensions, setImageDimensions] = useState({ width: 0, height: 0 })
  const [scale, setScale] = useState({ x: 1, y: 1 })

  // Extract data safely (before hooks to use in dependencies)
  const imageData = result?.imageData
  const predictions = result?.predictions
  const imageName = result?.imageName
  const timestamp = result?.timestamp
  
  // API response structure: { image_name, width, height, detections }
  // predictions is the API response directly
  const detections = (predictions && predictions.detections) ? predictions.detections : []
  const width = (predictions && predictions.width) ? predictions.width : 0
  const height = (predictions && predictions.height) ? predictions.height : 0

  // ALL hooks must be declared before any conditional returns
  useEffect(() => {
    // Load result from localStorage
    try {
      const history = JSON.parse(localStorage.getItem('inspectionHistory') || '[]')
      const found = history.find(item => item.id === imageId)
      
      if (found) {
        console.log('Found result:', found)
        console.log('Predictions:', found.predictions)
        setResult(found)
      } else {
        console.warn('Result not found for imageId:', imageId)
        console.log('Available IDs:', history.map(item => item.id))
        // If not found, redirect to home
        navigate('/')
      }
    } catch (error) {
      console.error('Error loading result:', error)
      navigate('/')
    }
  }, [imageId, navigate])

  useEffect(() => {
    if (!imageData) return
    
    const img = new Image()
    img.onload = () => {
      // Use original dimensions from predictions if available, otherwise use loaded image
      const originalWidth = (predictions && predictions.width) ? predictions.width : img.width
      const originalHeight = (predictions && predictions.height) ? predictions.height : img.height
      
      const containerWidth = Math.min(800, window.innerWidth - 40)
      const scaleX = containerWidth / originalWidth
      const scaleY = scaleX
      setImageDimensions({ width: originalWidth, height: originalHeight })
      setScale({ x: scaleX, y: scaleY })
    }
    img.src = imageData
  }, [imageData, predictions])

  useEffect(() => {
    if (!imageData || !detections || !Array.isArray(detections) || !scale || scale.x === 0) return
    
    const canvas = document.getElementById('result-canvas')
    if (!canvas) return
    
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const drawBoundingBoxes = () => {
      const img = new Image()
      img.onload = () => {
        // Use original image dimensions from predictions if available, otherwise use loaded image
        const originalWidth = predictions?.width || img.width
        const originalHeight = predictions?.height || img.height
        
        // Calculate scale based on original dimensions
        const containerWidth = Math.min(800, window.innerWidth - 40)
        const actualScaleX = containerWidth / originalWidth
        const actualScaleY = actualScaleX
        
        // Set canvas size
        canvas.width = originalWidth * actualScaleX
        canvas.height = originalHeight * actualScaleY
        
        // Clear canvas first
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        
        // Draw the image (scaled)
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

        // Draw bounding boxes
        detections.forEach((det, index) => {
          if (!det || !det.bbox_xyxy || !Array.isArray(det.bbox_xyxy) || det.bbox_xyxy.length !== 4) return
          
          const [x1, y1, x2, y2] = det.bbox_xyxy
          
          // Scale bounding box coordinates
          const scaledX1 = x1 * actualScaleX
          const scaledY1 = y1 * actualScaleY
          const scaledX2 = x2 * actualScaleX
          const scaledY2 = y2 * actualScaleY
          
          // Calculate width and height
          const boxWidth = scaledX2 - scaledX1
          const boxHeight = scaledY2 - scaledY1

          // Different colors for component vs corrosion
          const isCorrosion = det.detection_type === 'corrosion'
          let color
          if (isCorrosion) {
            color = '#ef4444' // Red for corrosion
          } else {
            const colors = [
              '#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4'
            ]
            const classId = det.component_class_id || 0
            color = colors[classId % colors.length] || '#666'
          }

          // Draw rectangle
          ctx.strokeStyle = color
          ctx.lineWidth = 3
          ctx.strokeRect(scaledX1, scaledY1, boxWidth, boxHeight)

          // Draw label background
          const className = det.component_class || det.corrosion_class || det.model_class || det.original_class || 'Unknown'
          const confidence = det.component_conf || det.corrosion_conf || 0
          const label = `${className} (${(confidence * 100).toFixed(1)}%)`
          ctx.font = 'bold 14px Arial'
          const textWidth = ctx.measureText(label).width
          const textHeight = 20

          // Draw label background (above the box)
          ctx.fillStyle = color
          ctx.fillRect(scaledX1, Math.max(0, scaledY1 - textHeight - 5), textWidth + 10, textHeight + 5)

          // Draw label text
          ctx.fillStyle = 'white'
          ctx.fillText(label, scaledX1 + 5, Math.max(textHeight, scaledY1 - 8))
        })
      }
      img.onerror = () => {
        console.error('Failed to load image for canvas')
      }
      img.src = imageData
    }
    
    drawBoundingBoxes()
  }, [imageData, scale, detections, predictions])

  // Now we can have conditional returns AFTER all hooks
  if (!result) {
    return (
      <div className="loading-container">
        <div className="spinner"></div>
        <p>Loading results...</p>
        <p style={{ fontSize: '0.9rem', color: '#666', marginTop: '1rem' }}>
          If this takes too long, the result may not be found. 
          <button 
            onClick={() => navigate('/')} 
            style={{ marginLeft: '0.5rem', padding: '0.5rem 1rem', cursor: 'pointer' }}
          >
            Go Home
          </button>
        </p>
      </div>
    )
  }

  const classCounts = {}
  if (detections && Array.isArray(detections)) {
    detections.forEach(det => {
      if (det && typeof det === 'object') {
        const className = det.component_class || det.corrosion_class || det.model_class || det.original_class || 'unknown'
        classCounts[className] = (classCounts[className] || 0) + 1
      }
    })
  }

  return (
    <div className="results-container">
      <div className="results-header">
        <button onClick={() => navigate('/')} className="back-button">
          ← Back to Home
        </button>
        <h1>Detection Results</h1>
        <p className="image-name">{imageName}</p>
        <p className="timestamp">{new Date(timestamp).toLocaleString()}</p>
      </div>

      <div className="results-content">
        <div className="image-section">
          <div className="canvas-container">
            <canvas id="result-canvas" className="result-canvas"></canvas>
          </div>
          <div className="stats-summary">
            <div className="stat-card">
              <div className="stat-value">{detections.length}</div>
              <div className="stat-label">Total Detections</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">
                {detections.filter(d => d.detection_type === 'component').length}
              </div>
              <div className="stat-label">Components</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">
                {detections.filter(d => d.detection_type === 'corrosion').length}
              </div>
              <div className="stat-label">Corrosion</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{Object.keys(classCounts).length}</div>
              <div className="stat-label">Unique Classes</div>
            </div>
          </div>
        </div>

        <div className="detections-section">
          <h2>Detections ({detections.length})</h2>
          <div className="detections-list">
            {detections && Array.isArray(detections) && detections.length > 0 ? (
              detections.map((det, index) => {
                if (!det || typeof det !== 'object') return null
                
                const isCorrosion = det.detection_type === 'corrosion'
                const className = det.component_class || det.corrosion_class || det.model_class || det.original_class || 'Unknown'
                const confidence = det.component_conf || det.corrosion_conf || 0
                
                return (
                  <div
                    key={index}
                    className={`detection-card ${selectedDetection === index ? 'selected' : ''}`}
                    onClick={() => setSelectedDetection(selectedDetection === index ? null : index)}
                    style={{
                      borderLeft: `4px solid ${isCorrosion ? '#ef4444' : '#2563eb'}`
                    }}
                  >
                    <div className="detection-header">
                      <span className="detection-class">
                        {isCorrosion ? '🔴 ' : '🔵 '}
                        {className}
                      </span>
                      <span className="detection-confidence">
                        {(confidence * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="detection-details">
                      <div className="detail-item">
                        <span className="detail-label">Type:</span>
                        <span className="detail-value">
                          {isCorrosion ? 'Corrosion' : 'Component'}
                        </span>
                      </div>
                      <div className="detail-item">
                        <span className="detail-label">Bounding Box:</span>
                        <span className="detail-value">
                          {det.bbox_xyxy && Array.isArray(det.bbox_xyxy) 
                            ? `[${det.bbox_xyxy.join(', ')}]`
                            : '[N/A]'}
                        </span>
                      </div>
                      {/* Show original class if different */}
                      {(det.model_class || det.original_class) && 
                       (det.model_class !== det.component_class || det.original_class !== det.corrosion_class) && (
                        <div className="detail-item">
                          <span className="detail-label">Original Class:</span>
                          <span className="detail-value">
                            {det.model_class || det.original_class}
                          </span>
                        </div>
                      )}
                      {(det.component_class_id !== null && det.component_class_id !== undefined) && (
                        <div className="detail-item">
                          <span className="detail-label">Class ID:</span>
                          <span className="detail-value">{det.component_class_id}</span>
                        </div>
                      )}
                      {(det.corrosion_class_id !== null && det.corrosion_class_id !== undefined) && (
                        <div className="detail-item">
                          <span className="detail-label">Class ID:</span>
                          <span className="detail-value">{det.corrosion_class_id}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })
            ) : (
              <div className="no-detections">
                <p>No detections found in this image.</p>
              </div>
            )}
          </div>
        </div>

        <div className="classes-section">
          <h2>Class Distribution</h2>
          <div className="classes-list">
            {Object.entries(classCounts)
              .sort((a, b) => b[1] - a[1])
              .map(([className, count]) => (
                <div key={className} className="class-item">
                  <span className="class-name">{className}</span>
                  <span className="class-count">{count}</span>
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Results
