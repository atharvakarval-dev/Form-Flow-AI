import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import { RegistrationForm } from '@/components/RegistrationForm'
import { LoginForm } from '@/components/LoginForm'
import { Dashboard } from '@/components/Dashboard'
import LinkPaste from './LinkPaste'
import Aurora from '@/components/ui/Aurora'

const AURORA_COLORS = ['#bfe4be', '#69da93', '#86efac'];

// Nav Component to use useLocation hook
const Navigation = () => {
  const location = useLocation();

  return (
    <nav className="absolute top-6 right-8 z-50 flex items-center gap-2 bg-white/40 backdrop-blur-xl px-2 py-2 rounded-full border border-white/20 shadow-lg shadow-black/5">
      <Link to="/" className="px-4 py-2 rounded-full text-gray-600 hover:text-black hover:bg-white/50 transition-all font-medium text-sm tracking-wide">Home</Link>

      {localStorage.getItem('token') ? (
        <>
          <Link to="/dashboard" className="px-4 py-2 rounded-full text-gray-600 hover:text-black hover:bg-white/50 transition-all font-medium text-sm tracking-wide">Dashboard</Link>
          <div className="w-px h-4 bg-gray-300 mx-1"></div>
          <button
            onClick={() => {
              localStorage.removeItem('token');
              window.location.href = '/login';
            }}
            className="flex items-center gap-2 px-4 py-2 rounded-full bg-red-500/10 hover:bg-red-500/20 text-red-600 border border-red-500/10 text-sm font-medium transition-all ml-1"
          >
            Sign Out
          </button>
        </>
      ) : (
        <>
          {/* Hide "Login" link if on /login */}
          {location.pathname !== '/login' && (
            <Link to="/login" className="px-4 py-2 rounded-full text-gray-600 hover:text-black hover:bg-white/50 transition-all font-medium text-sm tracking-wide">Login</Link>
          )}

          {/* Hide "Sign Up" button if on /register */}
          {location.pathname !== '/register' && (
            <Link to="/register" className="px-5 py-2.5 rounded-full bg-black hover:bg-gray-900 text-white text-sm font-medium transition-all shadow-lg shadow-black/20 ml-1">
              Sign Up
            </Link>
          )}
        </>
      )}
    </nav>
  );
};

function App() {
  return (
    <BrowserRouter>
      <div className="relative min-h-screen font-sans bg-white selection:bg-green-100">
        {/* Global WebGL Background */}
        <div className="fixed inset-0 z-0 pointer-events-none">
          <Aurora colorStops={AURORA_COLORS} amplitude={1.0} blend={0.5} speed={0.4} />
        </div>

        {/* Content Layer */}
        <div className="relative z-10 w-full min-h-screen">
          <Navigation />

          <Routes>
            <Route path="/" element={<LinkPaste />} />
            <Route path="/register" element={<RegistrationForm />} />
            <Route path="/login" element={<LoginForm />} />
            <Route path="/dashboard" element={<Dashboard />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  )
}

export default App
