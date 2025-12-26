import React, { useState, useEffect, memo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Lock, Smartphone, Globe, Zap, Keyboard, Sparkles, CheckCircle2, ShieldCheck, Languages, HandMetal, Eye } from "lucide-react";
import { useTheme } from "@/context/ThemeProvider";

const ANIMATION_EASE = [0.16, 1, 0.3, 1];

// ... (Keep existing CardSkeleton, AutoFillDemo component lines 16-75) ...
const AutoFillDemo = memo(function AutoFillDemo() {
    const [text, setText] = useState("");
    const fullText = "Alexandra Chen";
    const [isVisible, setIsVisible] = useState(false);

    useEffect(() => {
        const startDelay = setTimeout(() => setIsVisible(true), 100);
        return () => clearTimeout(startDelay);
    }, []);

    useEffect(() => {
        if (!isVisible) return;
        let index = 0;
        const interval = setInterval(() => {
            setText(fullText.slice(0, index + 1));
            index = (index + 1) % (fullText.length + 12);
        }, 150);
        return () => clearInterval(interval);
    }, [isVisible]);

    return (
        <div className="flex items-center justify-center w-full h-full min-h-[140px]">
            <div className="bg-white/90 dark:bg-zinc-800/90 backdrop-blur-sm rounded-xl border border-zinc-200/50 dark:border-zinc-700/50 p-5 shadow-sm w-full max-w-[220px]">
                <div className="flex gap-2 mb-3">
                    <div className="w-8 h-8 rounded-full bg-zinc-100 dark:bg-zinc-700" />
                    <div className="space-y-1">
                        <div className="w-20 h-2 bg-zinc-100 dark:bg-zinc-700 rounded-full" />
                        <div className="w-12 h-2 bg-zinc-50 dark:bg-zinc-600 rounded-full" />
                    </div>
                </div>
                <div className="space-y-3">
                    <div>
                        <div className="text-[10px] font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider mb-1.5">Full Name</div>
                        <div className="flex items-center h-9 px-3 bg-zinc-50 dark:bg-zinc-700 rounded-md border border-zinc-100 dark:border-zinc-600">
                            <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                                {text}
                            </span>
                            {isVisible && (
                                <motion.div
                                    animate={{ opacity: [1, 0] }}
                                    transition={{ repeat: Infinity, duration: 0.8 }}
                                    className="w-0.5 h-4 bg-emerald-500 ml-0.5"
                                />
                            )}
                        </div>
                    </div>
                    <div className="opacity-40">
                        <div className="text-[10px] font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider mb-1.5">Email</div>
                        <div className="h-9 w-full bg-zinc-50 dark:bg-zinc-700 rounded-md border border-zinc-100 dark:border-zinc-600" />
                    </div>
                </div>
            </div>
        </div>
    );
});

// ... (Keep existing MultilingualAnim component lines 77-126) ...
const MultilingualAnim = memo(function MultilingualAnim() {
    const languages = [
        { text: "Hello", lang: "en" },
        { text: "Hola", lang: "es" },
        { text: "Bonjour", lang: "fr" },
        { text: "नमस्ते", lang: "hi" },
        { text: "你好", lang: "zh" }
    ];
    const [index, setIndex] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setIndex((prev) => (prev + 1) % languages.length);
        }, 2000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="flex flex-col items-center justify-center h-full w-full gap-4 min-h-[140px]">
            <div className="relative w-28 h-20 flex items-center justify-center">
                <Globe className="w-20 h-20 text-emerald-100 dark:text-emerald-900/30 absolute" strokeWidth={1} />
                <AnimatePresence mode="wait">
                    <motion.div
                        key={index}
                        initial={{ opacity: 0, scale: 0.8, y: 10 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.8, y: -10 }}
                        transition={{ duration: 0.3 }}
                        className="relative z-10 bg-white/90 dark:bg-zinc-800/90 backdrop-blur-sm px-4 py-2 rounded-full border border-zinc-200/50 dark:border-zinc-700/50 shadow-lg min-w-[100px] text-center"
                    >
                        <span className="text-lg font-bold text-zinc-900 dark:text-white">
                            {languages[index].text}
                        </span>
                        <span className="absolute -top-1 -right-1 flex h-3 w-3">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                        </span>
                    </motion.div>
                </AnimatePresence>
            </div>
            <div className="flex gap-2">
                {languages.map((l, i) => (
                    <div
                        key={l.lang}
                        className={`w-2 h-2 rounded-full transition-colors duration-300 ${i === index ? 'bg-emerald-500' : 'bg-zinc-200 dark:bg-zinc-700'}`}
                    />
                ))}
            </div>
        </div>
    );
});

