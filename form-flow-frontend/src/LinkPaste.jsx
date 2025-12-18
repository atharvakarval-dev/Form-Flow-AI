import React, { useState } from 'react'
import axios from 'axios';
import VoiceFormFiller from './VoiceFormFiller';
import FormCompletion from './FormCompletion';
import { TransformationTimeline } from './TransformationTimeline';
import { Hero } from '@/components/ui/animated-hero';
import TerminalLoader from '@/components/ui/TerminalLoader';

const LinkPaste = () => {
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
            const response = await axios.post("http://localhost:8000/scrape", { url: urlToUse });
            setResult(response.data);
            setScrapedUrl(urlToUse);
            setUrl('');
        } catch (error) {
            console.log("Error submitting URL:", error);
            alert("Failed to submit URL. Please try again.");
        } finally {
            setLoading(false);
        }
    }

    const startVoiceFilling = () => {
        setShowVoiceForm(true);
    }

    React.useEffect(() => {
        if (result && !showVoiceForm && !showCompletion) {
            startVoiceFilling();
        }
    }, [result]);

    const handleVoiceComplete = (formData) => {
        setCompletedData(formData);
        setShowVoiceForm(false);
        setShowCompletion(true);
    }

    const handleReset = () => {
        setResult(null);
        setCompletedData(null);
        setShowCompletion(false);
        setShowVoiceForm(false);
        setUrl('');
        setScrapedUrl('');
    }

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
                    <TransformationTimeline />
                </>
            )}
        </div>
    )
}

export default LinkPaste;