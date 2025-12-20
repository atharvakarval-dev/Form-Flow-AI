/**
 * Loading Spinner Component
 * 
 * Provides consistent loading states across the application.
 */

/**
 * Simple spinner animation
 */
export const Spinner = ({ size = 'md', className = '' }) => {
    const sizes = {
        sm: 'w-4 h-4',
        md: 'w-8 h-8',
        lg: 'w-12 h-12',
        xl: 'w-16 h-16',
    };

    return (
        <div className={`${sizes[size]} ${className}`}>
            <svg
                className="animate-spin"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
            >
                <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                />
                <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
            </svg>
        </div>
    );
};

/**
 * Full page loading overlay
 */
export const PageLoader = ({ message = 'Loading...' }) => {
    return (
        <div className="fixed inset-0 bg-white/80 backdrop-blur-sm z-50 flex items-center justify-center">
            <div className="text-center">
                <Spinner size="xl" className="text-black mx-auto mb-4" />
                <p className="text-gray-600 font-medium">{message}</p>
            </div>
        </div>
    );
};

/**
 * Inline loading state
 */
export const InlineLoader = ({ message = 'Loading...' }) => {
    return (
        <div className="flex items-center justify-center py-8">
            <Spinner size="md" className="text-gray-400 mr-3" />
            <span className="text-gray-500">{message}</span>
        </div>
    );
};

/**
 * Skeleton loading placeholder
 */
export const Skeleton = ({ className = '', variant = 'text' }) => {
    const variants = {
        text: 'h-4 rounded',
        title: 'h-8 rounded',
        avatar: 'w-12 h-12 rounded-full',
        card: 'h-32 rounded-xl',
        button: 'h-10 w-24 rounded-full',
    };

    return (
        <div
            className={`bg-gray-200 animate-pulse ${variants[variant]} ${className}`}
        />
    );
};

/**
 * Card skeleton for dashboard items
 */
export const CardSkeleton = () => {
    return (
        <div className="bg-white/50 backdrop-blur-xl rounded-2xl p-6 border border-white/20">
            <div className="flex items-center gap-4 mb-4">
                <Skeleton variant="avatar" />
                <div className="flex-1">
                    <Skeleton variant="text" className="w-3/4 mb-2" />
                    <Skeleton variant="text" className="w-1/2" />
                </div>
            </div>
            <Skeleton variant="card" />
        </div>
    );
};

export default Spinner;