// ... (Keep existing AccessibilityAnim component lines 128-158) ...
const AccessibilityAnim = memo(function AccessibilityAnim() {
    return (
        <div className="flex flex-col items-center justify-center h-full w-full min-h-[140px] gap-4">
            <div className="grid grid-cols-2 gap-3">
                <motion.div
                    className="w-16 h-16 bg-white/50 dark:bg-zinc-800/50 rounded-2xl border border-zinc-200/50 dark:border-zinc-700/50 flex items-center justify-center shadow-sm backdrop-blur-sm"
                    whileHover={{ scale: 1.05 }}
                    animate={{ y: [0, -4, 0] }}
                    transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                >
                    <Eye className="w-8 h-8 text-zinc-900 dark:text-white" />
                </motion.div>
                <motion.div
                    className="w-16 h-16 bg-zinc-900/90 dark:bg-white/90 rounded-2xl border border-zinc-800/50 dark:border-zinc-200/50 flex items-center justify-center shadow-sm backdrop-blur-sm"
                    whileHover={{ scale: 1.05 }}
                    animate={{ y: [0, -4, 0] }}
                    transition={{ duration: 3, repeat: Infinity, ease: "easeInOut", delay: 1.5 }}
                >
                    <HandMetal className="w-8 h-8 text-white dark:text-zinc-900" />
                </motion.div>
            </div>
            <div className="bg-zinc-100 dark:bg-zinc-800/80 backdrop-blur-sm px-3 py-1 rounded-full text-[10px] font-bold text-zinc-600 dark:text-zinc-300 uppercase tracking-widest border border-zinc-200 dark:border-zinc-700">
                WCAG 2.1 Compliant
            </div>
        </div>
    );
});

// ... (Keep existing SpeedMetric, SecurityShield, VoiceCommandAnim lines ... ) ...
// (I will just copy them to be safe, but with minor style tweaks to match new aesthetic)

const SpeedMetric = memo(function SpeedMetric() {
    const [progress, setProgress] = useState(0);
    const [isVisible, setIsVisible] = useState(false);

    useEffect(() => {
        const startDelay = setTimeout(() => setIsVisible(true), 300);
        return () => clearTimeout(startDelay);
    }, []);

    useEffect(() => {
        if (!isVisible) return;
        const interval = setInterval(() => {
            setProgress(0);
            setTimeout(() => setProgress(100), 100);
        }, 3000);
        return () => clearInterval(interval);
    }, [isVisible]);

    return (
        <div className="flex flex-col items-center justify-center h-full w-full gap-6 min-h-[140px]">
            <div className="relative">
                <svg className="w-24 h-24 -rotate-90">
                    <circle cx="48" cy="48" r="40" stroke="currentColor" strokeWidth="6" fill="transparent" className="text-zinc-100 dark:text-zinc-800" />
                    <motion.circle
                        cx="48" cy="48" r="40"
                        stroke="currentColor" strokeWidth="6"
                        fill="transparent"
                        className="text-emerald-500"
                        strokeLinecap="round"
                        style={{ filter: "drop-shadow(0 0 4px rgba(16, 185, 129, 0.5))" }}
                        initial={{ pathLength: 0 }}
                        animate={{ pathLength: isVisible ? progress / 100 : 0 }}
                        transition={{ duration: 1.5, ease: "easeOut" }}
                    />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-2xl font-bold text-zinc-900 dark:text-white">0.2s</span>
                </div>
            </div>
            <div className="flex items-center gap-2 px-3 py-1 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-100 dark:border-emerald-900/50 text-emerald-700 dark:text-emerald-400 rounded-full text-xs font-medium backdrop-blur-sm">
                <Zap className="w-3 h-3 fill-emerald-700 dark:fill-emerald-400" />
                <span>Instant Execution</span>
            </div>
        </div>
    );
});

