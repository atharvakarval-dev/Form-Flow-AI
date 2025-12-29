import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Settings, X, Moon, Sun, Eye } from 'lucide-react';
import { ROUTES } from '@/constants';
import { useTheme, AccessibilitySettings } from '@/context/ThemeProvider';

/**
 * Navigation - Global navigation bar component with accessibility controls
 */
const Navigation = () => {
    const location = useLocation();
    const [showSettings, setShowSettings] = useState(false);

    // Theme controls - always call the hook (React rules)
    // useTheme returns null if not in provider context
    const themeContext = useTheme();

    return (
        <>
            <nav className="fixed top-6 right-8 z-[100] flex items-center gap-2 bg-white/40 dark:bg-gray-800/40 backdrop-blur-xl p-1.5 rounded-full border border-white/20 dark:border-gray-700/30 shadow-lg shadow-black/5">
                <Link to={ROUTES.HOME} className="relative w-10 h-10 rounded-full flex items-center justify-center transition-transform hover:scale-105 overflow-hidden">
                    <img
                        src={themeContext?.isDark ? "/logo_black.jpg" : "/logo_white.jpg"}
                        alt="Home"
                        className="w-full h-full object-cover"
                    />
                </Link>

                <a href={ROUTES.HOME} className="px-5 py-2 rounded-full text-gray-700 dark:text-gray-200 hover:text-black dark:hover:text-white hover:bg-white/50 dark:hover:bg-gray-700/50 transition-all font-medium text-sm tracking-normal">Home</a>

                {localStorage.getItem('token') ? (
                    <>
                        <Link to={ROUTES.DASHBOARD} className="px-4 py-2 rounded-full text-gray-600 dark:text-gray-300 hover:text-black dark:hover:text-white hover:bg-white/50 dark:hover:bg-gray-700/50 transition-all font-medium text-sm tracking-wide">Dashboard</Link>
                        <div className="w-px h-4 bg-gray-300 dark:bg-gray-600 mx-1"></div>
                        <button
                            onClick={() => {
                                localStorage.removeItem('token');
                                window.location.href = ROUTES.LOGIN;
                            }}
                            className="flex items-center gap-2 px-4 py-2 rounded-full bg-red-500/10 hover:bg-red-500/20 text-red-600 dark:text-red-400 border border-red-500/10 text-sm font-medium transition-all ml-1"
                        >
                            Sign Out
                        </button>
                    </>
                ) : (
                    <>
                        {location.pathname !== ROUTES.LOGIN && (
                            <Link to={ROUTES.LOGIN} className="px-4 py-2 rounded-full text-gray-600 dark:text-gray-300 hover:text-black dark:hover:text-white hover:bg-white/50 dark:hover:bg-gray-700/50 transition-all font-medium text-sm tracking-wide">Login</Link>
                        )}

                        {location.pathname !== ROUTES.REGISTER && (
                            <Link to={ROUTES.REGISTER} className="px-5 py-2.5 rounded-full bg-black dark:bg-white hover:bg-gray-900 dark:hover:bg-gray-100 text-white dark:text-black text-sm font-medium transition-all shadow-lg shadow-black/20 ml-1">
                                Sign Up
                            </Link>
                        )}
                    </>
                )}

                {/* Accessibility Settings Button */}
                <div className="w-px h-4 bg-gray-300 dark:bg-gray-600 mx-1"></div>

                {/* Quick Dark Mode Toggle */}
                {themeContext && (
                    <button
                        onClick={() => themeContext.toggleDarkMode()}
                        className="p-2 rounded-full text-gray-600 dark:text-gray-300 hover:bg-white/50 dark:hover:bg-gray-700/50 transition-all"
                        aria-label={themeContext.isDark ? 'Switch to light mode' : 'Switch to dark mode'}
                    >
                        {themeContext.isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                    </button>
                )}

                {/* Full Accessibility Settings */}
                <button
                    onClick={() => setShowSettings(true)}
                    className="p-2 rounded-full text-gray-600 dark:text-gray-300 hover:bg-white/50 dark:hover:bg-gray-700/50 transition-all"
                    aria-label="Accessibility settings"
                    title="Accessibility Settings"
                >
                    <Eye className="w-4 h-4" />
                </button>
            </nav>

            {/* Accessibility Settings Modal */}
            {showSettings && (
                <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 backdrop-blur-sm">
                    <div className="relative w-full max-w-md mx-4">
                        <button
                            onClick={() => setShowSettings(false)}
                            className="absolute -top-3 -right-3 p-2 bg-white dark:bg-gray-800 rounded-full shadow-lg z-10 hover:bg-gray-100 dark:hover:bg-gray-700"
                            aria-label="Close settings"
                        >
                            <X className="w-4 h-4" />
                        </button>
                        <AccessibilitySettings className="shadow-2xl" />
                    </div>
                </div>
            )}
        </>
    );
};

export default Navigation;

