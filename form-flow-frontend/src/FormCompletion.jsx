import React, { useState } from 'react';
import { CheckCircle, Send, AlertTriangle, ExternalLink, Download, FileText, Copy, RotateCcw } from 'lucide-react';
import axios from 'axios';
import { motion } from 'framer-motion';

const FormCompletion = ({ formData, formSchema, originalUrl, onReset }) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submissionResult, setSubmissionResult] = useState(null);

  const handleSubmitToWebsite = async () => {
    setIsSubmitting(true);
    try {
      const response = await axios.post('http://localhost:8000/submit-form', {
        url: originalUrl,
        form_data: formData,
        form_schema: formSchema
      });

      setSubmissionResult(response.data);
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

  const downloadFormData = () => {
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
        /* Hide scrollbar for Chrome, Safari and Opera */
        .no-scrollbar::-webkit-scrollbar {
          display: none !important;
          width: 0px !important;
          background: transparent !important;
        }
        .no-scrollbar {
          -ms-overflow-style: none !important;  /* IE and Edge */
          scrollbar-width: none !important;  /* Firefox */
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
            <p className="text-white/60">
              All required information has been collected successfully.
            </p>
          </div>

          {/* Form Data Summary - Dark Glass Card */}
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

          {/* Submission Result - Alerts */}
          {submissionResult && (
            <div className={`p-4 rounded-xl mb-6 border flex gap-3 text-sm ${submissionResult.success || (submissionResult.message && !submissionResult.error)
              ? 'bg-green-500/10 border-green-500/20 text-green-200'
              : 'bg-red-500/10 border-red-500/20 text-red-200'
              }`}>
              {submissionResult.success ? <CheckCircle size={18} /> : <AlertTriangle size={18} />}
              <div>
                <strong>{submissionResult.success ? 'Success' : 'Submission Alert'}: </strong>
                {submissionResult.message}
                {submissionResult.error && (
                  <div className="mt-1 opacity-80 text-xs font-mono bg-black/20 p-2 rounded">
                    {JSON.stringify(submissionResult.error)}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="space-y-3">
            {!submissionResult && (
              <button
                onClick={handleSubmitToWebsite}
                disabled={isSubmitting}
                className="w-full bg-green-500 hover:bg-green-400 text-black font-bold py-4 px-6 rounded-xl flex items-center justify-center space-x-2 transition-all shadow-[0_0_20px_rgba(34,197,94,0.3)] hover:shadow-[0_0_30px_rgba(34,197,94,0.5)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-black"></div>
                    <span>Submitting to Website...</span>
                  </>
                ) : (
                  <>
                    <Send size={20} />
                    <span>Submit to Original Website</span>
                  </>
                )}
              </button>
            )}

            <div className="flex gap-3">
              <button
                onClick={downloadFormData}
                className="flex-1 bg-white/5 hover:bg-white/10 text-white border border-white/10 font-medium py-3 px-4 rounded-xl flex items-center justify-center space-x-2 transition-all"
              >
                <Download size={18} />
                <span>Download</span>
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