/**
 * FormFlow Plugin SDK Type Definitions
 */

export interface FormFlowConfig {
    /** Plugin API key */
    apiKey: string;
    /** Plugin ID */
    pluginId: string;
    /** Custom API base URL */
    apiBase?: string;
    /** Container selector or element */
    container?: string | HTMLElement;
    /** Widget title */
    title?: string;
    /** Widget subtitle */
    subtitle?: string;
    /** Voice recognition language (default: en-US) */
    language?: string;
    /** Called when session starts */
    onStart?: (session: SessionData) => void;
    /** Called when data collection completes */
    onComplete?: (result: CompletionResult) => void;
    /** Called on error */
    onError?: (error: Error) => void;
    /** Called on progress update */
    onProgress?: (progress: ProgressData) => void;
}

export interface SessionData {
    session_id: string;
    plugin_id: number;
    current_question?: string;
    fields?: FieldInfo[];
    progress?: number;
}

export interface FieldInfo {
    column_name: string;
    column_type: string;
    question_text: string;
    is_required: boolean;
    question_group?: string;
}

export interface CompletionResult {
    session_id: string;
    plugin_id: number;
    extracted_values: Record<string, any>;
    confidence_scores: Record<string, number>;
    inserted_rows: number;
    failed_rows: number;
    status: 'success' | 'partial' | 'failed';
    duration_ms: number;
}

export interface ProgressData {
    progress: number;
    completed_fields: string[];
    remaining_fields: string[];
    next_question?: string;
    extracted_values: Record<string, any>;
}

export interface FormFlowPluginController {
    /** Initialize the plugin */
    init(): Promise<FormFlowPluginController>;
    /** Destroy the plugin and cleanup */
    destroy(): void;
}

export interface FormFlowPluginAPI {
    /** SDK version */
    version: string;
    /** Current plugin instance */
    instance: FormFlowPluginController | null;
    /** Initialize the plugin with config */
    init(config: FormFlowConfig): Promise<FormFlowPluginController>;
    /** Destroy the current instance */
    destroy(): void;
    /** APIClient class for advanced usage */
    APIClient: new (config: FormFlowConfig) => APIClientInstance;
    /** Widget class for advanced usage */
    Widget: new (container: string | HTMLElement, options: FormFlowConfig) => WidgetInstance;
    /** VoiceRecognizer class for advanced usage */
    VoiceRecognizer: new (
        onResult: (transcript: string, isFinal: boolean) => void,
        onError: (error: Error) => void,
        options?: VoiceRecognizerOptions
    ) => VoiceRecognizerInstance;
}

export interface APIClientInstance {
    startSession(metadata?: Record<string, any>): Promise<SessionData>;
    submitInput(sessionId: string, input: string, requestId: string): Promise<ProgressData & { is_complete: boolean }>;
    completeSession(sessionId: string): Promise<CompletionResult>;
    getSession(sessionId: string): Promise<SessionData>;
}

export interface WidgetInstance {
    render(): WidgetInstance;
    setState(state: WidgetState): void;
    setQuestion(text: string): void;
    setTranscript(text: string, show?: boolean): void;
    setProgress(percent: number): void;
    showError(message: string): void;
    on(event: string, callback: (data?: any) => void): void;
    destroy(): void;
}

export type WidgetState = 'idle' | 'listening' | 'processing' | 'success' | 'error';

export interface VoiceRecognizerOptions {
    language?: string;
    continuous?: boolean;
    interimResults?: boolean;
}

export interface VoiceRecognizerInstance {
    isSupported(): boolean;
    isListening: boolean;
    start(): boolean;
    stop(): void;
}

declare global {
    interface Window {
        FormFlowPlugin: FormFlowPluginAPI;
    }
}

export default FormFlowPluginAPI;