const SecurityShield = memo(function SecurityShield() {
    return (
        <div className="flex items-center justify-center h-full w-full min-h-[140px]">
            <div className="relative">
                <div className="absolute inset-0 bg-emerald-500/20 blur-3xl rounded-full" />
                <div className="relative w-32 h-32 bg-white/90 dark:bg-zinc-800/80 backdrop-blur-md rounded-2xl border border-zinc-200/50 dark:border-zinc-700/50 shadow-xl flex items-center justify-center overflow-hidden">
                    <div className="absolute inset-0 bg-[radial-gradient(#e4e4e7_1px,transparent_1px)] dark:bg-[radial-gradient(#3f3f46_1px,transparent_1px)] [background-size:16px_16px] opacity-20" />
                    <motion.div
                        animate={{ scale: [1, 1.05, 1] }}
                        transition={{ duration: 3, repeat: Infinity }}
                    >
                        <ShieldCheck className="w-12 h-12 text-emerald-500 drop-shadow-md" />
                    </motion.div>
                    <motion.div
                        className="absolute top-0 left-0 w-full h-1 bg-emerald-400/50 blur-[2px]"
                        animate={{ top: ["0%", "100%", "0%"] }}
                        transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
                    />
                </div>
                <motion.div
                    className="absolute -top-3 -right-3 bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 text-[10px] font-bold px-2 py-1 rounded-md shadow-lg flex items-center gap-1"
                    animate={{ y: [0, -5, 0] }}
                    transition={{ duration: 2, repeat: Infinity }}
                >
                    <Lock className="w-3 h-3" />
                    256-BIT
                </motion.div>
            </div>
        </div>
    );
});

