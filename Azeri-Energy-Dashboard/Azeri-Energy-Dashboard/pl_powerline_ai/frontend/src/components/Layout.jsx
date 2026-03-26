import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import './Layout.css'

function Layout({ children }) {
  const location = useLocation()

  const isActive = (path) => location.pathname === path

  return (
    <div className="app-container">
      <nav className="navbar">
        <div className="nav-container">
          <Link to="/" className="nav-logo">
            <span className="logo-icon">⚡</span>
            <span className="logo-text">Powerline AI</span>
          </Link>
          <div className="nav-links">
            <Link 
              to="/" 
              className={`nav-link ${isActive('/') ? 'active' : ''}`}
            >
              Home
            </Link>
            <Link 
              to="/bulk" 
              className={`nav-link ${isActive('/bulk') ? 'active' : ''}`}
            >
              Bulk Upload
            </Link>
            <Link 
              to="/history" 
              className={`nav-link ${isActive('/history') ? 'active' : ''}`}
            >
              History
            </Link>
            <Link 
              to="/settings" 
              className={`nav-link ${isActive('/settings') ? 'active' : ''}`}
            >
              Settings
            </Link>
          </div>
        </div>
      </nav>
      <main className="content">
        {children}
      </main>
      <footer className="footer">
        <p>&copy; 2024 Powerline Inspection AI System</p>
      </footer>
    </div>
  )
}

export default Layout
