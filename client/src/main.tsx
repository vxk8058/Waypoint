import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import ComponentShowcase from './components/component-showcase.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ComponentShowcase />
    {/* <App/> */}
  </StrictMode>,
)
