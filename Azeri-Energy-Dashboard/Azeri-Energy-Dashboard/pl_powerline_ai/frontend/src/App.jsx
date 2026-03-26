import React from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import BulkUpload from './pages/BulkUpload'
import Results from './pages/Results'
import History from './pages/History'
import Settings from './pages/Settings'
import './App.css'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/bulk" element={<BulkUpload />} />
        <Route path="/results/:imageId" element={<Results />} />
        <Route path="/history" element={<History />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Layout>
  )
}

export default App
