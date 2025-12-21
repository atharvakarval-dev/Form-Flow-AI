/**
 * SiriWave Component - Custom SVG Version
 * 
 * Custom-built Siri-style visualization using pure SVG and Framer Motion.
 * Guarantees distinct, responsive waves without external libraries.
 */

import React, { useEffect, useState } from 'react';
import { Mic, MicOff, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

/**
 * Curve Component - Filled liquid blob with "Screen" blending
 */
const Curve = ({ color, speed, volume, index, isActive }) => {
    const [path, setPath] = useState("");

    useEffect(() => {
        let phase = 0;
        let animationId;

        const animate = () => {
            // De-sync phases for organic liquid movement
            phase += speed + (index * 0.01);

            const width = 450;
            const height = 150;
            const center = height / 2;

            // Base amplitude (breathing) + Volume reaction
            const baseAmp = isActive ? 15 : 2;
            const volumeAmp = isActive ? (volume * 60) : 0;
            const amplitude = baseAmp + volumeAmp;

            let topPath = "";
            let bottomPath = "";

            // Draw smooth curves
            // Re-loop for bottom curve (drawing backwards from right to left)
            let d = `M 0 ${center}`;

            // 1. Forward: Top Curve
            for (let x = 0; x <= width; x += 5) {
                const xp = x / width;
                const attenuation = Math.pow(4 * xp * (1 - xp), 2.5);
                const freq = 0.012 - (index * 0.001); // Vary freq slightly
                // Use Sine but ensure positive bulge for structure
                const wave = Math.sin((x * freq) + phase + (index * 1.5));
                const y = center - (Math.abs(wave) * amplitude * attenuation);
                d += ` L ${x} ${y}`;
            }

            // 2. Backward: Bottom Curve (mirror)
            for (let x = width; x >= 0; x -= 5) {
                const xp = x / width;
                const attenuation = Math.pow(4 * xp * (1 - xp), 2.5);
                const freq = 0.012 - (index * 0.001);
                const wave = Math.sin((x * freq) + phase + (index * 1.5));
                const y = center + (Math.abs(wave) * amplitude * attenuation);
                d += ` L ${x} ${y}`;
            }

            d += " Z"; // Close path

            setPath(d);
            animationId = requestAnimationFrame(animate);
        };

        animationId = requestAnimationFrame(animate);
        return () => cancelAnimationFrame(animationId);
    }, [speed, volume, index, isActive]);

    return (
        <path
            d={path}
            fill={color}
            stroke="none"
            style={{
                mixBlendMode: 'screen', // CORE EFFECT: Colors add up to white
                opacity: isActive ? 0.9 : 0.3,
                transition: 'opacity 0.3s ease'
            }}
        />
    );
};

/**
 * SiriWave - Main Component
 */
const SiriWave = ({
    isActive = false,
    volumeLevel = 0,
    onToggle,
    status = 'idle',
    color = '#10b981',
    showLabel = true,
    className = '',
}) => {
    const [smoothVol, setSmoothVol] = useState(0);

    useEffect(() => {
        setSmoothVol(prev => prev + (volumeLevel - prev) * 0.4);
    }, [volumeLevel]);

    // Status labels
    const statusLabels = {
        idle: 'Tap microphone',
        listening: 'Listening...',
        processing: 'Processing...',
        speaking: 'Speaking...',
    };

    const renderIcon = () => {
        if (status === 'processing') return <Loader2 size={24} className="animate-spin text-white" />;
        return isActive ? <MicOff size={24} className="text-black" /> : <Mic size={24} className="text-white" />;
    };

    return (
        <div className={`flex flex-col items-center gap-6 ${className}`}>
            <div className="flex items-center justify-center gap-4">
                {/* Mic Button */}
                <motion.button
                    onClick={onToggle}
                    className={`
            relative z-20 w-16 h-16 rounded-full flex items-center justify-center
            transition-all duration-300 ease-out
            ${isActive
                            ? 'bg-white shadow-[0_0_50px_rgba(255,255,255,0.6)] scale-110'
                            : 'bg-white/10 hover:bg-white/20 backdrop-blur-md border border-white/20'
                        }
          `}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                >
                    {renderIcon()}

                    {/* Subtle pulse ring when active */}
                    {isActive && (
                        <motion.div
                            className="absolute inset-0 rounded-full border border-white/40"
                            initial={{ opacity: 0.8, scale: 1 }}
                            animate={{ opacity: 0, scale: 1.8 }}
                            transition={{ duration: 2, repeat: Infinity }}
                        />
                    )}
                </motion.button>

                {/* Siri Waveform Container */}
                <div
                    className="relative overflow-hidden rounded-full"
                    style={{
                        width: 480,
                        height: 160,
                        background: 'radial-gradient(ellipse at center, rgba(10,10,30,0.4) 0%, transparent 70%)',
                    }}
                >
                    <svg
                        width="100%"
                        height="100%"
                        viewBox="0 0 450 150"
                        className="absolute inset-0 w-full h-full"
                        style={{
                            // REMOVED BLUR for crisp, distinct edges
                            transform: 'scale(1.1)'
                        }}
                    >
                        {/* 
                   FILLED SHAPES - Crisp, overlapping colors
                   Using Screen blending for white center
                */}

                        {/* Layer 1: Deep Blue (Base) */}
                        <Curve isActive={isActive} volume={smoothVol} speed={0.06} index={1} color="rgba(0, 50, 255, 0.8)" />

                        {/* Layer 2: Radiant Cyan */}
                        <Curve isActive={isActive} volume={smoothVol} speed={0.09} index={2} color="rgba(0, 255, 255, 0.7)" />

                        {/* Layer 3: Hot Magenta/Pink */}
                        <Curve isActive={isActive} volume={smoothVol} speed={0.12} index={3} color="rgba(255, 0, 128, 0.7)" />

                        {/* Layer 4: White Highlight (Center) */}
                        <Curve isActive={isActive} volume={smoothVol} speed={0.15} index={4} color="rgba(255, 255, 255, 0.5)" />
                    </svg>
                </div>
            </div>

            {/* Status Label Pill */}
            {showLabel && (
                <AnimatePresence mode="wait">
                    <motion.div
                        key={status}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className={`
              text-sm font-medium px-4 py-1.5 rounded-full
              ${isActive
                                ? 'text-emerald-400 bg-emerald-500/10'
                                : 'text-slate-400 bg-slate-500/10'
                            }
            `}
                    >
                        {statusLabels[status]}
                    </motion.div>
                </AnimatePresence>
            )}
        </div>
    );
};

/**
 * SiriWaveCard - Full card component
 */
export const SiriWaveCard = ({
    isActive = false,
    volumeLevel = 0,
    onToggle,
    status = 'idle',
    transcript = '',
    interimTranscript = '',
    className = '',
}) => {
    return (
        <motion.div
            className={`
        relative overflow-hidden rounded-3xl p-6
        bg-gradient-to-br from-slate-900/95 to-slate-800/95
        backdrop-blur-xl border border-white/10
        shadow-2xl shadow-black/40
        ${className}
      `}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
        >
            <div className="relative z-10 w-full">
                {/* Header */}
                <div className="flex items-center gap-3 mb-6">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shadow-lg shadow-emerald-500/30">
                        <Mic size={20} className="text-white" />
                    </div>
                    <div>
                        <h3 className="text-white font-semibold">FormFlow Voice</h3>
                        <p className="text-slate-400 text-sm">Speak naturally to fill forms</p>
                    </div>
                </div>

                {/* Waveform Central Area */}
                <div className="flex justify-center mb-6 w-full">
                    <SiriWave
                        isActive={isActive}
                        volumeLevel={volumeLevel}
                        onToggle={onToggle}
                        status={status}
                        showLabel={false}
                    />
                </div>

                {/* Transcript Box */}
                <div className="min-h-[80px] p-4 rounded-2xl bg-black/40 border border-white/5 transition-all">
                    {transcript || interimTranscript ? (
                        <div className="text-white/90 text-sm leading-relaxed font-light">
                            {transcript}
                            {interimTranscript && (
                                <span className="text-emerald-400/80 italic animate-pulse">
                                    {' '}{interimTranscript}
                                </span>
                            )}
                        </div>
                    ) : (
                        <div className="text-slate-500 text-sm text-center py-4 italic">
                            {isActive ? 'Listening for your voice...' : 'Tap microphone to start'}
                        </div>
                    )}
                </div>

                {/* Footer Status */}
                <div className="flex justify-center mt-4">
                    <div className={`
            flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-medium border
            ${isActive
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                            : 'bg-slate-500/10 text-slate-400 border-slate-500/20'
                        }
          `}>
                        <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
                        {status === 'idle' && 'Ready'}
                        {status === 'listening' && 'Listening'}
                        {status === 'processing' && 'Processing'}
                        {status === 'speaking' && 'Speaking'}
                    </div>
                </div>
            </div>
        </motion.div>
    );
};

export default SiriWave;
