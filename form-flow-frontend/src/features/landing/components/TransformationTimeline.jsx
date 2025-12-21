import React, { useEffect, useRef, useState } from 'react';
import { useScroll, useTransform, motion } from 'framer-motion';
import { Mic, Keyboard, Clock, Zap, CheckCircle2, XCircle, ArrowRight } from 'lucide-react';

const timelineData = [
    {
        title: 'The Old Way',
        icon: <Keyboard className="w-6 h-6" />,
        color: '#ef4444', // Red for "Problem"
        content: (
            <div className="space-y-4">
                <div className="group relative bg-gradient-to-br from-red-500/5 via-red-500/0 to-transparent p-6 rounded-2xl border border-red-500/10 backdrop-blur-md transition-all duration-300 hover:border-red-500/20 hover:shadow-[0_0_30px_-5px_rgba(239,68,68,0.1)]">
                    {/* Inner glow */}
                    <div className="absolute inset-0 bg-red-500/5 blur-3xl rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

                    <div className="relative space-y-6">
                        <div className="flex gap-4">
                            <div className="flex-shrink-0 mt-1">
                                <div className="h-8 w-8 rounded-full bg-red-500/10 flex items-center justify-center border border-red-500/20 shadow-inner">
                                    <XCircle className="w-4 h-4 text-red-500" />
                                </div>
                            </div>
                            <div>
                                <h4 className="font-bold text-foreground mb-2 text-lg">Manual Typing</h4>
                                <p className="text-muted-foreground text-sm leading-relaxed">
                                    Painstakingly typing each field, one character at a time. Copy-pasting from documents,
                                    double-checking every entry, losing your place mid-form.
                                </p>
                            </div>
                        </div>

                        <div className="flex gap-4">
                            <div className="flex-shrink-0 mt-1">
                                <div className="h-8 w-8 rounded-full bg-red-500/10 flex items-center justify-center border border-red-500/20 shadow-inner">
                                    <XCircle className="w-4 h-4 text-red-500" />
                                </div>
                            </div>
                            <div>
                                <h4 className="font-bold text-foreground mb-2 text-lg">Accessibility Barriers</h4>
                                <p className="text-muted-foreground text-sm leading-relaxed">
                                    Forms inaccessible to those with motor disabilities, visual impairments, or
                                    language barriers. A digital divide that excludes millions.
                                </p>
                            </div>
                        </div>

                        <div className="flex gap-4">
                            <div className="flex-shrink-0 mt-1">
                                <div className="h-8 w-8 rounded-full bg-red-500/10 flex items-center justify-center border border-red-500/20 shadow-inner">
                                    <XCircle className="w-4 h-4 text-red-500" />
                                </div>
                            </div>
                            <div>
                                <h4 className="font-bold text-foreground mb-2 text-lg">Time Consuming</h4>
                                <p className="text-muted-foreground text-sm leading-relaxed">
                                    Average form takes 5-10 minutes. Complex forms? 20+ minutes of frustration,
                                    errors, and abandonment.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        ),
    },
    {
        title: 'Form Flow AI',
        icon: <Zap className="w-6 h-6" />,
        color: '#16a34a', // Green for "Solution"
        content: (
            <div className="space-y-4">
                <div className="group relative bg-gradient-to-br from-primary/10 via-primary/5 to-transparent p-6 rounded-2xl border-2 border-primary/20 backdrop-blur-md transition-all duration-300 hover:border-primary/40 hover:shadow-[0_0_40px_-10px_rgba(22,163,74,0.2)] overflow-hidden">
                    {/* Background sheen */}
                    <div className="absolute inset-0 bg-[linear-gradient(45deg,transparent,rgba(255,255,255,0.03),transparent)] translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000" />

                    <div className="relative space-y-6">
                        <div className="flex gap-4">
                            <div className="flex-shrink-0 mt-1">
                                <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20 shadow-[0_0_10px_rgba(22,163,74,0.2)]">
                                    <CheckCircle2 className="w-4 h-4 text-primary" />
                                </div>
                            </div>
                            <div>
                                <h4 className="font-bold text-foreground mb-2 text-lg flex items-center gap-2">
                                    Natural Voice Interaction
                                    <span className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-full border border-primary/20 font-medium tracking-wide">AI POWERED</span>
                                </h4>
                                <p className="text-muted-foreground text-sm leading-relaxed">
                                    Simply speak your information. The AI understands context, asks clarifying questions,
                                    and formats everything perfectly. No typing required.
                                </p>
                            </div>
                        </div>

                        <div className="flex gap-4">
                            <div className="flex-shrink-0 mt-1">
                                <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20 shadow-[0_0_10px_rgba(22,163,74,0.2)]">
                                    <CheckCircle2 className="w-4 h-4 text-primary" />
                                </div>
                            </div>
                            <div>
                                <h4 className="font-bold text-foreground mb-2 text-lg">Universal Access</h4>
                                <p className="text-muted-foreground text-sm leading-relaxed">
                                    Voice-first design breaks down barriers. Accessible to everyone, regardless of
                                    ability, language, or technical skill.
                                </p>
                            </div>
                        </div>

                        <div className="flex gap-4">
                            <div className="flex-shrink-0 mt-1">
                                <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20 shadow-[0_0_10px_rgba(22,163,74,0.2)]">
                                    <CheckCircle2 className="w-4 h-4 text-primary" />
                                </div>
                            </div>
                            <div>
                                <h4 className="font-bold text-foreground mb-2 text-lg">Lightning Fast</h4>
                                <p className="text-muted-foreground text-sm leading-relaxed">
                                    Complete complex forms in 2-3 minutes. AI handles formatting, validation,
                                    and submission automatically. Your time, reclaimed.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        ),
    },
];

