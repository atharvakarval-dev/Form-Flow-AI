/**
 * Plugin Form Context
 * Multi-step form state management for plugin creation wizard
 */
import { createContext, useContext, useReducer, useCallback, useMemo } from 'react';
import { getPluginDefaults, getTableDefaults, getFieldDefaults } from '../schemas/pluginSchemas';

// ============ Actions ============
const ACTIONS = {
    SET_STEP: 'SET_STEP',
    UPDATE_BASIC_INFO: 'UPDATE_BASIC_INFO',
    UPDATE_CONNECTION: 'UPDATE_CONNECTION',
    ADD_TABLE: 'ADD_TABLE',
    UPDATE_TABLE: 'UPDATE_TABLE',
    REMOVE_TABLE: 'REMOVE_TABLE',
    ADD_FIELD: 'ADD_FIELD',
    UPDATE_FIELD: 'UPDATE_FIELD',
    REMOVE_FIELD: 'REMOVE_FIELD',
    SET_ERRORS: 'SET_ERRORS',
    CLEAR_ERRORS: 'CLEAR_ERRORS',
    RESET: 'RESET',
    LOAD_TEMPLATE: 'LOAD_TEMPLATE',
};

// ============ Reducer ============
const initialState = {
    step: 1,
    maxStep: 4, // Basic Info → Connection → Tables → Review
    ...getPluginDefaults(),
    errors: {},
    isSubmitting: false,
};

function pluginFormReducer(state, action) {
    switch (action.type) {
        case ACTIONS.SET_STEP:
            return { ...state, step: Math.min(Math.max(1, action.payload), state.maxStep) };

        case ACTIONS.UPDATE_BASIC_INFO:
            return { ...state, ...action.payload, errors: {} };

        case ACTIONS.UPDATE_CONNECTION:
            return {
                ...state,
                connection_config: { ...state.connection_config, ...action.payload },
                errors: {},
            };

        case ACTIONS.ADD_TABLE:
            return {
                ...state,
                tables: [...state.tables, action.payload || getTableDefaults()],
                errors: {},
            };

        case ACTIONS.UPDATE_TABLE:
            return {
                ...state,
                tables: state.tables.map((table, idx) =>
                    idx === action.payload.index ? { ...table, ...action.payload.data } : table
                ),
                errors: {},
            };

        case ACTIONS.REMOVE_TABLE:
            return {
                ...state,
                tables: state.tables.filter((_, idx) => idx !== action.payload),
                errors: {},
            };

        case ACTIONS.ADD_FIELD:
            return {
                ...state,
                tables: state.tables.map((table, idx) =>
                    idx === action.payload.tableIndex
                        ? { ...table, fields: [...table.fields, getFieldDefaults()] }
                        : table
                ),
                errors: {},
            };

        case ACTIONS.UPDATE_FIELD:
            return {
                ...state,
                tables: state.tables.map((table, tableIdx) =>
                    tableIdx === action.payload.tableIndex
                        ? {
                            ...table,
                            fields: table.fields.map((field, fieldIdx) =>
                                fieldIdx === action.payload.fieldIndex
                                    ? { ...field, ...action.payload.data }
                                    : field
                            ),
                        }
                        : table
                ),
                errors: {},
            };

        case ACTIONS.REMOVE_FIELD:
            return {
                ...state,
                tables: state.tables.map((table, tableIdx) =>
                    tableIdx === action.payload.tableIndex
                        ? {
                            ...table,
                            fields: table.fields.filter((_, fieldIdx) => fieldIdx !== action.payload.fieldIndex),
                        }
                        : table
                ),
                errors: {},
            };

        case ACTIONS.SET_ERRORS:
            return { ...state, errors: action.payload };

        case ACTIONS.CLEAR_ERRORS:
            return { ...state, errors: {} };

        case ACTIONS.RESET:
            return { ...initialState };

        case ACTIONS.LOAD_TEMPLATE:
            return { ...state, ...action.payload, step: 3 }; // Skip to tables step

        default:
            return state;
    }
}

// ============ Context ============
const PluginFormContext = createContext(null);

/**
 * Plugin Form Provider
 * Wraps plugin creation wizard with shared state
 */
