/**
 * Theme Provider with High Contrast Support
 * 
 * Features:
 * - 5 themes: Default, Dark, High Contrast, Dyslexia, Low Vision
 * - Font size customization
 * - Animation toggle (reduced motion)
 * - Haptic feedback toggle
 * - Persists to localStorage
 */

import React, { createContext, useContext, useState, useEffect } from 'react';

// Theme definitions
const THEMES = {
    default: {
        name: 'Default',
        colors: {
            background: '#ffffff',
            backgroundAlt: '#f3f4f6',
            text: '#111827',
            textMuted: '#6b7280',
            primary: '#10b981',
            secondary: '#6366f1',
            success: '#22c55e',
            error: '#ef4444',
            warning: '#f59e0b',
            border: '#e5e7eb',
        },
        isDark: false,
    },

    dark: {
        name: 'Dark Mode',
        colors: {
            background: '#111827',
            backgroundAlt: '#1f2937',
            text: '#f9fafb',
            textMuted: '#9ca3af',
            primary: '#34d399',
            secondary: '#818cf8',
            success: '#4ade80',
            error: '#f87171',
            warning: '#fbbf24',
            border: '#374151',
        },
        isDark: true,
    },

    highContrast: {
        name: 'High Contrast',
        colors: {
            background: '#000000',
            backgroundAlt: '#1a1a1a',
            text: '#ffff00',
            textMuted: '#ffffff',
            primary: '#ffffff',
            secondary: '#00ffff',
            success: '#00ff00',
            error: '#ff0000',
            warning: '#ffff00',
            border: '#ffffff',
        },
        isDark: true,
        styles: {
            borderWidth: '3px',
            fontWeight: '600',
        },
    },

    dyslexia: {
        name: 'Dyslexia Friendly',
        colors: {
            background: '#fef9e7',
            backgroundAlt: '#fdf2d1',
            text: '#2c3e50',
            textMuted: '#5d6d7e',
            primary: '#3498db',
            secondary: '#9b59b6',
            success: '#27ae60',
            error: '#e74c3c',
            warning: '#f39c12',
            border: '#bdc3c7',
        },
        isDark: false,
        styles: {
            fontFamily: 'OpenDyslexic, Comic Sans MS, Arial, sans-serif',
            lineHeight: '1.8',
            letterSpacing: '0.05em',
            wordSpacing: '0.2em',
        },
    },

    lowVision: {
        name: 'Low Vision',
        colors: {
            background: '#ffffff',
            backgroundAlt: '#f5f5f5',
            text: '#000000',
            textMuted: '#333333',
            primary: '#0000cc',
            secondary: '#660066',
            success: '#006600',
            error: '#cc0000',
            warning: '#cc6600',
            border: '#000000',
        },
        isDark: false,
        styles: {
            fontSize: '1.25rem',
            fontWeight: '600',
            lineHeight: '2.0',
            borderWidth: '3px',
        },
    },
};

// Default customization options
const DEFAULT_CUSTOMIZATIONS = {
    fontSize: 16,
    animationsEnabled: true,
    hapticEnabled: true,
    highContrastFocus: false,
};

// Create context
const ThemeContext = createContext(null);

export const ThemeProvider = ({ children }) => {
    // Lazy initialize state from localStorage to prevent theme flash
    const [themeName, setThemeName] = useState(() => {
        try {
            const saved = localStorage.getItem('formflow-theme-prefs');
            if (saved) {
                return JSON.parse(saved).theme || 'default';
            }
        } catch (e) {
            console.warn('Error reading theme from localStorage', e);
        }
        return 'default';
    });

    const [customizations, setCustomizations] = useState(() => {
        try {
            const saved = localStorage.getItem('formflow-theme-prefs');
            if (saved) {
                return {
                    ...DEFAULT_CUSTOMIZATIONS,
                    ...JSON.parse(saved).customizations
                };
            }
        } catch (e) {
            console.warn('Error reading customizations from localStorage', e);
        }

        // Check for reduced motion if no preference saved
        const prefersReducedMotion = typeof window !== 'undefined' &&
            window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        return {
            ...DEFAULT_CUSTOMIZATIONS,
            animationsEnabled: !prefersReducedMotion
        };
    });

    const [_isInitialized, _setIsInitialized] = useState(true);

    // Apply theme to document - runs immediately and on every theme change
    useEffect(() => {
        const theme = THEMES[themeName];
        if (!theme) return;

        const root = document.documentElement;

        // IMPORTANT: Handle dark class FIRST before anything else
        if (theme.isDark) {
            root.classList.add('dark');
        } else {
            root.classList.remove('dark');
        }

        // Apply color variables
        Object.entries(theme.colors).forEach(([key, value]) => {
            root.style.setProperty(`--color-${key}`, value);
        });

        // Apply theme-specific styles
        if (theme.styles) {
            Object.entries(theme.styles).forEach(([key, value]) => {
                root.style.setProperty(`--theme-${key}`, value);
            });
        } else {
            // Reset theme-specific styles for default theme
            root.style.removeProperty('--theme-fontFamily');
            root.style.removeProperty('--theme-lineHeight');
            root.style.removeProperty('--theme-letterSpacing');
            root.style.removeProperty('--theme-wordSpacing');
            root.style.removeProperty('--theme-fontSize');
            root.style.removeProperty('--theme-fontWeight');
            root.style.removeProperty('--theme-borderWidth');
        }

        // Apply customizations
        root.style.setProperty('--font-size-base', `${customizations.fontSize}px`);

        // Toggle animations
        if (!customizations.animationsEnabled) {
            root.style.setProperty('--animation-duration', '0s');
            root.classList.add('reduce-motion');
        } else {
            root.style.setProperty('--animation-duration', '0.3s');
            root.classList.remove('reduce-motion');
        }

        // Save preferences
        try {
            localStorage.setItem('formflow-theme-prefs', JSON.stringify({
                theme: themeName,
                customizations
            }));
        } catch (e) {
            console.warn('Could not save theme preferences:', e);
        }
    }, [themeName, customizations]);

    // Also ensure dark class is correctly set on initial mount
    useEffect(() => {
        const theme = THEMES[themeName];
        if (theme && !theme.isDark) {
            document.documentElement.classList.remove('dark');
        }
    }, [themeName]);

    const value = {
        theme: THEMES[themeName],
        themeName,
        setTheme: setThemeName,
        customizations,
        setCustomizations,
        themes: THEMES,
        isInitialized: _isInitialized,

        // Helper methods
        isDark: THEMES[themeName]?.isDark || false,
        toggleDarkMode: () => {
            setThemeName(current =>
                THEMES[current]?.isDark ? 'default' : 'dark'
            );
        },
        resetToDefault: () => {
            setThemeName('default');
            setCustomizations(DEFAULT_CUSTOMIZATIONS);
            localStorage.removeItem('formflow-theme-prefs');
            document.documentElement.classList.remove('dark');
        },
    };


    return (
        <ThemeContext.Provider value={value}>
            {children}
        </ThemeContext.Provider>
    );
};

