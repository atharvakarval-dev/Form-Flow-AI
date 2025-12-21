import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Github, Linkedin, Mail, ArrowLeft,
    Code2, Terminal, Briefcase, GraduationCap, Trophy,
    ExternalLink
} from 'lucide-react';
import atharvaImg from '@/assets/images/atharva.jpeg';
import { cn } from '@/lib/utils';

// --- Data ---
const TEAM = [
    {
        id: 'atharva',
        name: "Atharva Karval",
        role: "Lead Full Stack Developer",
        image: atharvaImg,
        shortBio: "Architecting scalable web apps & crafting seamless digital experiences. Full Stack Developer with a passion for AI & High-Performance Systems.",
        socials: {
            linkedin: "https://linkedin.com/in/atharva-karval",
            github: "https://github.com/atharvak-dev",
            email: "mailto:atharva.shashikant.karval@gmail.com"
        },
        details: {
            education: [
                { school: "Marathwada Mitra Mandal’s College of Engineering", degree: "B.E. Computer Engineering", year: "Aug 2022 – May 2026", grade: "CGPA: 8.81/10.0" }
            ],
            skills: [
                { category: "Languages", items: ["Java", "C++", "Python", "JavaScript", "TypeScript", "SQL", "Go"] },
                { category: "Frameworks", items: ["React", "Next.js", "Node.js", "NestJS", "FastAPI", "PyTorch"] },
                { category: "Tools", items: ["Docker", "Kubernetes", "AWS", "Firebase", "Redis", "Git"] }
            ],
            experience: [
                { company: "Roxiler Systems", role: "Full Stack Developer Intern", period: "Oct 2025 – Present", points: ["Architected scalable web apps using React, NextJS, NestJS, and PostgreSQL.", "Optimized DB queries reducing latency by 20%."] },
                { company: "Kahani Technologies", role: "SDE Intern", period: "Jun 2025 – Aug 2025", points: ["Engineered responsive web apps using C# MVC and .NET Core.", "Optimized SQL queries reducing page load time by 40%."] },
                { company: "Xtreme Engineering Equipments", role: "Software Dev Intern", period: "Mar 2025 – Apr 2025", points: ["Built industrial automation app using .NET, increasing efficiency by 75%.", "Designed high-concurrency architecture."] }
            ],
            projects: [
                { name: "Campus Connect", tech: "TypeScript, React, MongoDB, ML", desc: "Real-time mentor matchmaking platform.", link: "https://campus-connect-alakazam.vercel.app/" },
                { name: "Nectar - AI Agricultural Assistant", tech: "React Native, TensorFlow", desc: "AI plant disease detection app.", link: "https://github.com/atharvak-dev/Nectar" },
                { name: "Sea Tale - RMS", tech: "NestJS, Next.js, PostgreSQL", desc: "Mobile-first restaurant management system.", link: "https://sea-tale-cafe.netlify.app/" },
                { name: "CryptoLabPro", tech: "Python, ML, Streamlit", desc: "Algorithmic trading modules with NLP.", link: "https://cryptoanalyst.streamlit.app/" }
            ],
            achievements: ["Sponsor’s Choice Award (HackSprint 2025)", "SIH 2023 Internal Winner", "AIR 1886 in Naukri Campus Test (Top 0.4%)"]
        }
    },
    {
        id: 'swarali', name: "Swarali Kulkarni", role: "Contributor", image: null, shortBio: "Contributing to the future of voice-first interfaces.", socials: {}
    },
    {
        id: 'shweta', name: "Shweta Ingole", role: "Contributor", image: null, shortBio: "Building robust systems for seamless automation.", socials: {}
    },
    {
        id: 'samarth', name: "Samarth Patil", role: "Contributor", image: null, shortBio: "Crafting intuitive user experiences through code.", socials: {}
    }
];

