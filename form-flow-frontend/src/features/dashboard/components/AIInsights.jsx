/**
 * AIInsights Component
 * 
 * Displays AI-generated insights about form filling patterns.
 */

import { Sparkles, RefreshCw } from 'lucide-react';
import { useTheme } from '@/context/ThemeProvider';

export function AIInsights({ insights, isLoading, onRefresh }) {
    const { isDark } = useTheme();

    const cardClass = isDark
        ? "bg-black/20"
        : "bg-white/40";

    const textClass = isDark ? "text-white/60" : "text-zinc-500";

    // Reference Design: Green badge-like container for title, centered content
    return (
        <div className={`h-full flex flex-col items-center justify-center p-6 text-center relative group`}>
            {/* Header / Title Badge */}
            <div className={`px-5 py-2.5 rounded-2xl flex items-center gap-2 mb-4 transition-all ${isDark ? 'bg-emerald-500/10 text-emerald-400' : 'bg-emerald-50 text-emerald-900'}`}>
                <div className={`p-1 rounded-md ${isDark ? 'bg-emerald-500/20' : 'bg-emerald-100'}`}>
                    <Sparkles className="h-4 w-4 text-emerald-500" />
                </div>
                <h3 className="font-semibold text-sm">AI Insights</h3>
            </div>

            {/* Content */}
            <div className="flex-1 flex items-center justify-center">
                <p className={`text-sm leading-relaxed max-w-[90%] ${textClass}`}>
                    {isLoading ? (
                        <span className="flex items-center gap-2">
                            <span className="animate-spin h-3 w-3 rounded-full border-2 border-current border-t-transparent"></span>
                            Analyzing...
                        </span>
                    ) : (
                        insights || "Not enough data to generate insights yet."
                    )}
                </p>
            </div>

            {/* Refresh Button (Absolute top right like image) */}
            <button
                onClick={onRefresh}
                disabled={isLoading}
                className={`absolute top-6 right-6 p-2 rounded-full transition-all opacity-0 group-hover:opacity-100 ${isDark
                    ? 'hover:bg-white/10 text-white/40 hover:text-white'
                    : 'hover:bg-zinc-100 text-zinc-400 hover:text-zinc-900'
                    }`}
                title="Refresh insights"
            >
                <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
        </div>
    );
}