// Hook to use theme
export const useTheme = () => {
    const context = useContext(ThemeContext);
    // Return null if not in provider (allows graceful fallback)
    return context;
};

/**
 * Accessibility Settings Panel
 */
export const AccessibilitySettings = ({ className = '' }) => {
    const {
        themeName,
        setTheme,
        customizations,
        setCustomizations,
        themes
    } = useTheme();

    return (
        <div
            className={`accessibility-settings p-4 bg-white dark:bg-gray-800 rounded-xl shadow-lg ${className}`}
            role="region"
            aria-label="Accessibility Settings"
        >
            <h2 className="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-100">
                ♿ Accessibility Preferences
            </h2>

            {/* Theme Selector */}
            <div className="mb-4">
                <label
                    htmlFor="theme-select"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                >
                    Visual Theme
                </label>
                <select
                    id="theme-select"
                    value={themeName}
                    onChange={(e) => setTheme(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    aria-describedby="theme-description"
                >
                    {Object.entries(themes).map(([key, t]) => (
                        <option key={key} value={key}>
                            {t.name}
                        </option>
                    ))}
                </select>
                <p id="theme-description" className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    Choose a theme that works best for your vision
                </p>
            </div>

            {/* Font Size Slider */}
            <div className="mb-4">
                <label
                    htmlFor="font-size"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                >
                    Font Size: {customizations.fontSize}px
                </label>
                <input
                    id="font-size"
                    type="range"
                    min="14"
                    max="28"
                    step="2"
                    value={customizations.fontSize}
                    onChange={(e) => setCustomizations({
                        ...customizations,
                        fontSize: parseInt(e.target.value)
                    })}
                    className="w-full h-2 bg-gray-200 dark:bg-gray-600 rounded-lg appearance-none cursor-pointer"
                    aria-valuemin={14}
                    aria-valuemax={28}
                    aria-valuenow={customizations.fontSize}
                />
            </div>

            {/* Reduce Motion Toggle */}
            <div className="mb-3">
                <label className="flex items-center gap-3 cursor-pointer">
                    <input
                        type="checkbox"
                        checked={!customizations.animationsEnabled}
                        onChange={(e) => setCustomizations({
                            ...customizations,
                            animationsEnabled: !e.target.checked
                        })}
                        className="w-5 h-5 rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
                    />
                    <span className="text-sm text-gray-700 dark:text-gray-300">
                        Reduce Motion
                    </span>
                </label>
                <p className="ml-8 text-xs text-gray-500 dark:text-gray-400">
                    Disable animations for vestibular disorders
                </p>
            </div>

            {/* Haptic Feedback Toggle */}
            <div className="mb-3">
                <label className="flex items-center gap-3 cursor-pointer">
                    <input
                        type="checkbox"
                        checked={customizations.hapticEnabled}
                        onChange={(e) => setCustomizations({
                            ...customizations,
                            hapticEnabled: e.target.checked
                        })}
                        className="w-5 h-5 rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
                    />
                    <span className="text-sm text-gray-700 dark:text-gray-300">
                        Haptic Feedback
                    </span>
                </label>
                <p className="ml-8 text-xs text-gray-500 dark:text-gray-400">
                    Vibration feedback for actions (mobile)
                </p>
            </div>
        </div>
    );
};

export default ThemeProvider;
