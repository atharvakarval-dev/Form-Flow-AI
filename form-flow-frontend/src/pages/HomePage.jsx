import React, { useState } from 'react';
import { VoiceFormFiller, FormCompletion } from '@/features/form-filler';
import { Hero, TransformationTimeline, EditorialTeam, FeaturesGrid } from '@/features/landing';
import { TerminalLoader } from '@/components/ui';
import { scrapeForm, uploadPdf } from '@/services/api';

/**
 * HomePage - Main landing page with form URL input and voice form filling flow
 * 
 * Supports:
 * - URL-based form scraping
 * - PDF form upload
 * - Word document upload (limited support)
 */
const HomePage = () => {
    const [url, setUrl] = useState('');
    const [scrapedUrl, setScrapedUrl] = useState('');
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [showVoiceForm, setShowVoiceForm] = useState(false);
    const [completedData, setCompletedData] = useState(null);
    const [showCompletion, setShowCompletion] = useState(false);
    const [pdfId, setPdfId] = useState(null); // For PDF form filling

    const handleSubmit = async (e, submittedUrl = null) => {
        if (e && e.preventDefault) e.preventDefault();
        setLoading(true);
        const urlToUse = submittedUrl || url;
        try {
            const response = await scrapeForm(urlToUse);
            setResult(response);
            setScrapedUrl(urlToUse);
            setPdfId(null); // Not a PDF
            setUrl('');
        } catch (error) {
            console.log("Error submitting URL:", error);
            alert("Failed to submit URL. Please try again.");
        } finally {
            setLoading(false);
        }
    };

    /**
     * Handle PDF or Word document upload
     * @param {File} file - The uploaded file
     */
    const handleFileUpload = async (file) => {
        setLoading(true);
        try {
            const fileName = file.name.toLowerCase();
            const isDocx = fileName.endsWith('.docx') || fileName.endsWith('.doc');

            // Route to appropriate endpoint based on file type
            let response;
            if (isDocx) {
                const { uploadDocx } = await import('@/services/api');
                response = await uploadDocx(file);
            } else {
                response = await uploadPdf(file);
            }

            if (!response.success) {
                throw new Error(response.message || 'Failed to parse document');
            }

            // Check if document has fillable fields
            if (!response.fields || response.fields.length === 0) {
                throw new Error(
                    isDocx
                        ? 'No fillable placeholders found in this Word document. Try using [brackets] or ____ underscores to mark fields.'
                        : 'This PDF has no fillable form fields. It appears to be a static document. ' +
                        'Form Flow AI works with interactive PDF forms that have text boxes, checkboxes, or dropdowns.'
                );
            }

            // Convert schema to form filler compatible format
            const fields = response.fields.map(field => ({
                name: field.name || field.id,
                id: field.id || field.name,
                type: field.type || 'text',
                label: field.display_name || field.label || field.name,
                required: field.constraints?.required || false,
                options: field.options || [],
                max_length: field.constraints?.max_length || field.text_capacity,
                purpose: field.purpose,
                page: field.page,
            }));

            // Set result in the same format as web form scraping
            setResult({
                form_schema: [{ fields: fields }],
                form_context: {
                    source: isDocx ? 'docx' : 'pdf',
                    fileName: response.file_name,
                    totalPages: response.total_pages,
                    totalFields: response.total_fields,
                    isScanned: response.is_scanned,
                },
            });

            // Store ID for later filling (pdf_id or docx_id)
            setPdfId(response.pdf_id || response.docx_id);
            setScrapedUrl(`${isDocx ? 'Word' : 'PDF'}: ${response.file_name}`);
            setUrl('');

        } catch (error) {
            console.log("Error uploading file:", error);
            alert(`Failed to process ${file.name}. ${error.message || 'Please try again.'}`);
        } finally {
            setLoading(false);
        }
    };

    const startVoiceFilling = () => {
        setShowVoiceForm(true);
    };

    React.useEffect(() => {
        if (result && !showVoiceForm && !showCompletion) {
            startVoiceFilling();
        }
    }, [result]);

    const handleVoiceComplete = (formData) => {
        setCompletedData(formData);
        setShowVoiceForm(false);
        setShowCompletion(true);
    };

    const handleReset = () => {
        setResult(null);
        setCompletedData(null);
        setShowCompletion(false);
        setShowVoiceForm(false);
        setUrl('');
        setScrapedUrl('');
        setPdfId(null);
    };

    if (showCompletion && completedData && result) {
        return (
            <FormCompletion
                formData={completedData}
                formSchema={result.form_schema}
                originalUrl={scrapedUrl}
                pdfId={pdfId}
                onReset={handleReset}
            />
        );
    }

    if (showVoiceForm && result) {
        return (
            <VoiceFormFiller
                formSchema={result.form_schema}
                formContext={result.form_context}
                pdfId={pdfId}
                initialFilledData={result.magic_fill_data}
                onComplete={handleVoiceComplete}
                onClose={() => setShowVoiceForm(false)}
            />
        );
    }

    return (
        <div>
            {loading && <TerminalLoader url={url || 'Processing document...'} />}

            {!result && !loading && (
                <>
                    <Hero
                        url={url}
                        setUrl={setUrl}
                        handleSubmit={handleSubmit}
                        handleFileUpload={handleFileUpload}
                        loading={loading}
                    />
                    <FeaturesGrid />
                    <TransformationTimeline />
                    <EditorialTeam />
                </>
            )}
        </div>
    );
};

export default HomePage;

