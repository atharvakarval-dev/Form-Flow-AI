/**
 * Create Plugin Modal - Multi-step wizard
 * REDESIGNED: Premium Side Drawer (Apple Style)
 */
import { useState, useCallback, useEffect, useRef, memo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
    X, ChevronLeft, ChevronRight, Database, Table2, Plus, Trash2,
    CheckCircle2, AlertCircle, Loader2, Zap, Sparkles, Server, Globe
} from 'lucide-react';
import { useTheme } from '@/context/ThemeProvider';
import { PluginFormProvider, usePluginForm } from '../context/PluginFormContext';
import { useCreatePlugin } from '@/hooks/usePluginQueries';
import {
    pluginBasicInfoSchema,
    pluginConnectionSchema,
    columnTypes,
} from '../schemas/pluginSchemas';
import toast from 'react-hot-toast';

// ============ Reusable UI Components ============

const InputField = ({ label, error, required, ...props }) => {
    const { isDark } = useTheme();
    return (
        <div className="space-y-1.5">
            <label className={`text-[11px] font-black uppercase tracking-[0.15em] ml-1 ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
                {label} {required && <span className="text-emerald-500">*</span>}
            </label>
            <input
                {...props}
                className={`
                    w-full px-5 py-4 rounded-2xl border text-sm font-medium transition-all duration-300
                    ${isDark
                        ? 'bg-zinc-950/40 border-white/[0.05] text-white placeholder:text-zinc-600 focus:border-emerald-500/50 focus:bg-zinc-950/60 focus:ring-4 focus:ring-emerald-500/5'
                        : 'bg-zinc-50/50 border-zinc-200 text-zinc-900 placeholder:text-zinc-400 focus:border-emerald-500 focus:bg-white focus:ring-4 focus:ring-emerald-500/5'
                    }
                    focus:outline-none 
                `}
            />
            {error && <p className="text-[10px] font-bold text-red-500 ml-1 mt-1 uppercase tracking-wider">{error}</p>}
        </div>
    );
};

const CardSelector = ({ type, icon: Icon, isSelected, onClick, label, isDark }) => (
    <motion.button
        type="button"
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        onClick={onClick}
        className={`
            relative flex flex-col items-center justify-center p-6 rounded-[2rem] border-2 transition-all duration-500
            ${isSelected
                ? isDark
                    ? 'bg-emerald-500/10 border-emerald-500/50 shadow-[0_0_30px_rgba(16,185,129,0.1)]'
                    : 'bg-emerald-50 border-emerald-500 shadow-lg shadow-emerald-500/10'
                : isDark
                    ? 'bg-zinc-950/40 border-white/[0.05] hover:border-white/20'
                    : 'bg-zinc-50 border-zinc-100 hover:border-zinc-200'
            }
        `}
    >
        <div className={`
            w-14 h-14 rounded-2xl flex items-center justify-center mb-4 transition-all duration-500
            ${isSelected
                ? 'bg-emerald-500 text-white shadow-lg'
                : isDark ? 'bg-zinc-800 text-zinc-500' : 'bg-white text-zinc-400 shadow-sm'
            }
        `}>
            <Icon className="w-7 h-7" />
        </div>
        <span className={`text-sm font-black uppercase tracking-widest ${isSelected ? (isDark ? 'text-white' : 'text-emerald-700') : 'text-zinc-500'}`}>
            {label}
        </span>
        {isSelected && (
            <motion.div
                layoutId="selector-glow-create"
                className="absolute inset-0 rounded-[2rem] bg-emerald-500/5 blur-xl -z-10"
            />
        )}
    </motion.button>
);

// ============ Step Components ============

function StepBasicInfo({ onNext }) {
    const { isDark } = useTheme();
    const { name, description, database_type, updateBasicInfo } = usePluginForm();

    const { register, handleSubmit, setValue, watch, formState: { errors } } = useForm({
        resolver: zodResolver(pluginBasicInfoSchema),
        defaultValues: { name, description, database_type },
    });

    const currentType = watch('database_type');

    const onSubmit = (data) => {
        updateBasicInfo(data);
        onNext();
    };

    return (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
            <div className="space-y-6">
                <InputField
                    label="Plugin Identity"
                    required
                    placeholder="Enter an evocative name..."
                    error={errors.name?.message}
                    {...register('name')}
                />

                <div className="space-y-1.5">
                    <label className={`text-[11px] font-black uppercase tracking-[0.15em] ml-1 ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
                        Description
                    </label>
                    <textarea
                        {...register('description')}
                        placeholder="Define the purpose of this collector..."
                        rows={3}
                        className={`
                            w-full px-5 py-4 rounded-2xl border text-sm font-medium transition-all duration-300
                            ${isDark
                                ? 'bg-zinc-950/40 border-white/[0.05] text-white placeholder:text-zinc-600 focus:border-emerald-500/50 focus:bg-zinc-950/60 focus:ring-4 focus:ring-emerald-500/5'
                                : 'bg-zinc-50/50 border-zinc-200 text-zinc-900 placeholder:text-zinc-400 focus:border-emerald-500 focus:bg-white focus:ring-4 focus:ring-emerald-500/5'
                            }
                            focus:outline-none resize-none
                        `}
                    />
                </div>

                <div className="space-y-4">
                    <label className={`text-[11px] font-black uppercase tracking-[0.15em] ml-1 ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
                        Engine Architecture <span className="text-emerald-500">*</span>
                    </label>
                    <div className="grid grid-cols-2 gap-4">
                        <CardSelector
                            type="postgresql"
                            icon={Database}
                            label="PostgreSQL"
                            isSelected={currentType === 'postgresql'}
                            onClick={() => setValue('database_type', 'postgresql')}
                            isDark={isDark}
                        />
                        <CardSelector
                            type="mysql"
                            icon={Server}
                            label="MySQL"
                            isSelected={currentType === 'mysql'}
                            onClick={() => setValue('database_type', 'mysql')}
                            isDark={isDark}
                        />
                    </div>
                    {errors.database_type && <p className="text-[10px] font-bold text-red-500 ml-1 uppercase">{errors.database_type.message}</p>}
                </div>
            </div>

            <motion.button
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.99 }}
                type="submit"
                className={`
                    w-full py-5 rounded-[2rem] font-black uppercase tracking-[0.2em] text-xs transition-all shadow-xl
                    ${isDark
                        ? 'bg-emerald-500 text-white shadow-emerald-500/20 hover:shadow-emerald-500/40'
                        : 'bg-zinc-900 text-white shadow-zinc-900/10 hover:shadow-zinc-900/20'
                    }
                    flex items-center justify-center gap-3
                `}
            >
                Initialize Phase <ChevronRight className="w-4 h-4" />
            </motion.button>
        </form>
    );
}

function StepConnection({ onNext, onBack }) {
    const { isDark } = useTheme();
    const { connection_config, database_type, updateConnection } = usePluginForm();

    const { register, handleSubmit, formState: { errors } } = useForm({
        resolver: zodResolver(pluginConnectionSchema),
        defaultValues: connection_config,
    });

    const onSubmit = (data) => {
        updateConnection(data);
        onNext();
    };

    return (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
            <div className="grid grid-cols-6 gap-5">
                <div className="col-span-4">
                    <InputField label="Host Address" required placeholder="db.example.com" error={errors.host?.message} {...register('host')} />
                </div>
                <div className="col-span-2">
                    <InputField label="Port" required placeholder={database_type === 'postgresql' ? '5432' : '3306'} error={errors.port?.message} {...register('port', { valueAsNumber: true })} />
                </div>
                <div className="col-span-6">
                    <InputField label="Target Schema / Database" required placeholder="production_v1" error={errors.database?.message} {...register('database')} />
                </div>
                <div className="col-span-3">
                    <InputField label="Access Identity" required placeholder="admin" error={errors.username?.message} {...register('username')} autoComplete="off" />
                </div>
                <div className="col-span-3">
                    <InputField label="Secure Password" required type="password" placeholder="••••••••" error={errors.password?.message} {...register('password')} autoComplete="new-password" />
                </div>
            </div>

            <div className="flex gap-4">
                <button
                    type="button"
                    onClick={onBack}
                    className={`
                        flex-1 py-4 rounded-[1.5rem] font-black uppercase tracking-[0.2em] text-[10px] transition-all
                        ${isDark ? 'bg-white/5 text-zinc-400 hover:text-white hover:bg-white/10' : 'bg-zinc-100 text-zinc-500 hover:bg-zinc-200'}
                        flex items-center justify-center gap-2
                    `}
                >
                    <ChevronLeft className="w-4 h-4" /> Go Back
                </button>
                <motion.button
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    type="submit"
                    className={`
                        flex-[2] py-4 rounded-[1.5rem] font-black uppercase tracking-[0.2em] text-xs transition-all shadow-xl
                        ${isDark
                            ? 'bg-emerald-500 text-white shadow-emerald-500/20 hover:shadow-emerald-500/40'
                            : 'bg-zinc-900 text-white shadow-zinc-900/10 hover:shadow-zinc-900/20'
                        }
                        flex items-center justify-center gap-3
                    `}
                >
                    Secure Connection <ChevronRight className="w-4 h-4" />
                </motion.button>
            </div>
        </form>
    );
}

function StepTables({ onNext, onBack }) {
    const { isDark } = useTheme();
    const { tables, addTable, updateTable, removeTable, addField, updateField, removeField } = usePluginForm();

    const canProceed = tables.length > 0 && tables.every(
        (t) => t.table_name && t.fields.length > 0 && t.fields.every(
            (f) => f.column_name && f.column_type && f.question_text
        )
    );

    return (
        <div className="space-y-8">
            <div className="space-y-6">
                {tables.map((table, tableIdx) => (
                    <motion.div
                        key={tableIdx}
                        initial={{ opacity: 0, scale: 0.98 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className={`
                            p-8 rounded-[3rem] border transition-all duration-500
                            ${isDark ? 'bg-zinc-950/40 border-white/[0.05]' : 'bg-white border-zinc-200/50 shadow-sm'}
                        `}
                    >
                        <div className="flex items-center gap-4 mb-8">
                            <div className="p-4 bg-emerald-500/10 rounded-3xl">
                                <Table2 className="w-7 h-7 text-emerald-500" />
                            </div>
                            <input
                                type="text"
                                value={table.table_name}
                                onChange={(e) => updateTable(tableIdx, { table_name: e.target.value })}
                                placeholder="Schema Table Name..."
                                className={`
                                    flex-1 bg-transparent border-none text-2xl font-black tracking-tighter placeholder:text-zinc-600 focus:ring-0
                                    ${isDark ? 'text-white' : 'text-zinc-900'}
                                `}
                            />
                            <button
                                onClick={() => removeTable(tableIdx)}
                                className={`p-4 rounded-2xl transition-all ${isDark ? 'hover:bg-red-500/10 text-zinc-500 hover:text-red-400' : 'hover:bg-red-50 text-zinc-400 hover:text-red-500'}`}
                            >
                                <Trash2 className="w-6 h-6" />
                            </button>
                        </div>

                        <div className="space-y-6">
                            {table.fields.map((field, fieldIdx) => (
                                <div key={fieldIdx} className="grid grid-cols-12 gap-4 items-end group">
                                    <div className="col-span-4">
                                        <InputField label="Field" placeholder="column_name" value={field.column_name} onChange={(e) => updateField(tableIdx, fieldIdx, { column_name: e.target.value })} />
                                    </div>
                                    <div className="col-span-5">
                                        <InputField label="Voice Prompt" placeholder="Ask the user..." value={field.question_text} onChange={(e) => updateField(tableIdx, fieldIdx, { question_text: e.target.value })} />
                                    </div>
                                    <div className="col-span-2 h-[58px]">
                                        <select
                                            value={field.column_type}
                                            onChange={(e) => updateField(tableIdx, fieldIdx, { column_type: e.target.value })}
                                            className={`
                                                w-full h-full px-4 rounded-2xl border text-[11px] font-black uppercase tracking-wider transition-all
                                                ${isDark ? 'bg-zinc-950 border-white/5 text-zinc-400' : 'bg-white border-zinc-200 text-zinc-500'}
                                                focus:outline-none focus:border-emerald-500/50
                                            `}
                                        >
                                            {columnTypes.map((type) => <option key={type} value={type}>{type}</option>)}
                                        </select>
                                    </div>
                                    <div className="col-span-1 pb-1 flex justify-center">
                                        <button
                                            onClick={() => removeField(tableIdx, fieldIdx)}
                                            disabled={table.fields.length === 1}
                                            className="p-3 bg-red-500/0 hover:bg-red-500/10 text-zinc-500 hover:text-red-400 rounded-xl transition-all disabled:opacity-0"
                                        >
                                            <X className="w-5 h-5" />
                                        </button>
                                    </div>
                                </div>
                            ))}

                            <button
                                onClick={() => addField(tableIdx)}
                                className={`
                                    w-full py-5 rounded-[2rem] border-2 border-dashed flex items-center justify-center gap-3 text-[11px] font-bold uppercase tracking-[0.2em] transition-all
                                    ${isDark ? 'border-white/5 text-zinc-500 hover:border-emerald-500/30 hover:text-emerald-400 shadow-inner' : 'border-zinc-100 text-zinc-400 hover:border-emerald-200 hover:text-emerald-600'}
                                `}
                            >
                                <Plus className="w-4 h-4" /> Append Attribute
                            </button>
                        </div>
                    </motion.div>
                ))}

                <button
                    onClick={() => addTable()}
                    className={`
                        w-full py-8 rounded-[3rem] border-2 border-dashed flex items-center justify-center gap-4 transition-all
                        ${isDark
                            ? 'border-white/5 text-zinc-500 hover:border-emerald-500/40 hover:text-emerald-400 bg-white/[0.01]'
                            : 'border-zinc-100 text-zinc-400 hover:border-emerald-200 hover:text-emerald-600 bg-zinc-50/10'
                        }
                    `}
                >
                    <Plus className="w-7 h-7" />
                    <span className="text-sm font-black uppercase tracking-[0.3em]">Deploy Table Schema</span>
                </button>
            </div>

            <div className="flex gap-4 pt-4">
                <button
                    type="button"
                    onClick={onBack}
                    className={`
                        flex-1 py-5 rounded-[2rem] font-black uppercase tracking-[0.2em] text-[10px] transition-all
                        ${isDark ? 'bg-white/5 text-zinc-400 hover:text-white hover:bg-white/10' : 'bg-zinc-100 text-zinc-500 hover:bg-zinc-200'}
                        flex items-center justify-center gap-2
                    `}
                >
                    <ChevronLeft className="w-4 h-4" /> Previous
                </button>
                <motion.button
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    onClick={onNext}
                    disabled={!canProceed}
                    className={`
                        flex-[2] py-5 rounded-[2rem] font-black uppercase tracking-[0.2em] text-xs transition-all shadow-xl
                        ${isDark
                            ? 'bg-emerald-500 text-white shadow-emerald-500/20 hover:shadow-emerald-500/40'
                            : 'bg-zinc-900 text-white shadow-zinc-900/10 hover:shadow-zinc-900/20'
                        }
                        ${!canProceed ? 'opacity-30 grayscale cursor-not-allowed' : ''}
                        flex items-center justify-center gap-3
                    `}
                >
                    Review Architecture <ChevronRight className="w-4 h-4" />
                </motion.button>
            </div>
        </div>
    );
}

function StepReview({ onBack, onSubmit, isSubmitting }) {
    const { isDark } = useTheme();
    const { name, database_type, connection_config, tables, getFormData } = usePluginForm();

    return (
        <div className="space-y-8">
            <div className={`
                p-10 rounded-[3.5rem] border space-y-10 relative overflow-hidden
                ${isDark ? 'bg-zinc-950/40 border-white/[0.05]' : 'bg-zinc-50/50 border-zinc-200 shadow-inner'}
            `}>
                <div className="flex items-center gap-8 relative z-10">
                    <div className="w-20 h-20 bg-emerald-500 rounded-[2rem] flex items-center justify-center shadow-2xl shadow-emerald-500/40">
                        <Sparkles className="w-10 h-10 text-white" />
                    </div>
                    <div>
                        <h2 className={`text-4xl font-black tracking-tighter ${isDark ? 'text-white' : 'text-zinc-900'}`}>{name}</h2>
                        <div className="flex gap-6 mt-2 opacity-50">
                            <span className="text-xs font-black uppercase tracking-[0.2em] flex items-center gap-2">
                                <Database className="w-4 h-4" /> {database_type}
                            </span>
                            <span className="text-xs font-black uppercase tracking-[0.2em] flex items-center gap-2">
                                <Globe className="w-4 h-4" /> {connection_config.host}
                            </span>
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-1 gap-4 relative z-10">
                    {tables.map((table, idx) => (
                        <div key={idx} className={`p-6 rounded-[2.5rem] border ${isDark ? 'bg-white/5 border-white/5' : 'bg-white border-zinc-100 shadow-sm'}`}>
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="p-2 bg-emerald-500/10 rounded-xl">
                                        <Table2 className="w-5 h-5 text-emerald-500" />
                                    </div>
                                    <span className={`text-lg font-black tracking-tight ${isDark ? 'text-zinc-300' : 'text-zinc-800'}`}>{table.table_name}</span>
                                </div>
                                <span className="text-[10px] font-black uppercase tracking-[0.2em] opacity-40">{table.fields.length} Active Attributes</span>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Decorative glow */}
                <div className="absolute -bottom-32 -right-32 w-80 h-80 bg-emerald-500/10 blur-[120px] rounded-full" />
            </div>

            <div className="flex gap-4">
                <button
                    type="button"
                    onClick={onBack}
                    disabled={isSubmitting}
                    className={`
                        flex-1 py-5 rounded-[2rem] font-black uppercase tracking-[0.2em] text-[10px] transition-all
                        ${isDark ? 'bg-white/5 text-zinc-400 hover:text-white hover:bg-white/10' : 'bg-zinc-100 text-zinc-500 hover:bg-zinc-200'}
                        flex items-center justify-center gap-2
                    `}
                >
                    <ChevronLeft className="w-4 h-4" /> Adjust
                </button>
                <motion.button
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    onClick={() => onSubmit(getFormData())}
                    disabled={isSubmitting}
                    className={`
                        flex-[2] py-5 rounded-[2rem] font-black uppercase tracking-[0.2em] text-xs transition-all shadow-xl
                        ${isDark
                            ? 'bg-emerald-500 text-white shadow-emerald-500/20 hover:shadow-emerald-500/40'
                            : 'bg-zinc-900 text-white shadow-zinc-900/10 hover:shadow-zinc-900/20'
                        }
                        flex items-center justify-center gap-3
                    `}
                >
                    {isSubmitting ? (
                        <><Loader2 className="w-5 h-5 animate-spin" /> Synchronizing...</>
                    ) : (
                        <><Zap className="w-5 h-5" /> Launch Architecture</>
                    )}
                </motion.button>
            </div>
        </div>
    );
}

// ============ Main Drawer ============

function CreatePluginModalContent({ onClose, onSuccess }) {
    const { isDark } = useTheme();
    const { step, nextStep, prevStep, reset } = usePluginForm();
    const createPlugin = useCreatePlugin();

    const handleSubmit = async (formData) => {
        try {
            await createPlugin.mutateAsync(formData);
            reset();
            onSuccess?.();
            onClose();
            toast.success('Plugin Architecture Deployed');
        } catch (error) { }
    };

    const steps = [
        { title: 'Identity', component: StepBasicInfo },
        { title: 'Connection', component: StepConnection },
        { title: 'Arch', component: StepTables },
        { title: 'Launch', component: StepReview },
    ];

    const CurrentStep = steps[step - 1].component;

    return (
        <div className="h-full flex flex-col">
            {/* Nav Header */}
            <div className="flex items-center justify-between p-10 pt-16 pb-2">
                <div className="space-y-1">
                    <div className="flex items-center gap-3">
                        <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.8)] animate-pulse" />
                        <span className={`text-[11px] font-black uppercase tracking-[0.4em] ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
                            Genesis Session
                        </span>
                    </div>
                    <h2 className={`text-4xl font-black tracking-tighter ${isDark ? 'text-white' : 'text-zinc-900'}`}>
                        Initialize Engine
                    </h2>
                </div>
                {/* Internal close button removed to avoid nav bar overlap, replaced by floating external arrow */}
                <div className="w-14" />
            </div>

            {/* Progress Segmented Pills */}
            <div className="flex gap-3 px-10 py-2">
                {steps.map((s, idx) => (
                    <div key={idx} className="flex-1 space-y-3">
                        <div className={`
                            h-2 rounded-full transition-all duration-1000
                            ${idx < step ? 'bg-emerald-500 shadow-[0_0_20px_rgba(16,185,129,0.5)]' : isDark ? 'bg-white/5' : 'bg-zinc-100'}
                        `} />
                        <span className={`
                            text-[9px] font-black uppercase tracking-[0.2em] block text-center transition-all duration-500
                            ${idx === step - 1 ? 'opacity-100 text-emerald-500 translate-y-0' : 'opacity-20 translate-y-1'}
                        `}>
                            {s.title}
                        </span>
                    </div>
                ))}
            </div>

            {/* Content Context */}
            <div className="flex-1 p-10 pt-0 overflow-y-auto custom-scrollbar">
                <AnimatePresence mode="wait">
                    <motion.div
                        key={step}
                        initial={{ opacity: 0, x: 40, filter: 'blur(20px)' }}
                        animate={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
                        exit={{ opacity: 0, x: -40, filter: 'blur(20px)' }}
                        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                    >
                        <CurrentStep
                            onNext={nextStep}
                            onBack={prevStep}
                            onSubmit={handleSubmit}
                            isSubmitting={createPlugin.isPending}
                        />
                    </motion.div>
                </AnimatePresence>
            </div>

            {/* Subtle Footer info */}
            <div className={`p-8 border-t text-center ${isDark ? 'border-white/[0.05]' : 'border-zinc-100'}`}>
                <p className="text-[10px] font-black uppercase tracking-[0.4em] opacity-20">FormFlow AI • Secure Genesis Environment</p>
            </div>
        </div>
    );
}

export function CreatePluginModal({ isOpen, onClose, onSuccess }) {
    const { isDark } = useTheme();
    const modalRef = useRef(null);

    useEffect(() => {
        if (isOpen) modalRef.current?.focus();
    }, [isOpen]);

    const handleKeyDown = (e) => {
        if (e.key === 'Escape') onClose();
    };

    return (
        <AnimatePresence>
            {isOpen && (
                <div className="fixed inset-0 z-[500] flex justify-end overflow-hidden">
                    {/* Immersive Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                        className="absolute inset-0 bg-zinc-950/60 backdrop-blur-3xl"
                    />

                    {/* Side Drawer Body */}
                    <motion.div
                        ref={modalRef}
                        initial={{ x: '100%', filter: 'blur(30px)' }}
                        animate={{ x: 0, filter: 'blur(0px)' }}
                        exit={{ x: '100%', filter: 'blur(30px)' }}
                        transition={{ type: "spring", damping: 35, stiffness: 350 }}
                        onKeyDown={handleKeyDown}
                        tabIndex={-1}
                        role="dialog"
                        aria-modal="true"
                        className={`
                            relative z-10 w-full max-w-3xl h-full shadow-[-40px_0_80px_rgba(0,0,0,0.5)] overflow-visible border-l
                            ${isDark ? 'bg-zinc-900/98 border-white/[0.05]' : 'bg-white/95 border-zinc-200/50 backdrop-blur-3xl'}
                        `}
                    >
                        {/* Floating Back Arrow - External to white area */}
                        <motion.button
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: 20 }}
                            transition={{ delay: 0.3 }}
                            onClick={onClose}
                            className={`
                                absolute -left-16 top-10 w-12 h-12 rounded-full flex items-center justify-center transition-all hover:scale-110 active:scale-95 z-20
                                ${isDark
                                    ? 'bg-zinc-800/80 text-white hover:bg-zinc-700 border-white/10'
                                    : 'bg-white/80 text-zinc-900 hover:bg-white shadow-2xl border-zinc-200'
                                }
                                backdrop-blur-xl border
                            `}
                        >
                            <ChevronLeft className="w-6 h-6" />
                        </motion.button>

                        <PluginFormProvider>
                            <CreatePluginModalContent onClose={onClose} onSuccess={onSuccess} />
                        </PluginFormProvider>
                    </motion.div>
                </div>
            )}
        </AnimatePresence>
    );
}

export default CreatePluginModal;
