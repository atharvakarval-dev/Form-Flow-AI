import React, { useState, useRef } from 'react';
import { Upload, X, File as FileIcon, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { uploadAttachment } from '@/services/api';

const AttachmentField = ({
    label,
    value,
    onChange,
    required = false,
    accept = "*/*",
    error = null
}) => {
    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadError, setUploadError] = useState(null);
    const fileInputRef = useRef(null);

    // Value is expected to be { file_id, url, name } or just a string URL if previously saved
    // We normalize it to object for internal state if possible, or just treat as success if present.
    const hasFile = !!value;

    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        setIsDragging(false);
    };

    const handleDrop = async (e) => {
        e.preventDefault();
        setIsDragging(false);
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            await handleUpload(files[0]);
        }
    };

    const handleFileSelect = async (e) => {
        const files = e.target.files;
        if (files.length > 0) {
            await handleUpload(files[0]);
        }
    };

    const handleUpload = async (file) => {
        setIsUploading(true);
        setUploadError(null);

        try {
            const response = await uploadAttachment(file);
            if (response.success) {
                // Return structured data for the form
                onChange({
                    file_id: response.file_id,
                    url: response.url,
                    name: response.file_name,
                    content_type: response.content_type,
                    size: response.size
                });
            } else {
                throw new Error(response.message || 'Upload failed');
            }
        } catch (err) {
            console.error("Upload error:", err);
            setUploadError(err.message || "Failed to upload file");
        } finally {
            setIsUploading(false);
            // Reset input so same file can be selected again if needed
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        }
    };

    const handleClear = (e) => {
        e.stopPropagation();
        e.preventDefault();
        onChange(null);
        setUploadError(null);
    };

    return (
        <div className="w-full">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">
                {label}
                {required && <span className="text-red-500 ml-1">*</span>}
            </label>

            <AnimatePresence mode="wait">
                {hasFile ? (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className="relative p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center gap-3 group"
                    >
                        <div className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400">
                            <FileIcon size={20} />
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-white truncate">
                                {value.name || 'Attached File'}
                            </p>
                            <p className="text-xs text-white/50">
                                {value.size ? `${(value.size / 1024).toFixed(1)} KB` : 'Ready to submit'}
                            </p>
                        </div>
                        <button
                            onClick={handleClear}
                            className="p-1.5 rounded-lg hover:bg-white/10 text-white/40 hover:text-white transition-colors"
                            type="button"
                        >
                            <X size={16} />
                        </button>
                    </motion.div>
                ) : (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                    >
                        <div
                            className={`
                                relative border-2 border-dashed rounded-xl p-6 transition-all cursor-pointer
                                flex flex-col items-center justify-center gap-2 text-center
                                ${isDragging
                                    ? 'border-emerald-500 bg-emerald-500/10'
                                    : 'border-white/10 hover:border-white/20 hover:bg-white/5'
                                }
                                ${error || uploadError ? 'border-red-500/50 bg-red-500/5' : ''}
                            `}
                            onDragOver={handleDragOver}
                            onDragLeave={handleDragLeave}
                            onDrop={handleDrop}
                            onClick={() => fileInputRef.current?.click()}
                        >
                            <input
                                ref={fileInputRef}
                                type="file"
                                className="hidden"
                                onChange={handleFileSelect}
                                accept={accept}
                            />

                            {isUploading ? (
                                <div className="flex flex-col items-center gap-2 text-emerald-400">
                                    <Loader2 size={24} className="animate-spin" />
                                    <span className="text-sm font-medium">Uploading...</span>
                                </div>
                            ) : (
                                <>
                                    <div className="p-3 rounded-full bg-white/5 text-white/50 group-hover:text-white transition-colors">
                                        <Upload size={24} />
                                    </div>
                                    <div>
                                        <p className="text-sm font-medium text-white">
                                            Click to upload or drag and drop
                                        </p>
                                        <p className="text-xs text-white/40 mt-1">
                                            PDF, DOCX, JPG, PNG (max 10MB)
                                        </p>
                                    </div>
                                </>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Error Message */}
            {(error || uploadError) && (
                <div className="flex items-center gap-1.5 mt-2 text-sm text-red-500">
                    <AlertCircle size={14} />
                    <span>{error || uploadError}</span>
                </div>
            )}
        </div>
    );
};

export default AttachmentField;
