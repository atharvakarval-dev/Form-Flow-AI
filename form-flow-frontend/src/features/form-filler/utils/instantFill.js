/**
 * Instant Fill Utility
 * 
 * Provides immediate, rule-based field filling without waiting for AI.
 * Maps user profile data to form fields using intelligent name matching.
 */

// Field name patterns for common profile fields
const FIELD_PATTERNS = {
    first_name: [
        'first_name', 'firstname', 'fname', 'given_name', 'givenname',
        'first name', 'forename', 'name_first'
    ],
    last_name: [
        'last_name', 'lastname', 'lname', 'surname', 'family_name',
        'familyname', 'last name', 'name_last'
    ],
    full_name: [
        'full_name', 'fullname', 'name', 'your_name', 'yourname',
        'applicant_name', 'applicantname', 'complete_name'
    ],
    email: [
        'email', 'e-mail', 'mail', 'emailaddress', 'email_address',
        'e_mail', 'emailid', 'email_id', 'user_email'
    ],
    phone: [
        'phone', 'mobile', 'cell', 'telephone', 'tel', 'phonenumber',
        'phone_number', 'mobile_number', 'contact_number', 'cellphone',
        'mobilenumber', 'contact'
    ],
    city: [
        'city', 'town', 'municipality', 'locality', 'city_name'
    ],
    state: [
        'state', 'province', 'region', 'state_province', 'stateprovince'
    ],
    country: [
        'country', 'nation', 'country_name'
    ],
    zip: [
        'zip', 'zipcode', 'zip_code', 'postal', 'postalcode', 'postal_code',
        'pincode', 'pin_code', 'pin'
    ],
    address: [
        'address', 'street', 'street_address', 'address_line', 'addressline',
        'address1', 'address_1', 'location'
    ]
};

/**
 * Normalize a field name for matching
 * @param {string} name - Field name or label
 * @returns {string} Normalized name
 */
function normalizeFieldName(name) {
    if (!name) return '';
    return name
        .toLowerCase()
        .replace(/[^a-z0-9]/g, '_')  // Replace special chars with underscore
        .replace(/_+/g, '_')          // Collapse multiple underscores
        .replace(/^_|_$/g, '');       // Trim leading/trailing underscores
}

/**
 * Find the best match for a field against known patterns
 * @param {string} fieldName - The field's name attribute
 * @param {string} fieldLabel - The field's label (optional)
 * @returns {string|null} The profile key that matches, or null
 */
function findProfileKey(fieldName, fieldLabel = '') {
    const normalizedName = normalizeFieldName(fieldName);
    const normalizedLabel = normalizeFieldName(fieldLabel);

    for (const [profileKey, patterns] of Object.entries(FIELD_PATTERNS)) {
        for (const pattern of patterns) {
            const normalizedPattern = normalizeFieldName(pattern);

            // Exact match on name
            if (normalizedName === normalizedPattern) {
                return profileKey;
            }

            // Exact match on label
            if (normalizedLabel === normalizedPattern) {
                return profileKey;
            }

            // Contains match (for compound fields like "applicant_first_name")
            if (normalizedName.includes(normalizedPattern) || normalizedPattern.includes(normalizedName)) {
                return profileKey;
            }
        }
    }

    return null;
}

/**
 * Instantly fill form fields from user profile using rule-based matching
 * 
 * @param {Array} fields - Array of form fields with {name, label, type}
 * @param {Object} userProfile - User profile data
 * @returns {Object} { filled: {fieldName: value}, matched: count }
 */
export function instantFillFromProfile(fields, userProfile) {
    if (!fields?.length || !userProfile) {
        return { filled: {}, matched: 0 };
    }

    const filled = {};
    let matched = 0;

    // Build a profile lookup with computed values
    const profileData = {
        first_name: userProfile.first_name || userProfile.firstName || '',
        last_name: userProfile.last_name || userProfile.lastName || '',
        full_name: userProfile.fullname || userProfile.full_name ||
            `${userProfile.first_name || ''} ${userProfile.last_name || ''}`.trim(),
        email: userProfile.email || '',
        phone: userProfile.mobile || userProfile.phone || userProfile.contact || '',
        city: userProfile.city || '',
        state: userProfile.state || '',
        country: userProfile.country || '',
        zip: userProfile.zip || userProfile.zipcode || userProfile.pincode || '',
        address: userProfile.address || userProfile.street || ''
    };

    for (const field of fields) {
        if (!field.name) continue;

        // Skip certain field types
        if (['submit', 'button', 'hidden', 'file', 'image'].includes(field.type)) {
            continue;
        }

        const profileKey = findProfileKey(field.name, field.label);

        if (profileKey && profileData[profileKey]) {
            filled[field.name] = profileData[profileKey];
            matched++;
        }
    }

    console.log(`⚡ Instant Fill: Matched ${matched} fields`, filled);

    return { filled, matched };
}

/**
 * Extract all fillable fields from form schema
 * @param {Array} formSchema - Form schema array
 * @returns {Array} Flattened array of field objects
 */
export function extractFillableFields(formSchema) {
    const fields = [];

    for (const form of formSchema || []) {
        for (const field of form.fields || []) {
            if (!field.hidden && !['submit', 'button'].includes(field.type)) {
                fields.push({
                    name: field.name,
                    label: field.label || '',
                    type: field.type || 'text'
                });
            }
        }
    }

    return fields;
}

export default {
    instantFillFromProfile,
    extractFillableFields
};
