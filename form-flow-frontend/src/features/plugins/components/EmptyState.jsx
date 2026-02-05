/**
 * Empty State Component - High end visual placeholders
 */
import { motion } from 'framer-motion';
import { useTheme } from '@/context/ThemeProvider';
import { Plus, Sparkles, AlertTriangle, RefreshCcw } from 'lucide-react';

export function EmptyState({
    icon: Icon = Sparkles,
    title,
    description,
    actionLabel,
    onAction,
    className = '',
}) {
    const { isDark } = useTheme();

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className={`flex flex-col items-center justify-center py-24 px-8 text-center ${className}`}
        >
            <div className="relative mb-8">
                <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                    className={`absolute inset-0 blur-3xl opacity-20 ${isDark ? 'bg-emerald-500' : 'bg-emerald-400'}`}
                />
                <div className={`
                    relative w-24 h-24 rounded-[2rem] flex items-center justify-center
                    ${isDark ? 'bg-white/5 border border-white/10' : 'bg-zinc-100/50 border border-zinc-200'}
                    backdrop-blur-xl shadow-2xl
                `}>
                    <Icon className={`w-10 h-10 ${isDark ? 'text-emerald-400' : 'text-emerald-500'}`} />
                </div>
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.5 }}
                    className="absolute -top-2 -right-2 w-8 h-8 bg-emerald-500 rounded-full flex items-center justify-center text-white shadow-lg"
                >
                    <Plus className="w-5 h-5" />
                </motion.div>
            </div>

            <h3 className={`text-3xl font-black tracking-tighter mb-4 ${isDark ? 'text-white' : 'text-zinc-900'}`}>
                {title}
            </h3>

            {description && (
                <p className={`text-base font-medium max-w-md mb-10 leading-relaxed ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
                    {description}
                </p>
            )}

            {actionLabel && onAction && (
                <motion.button
                    whileHover={{ scale: 1.02, y: -2 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={onAction}
                    className={`
                        px-10 py-5 rounded-[2rem] font-black uppercase tracking-[0.2em] text-xs transition-all shadow-2xl
                        ${isDark
                            ? 'bg-white text-black shadow-white/10'
                            : 'bg-zinc-900 text-white shadow-zinc-900/20'
                        }
                    `}
                >
                    {actionLabel}
                </motion.button>
            )}
        </motion.div>
    );
}

export function ErrorState({ error, onRetry, title = 'System Anomaly', className = '' }) {
    const { isDark } = useTheme();

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className={`flex flex-col items-center justify-center py-20 text-center ${className}`}
        >
            <div className="p-6 bg-red-500/10 rounded-[2rem] mb-6 border border-red-500/20">
                <AlertTriangle className="w-10 h-10 text-red-500" />
            </div>

            <h3 className={`text-2xl font-black tracking-tight mb-2 ${isDark ? 'text-white' : 'text-zinc-900'}`}>
                {title}
            </h3>

            <p className={`text-sm font-medium mb-8 ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
                {error?.message || 'The engine encountered an unexpected interruption.'}
            </p>

            {onRetry && (
                <button
                    onClick={onRetry}
                    className={`
                        flex items-center gap-3 px-8 py-4 rounded-2xl font-black uppercase tracking-widest text-[10px] transition-all
                        ${isDark ? 'bg-white/5 text-white hover:bg-white/10' : 'bg-zinc-100 text-zinc-900 hover:bg-zinc-200'}
                    `}
                >
                    <RefreshCcw className="w-4 h-4" /> Reset Module
                </button>
            )}
        </motion.div>
    );
}

export default EmptyState;