export function PluginFormProvider({ children }) {
    const [state, dispatch] = useReducer(pluginFormReducer, initialState);

    // Step navigation
    const nextStep = useCallback(() => {
        dispatch({ type: ACTIONS.SET_STEP, payload: state.step + 1 });
    }, [state.step]);

    const prevStep = useCallback(() => {
        dispatch({ type: ACTIONS.SET_STEP, payload: state.step - 1 });
    }, [state.step]);

    const goToStep = useCallback((step) => {
        dispatch({ type: ACTIONS.SET_STEP, payload: step });
    }, []);

    // Form updates
    const updateBasicInfo = useCallback((data) => {
        dispatch({ type: ACTIONS.UPDATE_BASIC_INFO, payload: data });
    }, []);

    const updateConnection = useCallback((data) => {
        dispatch({ type: ACTIONS.UPDATE_CONNECTION, payload: data });
    }, []);

    // Table management
    const addTable = useCallback((template) => {
        dispatch({ type: ACTIONS.ADD_TABLE, payload: template });
    }, []);

    const updateTable = useCallback((index, data) => {
        dispatch({ type: ACTIONS.UPDATE_TABLE, payload: { index, data } });
    }, []);

    const removeTable = useCallback((index) => {
        dispatch({ type: ACTIONS.REMOVE_TABLE, payload: index });
    }, []);

    // Field management
    const addField = useCallback((tableIndex) => {
        dispatch({ type: ACTIONS.ADD_FIELD, payload: { tableIndex } });
    }, []);

    const updateField = useCallback((tableIndex, fieldIndex, data) => {
        dispatch({ type: ACTIONS.UPDATE_FIELD, payload: { tableIndex, fieldIndex, data } });
    }, []);

    const removeField = useCallback((tableIndex, fieldIndex) => {
        dispatch({ type: ACTIONS.REMOVE_FIELD, payload: { tableIndex, fieldIndex } });
    }, []);

    // Errors
    const setErrors = useCallback((errors) => {
        dispatch({ type: ACTIONS.SET_ERRORS, payload: errors });
    }, []);

    const clearErrors = useCallback(() => {
        dispatch({ type: ACTIONS.CLEAR_ERRORS });
    }, []);

    // Reset
    const reset = useCallback(() => {
        dispatch({ type: ACTIONS.RESET });
    }, []);

    // Load template
    const loadTemplate = useCallback((template) => {
        dispatch({ type: ACTIONS.LOAD_TEMPLATE, payload: template });
    }, []);

    // Get form data for submission
    const getFormData = useCallback(() => ({
        name: state.name,
        description: state.description,
        database_type: state.database_type,
        connection_config: state.connection_config,
        tables: state.tables,
    }), [state]);

    // Check if step is valid
    const isStepValid = useCallback((step) => {
        switch (step) {
            case 1:
                return state.name.length >= 3 && state.database_type;
            case 2:
                return (
                    state.connection_config.host &&
                    state.connection_config.port &&
                    state.connection_config.database &&
                    state.connection_config.username &&
                    state.connection_config.password
                );
            case 3:
                return state.tables.length > 0 && state.tables.every(
                    (t) => t.table_name && t.fields.length > 0 && t.fields.every(
                        (f) => f.column_name && f.column_type && f.question_text
                    )
                );
            default:
                return true;
        }
    }, [state]);

    const value = useMemo(() => ({
        // State
        ...state,
        formData: getFormData(),

        // Navigation
        nextStep,
        prevStep,
        goToStep,
        canGoNext: isStepValid(state.step),
        canGoBack: state.step > 1,

        // Updates
        updateBasicInfo,
        updateConnection,
        addTable,
        updateTable,
        removeTable,
        addField,
        updateField,
        removeField,

        // Errors
        setErrors,
        clearErrors,

        // Actions
        reset,
        loadTemplate,
        getFormData,
        isStepValid,
    }), [
        state,
        nextStep,
        prevStep,
        goToStep,
        isStepValid,
        updateBasicInfo,
        updateConnection,
        addTable,
        updateTable,
        removeTable,
        addField,
        updateField,
        removeField,
        setErrors,
        clearErrors,
        reset,
        loadTemplate,
        getFormData,
    ]);

    return (
        <PluginFormContext.Provider value={value}>
            {children}
        </PluginFormContext.Provider>
    );
}

/**
 * Hook to access plugin form context
 */
export function usePluginForm() {
    const context = useContext(PluginFormContext);
    if (!context) {
        throw new Error('usePluginForm must be used within a PluginFormProvider');
    }
    return context;
}

export default PluginFormContext;
