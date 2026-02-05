import { useState, useCallback } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Settings, X, Moon, Sun, Eye, LogOut, LayoutDashboard, Home, User
} from 'lucide-react';
import { ROUTES } from '@/constants';
import { useTheme, AccessibilitySettings } from '@/context/ThemeProvider';

const Navigation = () => {
    const location = useLocation();
    const [showSettings, setShowSettings] = useState(false);
    const themeContext = useTheme();
    const isDark = themeContext?.isDark;

    const handleSignOut = useCallback(() => {
        localStorage.removeItem('token');
        window.location.href = ROUTES.LOGIN;
    }, []);

    const navItems = [
        { label: 'Home', path: ROUTES.HOME, icon: Home },
        { label: 'Dashboard', path: ROUTES.DASHBOARD, icon: LayoutDashboard },
    ];

    return (
        <>
            <motion.nav
                initial={{ y: -20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                className={`
                    fixed top-5 right-6 z-[100] flex items-center gap-1 p-1.5 rounded-full border transition-all duration-300
                    ${isDark
                        ? 'bg-zinc-900/60 border-white/10 backdrop-blur-2xl shadow-[0_8px_32px_rgba(0,0,0,0.4)]'
                        : 'bg-white/60 border-zinc-200/80 backdrop-blur-2xl shadow-[0_8px_32px_rgba(31,38,135,0.07)]'
                    }
                `}
            >
                {/* Logo/Brand link */}
                <Link
                    to={ROUTES.HOME}
                    className="group relative w-9 h-9 ml-0.5 rounded-full flex items-center justify-center transition-all hover:scale-105 overflow-hidden ring-1 ring-white/10 dark:ring-white/5 shadow-inner"
                >
                    <img
                        src={isDark ? "/logo_black.jpg" : "/logo_white.jpg"}
                        alt="Home"
                        className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
                    />
                </Link>

                <div className="flex items-center gap-0.5 px-2">
                    {navItems.map((item) => {
                        const isActive = location.pathname === item.path;
                        return (
                            <Link
                                key={item.path}
                                to={item.path}
                                className={`
                                    relative px-4 py-2 rounded-full text-xs font-semibold tracking-wide transition-all
                                    ${isActive
                                        ? isDark ? 'text-white' : 'text-zinc-900'
                                        : isDark ? 'text-zinc-400 hover:text-white' : 'text-zinc-500 hover:text-zinc-900'
                                    }
                                `}
                            >
                                {isActive && (
                                    <motion.div
                                        layoutId="nav-bg"
                                        className={`absolute inset-0 rounded-full z-0 ${isDark ? 'bg-white/10' : 'bg-zinc-900/5'}`}
                                        transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                                    />
                                )}
                                <span className="relative z-10 flex items-center gap-1.5 text-[11px] uppercase tracking-wider">
                                    {item.label}
                                </span>
                            </Link>
                        );
                    })}
                </div>

                {localStorage.getItem('token') && (
                    <>
                        <div className={`w-[1px] h-4 mx-1 ${isDark ? 'bg-white/10' : 'bg-zinc-200'}`} />
                        <button
                            onClick={handleSignOut}
                            className={`
                                flex items-center gap-2 px-3 py-2 rounded-full transition-all group
                                ${isDark
                                    ? 'hover:bg-red-500/10 text-zinc-400 hover:text-red-400'
                                    : 'hover:bg-red-50 text-zinc-500 hover:text-red-600'
                                }
                            `}
                            aria-label="Sign Out"
                        >
                            <LogOut className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
                            <span className="text-[11px] font-bold uppercase tracking-wider">Exit</span>
                        </button>
                    </>
                )}

                <div className={`w-[1px] h-4 mx-1 ${isDark ? 'bg-white/10' : 'bg-zinc-200'}`} />

                <div className="flex items-center gap-0.5 pr-1">
                    {themeContext && (
                        <button
                            onClick={() => themeContext.toggleDarkMode()}
                            className={`
                                p-2 rounded-full transition-all
                                ${isDark
                                    ? 'text-zinc-400 hover:text-yellow-400 hover:bg-white/5'
                                    : 'text-zinc-500 hover:text-zinc-900 hover:bg-zinc-900/5'
                                }
                            `}
                            aria-label={isDark ? 'Light mode' : 'Dark mode'}
                        >
                            {isDark ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
                        </button>
                    )}

                    <button
                        onClick={() => setShowSettings(true)}
                        className={`
                            p-2 rounded-full transition-all
                            ${isDark
                                ? 'text-zinc-400 hover:text-emerald-400 hover:bg-white/5'
                                : 'text-zinc-500 hover:text-emerald-600 hover:bg-zinc-900/5'
                            }
                        `}
                        aria-label="Accessibility settings"
                    >
                        <Eye className="w-3.5 h-3.5" />
                    </button>
                </div>
            </motion.nav>

            <AnimatePresence>
                {showSettings && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-[200] flex items-center justify-center bg-zinc-950/40 backdrop-blur-md px-4"
                    >
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0, y: 20 }}
                            animate={{ scale: 1, opacity: 1, y: 0 }}
                            exit={{ scale: 0.9, opacity: 0, y: 20 }}
                            className="relative w-full max-w-sm"
                        >
                            <button
                                onClick={() => setShowSettings(false)}
                                className={`
                                    absolute -top-3 -right-3 p-2 rounded-full shadow-2xl z-10 transition-all hover:rotate-90
                                    ${isDark ? 'bg-zinc-800 text-white hover:bg-zinc-700' : 'bg-white text-zinc-900 hover:bg-zinc-50'}
                                `}
                            >
                                <X className="w-4 h-4" />
                            </button>
                            <div className="overflow-hidden rounded-3xl shadow-[0_32px_64px_rgba(0,0,0,0.2)]">
                                <AccessibilitySettings />
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
};

export default Navigation;