const VoiceCommandAnim = memo(function VoiceCommandAnim() {
    const [isVisible, setIsVisible] = useState(false);

    useEffect(() => {
        const startDelay = setTimeout(() => setIsVisible(true), 300);
        return () => clearTimeout(startDelay);
    }, []);

    return (
        <div className="flex items-center justify-center h-full w-full min-h-[240px]">
            <div className="relative">
                <div className="relative w-[140px] h-[240px] bg-white dark:bg-zinc-800 rounded-[2rem] border-[6px] border-zinc-900 dark:border-zinc-700 shadow-2xl overflow-hidden z-10 transition-colors duration-500">
                    <div className="absolute top-0 left-1/2 -translate-x-1/2 w-16 h-4 bg-zinc-900 dark:bg-zinc-700 rounded-b-xl z-20" />
                    <div className="pt-8 px-4 flex flex-col h-full bg-zinc-50 dark:bg-zinc-900/50">
                        <div className="flex items-center gap-2 mb-6">
                            <div className="w-8 h-8 rounded-full bg-emerald-100 dark:bg-emerald-900/50 flex items-center justify-center">
                                <div className="w-4 h-4 bg-emerald-500 rounded-full" />
                            </div>
                            <div className="space-y-1">
                                <div className="w-12 h-1.5 bg-zinc-200 dark:bg-zinc-700 rounded-full" />
                                <div className="w-20 h-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-full" />
                            </div>
                        </div>
                        <div className="mt-auto mb-8 flex flex-col items-center">
                            <div className="text-[10px] font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider mb-3">Listening...</div>
                            <div className="flex items-end gap-1 h-8">
                                {isVisible && [1, 2, 3, 4, 3, 2, 1].map((h, i) => (
                                    <motion.div
                                        key={i}
                                        className="w-1 bg-zinc-900 dark:bg-white rounded-full"
                                        animate={{ height: [8, 24, 12, 32, 16][i % 5] }}
                                        transition={{ repeat: Infinity, duration: 0.8, delay: i * 0.1 }}
                                    />
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
                <div className="absolute -bottom-10 -right-10 w-32 h-32 bg-emerald-500/20 rounded-full blur-[60px]" />
            </div>
        </div>
    );
});

/**
 * FeatureCard - Redesigned with Glassmorphism and Spotlights
 */
const FeatureCard = memo(function FeatureCard({ children, className, title, description, icon: Icon, delay = 0 }) {
    const { isDark } = useTheme();

    return (
        <motion.div
            className={`
                group relative rounded-3xl p-[1px] overflow-hidden
                transition-all duration-500 h-full
                ${className}
            `}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ delay, duration: 0.5, ease: "easeOut" }}
            whileHover={{ y: -4 }}
        >
            {/* Animated Border Gradient */}
            <div className={`absolute inset-0 bg-gradient-to-br opacity-100 transition-opacity duration-500 ${isDark ? 'from-zinc-700/50 via-zinc-800/10 to-transparent' : 'from-zinc-300 via-zinc-200/50 to-transparent'}`} />

            {/* Hover Spotlight Effect */}
            <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/20 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

            {/* Inner Content - Glassy Background */}
            <div className={`relative h-full flex flex-col rounded-[calc(1.5rem-1px)] overflow-hidden transition-colors duration-500 ${isDark ? 'bg-zinc-900/40 backdrop-blur-sm' : 'bg-white shadow-[0_2px_8px_rgba(0,0,0,0.04)]'}`}>

                {/* Content Container - Fixed Height for Alignment */}
                <div className={`h-64 shrink-0 flex items-center justify-center p-6 border-b relative overflow-hidden ${isDark ? 'border-zinc-800/50' : 'border-zinc-100'}`}>
                    {/* Subtle grid pattern in background */}
                    <div className={`absolute inset-0 opacity-[0.03] ${isDark ? 'opacity-[0.05] bg-[radial-gradient(#fff_1px,transparent_1px)]' : 'bg-[radial-gradient(#000_1px,transparent_1px)]'} [background-size:16px_16px]`} />
                    <div className="relative z-10 w-full">
                        {children}
                    </div>
                </div>

                {/* Text Content */}
                <div className={`p-8 flex-1 flex flex-col items-center text-center ${isDark ? 'bg-transparent' : 'bg-white'}`}>
                    <div className="mb-4">
                        <div className={`p-2.5 rounded-xl transition-colors duration-300 border ${isDark ? 'bg-zinc-800/50 border-zinc-700/50 group-hover:bg-emerald-900/20' : 'bg-zinc-50 border-zinc-200 group-hover:bg-emerald-50'}`}>
                            <Icon className={`w-5 h-5 transition-colors duration-300 ${isDark ? 'text-zinc-300 group-hover:text-emerald-400' : 'text-zinc-600 group-hover:text-emerald-600'}`} />
                        </div>
                    </div>
                    <h3 className={`text-xl font-semibold mb-2 transition-colors ${isDark ? 'text-zinc-100 group-hover:text-emerald-400' : 'text-zinc-900 group-hover:text-emerald-700'}`}>{title}</h3>
                    <p className={`text-sm leading-relaxed font-medium ${isDark ? 'text-zinc-400' : 'text-zinc-600'}`}>{description}</p>
                </div>
            </div>
        </motion.div>
    );
});

/**
 * FeaturesGrid - Main component
 */
function FeaturesGrid() {
    const { isDark } = useTheme();

    // Theme Variables - Enhanced for "Premium" look
    const sectionBg = isDark ? "bg-[#09090b]" : "bg-white"; // Deep black instead of zinc-950
    const voiceCardBg = isDark ? "bg-zinc-900/60 border border-zinc-800/50 backdrop-blur-md" : "bg-white border border-zinc-200 shadow-xl shadow-zinc-200/40";
    const voiceCardText = isDark ? "text-white" : "text-zinc-900";
    const voiceCardDesc = isDark ? "text-zinc-400" : "text-zinc-600";
    const voiceBadgeBg = isDark ? "bg-zinc-800/80 backdrop-blur-sm" : "bg-zinc-100";
    const voiceBadgeBorder = isDark ? "border-zinc-700" : "border-zinc-200";
    const voiceBadgeText = isDark ? "text-emerald-400" : "text-emerald-700";

    return (
        <section className={`${sectionBg} px-4 md:px-6 py-32 flex items-center justify-center relative overflow-hidden transition-colors duration-700`}>

            {/* Ambient Spotlights for Dark Mode */}
            {isDark && (
                <>
                    <div className="absolute top-0 left-1/4 w-[1000px] h-[400px] bg-emerald-900/10 rounded-[100%] blur-[120px] pointer-events-none" />
                    <div className="absolute bottom-0 right-1/4 w-[800px] h-[600px] bg-indigo-900/5 rounded-[100%] blur-[120px] pointer-events-none" />
                </>
            )}

            <div className="max-w-[1400px] w-full mx-auto relative z-10">

                {/* Header Section */}
                <div className="mb-24 flex flex-col md:flex-row md:items-end justify-between gap-8 md:gap-20">
                    <div className="max-w-2xl">
                        <motion.div
                            className={`inline-flex items-center gap-2 px-3 py-1 rounded-full ${isDark ? 'bg-zinc-900/50 border-zinc-800 text-zinc-400' : 'bg-zinc-100 border-zinc-200 text-zinc-600'} border text-xs font-semibold uppercase tracking-wider mb-6 backdrop-blur-sm`}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                        >
                            <Sparkles className="w-3 h-3 fill-zinc-400 text-zinc-400" />
                            Capabilities
                        </motion.div>

                        <motion.h2
                            className="text-4xl md:text-6xl font-semibold text-zinc-900 dark:text-white tracking-tight leading-[1.1]"
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: 0.1 }}
                        >
                            Built for speed, <span className="text-zinc-400 dark:text-zinc-600">accessibility & scale.</span>
                        </motion.h2>
                    </div>

                    <motion.p
                        className="text-lg text-zinc-600 dark:text-zinc-400 max-w-md leading-relaxed mb-1"
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.2 }}
                    >
                        Our intelligent agents now speak 5+ languages and support full WCAG accessibility compliance out of the box.
                    </motion.p>
                </div>

                {/* Bento Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <FeatureCard
                        className="md:col-start-1"
                        title="Smart Auto-Fill"
                        description="Our agents type naturally, detecting fields contextually to fill widely different forms accurately."
                        icon={Keyboard}
                        delay={0.1}
                    >
                        <AutoFillDemo />
                    </FeatureCard>

                    <FeatureCard
                        className="md:col-start-2"
                        title="Multilingual Support"
                        description="Seamlessly translates and fills forms in English, Spanish, French, Hindi, and Mandarin."
                        icon={Languages}
                        delay={0.2}
                    >
                        <MultilingualAnim />
                    </FeatureCard>

                    <FeatureCard
                        className="md:col-start-3"
                        title="Inclusive Design"
                        description="Fully WCAG 2.1 AA compliant with high contrast, dyslexia-friendly fonts, and screen reader support."
                        icon={Eye}
                        delay={0.3}
                    >
                        <AccessibilityAnim />
                    </FeatureCard>

                    <FeatureCard
                        className="md:col-span-2"
                        title="Enterprise Security"
                        description="End-to-end encryption with zero-retention policy. Your data is processed securely in isolated environments and wiped immediately after submission."
                        icon={Lock}
                        delay={0.4}
                    >
                        <SecurityShield />
                    </FeatureCard>

                    <FeatureCard
                        className="md:col-span-1"
                        title="Lightning Fast"
                        description="Optimized execution pipeline ensures submissions happen in milliseconds, not seconds."
                        icon={Zap}
                        delay={0.5}
                    >
                        <SpeedMetric />
                    </FeatureCard>

                    {/* Full Width Voice Feature - REFINED */}
                    <motion.div
                        className={`md:col-span-3 ${voiceCardBg} rounded-[2.5rem] p-8 md:p-12 overflow-hidden relative group transition-all duration-500`}
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.6 }}
                    >
                        {/* Subtle pulsing background for voice card */}
                        {isDark && <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-emerald-500/10 rounded-full blur-[120px] pointer-events-none animate-pulse" />}

                        <div className="relative z-10 flex flex-col md:flex-row items-center gap-12 md:gap-24">
                            <div className="flex-1 text-center md:text-left">
                                <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full ${voiceBadgeBg} border ${voiceBadgeBorder} ${voiceBadgeText} text-xs font-semibold uppercase tracking-wider mb-6 shadow-sm`}>
                                    <Smartphone className="w-3 h-3" />
                                    Voice Control
                                </div>
                                <h3 className={`text-3xl md:text-4xl font-semibold ${voiceCardText} mb-6 tracking-tight`}>"Fill this form for me."</h3>
                                <p className={`text-lg ${voiceCardDesc} leading-relaxed max-w-xl font-medium`}>
                                    Just say the word. Our voice agent parses your intent from natural language and executes complex form filling tasks hands-free.
                                </p>

                                <div className="mt-8 flex flex-col md:flex-row items-center gap-4 text-sm font-medium text-zinc-600 dark:text-zinc-300">
                                    <div className="flex items-center gap-2">
                                        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                        <span>High Accuracy ASR</span>
                                    </div>
                                    <div className="hidden md:block w-1 h-1 bg-zinc-300 dark:bg-zinc-700 rounded-full" />
                                    <div className="flex items-center gap-2">
                                        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                        <span>Context Awareness</span>
                                    </div>
                                </div>
                            </div>

                            <div className="flex-1 flex justify-center md:justify-end">
                                <VoiceCommandAnim />
                            </div>
                        </div>
                    </motion.div>
                </div>
            </div>
        </section>
    );
}

export default FeaturesGrid;
