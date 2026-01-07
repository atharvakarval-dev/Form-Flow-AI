import React, { useState } from 'react';
import { CheckCircle, Send, AlertTriangle, Download, FileText, Copy, RotateCcw, Loader2, Sparkles, Brain } from 'lucide-react';
import { motion } from 'framer-motion';
import { submitForm, fillPdf, getPdfDownloadUrl, generateProfile } from '@/services/api';
import { RatingInteraction } from '@/components/ui/RatingInteraction';

const FormCompletion = ({ formData, formSchema, originalUrl, pdfId, onReset }) => {
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [submissionResult, setSubmissionResult] = useState(null);
    const [isDownloading, setIsDownloading] = useState(false);
    const [profileUpdateStatus, setProfileUpdateStatus] = useState('idle'); // idle, updating, success, error

    // Auto-generate profile on completion
    React.useEffect(() => {
        const updateProfile = async () => {
            if (formData && Object.keys(formData).length > 0) {
                setProfileUpdateStatus('updating');
                try {
                    const response = await generateProfile(formData, "Web Form", "Form Completion");
                    if (response.success) {
                        setProfileUpdateStatus('success');
                    } else {
                        console.warn("Profile update API returned false:", response.message);
                        setProfileUpdateStatus('error');
                    }
                } catch (error) {
                    console.error("Profile update failed:", error);
                    setProfileUpdateStatus('error');
                }
            }
        };
        updateProfile();
    }, []);

    // Save rating to localStorage
    const handleRatingChange = (rating) => {
        try {
            const feedbackHistory = JSON.parse(localStorage.getItem('form_feedback_history') || '{}');
            // Use originalUrl as key to link rating to submission
            feedbackHistory[originalUrl] = {
                rating,
                timestamp: new Date().toISOString(),
                url: originalUrl
            };
            localStorage.setItem('form_feedback_history', JSON.stringify(feedbackHistory));
        } catch (err) {
            console.error("Failed to save rating:", err);
        }
    };

    const handleSubmitToWebsite = async () => {
        setIsSubmitting(true);
        try {
            const response = await submitForm(originalUrl, formData, formSchema);
            setSubmissionResult(response);
        } catch (error) {
            console.error('Submission error:', error);
            setSubmissionResult({
                success: false,
                message: 'Failed to submit form',
                error: error.response?.data?.detail || error.message
            });
        } finally {
            setIsSubmitting(false);
        }
    };

    const downloadFormData = async () => {
        // If we have a pdfId, try to fill and download the PDF
        if (pdfId) {
            setIsDownloading(true);
            try {
                const response = await fillPdf(pdfId, formData);
                if (response.success && response.download_id) {
                    // Open download URL
                    const downloadUrl = getPdfDownloadUrl(response.download_id);
                    window.open(downloadUrl, '_blank');
                } else {
                    alert('Failed to generate PDF: ' + (response.message || 'Unknown error'));
                    // Fallback to JSON
                    downloadAsJson();
                }
            } catch (error) {
                console.error('PDF download error:', error);
                alert('PDF download failed. Downloading as JSON instead.');
                downloadAsJson();
            } finally {
                setIsDownloading(false);
            }
        } else {
            // No PDF - download as JSON
            downloadAsJson();
        }
    };

    const downloadAsJson = () => {
        const dataStr = JSON.stringify(formData, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'form-data.json';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };

    const copyToClipboard = () => {
        const formText = Object.entries(formData)
            .map(([key, value]) => `${key}: ${value}`)
            .join('\n');
        navigator.clipboard.writeText(formText);
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 font-sans text-white">
            <style>{`
        .no-scrollbar::-webkit-scrollbar {
          display: none !important;
          width: 0px !important;
          background: transparent !important;
        }
        .no-scrollbar {
          -ms-overflow-style: none !important;
          scrollbar-width: none !important;
        }
      `}</style>

            {/* Window Container */}
            <div className="w-full max-w-2xl bg-black/40 border border-white/20 rounded-2xl backdrop-blur-2xl shadow-2xl relative overflow-hidden flex flex-col max-h-[90vh]">

                {/* Window Header */}
                <div className="bg-white/5 p-4 flex items-center justify-between border-b border-white/10 shrink-0">
                    <div className="flex gap-2">
                        <div className="w-3 h-3 rounded-full bg-red-400/80"></div>
                        <div className="w-3 h-3 rounded-full bg-yellow-400/80"></div>
                        <div className="w-3 h-3 rounded-full bg-green-400/80"></div>
                    </div>
                    <div className="text-xs font-semibold text-white/40 flex items-center gap-2 font-mono uppercase tracking-widest">
                        <FileText size={12} />
                        form_submission_module.exe
                    </div>
                    <div className="w-14"></div>
                </div>

                {/* Content Area */}
                <div className="p-8 overflow-y-auto no-scrollbar">

                    <div className="text-center mb-8">
                        <div className="w-20 h-20 bg-green-500/10 rounded-full flex items-center justify-center mx-auto mb-4 border border-green-500/20">
                            <CheckCircle className="text-green-400" size={40} />
                        </div>
                        <h2 className="text-3xl font-bold text-white mb-2">Form Completed!</h2>
                        <p className="text-white/60 mb-8">
                            All required information has been collected successfully.
                        </p>

                        {/* Profile Update Status */}
                        {profileUpdateStatus === 'updating' && (
                            <div className="flex items-center justify-center gap-2 text-xs text-blue-200/70 mb-6 bg-blue-500/10 py-1.5 px-3 rounded-full border border-blue-500/10 w-fit mx-auto">
                                <Loader2 size={12} className="animate-spin" />
                                Analyzing patterns & updating profile...
                            </div>
                        )}
                        {profileUpdateStatus === 'success' && (
                            <div className="flex items-center justify-center gap-2 text-xs text-purple-200/80 mb-6 bg-purple-500/10 py-1.5 px-3 rounded-full border border-purple-500/10 w-fit mx-auto">
                                <Brain size={12} />
                                Behavioral profile extracted & saved
                            </div>
                        )}

                        {/* Feedback Rating */}
                        <div className="bg-white/5 rounded-2xl p-6 border border-white/10 inline-block w-full max-w-md">
                            <RatingInteraction onChange={handleRatingChange} />
                        </div>
                    </div>

                    {/* Form Data Summary */}
                    <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden mb-6">
                        <div className="px-4 py-3 bg-white/5 border-b border-white/10 flex justify-between items-center">
                            <h3 className="font-semibold text-white/80 text-sm uppercase tracking-wider">Collected Information</h3>
                            <span className="text-xs text-white/40 font-mono">{Object.keys(formData).length} fields</span>
                        </div>
                        <div className="max-h-60 overflow-y-auto p-4 space-y-3">
                            {Object.entries(formData).length > 0 ? (
                                Object.entries(formData).map(([key, value]) => (
                                    <div key={key} className="flex justify-between items-start text-sm group">
                                        <span className="text-white/50 font-mono capitalize shrink-0 pr-4 mt-0.5 group-hover:text-white/70 transition-colors">
                                            {key}:
                                        </span>
                                        <span className="font-medium text-white text-right break-words">{value}</span>
                                    </div>
                                ))
                            ) : (
                                <div className="text-center text-white/30 italic py-4">No data collected</div>
                            )}
                        </div>
                    </div>

                    {/* Submission Result */}
                    {submissionResult && (
                        <div className={`p-4 rounded-xl mb-6 border flex gap-3 text-sm ${submissionResult.captcha_detected
                            ? 'bg-yellow-500/10 border-yellow-500/20 text-yellow-200'
                            : submissionResult.success || (submissionResult.message && !submissionResult.error)
                                ? 'bg-green-500/10 border-green-500/20 text-green-200'
                                : 'bg-red-500/10 border-red-500/20 text-red-200'
                            }`}>
                            {submissionResult.captcha_detected ? <AlertTriangle size={18} className="text-yellow-400" /> :
                                submissionResult.success ? <CheckCircle size={18} /> : <AlertTriangle size={18} />}
                            <div>
                                <strong>
                                    {submissionResult.captcha_detected ? 'Action Required' :
                                        submissionResult.success ? 'Success' : 'Submission Alert'}:
                                </strong>
                                <span className="ml-1">{submissionResult.message}</span>

                                {submissionResult.captcha_detected && (
                                    <div className="mt-2 text-xs bg-yellow-500/20 p-2 rounded border border-yellow-500/10">
                                        The browser window has been left open. Please solve the CAPTCHA manually and submit the form there.
                                    </div>
                                )}

                                {submissionResult.error && !submissionResult.captcha_detected && (
                                    <div className="mt-1 opacity-80 text-xs font-mono bg-black/20 p-2 rounded">
                                        {JSON.stringify(submissionResult.error)}
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Action Buttons */}
                    <div className="space-y-3">
                        {/* Primary Action Button */}
                        {!submissionResult && (
                            <button
                                onClick={pdfId ? downloadFormData : handleSubmitToWebsite}
                                disabled={isSubmitting || isDownloading}
                                className="w-full bg-green-500 hover:bg-green-400 text-black font-bold py-4 px-6 rounded-xl flex items-center justify-center space-x-2 transition-all shadow-[0_0_20px_rgba(34,197,94,0.3)] hover:shadow-[0_0_30px_rgba(34,197,94,0.5)] disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {pdfId ? (
                                    isDownloading ? (
                                        <>
                                            <Loader2 size={20} className="animate-spin text-black" />
                                            <span>Generating PDF...</span>
                                        </>
                                    ) : (
                                        <>
                                            <Download size={20} />
                                            <span>Download Filled PDF</span>
                                        </>
                                    )
                                ) : (
                                    isSubmitting ? (
                                        <>
                                            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-black"></div>
                                            <span>Submitting to Website...</span>
                                        </>
                                    ) : (
                                        <>
                                            <Send size={20} />
                                            <span>Submit to Original Website</span>
                                        </>
                                    )
                                )}
                            </button>
                        )}

                        <div className="flex gap-3">
                            <button
                                onClick={pdfId ? downloadAsJson : downloadFormData}
                                className="flex-1 bg-white/5 hover:bg-white/10 text-white border border-white/10 font-medium py-3 px-4 rounded-xl flex items-center justify-center space-x-2 transition-all"
                            >
                                <FileText size={18} />
                                <span>{pdfId ? 'Download JSON' : 'Download'}</span>
                            </button>

                            <button
                                onClick={copyToClipboard}
                                className="flex-1 bg-white/5 hover:bg-white/10 text-white border border-white/10 font-medium py-3 px-4 rounded-xl flex items-center justify-center space-x-2 transition-all"
                            >
                                <Copy size={18} />
                                <span>Copy</span>
                            </button>
                        </div>

                        <button
                            onClick={onReset}
                            className="w-full text-white/40 hover:text-white text-sm py-2 transition-colors flex items-center justify-center gap-2"
                        >
                            <RotateCcw size={14} />
                            Start New Form
                        </button>

                    </div>
                </div>
            </div>
        </div>
    );
};

export default FormCompletion;
