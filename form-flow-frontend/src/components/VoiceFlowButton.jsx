/**
 * VoiceFlowButton - WhisperFlow Voice Input Component
 * 
 * A ready-to-use microphone button that integrates with the Flow Engine.
 * Shows visual feedback for listening/processing states.
 * 
 * Usage:
 *   <VoiceFlowButton
 *     appContext={{ view: 'DealPipeline' }}
 *     onResult={(result) => setInputValue(result.display_text)}
 *     onAction={(action) => handleAction(action)}
 *   />
 */

import { useState } from 'react';
import useVoiceFlow from '../hooks/useVoiceFlow';

// =============================================================================
// COMPONENT
// =============================================================================

const VoiceFlowButton = ({
    appContext = null,
    vocabulary = null,
    onResult = null,
    onAction = null,
    onError = null,
    // Custom action handlers
    onCalendarAction = null,
    onJiraAction = null,
    onSlackAction = null,
    onEmailAction = null,
    // Styling
    size = 'md',
    className = '',
    showFeedback = true,
    disabled = false
}) => {
    const [showToast, setShowToast] = useState(false);
    const [toastMessage, setToastMessage] = useState('');

    const {
        isListening,
        isProcessing,
        interimTranscript,
        displayText,
        intent,
        detectedApps,
        startListening,
        stopListening
    } = useVoiceFlow({
        appContext,
        vocabulary,
        onResult: (result) => {
            // Show feedback toast
            if (showFeedback && result) {
                if (result.intent === 'command' && result.detected_apps?.length > 0) {
                    setToastMessage(`Action: ${result.detected_apps.join(', ')}`);
                } else {
                    setToastMessage('Text captured');
                }
                setShowToast(true);
                setTimeout(() => setShowToast(false), 2000);
            }
            onResult?.(result);
        },
        onAction,
        onError: (err) => {
            if (showFeedback) {
                setToastMessage(`Error: ${err}`);
                setShowToast(true);
                setTimeout(() => setShowToast(false), 3000);
            }
            onError?.(err);
        },
        onCalendarAction,
        onJiraAction,
        onSlackAction,
        onEmailAction
    });

    // Size variants
    const sizeClasses = {
        sm: 'w-8 h-8 text-sm',
        md: 'w-12 h-12 text-base',
        lg: 'w-16 h-16 text-lg'
    };

    const handleClick = () => {
        if (isListening) {
            stopListening();
        } else {
            startListening();
        }
    };

    // State-based styling
    const getButtonClasses = () => {
        const base = `
            relative rounded-full flex items-center justify-center
            transition-all duration-200 ease-in-out
            focus:outline-none focus:ring-2 focus:ring-offset-2
            ${sizeClasses[size] || sizeClasses.md}
            ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        `;

        if (isProcessing) {
            return `${base} bg-yellow-500 text-white animate-pulse`;
        } else if (isListening) {
            return `${base} bg-red-500 text-white shadow-lg shadow-red-500/50`;
        } else {
            return `${base} bg-gradient-to-br from-purple-600 to-indigo-600 text-white hover:from-purple-500 hover:to-indigo-500`;
        }
    };

    return (
        <div className={`relative inline-flex flex-col items-center ${className}`}>
            {/* Main Button */}
            <button
                onClick={handleClick}
                disabled={disabled || isProcessing}
                className={getButtonClasses()}
                aria-label={isListening ? 'Stop listening' : 'Start voice input'}
            >
                {isProcessing ? (
                    // Processing spinner
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                ) : (
                    // Microphone icon
                    <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        className={`${size === 'sm' ? 'w-4 h-4' : size === 'lg' ? 'w-8 h-8' : 'w-6 h-6'}`}
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 10v2a7 7 0 0 1-14 0v-2" />
                        <line x1="12" y1="19" x2="12" y2="23" />
                        <line x1="8" y1="23" x2="16" y2="23" />
                    </svg>
                )}

                {/* Listening pulse animation */}
                {isListening && (
                    <span className="absolute inset-0 rounded-full animate-ping bg-red-400 opacity-75" />
                )}
            </button>

            {/* Interim transcript display */}
            {isListening && interimTranscript && showFeedback && (
                <div className="absolute top-full mt-2 px-3 py-1 bg-gray-800 text-white text-sm rounded-lg whitespace-nowrap max-w-xs truncate">
                    {interimTranscript}
                </div>
            )}

            {/* Toast notification */}
            {showToast && showFeedback && (
                <div className={`
                    absolute top-full mt-2 px-3 py-2 rounded-lg text-sm whitespace-nowrap
                    ${intent === 'command' ? 'bg-green-600' : 'bg-gray-800'} text-white
                    animate-fade-in
                `}>
                    {toastMessage}
                    {detectedApps.length > 0 && (
                        <span className="ml-1 font-medium">
                            ({detectedApps.join(', ')})
                        </span>
                    )}
                </div>
            )}
        </div>
    );
};

export default VoiceFlowButton;
