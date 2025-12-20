import React, { useEffect, useRef, useState } from 'react';
import { useScroll, useTransform, motion } from 'framer-motion';
import { Mic, Keyboard, Clock, Zap, CheckCircle2, XCircle, ArrowRight } from 'lucide-react';

const timelineData = [
    {
        title: 'The Old Way',
        icon: <Keyboard className="w-6 h-6" />,
        color: 'rgb(107, 107, 107)',
        content: (
            <div className="space-y-4">
                <div className="bg-muted/50 p-6 rounded-lg border-2 border-border/50 backdrop-blur-sm">
                    <div className="flex items-start gap-3 mb-4">
                        <XCircle className="w-5 h-5 text-destructive mt-0.5 flex-shrink-0" />
                        <div>
                            <h4 className="font-bold text-foreground mb-2">Manual Typing</h4>
                            <p className="text-muted-foreground text-sm leading-relaxed">
                                Painstakingly typing each field, one character at a time. Copy-pasting from documents,
                                double-checking every entry, losing your place mid-form.
                            </p>
                        </div>
                    </div>
                    <div className="flex items-start gap-3">
                        <XCircle className="w-5 h-5 text-destructive mt-0.5 flex-shrink-0" />
                        <div>
                            <h4 className="font-bold text-foreground mb-2">Accessibility Barriers</h4>
                            <p className="text-muted-foreground text-sm leading-relaxed">
                                Forms inaccessible to those with motor disabilities, visual impairments, or
                                language barriers. A digital divide that excludes millions.
                            </p>
                        </div>
                    </div>
                    <div className="flex items-start gap-3 mt-4">
                        <XCircle className="w-5 h-5 text-destructive mt-0.5 flex-shrink-0" />
                        <div>
                            <h4 className="font-bold text-foreground mb-2">Time Consuming</h4>
                            <p className="text-muted-foreground text-sm leading-relaxed">
                                Average form takes 5-10 minutes. Complex forms? 20+ minutes of frustration,
                                errors, and abandonment.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        ),
    },
    {
        title: 'Form Flow AI',
        icon: <Mic className="w-6 h-6" />,
        color: 'rgb(26, 137, 23)',
        content: (
            <div className="space-y-4">
                <div className="bg-gradient-to-br from-primary/10 via-primary/5 to-transparent p-6 rounded-lg border-2 border-primary/30 backdrop-blur-sm relative overflow-hidden">
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(26,137,23,0.1),transparent_70%)] pointer-events-none" />
                    <div className="relative">
                        <div className="flex items-start gap-3 mb-4">
                            <CheckCircle2 className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                            <div>
                                <h4 className="font-bold text-foreground mb-2">Natural Voice Interaction</h4>
                                <p className="text-muted-foreground text-sm leading-relaxed">
                                    Simply speak your information. The AI understands context, asks clarifying questions,
                                    and formats everything perfectly. No typing required.
                                </p>
                            </div>
                        </div>
                        <div className="flex items-start gap-3">
                            <CheckCircle2 className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                            <div>
                                <h4 className="font-bold text-foreground mb-2">Universal Access</h4>
                                <p className="text-muted-foreground text-sm leading-relaxed">
                                    Voice-first design breaks down barriers. Accessible to everyone, regardless of
                                    ability, language, or technical skill.
                                </p>
                            </div>
                        </div>
                        <div className="flex items-start gap-3 mt-4">
                            <CheckCircle2 className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                            <div>
                                <h4 className="font-bold text-foreground mb-2">Lightning Fast</h4>
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
            const rect = ref.current.getBoundingClientRect();
            setHeight(rect.height);
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
            className="w-full bg-background/95 backdrop-blur-sm relative overflow-hidden"
            ref={containerRef}
        >
            {/* Smooth top gradient */}
            <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-transparent to-background/95 pointer-events-none z-10" />

            {/* Background Pattern */}
            <div className="absolute inset-0 opacity-[0.03] pointer-events-none">
                <div
                    className="absolute inset-0"
                    style={{
                        backgroundImage: `radial-gradient(circle at 2px 2px, var(--foreground) 1px, transparent 0)`,
                        backgroundSize: '40px 40px',
                    }}
                />
            </div>

            <div className="max-w-7xl mx-auto py-24 px-4 md:px-8 lg:px-10 relative z-10">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                    className="mb-16"
                >
                    <div className="flex items-center gap-3 mb-4">
                        <div className="h-px w-16 bg-primary" />
                        <span className="text-primary font-mono text-sm uppercase tracking-wider">Transformation</span>
                        <div className="h-px flex-1 bg-border" />
                    </div>
                    <h2 className="text-4xl md:text-6xl font-bold text-foreground mb-6 leading-tight">
                        The World Before
                        <br />
                        <span className="text-primary relative inline-block">
                            Form Flow AI
                            <motion.div
                                className="absolute -bottom-2 left-0 right-0 h-1 bg-primary/30"
                                initial={{ scaleX: 0 }}
                                whileInView={{ scaleX: 1 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.8, delay: 0.3 }}
                            />
                        </span>
                    </h2>
                    <p className="text-muted-foreground text-lg md:text-xl max-w-2xl leading-relaxed">
                        A journey from manual frustration to intelligent automation.
                        See how voice AI is reshaping form completion forever.
                    </p>
                </motion.div>
            </div>

            <div ref={ref} className="relative max-w-7xl mx-auto pb-32 px-4 md:px-8 lg:px-10">
                {timelineData.map((item, index) => (
                    <motion.div
                        key={index}
                        initial={{ opacity: 0, x: index % 2 === 0 ? -30 : 30 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true, margin: '-100px' }}
                        transition={{ duration: 0.6, delay: index * 0.2 }}
                        className="flex justify-start pt-10 md:pt-32 md:gap-10"
                    >
                        <div className="sticky flex flex-col md:flex-row z-40 items-center top-40 self-start max-w-xs lg:max-w-sm md:w-full">
                            <div
                                className="h-12 absolute left-2 md:left-2 w-12 rounded-full bg-background border-2 flex items-center justify-center transition-all duration-300"
                                style={{ borderColor: item.color }}
                            >
                                <div
                                    className="h-6 w-6 rounded-full flex items-center justify-center transition-all duration-300"
                                    style={{
                                        backgroundColor: item.color,
                                        boxShadow: `0 0 20px ${item.color}40`
                                    }}
                                >
                                    <div className="text-white">
                                        {item.icon}
                                    </div>
                                </div>
                            </div>
                            <h3 className="hidden md:block text-2xl md:pl-24 md:text-5xl font-bold text-foreground leading-tight">
                                {item.title}
                            </h3>
                        </div>

                        <div className="relative pl-20 pr-4 md:pl-4 w-full">
                            <h3 className="md:hidden block text-3xl mb-6 text-left font-bold text-foreground">
                                {item.title}
                            </h3>
                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.5, delay: 0.3 }}
                            >
                                {item.content}
                            </motion.div>
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
