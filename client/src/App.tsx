import { ComponentShowcase } from './components/component-showcase'
import { SignIn } from './pages/sign-in'

function App() {
  // Temporary until a router is added: visit /components to see the component showcase.
  if (window.location.pathname === '/components') return <ComponentShowcase />

  return <SignIn />
}

export default App
