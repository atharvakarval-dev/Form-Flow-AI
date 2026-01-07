"""
Intelligent Fallback Extractor

Rule-based extraction when LLM is unavailable or fails.
Uses NLP-inspired techniques for field extraction.
"""

import re
from typing import Dict, List, Any, Tuple, Optional

from services.ai.normalizers import (
    normalize_email_smart,
    normalize_phone_smart, 
    normalize_name_smart,
    normalize_text_smart,
    normalize_number_smart,
)


class IntelligentFallbackExtractor:
    """
    Fallback extractor that uses NLP-inspired techniques without hardcoded patterns.
    Works by understanding sentence structure and field types dynamically.
    """
    
    @staticmethod
    def extract_with_intelligence(
        user_input: str,
        current_batch: List[Dict[str, Any]],
        remaining_fields: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, str], Dict[str, float]]:
        """
        Intelligent extraction using sentence segmentation and field type matching.
        
        Strategy:
        1. Split input into segments (by "and", "also", commas, etc.)
        2. For each segment, identify what field it's describing
        3. Extract the value portion from that segment
        4. Validate against field type expectations
        """
        
        extracted = {}
        confidence = {}
        
        # Step 1: Segment the input
        segments = IntelligentFallbackExtractor._segment_input(user_input)
        
        # Step 2: Create field matchers for ALL fields (current + remaining)
        # This allows users to Provide "Country" even if we asked for "City"
        # We prioritize current_batch in matching implicitly by ordering or logic if needed,
        # but for now, just matching everything is safer for "smart" feel.
        all_candidate_fields = current_batch + [f for f in remaining_fields if f not in current_batch]
        field_matchers = IntelligentFallbackExtractor._create_field_matchers(all_candidate_fields)
        
        # Step 3: Match segments to fields
        for segment in segments:
            segment_lower = segment.lower().strip()
            
            for field_info in field_matchers:
                if field_info['name'] in extracted:
                    continue  # Already extracted
                
                # Check if segment mentions this field OR if it's implicitly the current topic
                is_mentioned = IntelligentFallbackExtractor._segment_mentions_field(segment_lower, field_info)
                is_current = field_info['name'] in [f.get('name') for f in current_batch]
                
                if is_mentioned or is_current:
                    # Extract value from segment
                    value, conf = IntelligentFallbackExtractor._extract_value_from_segment(
                        segment, 
                        field_info
                    )
                    
                    if value:
                        extracted[field_info['name']] = value
                        confidence[field_info['name']] = conf
        
        return extracted, confidence
    
    @staticmethod
    def _segment_input(text: str) -> List[str]:
        """
        Split input into logical segments.
        Splits on: "and", "also", "plus", commas (smart comma detection)
        """
        # Replace common separators with a delimiter
        text = re.sub(r'\s+and\s+', ' |AND| ', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+also\s+', ' |AND| ', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+plus\s+', ' |AND| ', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+then\s+', ' |AND| ', text, flags=re.IGNORECASE)
        # Split on "in my X" or "for my X" to separate independent clauses
        text = re.sub(r'\s+in\s+my\s+', ' |AND| my ', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+for\s+my\s+', ' |AND| my ', text, flags=re.IGNORECASE)
        
        # Smart comma handling (don't split within email addresses or names)
        text = re.sub(r',\s+(?=(?:my|the|and)\s)', ' |AND| ', text, flags=re.IGNORECASE)
        
        # Split and clean
        segments = [s.strip() for s in text.split('|AND|') if s.strip()]
        
        return segments
    
    @staticmethod
    def _create_field_matchers(fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create matcher objects for each field with metadata."""
        matchers = []
        
        for field in fields:
            field_name = field.get('name') or ''
            field_label = field.get('label') or field_name or ''
            field_type = field.get('type') or 'text'
            
            # Extract keywords from label/name
            keywords = set()
            for word in (field_name + ' ' + field_label).lower().split():
                if len(word) > 2:  # Skip short words
                    keywords.add(word)
            
            matchers.append({
                'name': field_name,
                'label': field_label,
                'type': field_type,
                'keywords': keywords,
                'extractor': IntelligentFallbackExtractor._get_extractor_for_type(field_type, field_name, field_label)
            })
        
        return matchers
    
    @staticmethod
    def _get_extractor_for_type(field_type: str, field_name: str, field_label: str) -> Dict[str, Any]:
        """Get appropriate extractor configuration for field type."""
        field_type = field_type.lower()
        field_name_lower = field_name.lower()
        field_label_lower = field_label.lower()
        
        # Email detector
        if field_type == 'email' or 'email' in field_name_lower or 'email' in field_label_lower:
            return {
                'type': 'email',
                'pattern': r'[\w\.-]+@[\w\.-]+\.\w+',
                'normalizer': normalize_email_smart
            }
        
        # Phone detector
        if field_type == 'tel' or any(k in field_name_lower for k in ['phone', 'mobile', 'tel']):
            return {
                'type': 'phone',
                'pattern': r'[\d\s\-\+\(\)]{10,}',
                'normalizer': normalize_phone_smart
            }
        
        # Name detector
        if 'name' in field_name_lower or 'name' in field_label_lower:
            return {
                'type': 'name',
                'pattern': r'\b[A-Z][a-z]+(?:\s+[A-Z]?[a-z]+){0,3}\b',
                'normalizer': normalize_name_smart
            }
        
        # Number detector
        if field_type == 'number':
            return {
                'type': 'number',
                'pattern': r'\d+(?:\.\d+)?',
                'normalizer': normalize_number_smart
            }
        
        # Generic text - use smart text normalizer
        return {
            'type': 'text',
            'pattern': None,
            'normalizer': normalize_text_smart
        }
    
    @staticmethod
    def _segment_mentions_field(segment: str, field_info: Dict[str, Any]) -> bool:
        """Check if segment is talking about this field."""
        # Check if any field keyword appears in segment
        for keyword in field_info['keywords']:
            if keyword in segment:
                return True
        
        # Special patterns like "my X is", "the X is"
        label_pattern = rf'(?:my|the)\s+{re.escape(field_info["label"][:20])}'
        if re.search(label_pattern, segment, re.IGNORECASE):
            return True
        
        return False
    
    @staticmethod
    def _extract_value_from_segment(
        segment: str, 
        field_info: Dict[str, Any]
    ) -> Tuple[Optional[str], float]:
        """
        Extract actual value from a segment that mentions a field.
        Uses field-specific extractors and validates the result.
        """
        extractor = field_info['extractor']
        
        # 1. Try to extract using contextual patterns ("my X is Y")
        value_patterns = [
            rf'(?:my\s+)?{re.escape(field_info["label"][:20])}\s+(?:is|:)\s+(.+?)(?:\s+(?:and|my|the|also)|\s*$)',
            rf'{re.escape(field_info["label"][:20])}\s*[:=]\s*(.+?)(?:\s+(?:and|my|the)|\s*$)',
            rf'(?:my\s+)?{re.escape(field_info["name"][:20])}\s+(?:is|:)\s+(.+?)(?:\s+(?:and|my|the|also)|\s*$)',
        ]
        
        for pattern in value_patterns:
            match = re.search(pattern, segment, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                value = extractor['normalizer'](value)
                
                is_valid, confidence = IntelligentFallbackExtractor._validate_extraction(
                    value,
                    extractor['type']
                )
                
                if is_valid:
                    return value, confidence * 0.95
        
        if extractor['type'] == 'text':
            # Create regex to find field name at start of segment + optional connectors
            # e.g. ^(my|the)?\s*message(s)?\s*(is|that|about|:|was)\s*
            # Allow optional 's' for plural labels (message -> messages)
            label_part = re.escape(field_info["label"][:20])
            prefix_pattern = rf'^(?:my|the)?\s*{label_part}s?\s*(?:is|that|about|:|was)\s*'
            
            match = re.search(prefix_pattern, segment, re.IGNORECASE)
            if match:
                # E.g. "my message that I was testing..." -> "I was testing..."
                raw_value = segment[match.end():].strip()
                if raw_value:
                    normalized_val = extractor['normalizer'](raw_value)
                    is_valid, confidence = IntelligentFallbackExtractor._validate_extraction(normalized_val, 'text')
                    if is_valid:
                        return normalized_val, confidence * 0.90
        
        # 2. Apply normalizer to whole segment
        normalized_segment = extractor['normalizer'](segment)
        
        # 3. Extract using generic pattern if available
        if extractor['pattern']:
            match = re.search(extractor['pattern'], normalized_segment)
            if match:
                value = match.group().strip()
                
                # For names, avoid "My Name Is" being captured
                if extractor['type'] == 'name':
                    if value.lower().startswith('my name') or value.lower().startswith('my email'):
                        return None, 0.0

                is_valid, confidence = IntelligentFallbackExtractor._validate_extraction(
                    value, 
                    extractor['type']
                )
                
                if is_valid:
                    return value, confidence
        
        # 4. For raw text fields (like Message/Comments), if no specific pattern matched, 
        # just take the whole (normalized) segment!
        # This handles cases where user just speaks the message without preamble or with complex preamble we missed.
        if extractor['type'] == 'text' and normalized_segment:
             is_valid, confidence = IntelligentFallbackExtractor._validate_extraction(normalized_segment, 'text')
             if is_valid:
                 # Lower confidence since it's a catch-all
                 return normalized_segment, 0.70
        
        return None, 0.0
    
    @staticmethod
    def _validate_extraction(value: str, field_type: str) -> Tuple[bool, float]:
        """Validate extracted value against field type expectations."""
        if not value or len(value) < 2:
            return False, 0.0
        
        if field_type == 'email':
            if '@' in value and '.' in value.split('@')[1]:
                return True, 0.95
            return False, 0.0
        
        elif field_type == 'phone':
            digits = re.sub(r'[^\d]', '', value)
            if 10 <= len(digits) <= 15:
                return True, 0.92
            return False, 0.0
        
        elif field_type == 'name':
            # Common greetings and non-name words to filter out
            EXCLUDED_WORDS = {
                # Greetings
                'hello', 'hi', 'hey', 'howdy', 'greetings', 'good', 'morning', 
                'afternoon', 'evening', 'night', 'welcome',
                # Common conversational words
                'thanks', 'thank', 'please', 'sorry', 'yes', 'no', 'okay', 'ok',
                'sure', 'bye', 'goodbye', 'well', 'great', 'nice', 'cool',
                # Question words  
                'what', 'how', 'who', 'when', 'where', 'why', 'which',
                # Articles/pronouns
                'the', 'this', 'that', 'you', 'your', 'they', 'their',
            }
            
            words = value.split()
            
            # Check if value is just a common word (not a name)
            if len(words) == 1 and words[0].lower() in EXCLUDED_WORDS:
                return False, 0.0
            
            # Filter out excluded words from multi-word names
            filtered_words = [w for w in words if w.lower() not in EXCLUDED_WORDS]
            if not filtered_words:
                return False, 0.0
            
            if 2 <= len(filtered_words) <= 4 and all(w.isalpha() for w in filtered_words):
                return True, 0.88
            elif len(filtered_words) >= 1 and all(w.isalpha() for w in filtered_words):
                # Allow single names but with lower confidence
                return True, 0.60
            return False, 0.0
        
        elif field_type == 'number':
            try:
                float(value)
                return True, 0.95
            except ValueError:
                return False, 0.0
        
        else:  # text
            if 2 <= len(value) <= 500:
                return True, 0.80
            return False, 0.0
