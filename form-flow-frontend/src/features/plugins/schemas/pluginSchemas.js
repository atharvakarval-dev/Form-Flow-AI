/**
 * Plugin Validation Schemas
 * Zod schemas for form validation with comprehensive error messages
 */
import { z } from 'zod';

// ============ Field & Table Schemas ============

/**
 * Valid column types matching backend ColumnTypeEnum
 */
export const columnTypes = ['text', 'integer', 'email', 'phone', 'date', 'boolean', 'decimal'];

/**
 * Plugin field schema - individual column definition
 */
export const pluginFieldSchema = z.object({
    column_name: z
        .string()
        .min(1, 'Column name is required')
        .max(63, 'Column name must be 63 characters or less')
        .regex(/^[a-z_][a-z0-9_]*$/, 'Use lowercase letters, numbers, and underscores only'),
    column_type: z.enum(columnTypes, {
        errorMap: () => ({ message: 'Select a valid column type' }),
    }),
    question_text: z
        .string()
        .min(5, 'Question must be at least 5 characters')
        .max(500, 'Question must be 500 characters or less'),
    is_required: z.boolean().default(false),
    validation_regex: z.string().optional(),
    default_value: z.string().optional(),
});

/**
 * Plugin table schema - table with fields
 */
export const pluginTableSchema = z.object({
    table_name: z
        .string()
        .min(1, 'Table name is required')
        .max(63, 'Table name must be 63 characters or less')
        .regex(/^[a-z_][a-z0-9_]*$/, 'Use lowercase letters, numbers, and underscores only'),
    fields: z
        .array(pluginFieldSchema)
        .min(1, 'Add at least one field'),
});

// ============ Connection Config Schemas ============

/**
 * Database connection configuration
 */
export const connectionConfigSchema = z.object({
    host: z
        .string()
        .min(1, 'Host is required')
        .max(255, 'Host must be 255 characters or less'),
    port: z
        .number({ invalid_type_error: 'Port must be a number' })
        .int('Port must be an integer')
        .min(1, 'Port must be at least 1')
        .max(65535, 'Port must be 65535 or less'),
    database: z
        .string()
        .min(1, 'Database name is required')
        .max(63, 'Database name must be 63 characters or less'),
    username: z
        .string()
        .min(1, 'Username is required'),
    password: z
        .string()
        .min(1, 'Password is required'),
    ssl_mode: z.enum(['disable', 'require', 'verify-ca', 'verify-full']).optional(),
    ssl_cert: z.string().optional(),
});

// ============ Plugin Schemas ============

/**
 * Step 1: Basic Info
 */
export const pluginBasicInfoSchema = z.object({
    name: z
        .string()
        .min(3, 'Name must be at least 3 characters')
        .max(100, 'Name must be 100 characters or less'),
    description: z
        .string()
        .max(1000, 'Description must be 1000 characters or less')
        .optional(),
    database_type: z.enum(['postgresql', 'mysql'], {
        errorMap: () => ({ message: 'Select a database type' }),
    }),
});

/**
 * Step 2: Connection Config
 */
export const pluginConnectionSchema = connectionConfigSchema;

/**
 * Step 3: Tables & Fields
 */
export const pluginTablesSchema = z.object({
    tables: z
        .array(pluginTableSchema)
        .min(1, 'Add at least one table'),
});

/**
 * Full plugin create schema (all steps combined)
 */
export const pluginCreateSchema = pluginBasicInfoSchema
    .merge(z.object({ connection_config: connectionConfigSchema }))
    .merge(pluginTablesSchema);

/**
 * Plugin update schema (partial)
 */
export const pluginUpdateSchema = z.object({
    name: z.string().min(3).max(100).optional(),
    description: z.string().max(1000).optional(),
    is_active: z.boolean().optional(),
    tables: z.array(pluginTableSchema).optional(),
    webhook_url: z.string().url('Must be a valid URL').optional().or(z.literal('')),
});

// ============ API Key Schemas ============

/**
 * API key creation schema
 */
export const apiKeyCreateSchema = z.object({
    name: z
        .string()
        .min(1, 'Name is required')
        .max(100, 'Name must be 100 characters or less'),
    expires_at: z
        .string()
        .datetime()
        .optional()
        .or(z.literal('')),
});

// ============ Helper Functions ============

/**
 * Validate data against a schema with formatted errors
 * @param {z.ZodSchema} schema
 * @param {Object} data
 * @returns {{ success: boolean, data?: Object, errors?: Record<string, string> }}
 */
export const validateWithSchema = (schema, data) => {
    const result = schema.safeParse(data);
    if (result.success) {
        return { success: true, data: result.data };
    }

    // Format errors as { fieldName: 'error message' }
    const errors = {};
    result.error.issues.forEach((issue) => {
        const path = issue.path.join('.');
        if (!errors[path]) {
            errors[path] = issue.message;
        }
    });

    return { success: false, errors };
};

/**
 * Get default values for a new plugin
 */
export const getPluginDefaults = () => ({
    name: '',
    description: '',
    database_type: 'postgresql',
    connection_config: {
        host: 'localhost',
        port: 5432,
        database: '',
        username: '',
        password: '',
        ssl_mode: 'disable',
    },
    tables: [],
});

/**
 * Get default values for a new table
 */
export const getTableDefaults = () => ({
    table_name: '',
    fields: [getFieldDefaults()],
});

/**
 * Get default values for a new field
 */
export const getFieldDefaults = () => ({
    column_name: '',
    column_type: 'text',
    question_text: '',
    is_required: false,
});

export default {
    pluginFieldSchema,
    pluginTableSchema,
    connectionConfigSchema,
    pluginBasicInfoSchema,
    pluginConnectionSchema,
    pluginTablesSchema,
    pluginCreateSchema,
    pluginUpdateSchema,
    apiKeyCreateSchema,
    validateWithSchema,
    getPluginDefaults,
    getTableDefaults,
    getFieldDefaults,
    columnTypes,
};
