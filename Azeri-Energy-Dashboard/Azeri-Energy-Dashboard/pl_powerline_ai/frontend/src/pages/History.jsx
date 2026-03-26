import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import './History.css'

function History() {
  const [history, setHistory] = useState([])
  const navigate = useNavigate()

  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem('inspectionHistory') || '[]')
      // Automatically limit to 20 items if there are more
      if (stored.length > 20) {
        const limited = stored.slice(0, 20)
        localStorage.setItem('inspectionHistory', JSON.stringify(limited))
        setHistory(limited)
      } else {
        setHistory(stored)
      }
    } catch (error) {
      if (error.name === 'QuotaExceededError' || error.code === 22) {
        // If quota exceeded, try to clear and keep only 10
        try {
          const stored = JSON.parse(localStorage.getItem('inspectionHistory') || '[]')
          const reduced = stored.slice(0, 10)
          localStorage.setItem('inspectionHistory', JSON.stringify(reduced))
          setHistory(reduced)
          console.warn('Storage quota exceeded. History reduced to 10 items.')
        } catch (e) {
          // Last resort: clear everything
          localStorage.removeItem('inspectionHistory')
          setHistory([])
          console.error('Could not recover from storage error. History cleared.')
        }
      } else {
        console.error('Error loading history:', error)
        setHistory([])
      }
    }
  }, [])

  const clearHistory = () => {
    if (window.confirm('Are you sure you want to clear all history?')) {
      localStorage.removeItem('inspectionHistory')
      setHistory([])
    }
  }

  const deleteItem = (id) => {
    const updated = history.filter(item => item.id !== id)
    try {
      localStorage.setItem('inspectionHistory', JSON.stringify(updated))
      setHistory(updated)
    } catch (error) {
      if (error.name === 'QuotaExceededError' || error.code === 22) {
        // If still failing, try to reduce further
        const reduced = updated.slice(0, 10)
        localStorage.setItem('inspectionHistory', JSON.stringify(reduced))
        setHistory(reduced)
        alert('Storage quota exceeded. History reduced to 10 most recent items.')
      } else {
        console.error('Error saving history:', error)
        alert('Failed to save history. Please try again.')
      }
    }
  }

  const clearOldHistory = () => {
    if (window.confirm('Clear all but the 10 most recent items?')) {
      const recent = history.slice(0, 10)
      try {
        localStorage.setItem('inspectionHistory', JSON.stringify(recent))
        setHistory(recent)
      } catch (error) {
        console.error('Error clearing old history:', error)
        alert('Failed to clear history. Please try again.')
      }
    }
  }

  if (history.length === 0) {
    return (
      <div className="history-container">
        <div className="history-header">
          <h1>Inspection History</h1>
        </div>
        <div className="empty-history">
          <div className="empty-icon">📭</div>
          <h2>No history yet</h2>
          <p>Upload images to see your inspection history here</p>
          <button onClick={() => navigate('/')} className="upload-button">
            Upload Image
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="history-container">
      <div className="history-header">
        <h1>Inspection History ({history.length} items)</h1>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {history.length > 10 && (
            <button onClick={clearOldHistory} className="clear-button" style={{ background: '#f59e0b' }}>
              Clear Old (Keep 10)
            </button>
          )}
          <button onClick={clearHistory} className="clear-button">
            Clear All
          </button>
        </div>
      </div>

      <div className="history-grid">
        {history.map((item) => (
          <div key={item.id} className="history-card">
            <div className="history-image-container">
              <img
                src={item.imageData}
                alt={item.imageName}
                className="history-image"
              />
              <div className="history-overlay">
                <div className="history-stats">
                  <span className="stat-badge">
                    {item.predictions.detections.length} detections
                  </span>
                </div>
              </div>
            </div>
            <div className="history-info">
              <h3 className="history-name">{item.imageName}</h3>
              <p className="history-date">
                {new Date(item.timestamp).toLocaleString()}
              </p>
              <div className="history-actions">
                <button
                  onClick={() => navigate(`/results/${item.id}`)}
                  className="view-button"
                >
                  View Details
                </button>
                <button
                  onClick={() => deleteItem(item.id)}
                  className="delete-button"
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default History
