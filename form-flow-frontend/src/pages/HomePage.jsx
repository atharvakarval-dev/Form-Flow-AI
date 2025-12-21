import React, { useState } from 'react';
import { VoiceFormFiller, FormCompletion } from '@/features/form-filler';
import { Hero, TransformationTimeline, EditorialTeam, FeaturesGrid } from '@/features/landing';
import { TerminalLoader } from '@/components/ui';
import { scrapeForm } from '@/services/api';

/**
 * HomePage - Main landing page with form URL input and voice form filling flow
 */
const HomePage = () => {
    const [url, setUrl] = useState('');
    const [scrapedUrl, setScrapedUrl] = useState('');
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [showVoiceForm, setShowVoiceForm] = useState(false);
    const [completedData, setCompletedData] = useState(null);
    const [showCompletion, setShowCompletion] = useState(false);

    const handleSubmit = async (e, submittedUrl = null) => {
        if (e && e.preventDefault) e.preventDefault();
        setLoading(true);
        const urlToUse = submittedUrl || url;
        try {
            const response = await scrapeForm(urlToUse);
            setResult(response);
            setScrapedUrl(urlToUse);
            setUrl('');
        } catch (error) {
            console.log("Error submitting URL:", error);
            alert("Failed to submit URL. Please try again.");
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
    };

    if (showCompletion && completedData && result) {
        return (
            <FormCompletion
                formData={completedData}
                formSchema={result.form_schema}
                originalUrl={scrapedUrl}
                onReset={handleReset}
            />
        );
    }

    if (showVoiceForm && result) {
        return (
            <VoiceFormFiller
                formSchema={result.form_schema}
                formContext={result.form_context}
                onComplete={handleVoiceComplete}
            />
        );
    }

    return (
        <div>
            {loading && <TerminalLoader url={url} />}

            {!result && !loading && (
                <>
                    <Hero url={url} setUrl={setUrl} handleSubmit={handleSubmit} loading={loading} />
                    <FeaturesGrid />
                    <TransformationTimeline />
                    <EditorialTeam />
                </>
            )}
        </div>
    );
};

export default HomePage;
