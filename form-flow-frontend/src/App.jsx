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

function App() {
  return (
    <ErrorBoundary>
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
