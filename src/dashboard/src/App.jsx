import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import RequestList from './components/RequestList'
import RequestDetail from './components/RequestDetail'
import MetricsDashboard from './components/MetricsDashboard'
import './index.css'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <nav className="bg-white shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16">
              <div className="flex">
                <Link to="/" className="flex items-center">
                  <h1 className="text-2xl font-bold text-indigo-600">🤖 AI Agent</h1>
                </Link>
                <div className="ml-10 flex items-center space-x-4">
                  <Link to="/" className="text-gray-700 hover:text-indigo-600 px-3 py-2 rounded-md text-sm font-medium">
                    Requests
                  </Link>
                  <Link to="/metrics" className="text-gray-700 hover:text-indigo-600 px-3 py-2 rounded-md text-sm font-medium">
                    Metrics
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </nav>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Routes>
            <Route path="/" element={<RequestList />} />
            <Route path="/requests/:requestId" element={<RequestDetail />} />
            <Route path="/metrics" element={<MetricsDashboard />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
