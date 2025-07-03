import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import { BrowserRouter } from 'react-router-dom'
import './i18n'; // i18n konfigürasyonunu yükle

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <React.Suspense fallback="loading...">
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </React.Suspense>
  </React.StrictMode>,
)
