/**
 * VoiceInput Component
 * 
 * Complete voice input solution combining SiriWave visualization
 * with useVoice hook for a seamless voice interaction experience.
 */

import React, { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, X, RotateCcw, Sparkles } from 'lucide-react';
import SiriWave, { SiriWaveCard } from './SiriWave';
import useVoice from '@/hooks/useVoice';

/**
 * VoiceInput - Production-ready voice input with Siri waveform
 * 
 * @param {Object} props
 * @param {Function} props.onTranscript - Callback with final transcript
 * @param {Function} props.onSubmit - Callback when user submits
 * @param {'ios' | 'ios9'} props.theme - Waveform theme
 * @param {'compact' | 'full'} props.variant - Display mode
 * @param {string} props.placeholder - Placeholder text
 */
const VoiceInput = ({
    onTranscript,
    onSubmit,
    theme = 'ios9',
    variant = 'compact',
    placeholder = 'Click the mic and start speaking...',
    className = '',
}) => {
    const {
        isListening,
        volumeLevel,
        transcript,
        interimTranscript,
        error,
        toggleListening,
        resetTranscript,
    } = useVoice();

    const [status, setStatus] = useState('idle');

    // Update status based on listening state
    useEffect(() => {
        if (isListening) {
            setStatus(volumeLevel > 0.1 ? 'listening' : 'listening');
        } else if (transcript) {
            setStatus('idle');
        } else {
            setStatus('idle');
        }
    }, [isListening, volumeLevel, transcript]);

    // Notify parent of transcript changes
    useEffect(() => {
        if (onTranscript && transcript) {
            onTranscript(transcript);
        }
    }, [transcript, onTranscript]);

    const handleSubmit = useCallback(() => {
        if (onSubmit && transcript) {
            onSubmit(transcript);
            resetTranscript();
        }
    }, [onSubmit, transcript, resetTranscript]);

    const handleToggle = useCallback(() => {
        toggleListening();
    }, [toggleListening]);

    if (variant === 'full') {
        return (
            <div className={`relative ${className}`}>
                <SiriWaveCard
                    theme={theme}
                    isActive={isListening}
                    volumeLevel={volumeLevel}
                    onToggle={handleToggle}
                    status={status}
                    transcript={transcript}
                    interimTranscript={interimTranscript}
                />

                {/* Action Buttons */}
                <AnimatePresence>
                    {transcript && (
                        <motion.div
                            className="flex justify-center gap-3 mt-4"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: 10 }}
                        >
                            <motion.button
                                onClick={resetTranscript}
                                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
                                whileHover={{ scale: 1.02 }}
                                whileTap={{ scale: 0.98 }}
                            >
                                <RotateCcw size={16} />
                                Clear
                            </motion.button>

                            <motion.button
                                onClick={handleSubmit}
                                className="flex items-center gap-2 px-6 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 text-white font-medium shadow-lg shadow-emerald-500/30 hover:shadow-emerald-500/50 transition-shadow"
                                whileHover={{ scale: 1.02 }}
                                whileTap={{ scale: 0.98 }}
                            >
                                <Send size={16} />
                                Submit
                            </motion.button>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Error Display */}
                <AnimatePresence>
                    {error && (
                        <motion.div
                            className="mt-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: 10 }}
                        >
                            {error}
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        );
    }

    // Compact variant
    return (
        <div className={`relative ${className}`}>
            <div className="flex items-center gap-4">
                <SiriWave
                    theme={theme}
                    isActive={isListening}
                    volumeLevel={volumeLevel}
                    onToggle={handleToggle}
                    status={status}
                    size="md"
                    showLabel={false}
                />

                {/* Submit button when we have transcript */}
                <AnimatePresence>
                    {transcript && !isListening && (
                        <motion.button
                            onClick={handleSubmit}
                            className="p-3 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 text-white shadow-lg shadow-emerald-500/30"
                            initial={{ opacity: 0, scale: 0.8 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.8 }}
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                        >
                            <Send size={18} />
                        </motion.button>
                    )}
                </AnimatePresence>
            </div>

            {/* Inline transcript */}
            <AnimatePresence>
                {(transcript || interimTranscript) && (
                    <motion.div
                        className="mt-3 p-3 rounded-xl bg-slate-800/50 border border-white/5"
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                    >
                        <p className="text-white/80 text-sm">
                            {transcript}
                            {interimTranscript && (
                                <span className="text-emerald-400/60 italic"> {interimTranscript}</span>
                            )}
                        </p>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

/**
 * VoiceInputMinimal - Ultra-compact mic button with inline waveform
 */
export const VoiceInputMinimal = ({
    onTranscript,
    theme = 'ios9',
    className = '',
}) => {
    const { isListening, volumeLevel, toggleListening } = useVoice();

    return (
        <div className={`inline-flex items-center ${className}`}>
            <SiriWave
                theme={theme}
                isActive={isListening}
                volumeLevel={volumeLevel}
                onToggle={toggleListening}
                status={isListening ? 'listening' : 'idle'}
                size="sm"
                showLabel={false}
            />
        </div>
    );
};

export default VoiceInput;
