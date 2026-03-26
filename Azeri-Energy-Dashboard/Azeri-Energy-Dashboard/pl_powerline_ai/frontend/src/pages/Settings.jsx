import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './Settings.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function Settings() {
  const [apiUrl, setApiUrl] = useState(API_URL)
  const [healthStatus, setHealthStatus] = useState(null)
  const [checking, setChecking] = useState(false)

  useEffect(() => {
    // Load saved API URL
    const saved = localStorage.getItem('apiUrl')
    if (saved) {
      setApiUrl(saved)
    }
  }, [])

  const checkHealth = async () => {
    setChecking(true)
    setHealthStatus(null)
    try {
      const response = await axios.get(`${apiUrl}/health`)
      setHealthStatus({
        success: true,
        message: 'API is healthy',
        data: response.data
      })
    } catch (error) {
      setHealthStatus({
        success: false,
        message: error.response?.data?.detail || error.message || 'Failed to connect to API'
      })
    } finally {
      setChecking(false)
    }
  }

  const saveSettings = () => {
    localStorage.setItem('apiUrl', apiUrl)
    alert('Settings saved!')
  }

  return (
    <div className="settings-container">
      <div className="settings-header">
        <h1>Settings</h1>
      </div>

      <div className="settings-content">
        <div className="settings-section">
          <h2>API Configuration</h2>
          <div className="setting-item">
            <label htmlFor="api-url">API URL</label>
            <input
              id="api-url"
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder="http://localhost:8000"
              className="setting-input"
            />
            <p className="setting-hint">
              URL of the FastAPI server (default: http://localhost:8000)
            </p>
          </div>

          <div className="setting-actions">
            <button onClick={checkHealth} className="test-button" disabled={checking}>
              {checking ? 'Checking...' : 'Test Connection'}
            </button>
            <button onClick={saveSettings} className="save-button">
              Save Settings
            </button>
          </div>

          {healthStatus && (
            <div className={`health-status ${healthStatus.success ? 'success' : 'error'}`}>
              <span className="status-icon">
                {healthStatus.success ? '✅' : '❌'}
              </span>
              <div className="status-content">
                <p className="status-message">{healthStatus.message}</p>
                {healthStatus.data && (
                  <pre className="status-data">
                    {JSON.stringify(healthStatus.data, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="settings-section">
          <h2>About</h2>
          <div className="about-content">
            <p>
              <strong>Powerline Inspection AI System</strong>
            </p>
            <p>
              This application uses AI to detect and classify powerline components
              in inspection images.
            </p>
            <div className="about-features">
              <h3>Features:</h3>
              <ul>
                <li>✅ Real-time component detection</li>
                <li>✅ All detected component classes</li>
                <li>✅ Visual bounding box annotations</li>
                <li>✅ Inspection history tracking</li>
                <li>✅ Detailed detection statistics</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="settings-section">
          <h2>Instructions</h2>
          <div className="instructions-content">
            <ol>
              <li>
                <strong>Start the API server:</strong>
                <pre>python api_server.py</pre>
              </li>
              <li>
                <strong>Configure API URL:</strong>
                <p>Update the API URL above if your server runs on a different port</p>
              </li>
              <li>
                <strong>Test connection:</strong>
                <p>Click "Test Connection" to verify the API is running</p>
              </li>
              <li>
                <strong>Upload images:</strong>
                <p>Go to Home page and upload powerline inspection images</p>
              </li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Settings
