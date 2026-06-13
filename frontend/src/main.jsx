import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import CitizenSubmitApp from './CitizenSubmitApp'
import './index.css'

const isSubmitRoute = window.location.pathname === '/submit'
  || window.location.pathname.startsWith('/submit/')

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {isSubmitRoute ? <CitizenSubmitApp /> : <App />}
  </React.StrictMode>,
)