export const TransformationTimeline = () => {
    const ref = useRef(null);
    const containerRef = useRef(null);
    const [height, setHeight] = useState(0);

    useEffect(() => {
        if (ref.current) {
            const updateHeight = () => {
                const rect = ref.current.getBoundingClientRect();
                setHeight(rect.height);
            };

            updateHeight();
            window.addEventListener('resize', updateHeight);
            return () => window.removeEventListener('resize', updateHeight);
        }
    }, [ref]);

    const { scrollYProgress } = useScroll({
        target: containerRef,
        offset: ['start 20%', 'end 60%'],
    });

    const heightTransform = useTransform(scrollYProgress, [0, 1], [0, height]);
    const opacityTransform = useTransform(scrollYProgress, [0, 0.15], [0, 1]);

    return (
        <div
            className="w-full bg-background relative overflow-hidden"
            ref={containerRef}
            id="how-it-works"
        >
            {/* Ambient Background Glows */}
            <div className="absolute top-[20%] left-[-10%] w-[500px] h-[500px] bg-primary/5 rounded-full blur-[120px] pointer-events-none" />
            <div className="absolute bottom-[20%] right-[-10%] w-[500px] h-[500px] bg-primary/5 rounded-full blur-[120px] pointer-events-none" />

            {/* Background Grid */}
            <div className="absolute inset-0 opacity-[0.03] pointer-events-none">
                <div
                    className="absolute inset-0"
                    style={{
                        backgroundImage: `linear-gradient(var(--foreground) 1px, transparent 0), linear-gradient(90deg, var(--foreground) 1px, transparent 0)`,
                        backgroundSize: '80px 80px',
                    }}
                />
            </div>

            <div className="max-w-7xl mx-auto py-24 px-4 md:px-8 lg:px-10 relative z-10">
                <motion.div
                    initial={{ opacity: 0, y: 30 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.8 }}
                    className="mb-24 text-center"
                >
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-semibold tracking-wider uppercase mb-6">
                        <Zap className="w-3 h-3" />
                        Paradigm Shift
                    </div>

                    <h2 className="text-4xl md:text-5xl lg:text-7xl font-bold text-foreground mb-8 tracking-tight">
                        The Evolution of <br className="hidden md:block" />
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-primary/60">
                            Data Entry
                        </span>
                    </h2>

                    <p className="text-muted-foreground text-lg md:text-xl max-w-2xl mx-auto leading-relaxed">
                        We're not just improving forms. We're completely reimagining how humans interact with digital systems.
                    </p>
                </motion.div>
            </div>

            <div ref={ref} className="relative max-w-7xl mx-auto pb-32 px-4 md:px-8 lg:px-10">
                {timelineData.map((item, index) => (
                    <motion.div
                        key={index}
                        initial={{ opacity: 0, y: 40 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true, margin: '-100px' }}
                        transition={{ duration: 0.7, delay: index * 0.2 }}
                        className="flex flex-col md:flex-row gap-8 md:gap-20 mb-20 last:mb-0 relative z-20"
                    >
                        {/* Icon/Title Column */}
                        <div className="md:w-1/3 flex flex-row md:flex-col items-center md:items-end md:text-right gap-6 sticky top-32 self-start">
                            <div className="flex-1 md:flex-none">
                                <h3 className="text-3xl md:text-5xl font-bold text-foreground leading-tight">
                                    {item.title}
                                </h3>
                            </div>

                            <div className="relative group">
                                <div className="absolute inset-0 bg-current blur-2xl opacity-20 group-hover:opacity-40 transition-opacity duration-500 rounded-full" style={{ color: item.color }} />
                                <div
                                    className="relative w-16 h-16 md:w-20 md:h-20 rounded-full bg-background border-4 flex items-center justify-center transition-all duration-300 group-hover:scale-110"
                                    style={{ borderColor: item.color }}
                                >
                                    <div
                                        className="w-full h-full rounded-full flex items-center justify-center opacity-10 absolute inset-0"
                                        style={{ backgroundColor: item.color }}
                                    />
                                    {React.cloneElement(item.icon, {
                                        className: "w-8 h-8 md:w-10 md:h-10 transition-transform duration-300 group-hover:rotate-12",
                                        style: { color: item.color }
                                    })}
                                </div>
                            </div>
                        </div>

                        {/* Content Column */}
                        <div className="md:w-2/3">
                            {item.content}
                        </div>
                    </motion.div>
                ))}

                {/* Animated Timeline Line */}
                <div
                    style={{
                        height: height + 'px',
                    }}
                    className="absolute md:left-10 left-10 top-0 overflow-hidden w-[3px] bg-gradient-to-b from-transparent via-border to-transparent"
                >
                    <motion.div
                        style={{
                            height: heightTransform,
                            opacity: opacityTransform,
                        }}
                        className="absolute inset-x-0 top-0 w-[3px] rounded-full"
                    >
                        <div
                            className="h-full w-full rounded-full"
                            style={{
                                background: `linear-gradient(to bottom, 
                  transparent 0%, 
                  rgb(26, 137, 23) 10%, 
                  rgb(26, 137, 23) 90%, 
                  transparent 100%)`,
                                boxShadow: '0 0 20px rgba(26, 137, 23, 0.5)',
                            }}
                        />
                    </motion.div>
                </div>

                {/* Transformation Arrow */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.8 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5, delay: 0.5 }}
                    className="absolute left-8 md:left-10 top-1/2 -translate-y-1/2 -translate-x-1/2 z-50"
                >
                    <div className="bg-primary rounded-full p-3 shadow-lg" style={{ boxShadow: '0 0 30px rgba(26, 137, 23, 0.4)' }}>
                        <ArrowRight className="w-6 h-6 text-primary-foreground" />
                    </div>
                </motion.div>
            </div>

            {/* Bottom CTA Section */}
            <motion.div
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6 }}
                className="max-w-7xl mx-auto px-4 md:px-8 lg:px-10 pb-24 relative z-10"
            >
                <div className="bg-gradient-to-br from-primary/10 via-primary/5 to-transparent rounded-2xl p-8 md:p-12 border-2 border-primary/20 relative overflow-hidden">
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_20%,rgba(26,137,23,0.15),transparent_50%)] pointer-events-none" />
                    <div className="relative">
                        <div className="flex items-center gap-3 mb-4">
                            <Zap className="w-6 h-6 text-primary" />
                            <h3 className="text-2xl md:text-3xl font-bold text-foreground">
                                Ready to Transform Your Forms?
                            </h3>
                        </div>
                        <p className="text-muted-foreground text-lg md:text-xl mb-6 max-w-2xl">
                            Experience the future of form completion. Start with any form URL above and
                            let voice AI guide you through a seamless, accessible experience.
                        </p>
                        <div className="flex flex-wrap gap-4">
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Clock className="w-4 h-4 text-primary" />
                                <span>2-3 minutes per form</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <CheckCircle2 className="w-4 h-4 text-primary" />
                                <span>100% accessible</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Zap className="w-4 h-4 text-primary" />
                                <span>AI-powered accuracy</span>
                            </div>
                        </div>
                    </div>
                </div>
            </motion.div>
        </div>
    );
};

export default TransformationTimeline;
