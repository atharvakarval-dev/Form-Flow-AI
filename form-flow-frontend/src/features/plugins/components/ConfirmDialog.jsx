/**
 * Confirmation Dialog Component
 * Reusable confirmation modal for destructive actions
 */
import { useCallback, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, X } from 'lucide-react';
import { useTheme } from '@/context/ThemeProvider';

/**
 * ConfirmDialog - Modal confirmation for destructive actions
 */
export function ConfirmDialog({
    isOpen,
    onClose,
    onConfirm,
    title = 'Confirm Action',
    message = 'Are you sure you want to proceed?',
    confirmText = 'Confirm',
    cancelText = 'Cancel',
    variant = 'danger', // 'danger' | 'warning' | 'info'
    isLoading = false,
}) {
    const { isDark } = useTheme();
    const confirmButtonRef = useRef(null);
    const previousActiveElement = useRef(null);

    // Focus management
    useEffect(() => {
        if (isOpen) {
            previousActiveElement.current = document.activeElement;
            confirmButtonRef.current?.focus();
        } else if (previousActiveElement.current) {
            previousActiveElement.current.focus();
        }
    }, [isOpen]);

    // Keyboard handling
    const handleKeyDown = useCallback((e) => {
        if (e.key === 'Escape' && !isLoading) {
            onClose();
        }
    }, [onClose, isLoading]);

    // Variant styles
    const variantStyles = {
        danger: {
            icon: 'text-red-500',
            iconBg: isDark ? 'bg-red-500/10' : 'bg-red-50',
            button: 'bg-red-500 hover:bg-red-600 text-white',
        },
        warning: {
            icon: 'text-amber-500',
            iconBg: isDark ? 'bg-amber-500/10' : 'bg-amber-50',
            button: 'bg-amber-500 hover:bg-amber-600 text-white',
        },
        info: {
            icon: 'text-blue-500',
            iconBg: isDark ? 'bg-blue-500/10' : 'bg-blue-50',
            button: 'bg-blue-500 hover:bg-blue-600 text-white',
        },
    };

    const styles = variantStyles[variant];

    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={!isLoading ? onClose : undefined}
                        className="fixed inset-0 z-[600] bg-black/50 backdrop-blur-sm"
                        aria-hidden="true"
                    />

                    {/* Dialog */}
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 20 }}
                        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                        onKeyDown={handleKeyDown}
                        role="alertdialog"
                        aria-modal="true"
                        aria-labelledby="confirm-dialog-title"
                        aria-describedby="confirm-dialog-message"
                        className={`
              fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[600]
              w-full max-w-md p-6 rounded-2xl shadow-2xl
              ${isDark ? 'bg-zinc-900 border border-white/10' : 'bg-white'}
            `}
                    >
                        {/* Close button */}
                        <button
                            onClick={onClose}
                            disabled={isLoading}
                            className={`
                absolute top-4 right-4 p-1 rounded-lg transition-colors
                ${isDark ? 'hover:bg-white/10 text-white/50' : 'hover:bg-zinc-100 text-zinc-400'}
                ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}
              `}
                            aria-label="Close dialog"
                        >
                            <X className="w-5 h-5" />
                        </button>

                        {/* Icon */}
                        <div className={`w-12 h-12 rounded-xl ${styles.iconBg} flex items-center justify-center mb-4`}>
                            <AlertTriangle className={`w-6 h-6 ${styles.icon}`} />
                        </div>

                        {/* Content */}
                        <h2
                            id="confirm-dialog-title"
                            className={`text-lg font-semibold mb-2 ${isDark ? 'text-white' : 'text-zinc-900'}`}
                        >
                            {title}
                        </h2>
                        <p
                            id="confirm-dialog-message"
                            className={`text-sm mb-6 ${isDark ? 'text-white/60' : 'text-zinc-600'}`}
                        >
                            {message}
                        </p>

                        {/* Actions */}
                        <div className="flex gap-3">
                            <button
                                onClick={onClose}
                                disabled={isLoading}
                                className={`
                  flex-1 py-2.5 rounded-xl font-medium transition-colors
                  ${isDark
                                        ? 'bg-white/10 hover:bg-white/20 text-white'
                                        : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-700'
                                    }
                  ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}
                `}
                            >
                                {cancelText}
                            </button>
                            <button
                                ref={confirmButtonRef}
                                onClick={onConfirm}
                                disabled={isLoading}
                                className={`
                  flex-1 py-2.5 rounded-xl font-medium transition-colors
                  ${styles.button}
                  ${isLoading ? 'opacity-70 cursor-wait' : ''}
                `}
                            >
                                {isLoading ? (
                                    <span className="flex items-center justify-center gap-2">
                                        <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                        </svg>
                                        Processing...
                                    </span>
                                ) : (
                                    confirmText
                                )}
                            </button>
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
}

export default ConfirmDialog;
