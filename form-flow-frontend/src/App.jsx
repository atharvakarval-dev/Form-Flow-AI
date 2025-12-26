import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Navigation } from '@/components/layout';
import { Aurora } from '@/components/ui';
import { ErrorBoundary } from '@/components/common';
import { ROUTES, AURORA_COLORS } from '@/constants';

// Page components
import HomePage from '@/pages/HomePage';
import LoginPage from '@/pages/LoginPage';
import RegisterPage from '@/pages/RegisterPage';
import DashboardPage from '@/pages/DashboardPage';

import { useTheme } from '@/context/ThemeProvider';

function App() {
  const { isDark } = useTheme();

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <div className={`relative min-h-screen font-sans transition-colors duration-500
          ${isDark ? 'bg-[#09090b] selection:bg-green-900/30' : 'bg-white selection:bg-green-100'}`}>

          {/* Global WEBGL Background */}
          <div className="fixed inset-0 z-0 pointer-events-none">
            <Aurora
              colorStops={isDark ? ['#064e3b', '#065f46', '#059669'] : AURORA_COLORS}
              amplitude={isDark ? 0.8 : 1.0}
              blend={isDark ? 0.6 : 0.5}
              speed={0.4}
            />
          </div>

          {/* Content Layer */}
          <div className="relative z-10 w-full min-h-screen">


            <Navigation />

            <Routes>
              <Route path={ROUTES.HOME} element={<HomePage />} />
              <Route path={ROUTES.REGISTER} element={<RegisterPage />} />
              <Route path={ROUTES.LOGIN} element={<LoginPage />} />
              <Route path={ROUTES.DASHBOARD} element={<DashboardPage />} />
            </Routes>
          </div>
        </div>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