export const EditorialTeam = () => {
    const [active, setActive] = useState(0);
    const [isTransitioning, setIsTransitioning] = useState(false);
    const [selectedDev, setSelectedDev] = useState(null);
    const [hoveredIndex, setHoveredIndex] = useState(null);

    const handleChange = (index) => {
        if (index === active || isTransitioning) return;
        setIsTransitioning(true);
        setTimeout(() => {
            setActive(index);
            setTimeout(() => setIsTransitioning(false), 50);
        }, 300);
    };

    const current = TEAM[active];

    return (
        <section className="w-full bg-background relative py-[100px] overflow-hidden">
            {/* Background Effects */}
            <div className="absolute inset-0 bg-gradient-to-t from-background via-transparent to-transparent pointer-events-none z-10" />

            <div className="w-full max-w-6xl mx-auto px-6 relative z-0">
                <div className="flex flex-col md:flex-row items-start gap-8 md:gap-16">
                    {/* Large Index Number */}
                    <span
                        className="text-[120px] md:text-[180px] font-thin leading-none text-foreground/5 select-none transition-all duration-500 font-serif"
                        style={{ fontFeatureSettings: '"tnum"' }}
                    >
                        {String(active + 1).padStart(2, "0")}
                    </span>

                    <div className="flex-1 pt-6 md:pt-12">
                        {/* Bio / Quote */}
                        <div className={`transition-all duration-300 ${isTransitioning ? "opacity-0 translate-x-4" : "opacity-100 translate-x-0"}`}>
                            <h2 className="text-3xl md:text-5xl font-light leading-tight text-foreground tracking-tight mb-6">
                                "{current.shortBio}"
                            </h2>
                        </div>

                        {/* Author Info */}
                        <div className={`mt-10 group cursor-pointer inline-block transition-all duration-300 delay-100 ${isTransitioning ? "opacity-0" : "opacity-100"}`} onClick={() => current.details && setSelectedDev(current)}>
                            <div className="flex items-center gap-6">
                                <div className="relative w-16 h-16 md:w-20 md:h-20 rounded-full overflow-hidden ring-2 ring-primary/20 group-hover:ring-primary/60 transition-all duration-300 bg-muted shadow-lg">
                                    {current.image ? (
                                        <img src={current.image} alt={current.name} className="w-full h-full object-cover grayscale group-hover:grayscale-0 transition-all duration-500" />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center bg-muted text-muted-foreground">
                                            <Code2 className="w-8 h-8" />
                                        </div>
                                    )}
                                </div>
                                <div>
                                    <p className="text-2xl font-medium text-foreground group-hover:text-primary transition-colors">{current.name}</p>
                                    <p className="text-base text-muted-foreground mt-1">
                                        {current.role}
                                        {current.details && (
                                            <span className="ml-2 inline-flex items-center text-xs text-primary bg-primary/10 px-2 py-0.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity">
                                                View Profile <ExternalLink className="w-3 h-3 ml-1" />
                                            </span>
                                        )}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Pill Navigation Selector */}
                <div className="mt-20 border-t border-border/20 pt-10 flex flex-col md:flex-row items-center justify-between gap-6">
                    {/* Pills on the Left */}
                    <div className="flex items-center gap-3 flex-wrap justify-center md:justify-start">
                        {TEAM.map((member, index) => {
                            const isActive = active === index;
                            const isHovered = hoveredIndex === index && !isActive;
                            const showName = isActive || isHovered;

                            return (
                                <button
                                    key={member.id}
                                    onClick={() => handleChange(index)}
                                    onMouseEnter={() => setHoveredIndex(index)}
                                    onMouseLeave={() => setHoveredIndex(null)}
                                    className={cn(
                                        "relative flex items-center gap-0 rounded-full cursor-pointer h-12 overflow-hidden",
                                        "transition-all duration-300 ease-out border",
                                        isActive
                                            ? "bg-[#dcfce7] border-[#bbf7d0] shadow-[0_0_20px_rgba(22,163,74,0.4)] pr-6 pl-2 w-auto scale-105 ring-2 ring-[#22c55e]/50"
                                            : "bg-zinc-800/50 hover:bg-zinc-800 border-white/5 hover:border-white/10 p-2 w-12 hover:w-auto",
                                        showName ? "w-auto" : ""
                                    )}
                                >
                                    {/* Avatar */}
                                    <div className={cn(
                                        "relative flex-shrink-0 w-8 h-8 rounded-full overflow-hidden ring-2",
                                        isActive ? "ring-[#16a34a]/30 shadow-md" : "ring-white/10 bg-zinc-800"
                                    )}>
                                        {member.image ? (
                                            <img
                                                src={member.image}
                                                alt={member.name}
                                                className={cn(
                                                    "w-full h-full object-cover transition-all duration-300",
                                                    !isActive && "grayscale-[0.5] opacity-80 group-hover:grayscale-0"
                                                )}
                                            />
                                        ) : (
                                            <div className="w-full h-full flex items-center justify-center bg-zinc-800 text-zinc-400">
                                                <Code2 className="w-4 h-4" />
                                            </div>
                                        )}
                                    </div>

                                    <div
                                        className={cn(
                                            "grid transition-all duration-300 ease-out",
                                            showName ? "grid-cols-[1fr] opacity-100 ml-3" : "grid-cols-[0fr] opacity-0 ml-0",
                                        )}
                                    >
                                        <div className="overflow-hidden">
                                            <span
                                                className={cn(
                                                    "text-sm font-bold whitespace-nowrap block tracking-wide",
                                                    "transition-colors duration-300",
                                                    isActive ? "text-[#14532d]" : "text-zinc-400",
                                                )}
                                            >
                                                {member.name}
                                            </span>
                                        </div>
                                    </div>
                                </button>
                            );
                        })}
                    </div>

                    {/* Role Text on the Right */}
                    <p className={cn(
                        "text-xs md:text-sm text-zinc-400 tracking-[0.2em] uppercase font-medium text-right transition-all duration-500 ease-out",
                        isTransitioning ? "opacity-0 translate-y-2" : "opacity-100 translate-y-0",
                    )}>
                        {current.role}
                    </p>
                </div>
            </div>

            {/* Profile Modal */}
            <AnimatePresence>
                {selectedDev && (
                    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 md:p-8">
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.5, ease: "easeInOut" }}
                            onClick={() => setSelectedDev(null)}
                            className="absolute inset-0 bg-black/80 backdrop-blur-xl"
                        />

                        <motion.div
                            layoutId={`card-${selectedDev.id}`}
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.95, transition: { duration: 0.3, ease: "easeInOut" } }}
                            className="relative w-full max-w-5xl max-h-[85vh] bg-[#0a0a0a] border border-white/10 rounded-[2rem] shadow-2xl overflow-hidden flex flex-col md:flex-row z-50 text-left ring-1 ring-white/5"
                            onClick={(e) => e.stopPropagation()}
                        >
                            {/* Left Column - Sticky */}
                            <div className="w-full md:w-[35%] bg-zinc-900/30 p-8 flex flex-col items-center text-center border-b md:border-b-0 md:border-r border-white/5 relative overflow-y-auto no-scrollbar scrollbar-hide [&::-webkit-scrollbar]:hidden">
                                <div className="w-40 h-40 rounded-full overflow-hidden border-[3px] border-zinc-800 shadow-2xl mb-6 flex-shrink-0 ring-1 ring-white/10 relative group">
                                    <div className="absolute inset-0 bg-gradient-to-tr from-primary/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                                    <img src={selectedDev.image} alt={selectedDev.name} className="w-full h-full object-cover" />
                                </div>
                                <h2 className="text-3xl font-bold mb-2 tracking-tight text-white">{selectedDev.name}</h2>
                                <p className="text-primary font-medium mb-8 bg-primary/10 px-4 py-1.5 rounded-full text-sm border border-primary/20">{selectedDev.role}</p>

                                <div className="flex gap-4 mb-8">
                                    {Object.entries(selectedDev.socials).map(([platform, url]) => (
                                        <a key={platform} href={url} target="_blank" rel="noopener noreferrer" className="p-3.5 rounded-2xl bg-zinc-800/50 hover:bg-primary hover:text-white text-zinc-400 transition-all duration-300 border border-white/5 hover:border-primary hover:shadow-lg hover:shadow-primary/20 hover:-translate-y-1 group/icon">
                                            {platform === 'github' && <Github className="w-5 h-5" />}
                                            {platform === 'linkedin' && <Linkedin className="w-5 h-5" />}
                                            {platform === 'email' && <Mail className="w-5 h-5" />}
                                        </a>
                                    ))}
                                </div>

                                {/* Education Card */}
                                <div className="w-full text-left space-y-4 bg-zinc-900/50 p-5 rounded-2xl border border-white/5">
                                    <h4 className="flex items-center gap-2 font-bold text-xs uppercase tracking-wider text-zinc-500"><GraduationCap className="w-4 h-4 text-primary" /> Education</h4>
                                    {selectedDev.details.education.map((edu, i) => (
                                        <div key={i} className="text-sm">
                                            <p className="font-semibold text-zinc-200">{edu.school}</p>
                                            <p className="text-zinc-400 text-xs mt-1">{edu.degree}</p>
                                            <div className="flex justify-between mt-3 text-[10px] font-mono text-primary/80 uppercase tracking-widest bg-primary/5 px-2 py-1 rounded">
                                                <span>{edu.year}</span>
                                                <span className="text-primary">{edu.grade}</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Right Column - Scrollable Content */}
                            <div className="w-full md:w-[65%] p-8 overflow-y-auto no-scrollbar scrollbar-hide [&::-webkit-scrollbar]:hidden relative bg-gradient-to-br from-[#0a0a0a] to-zinc-900/50">
                                <button onClick={() => setSelectedDev(null)} className="absolute top-6 right-6 p-2 rounded-full hover:bg-white/10 transition-colors z-10 text-zinc-500 hover:text-white"><ArrowLeft className="w-5 h-5" /></button>

                                <div className="space-y-12">
                                    {/* Experience */}
                                    <section>
                                        <h3 className="text-xl font-bold mb-6 flex items-center gap-3 text-white"><Briefcase className="w-5 h-5 text-primary" /> Professional Experience</h3>
                                        <div className="space-y-8 relative border-l border-white/10 ml-3 pl-8">
                                            {selectedDev.details.experience.map((exp, i) => (
                                                <div key={i} className="relative group/exp">
                                                    <div className="absolute -left-[37px] top-1.5 w-4 h-4 rounded-full bg-[#0a0a0a] border-2 border-zinc-700 group-hover/exp:border-primary group-hover/exp:scale-110 transition-all shadow-[0_0_10px_rgba(0,0,0,0.5)]" />
                                                    <div className="flex justify-between items-start mb-3">
                                                        <div>
                                                            <h4 className="font-bold text-lg text-zinc-200 group-hover/exp:text-primary transition-colors">{exp.role}</h4>
                                                            <p className="text-sm text-zinc-400 font-medium">{exp.company}</p>
                                                        </div>
                                                        <span className="text-[10px] font-mono text-zinc-500 bg-white/5 border border-white/5 px-2 py-1 rounded">{exp.period}</span>
                                                    </div>
                                                    <ul className="space-y-2">
                                                        {exp.points.map((pt, j) => (
                                                            <li key={j} className="text-sm text-zinc-400 leading-relaxed flex items-start gap-2">
                                                                <span className="w-1 h-1 rounded-full bg-primary/50 mt-2 flex-shrink-0" />
                                                                {pt}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            ))}
                                        </div>
                                    </section>

                                    {/* Projects */}
                                    <section>
                                        <h3 className="text-xl font-bold mb-6 flex items-center gap-3 text-white"><Code2 className="w-5 h-5 text-primary" /> Featured Projects</h3>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            {selectedDev.details.projects.map((proj, i) => (
                                                <a key={i} href={proj.link} target="_blank" rel="noopener noreferrer" className="block p-5 rounded-2xl bg-zinc-900/30 border border-white/5 hover:border-primary/30 hover:bg-zinc-800/50 transition-all hover:scale-[1.02] group/proj relative overflow-hidden">

                                                    <div className="flex justify-between items-center mb-3">
                                                        <span className="text-[10px] uppercase font-bold text-primary/70 tracking-widest">{proj.tech.split(',')[0]}</span>
                                                        <ExternalLink className="w-3 h-3 text-zinc-600 group-hover/proj:text-primary transition-colors" />
                                                    </div>

                                                    <h4 className="font-bold text-base text-zinc-200 mb-2 group-hover/proj:text-primary transition-colors">{proj.name}</h4>
                                                    <p className="text-sm text-zinc-400 leading-relaxed line-clamp-2">{proj.desc}</p>
                                                </a>
                                            ))}
                                        </div>
                                    </section>

                                    {/* Achievements */}
                                    {selectedDev.details.achievements && (
                                        <section>
                                            <h3 className="text-xl font-bold mb-6 flex items-center gap-3 text-white"><Trophy className="w-5 h-5 text-yellow-500" /> Achievements</h3>
                                            <div className="grid grid-cols-1 gap-3">
                                                {selectedDev.details.achievements.map((ach, i) => (
                                                    <div key={i} className="flex items-start gap-4 p-4 rounded-xl bg-gradient-to-r from-yellow-500/5 to-transparent border border-yellow-500/10 hover:border-yellow-500/20 transition-colors">
                                                        <Trophy className="w-4 h-4 text-yellow-500 mt-1 flex-shrink-0" />
                                                        <span className="text-sm font-medium text-zinc-300">{ach}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </section>
                                    )}
                                </div>
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
        </section>
    );
}

export default EditorialTeam;
