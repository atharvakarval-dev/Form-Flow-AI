/**
 * Action Dispatcher - WhisperFlow Action Layer
 * 
 * Maps detected actions from Flow Engine to frontend functions.
 * Extensible pattern for adding new integrations (Jira, Calendar, Slack, Email).
 * 
 * Usage:
 *   import { useActionDispatcher } from './useActionDispatcher';
 *   const { dispatch, registerHandler } = useActionDispatcher();
 *   dispatch(action); // Called automatically by useVoiceFlow
 */

import { useState, useCallback, useMemo } from 'react';

// =============================================================================
// DEFAULT ACTION HANDLERS
// =============================================================================

/**
 * Default handlers for each tool type.
 * These can be overridden by registering custom handlers.
 */
const defaultHandlers = {
    /**
     * Calendar action handler
     * @param {Object} action - { tool: 'calendar', action_type: 'create_event', payload: {...} }
     */
    calendar: (action, context) => {
        console.log('[ActionDispatcher] Calendar action:', action);

        // Default: Open calendar modal or navigate to calendar page
        const payload = action.payload || {};
        const eventData = {
            title: payload.title || payload.raw_text || 'New Event',
            time: payload.time,
            date: payload.date,
            description: payload.description
        };

        // Dispatch custom event for app to handle
        window.dispatchEvent(new CustomEvent('flowAction:calendar', {
            detail: { action: action.action_type, data: eventData }
        }));

        return { handled: true, result: eventData };
    },

    /**
     * Jira action handler
     */
    jira: (action, context) => {
        console.log('[ActionDispatcher] Jira action:', action);

        const payload = action.payload || {};
        const issueData = {
            title: payload.title || payload.raw_text || 'New Issue',
            type: payload.type || 'task',
            priority: payload.priority || 'medium',
            description: payload.description
        };

        window.dispatchEvent(new CustomEvent('flowAction:jira', {
            detail: { action: action.action_type, data: issueData }
        }));

        return { handled: true, result: issueData };
    },

    /**
     * Slack action handler
     */
    slack: (action, context) => {
        console.log('[ActionDispatcher] Slack action:', action);

        const payload = action.payload || {};
        const messageData = {
            channel: payload.channel,
            recipient: payload.recipient,
            message: payload.message || payload.raw_text
        };

        window.dispatchEvent(new CustomEvent('flowAction:slack', {
            detail: { action: action.action_type, data: messageData }
        }));

        return { handled: true, result: messageData };
    },

    /**
     * Email action handler
     */
    email: (action, context) => {
        console.log('[ActionDispatcher] Email action:', action);

        const payload = action.payload || {};
        const emailData = {
            to: payload.to || payload.recipient,
            subject: payload.subject,
            body: payload.body || payload.raw_text
        };

        window.dispatchEvent(new CustomEvent('flowAction:email', {
            detail: { action: action.action_type, data: emailData }
        }));

        return { handled: true, result: emailData };
    }
};

// =============================================================================
// ACTION DISPATCHER HOOK
// =============================================================================

/**
 * Hook for dispatching Flow Engine actions to appropriate handlers
 * 
 * @param {Object} options - Configuration options
 * @param {Function} options.onCalendarAction - Custom calendar handler
 * @param {Function} options.onJiraAction - Custom Jira handler
 * @param {Function} options.onSlackAction - Custom Slack handler
 * @param {Function} options.onEmailAction - Custom email handler
 * @param {Function} options.onUnknownAction - Handler for unknown actions
 */
export const useActionDispatcher = ({
    onCalendarAction = null,
    onJiraAction = null,
    onSlackAction = null,
    onEmailAction = null,
    onUnknownAction = null
} = {}) => {

    // Custom handlers registry
    const [customHandlers, setCustomHandlers] = useState({});

    // Merge default handlers with custom ones from props and registry
    const handlers = useMemo(() => ({
        calendar: onCalendarAction || customHandlers.calendar || defaultHandlers.calendar,
        jira: onJiraAction || customHandlers.jira || defaultHandlers.jira,
        slack: onSlackAction || customHandlers.slack || defaultHandlers.slack,
        email: onEmailAction || customHandlers.email || defaultHandlers.email,
        ...customHandlers
    }), [onCalendarAction, onJiraAction, onSlackAction, onEmailAction, customHandlers]);

    /**
     * Register a custom handler for a tool
     * @param {string} tool - Tool name (e.g., 'notion', 'github')
     * @param {Function} handler - Handler function (action, context) => result
     */
    const registerHandler = useCallback((tool, handler) => {
        setCustomHandlers(prev => ({
            ...prev,
            [tool.toLowerCase()]: handler
        }));
    }, []);

    /**
     * Unregister a custom handler
     * @param {string} tool - Tool name
     */
    const unregisterHandler = useCallback((tool) => {
        setCustomHandlers(prev => {
            const next = { ...prev };
            delete next[tool.toLowerCase()];
            return next;
        });
    }, []);

    /**
     * Dispatch a single action
     * @param {Object} action - Action from Flow Engine
     * @param {Object} context - Additional context
     * @returns {Object} - { handled: boolean, result: any }
     */
    const dispatchAction = useCallback((action, context = {}) => {
        const tool = action.tool?.toLowerCase();

        if (!tool) {
            console.warn('[ActionDispatcher] Action missing tool:', action);
            return { handled: false };
        }

        const handler = handlers[tool];

        if (handler) {
            try {
                return handler(action, context);
            } catch (error) {
                console.error(`[ActionDispatcher] Handler error for ${tool}:`, error);
                return { handled: false, error: error.message };
            }
        } else if (onUnknownAction) {
            return onUnknownAction(action, context);
        } else {
            console.warn(`[ActionDispatcher] No handler for tool: ${tool}`);
            return { handled: false };
        }
    }, [handlers, onUnknownAction]);

    /**
     * Dispatch multiple actions from Flow Engine result
     * @param {Object[]} actions - Array of actions
     * @param {Object} context - Additional context
     * @returns {Object[]} - Array of results
     */
    const dispatchAll = useCallback((actions, context = {}) => {
        if (!Array.isArray(actions) || actions.length === 0) {
            return [];
        }

        return actions.map(action => dispatchAction(action, context));
    }, [dispatchAction]);

    return {
        dispatch: dispatchAction,
        dispatchAll,
        registerHandler,
        unregisterHandler,
        handlers
    };
};

// =============================================================================
// STANDALONE DISPATCHER (for non-hook usage)
// =============================================================================

/**
 * Dispatch an action without using the hook
 * Uses default handlers only
 */
export const dispatchFlowAction = (action, context = {}) => {
    const tool = action.tool?.toLowerCase();
    const handler = defaultHandlers[tool];

    if (handler) {
        return handler(action, context);
    }

    console.warn(`[dispatchFlowAction] No handler for tool: ${tool}`);
    return { handled: false };
};

export default useActionDispatcher;
