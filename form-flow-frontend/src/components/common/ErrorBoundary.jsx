import React from 'react';

/**
 * Error Boundary Component
 * 
 * Catches JavaScript errors in child component tree and displays
 * a fallback UI instead of crashing the whole application.
 * 
 * Usage:
 *   <ErrorBoundary>
 *     <MyComponent />
 *   </ErrorBoundary>
 * 
 *   // With custom fallback:
 *   <ErrorBoundary fallback={<CustomErrorUI />}>
 *     <MyComponent />
 *   </ErrorBoundary>
 */
class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error) {
        // Update state so next render shows fallback UI
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        // Log error to console (could send to error tracking service)
        console.error('ErrorBoundary caught an error:', error, errorInfo);
        this.setState({ errorInfo });

        // TODO: Send to error tracking service like Sentry
        // Sentry.captureException(error, { extra: errorInfo });
    }

    handleRetry = () => {
        this.setState({ hasError: false, error: null, errorInfo: null });
    };

    render() {
        if (this.state.hasError) {
            // Custom fallback if provided
            if (this.props.fallback) {
                return this.props.fallback;
            }

            // Default error UI
            return (
                <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-red-50 to-orange-50 p-4">
                    <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 text-center">
                        {/* Error Icon */}
                        <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
                            <svg className="w-8 h-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                        </div>

                        <h2 className="text-2xl font-bold text-gray-900 mb-2">
                            Something went wrong
                        </h2>

                        <p className="text-gray-600 mb-6">
                            We're sorry, but something unexpected happened. Please try again.
                        </p>

                        {/* Error details (dev mode only) */}
                        {import.meta.env.DEV && this.state.error && (
                            <details className="mb-6 text-left">
                                <summary className="cursor-pointer text-sm text-gray-500 hover:text-gray-700">
                                    Show error details
                                </summary>
                                <pre className="mt-2 p-3 bg-gray-100 rounded-lg text-xs text-red-600 overflow-auto max-h-40">
                                    {this.state.error.toString()}
                                    {this.state.errorInfo?.componentStack}
                                </pre>
                            </details>
                        )}

                        <div className="flex gap-3 justify-center">
                            <button
                                onClick={this.handleRetry}
                                className="px-6 py-2.5 bg-black text-white rounded-full font-medium hover:bg-gray-800 transition-colors"
                            >
                                Try Again
                            </button>
                            <button
                                onClick={() => window.location.href = '/'}
                                className="px-6 py-2.5 bg-gray-100 text-gray-700 rounded-full font-medium hover:bg-gray-200 transition-colors"
                            >
                                Go Home
                            </button>
                        </div>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
