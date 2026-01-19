"""
Smart Auto-Fill Service

Learns from user's previous form submissions to suggest values.
Provides intelligent suggestions with confidence scores.

Features:
- Learning from form history
- Confidence-based suggestions
- Privacy-aware (hashes sensitive data)
- Personalized per user
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import hashlib
import json
from collections import defaultdict

from utils.logging import get_logger
from utils.cache import get_cached, set_cached

# RAG service for semantic field matching
try:
    from services.ai.rag_service import get_rag_service
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

logger = get_logger(__name__)


class SmartAutofill:
    """
    Learns from user's previous forms to suggest values.
    Provides top suggestions with confidence scores.
    """
    
    # Fields that should be hashed for privacy
    SENSITIVE_FIELDS = {
        'ssn', 'social_security', 'tax_id',
        'credit_card', 'card_number', 'cvv', 'cvc',
        'password', 'pin', 'secret',
        'bank_account', 'routing_number'
    }
    
    # Field type mappings for suggestions
    FIELD_TYPE_MAP = {
        'email': '📧',
        'phone': '📱',
        'address': '🏠',
        'name': '👤',
        'date': '📅',
        'company': '🏢',
        'url': '🔗'
    }
    
    def __init__(self, max_history: int = 50, max_suggestions: int = 5):
        """
        Args:
            max_history: Maximum form submissions to analyze
            max_suggestions: Maximum suggestions to return
        """
        self.max_history = max_history
        self.max_suggestions = max_suggestions
    
    async def get_suggestions(
        self,
        user_id: str,
        field_name: str,
        field_type: str = "text",
        current_value: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Get smart suggestions for a field based on user history.
        
        Args:
            user_id: User identifier
            field_name: Name of the form field
            field_type: Type of field (email, phone, name, etc.)
            current_value: Current partial value (for filtering)
        
        Returns:
            List of suggestions with confidence scores
        """
        # Try to get from cache first
        cache_key = f"autofill:{user_id}:{field_name}"
        cached = await get_cached(cache_key)
        
        if cached:
            suggestions = json.loads(cached)
            # Filter by current value if provided
            if current_value:
                suggestions = [
                    s for s in suggestions
                    if s['value'].lower().startswith(current_value.lower())
                ]
            return suggestions[:self.max_suggestions]
        
        # Get user's form history from storage
        history = await self._get_user_history(user_id)
        
        if not history:
            return []
        
        # Analyze values for this field
        suggestions = self._analyze_field_values(
            history=history,
            field_name=field_name,
            field_type=field_type
        )
        
        # Cache for 1 hour
        await set_cached(cache_key, json.dumps(suggestions), expire=3600)
        
        # Filter by current value
        if current_value:
            suggestions = [
                s for s in suggestions
                if s['value'].lower().startswith(current_value.lower())
            ]
        
        # Enhance with RAG if history is insufficient
        if len(suggestions) < self.max_suggestions and RAG_AVAILABLE:
            try:
                rag = get_rag_service()
                rag_suggestions = rag.get_suggested_values(
                    user_id=user_id,
                    field_pattern=field_type,
                    n_results=self.max_suggestions - len(suggestions),
                    partial_value=current_value or None
                )
                # Add RAG suggestions that aren't already in the list
                existing_values = {s['value'].lower() for s in suggestions}
                for val in rag_suggestions:
                    if val.lower() not in existing_values:
                        suggestions.append({
                            'value': val,
                            'confidence': 0.7,
                            'source': 'rag',
                            'label': f'📚 {val}'  # Mark as RAG-sourced
                        })
                        existing_values.add(val.lower())
            except Exception as e:
                logger.debug(f"RAG suggestion enhancement skipped: {e}")
        
        return suggestions[:self.max_suggestions]

    async def get_profile_from_history(self, user_id: str) -> Dict[str, Any]:
        """
        Build a comprehensive user profile from their form submission history.
        Returns a dictionary of {field_name: value} for the most likely values.
        """
        history = await self._get_user_history(user_id)
        if not history:
            return {}

        # 1. Identify all unique, non-sensitive fields in history
        unique_fields = set()
        for entry in history:
            for name, data in entry.get('fields', {}).items():
                if data.get('type') == 'normal':
                    unique_fields.add(name)
        
        # 2. Get best value for each field
        profile = {}
        for field_name in unique_fields:
            # We treat everything as 'text' for generic profile building
            suggestions = self._analyze_field_values(history, field_name, 'text')
            if suggestions:
                # Take the top confidence suggestion
                profile[field_name] = suggestions[0]['value']
                
        return profile
    
    async def learn_from_submission(
        self,
        user_id: str,
        form_data: Dict[str, str],
        form_id: Optional[str] = None
    ) -> None:
        """
        Learn from a form submission for future suggestions.
        
        Args:
            user_id: User identifier
            form_data: Dictionary of field_name -> value
            form_id: Optional form identifier
        """
        # Get existing history
        history_key = f"autofill_history:{user_id}"
        history_raw = await get_cached(history_key)
        history = json.loads(history_raw) if history_raw else []
        
        # Prepare learned data (hash sensitive fields)
        learned_entry = {
            'timestamp': datetime.now().isoformat(),
            'form_id': form_id,
            'fields': {}
        }
        
        for field_name, value in form_data.items():
            if not value or not isinstance(value, str):
                continue
            
            # Check if sensitive
            is_sensitive = any(
                s in field_name.lower() 
                for s in self.SENSITIVE_FIELDS
            )
            
            if is_sensitive:
                # Hash sensitive data (can match but not reverse)
                learned_entry['fields'][field_name] = {
                    'hash': self._hash_value(value, user_id),
                    'type': 'sensitive'
                }
            else:
                learned_entry['fields'][field_name] = {
                    'value': value,
                    'type': 'normal'
                }
        
        # Add to history
        history.append(learned_entry)
        
        # Keep only recent history
        history = history[-self.max_history:]
        
        # Save updated history (30 days TTL)
        await set_cached(history_key, json.dumps(history), expire=30 * 24 * 3600)
        
        # Invalidate suggestion caches for updated fields
        for field_name in form_data.keys():
            cache_key = f"autofill:{user_id}:{field_name}"
            # Let cache expire naturally
        
        logger.info(f"Learned from submission: {len(form_data)} fields")
    
    def _analyze_field_values(
        self,
        history: List[Dict],
        field_name: str,
        field_type: str
    ) -> List[Dict[str, Any]]:
        """Analyze field values from history and generate suggestions."""
        value_stats: Dict[str, Dict] = defaultdict(lambda: {
            'count': 0,
            'first_used': None,
            'last_used': None
        })
        
        # Collect value occurrences
        for entry in history:
            fields = entry.get('fields', {})
            field_data = fields.get(field_name, {})
            
            # Skip sensitive or missing
            if field_data.get('type') == 'sensitive':
                continue
            
            value = field_data.get('value')
            if not value:
                continue
            
            timestamp = entry.get('timestamp', datetime.now().isoformat())
            
            stats = value_stats[value]
            stats['count'] += 1
            
            if stats['first_used'] is None:
                stats['first_used'] = timestamp
            stats['last_used'] = timestamp
        
        if not value_stats:
            return []
        
        # Calculate confidence scores
        total_occurrences = sum(s['count'] for s in value_stats.values())
        suggestions = []
        
        for value, stats in value_stats.items():
            # Frequency score (how often used)
            frequency_score = stats['count'] / total_occurrences
            
            # Recency score (how recently used)
            recency_score = self._calculate_recency_score(stats['last_used'])
            
            # Consistency score (used multiple times)
            consistency_score = min(stats['count'] / 5, 1.0)
            
            # Combined confidence (weighted average)
            confidence = (
                frequency_score * 0.5 +
                recency_score * 0.3 +
                consistency_score * 0.2
            )
            
            # Format label
            emoji = self.FIELD_TYPE_MAP.get(field_type, '')
            label = f"{emoji} {value}" if emoji else value
            
            suggestions.append({
                'value': value,
                'confidence': round(confidence, 2),
                'usage_count': stats['count'],
                'last_used': stats['last_used'],
                'label': label
            })
        
        # Sort by confidence
        suggestions.sort(key=lambda x: x['confidence'], reverse=True)
        
        return suggestions
    
    async def _get_user_history(self, user_id: str) -> List[Dict]:
        """Get user's form submission history."""
        history_key = f"autofill_history:{user_id}"
        history_raw = await get_cached(history_key)
        
        if history_raw:
            return json.loads(history_raw)
        return []
    
    def _calculate_recency_score(self, last_used: str) -> float:
        """Calculate recency score (more recent = higher)."""
        try:
            last_date = datetime.fromisoformat(last_used)
            days_ago = (datetime.now() - last_date).days
            
            if days_ago < 7:
                return 1.0
            elif days_ago < 30:
                return 0.8
            elif days_ago < 90:
                return 0.5
            else:
                return 0.2
        except Exception:
            return 0.5
    
    def _hash_value(self, value: str, salt: str) -> str:
        """Hash a value for privacy-preserving storage."""
        combined = f"{value}:{salt}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]


class CrossFieldInference:
    """
    Infer related field values from already-filled fields.
    
    Example:
    - Name: "Dr. John Smith" → Title: "Dr.", First: "John", Last: "Smith"
    - Address: "Mumbai, India" → Country: "India", City: "Mumbai"
    """
    
    # Common name prefixes/titles
    TITLES = ['dr', 'mr', 'mrs', 'ms', 'miss', 'prof', 'sir', 'lady']
    
    @staticmethod
    def infer_from_name(full_name: str) -> Dict[str, str]:
        """Extract title, first name, last name from full name."""
        parts = full_name.strip().split()
        result = {}
        
        if not parts:
            return result
        
        # Check for title
        first_word = parts[0].lower().rstrip('.')
        if first_word in CrossFieldInference.TITLES:
            result['title'] = parts[0]
            parts = parts[1:]
        
        if len(parts) >= 2:
            result['first_name'] = parts[0]
            result['last_name'] = parts[-1]
            if len(parts) > 2:
                result['middle_name'] = ' '.join(parts[1:-1])
        elif len(parts) == 1:
            result['first_name'] = parts[0]
        
        # Generate salutation
        if 'title' in result and 'last_name' in result:
            result['salutation'] = f"{result['title']} {result['last_name']}"
        elif 'first_name' in result:
            result['salutation'] = result['first_name']
        
        return result
    
    @staticmethod
    def infer_email_from_name(name: str, domain: str = "gmail.com") -> List[str]:
        """Generate email suggestions from name."""
        parts = name.lower().strip().split()
        suggestions = []
        
        if len(parts) >= 2:
            first, last = parts[0], parts[-1]
            suggestions.extend([
                f"{first}@{domain}",
                f"{first}{last}@{domain}",
                f"{first}.{last}@{domain}",
                f"{first[0]}{last}@{domain}",
                f"{last}{first[0]}@{domain}"
            ])
        elif len(parts) == 1:
            suggestions.append(f"{parts[0]}@{domain}")
        
        return suggestions
    
    @staticmethod
    def format_phone_by_country(phone: str, country: str = "US") -> str:
        """Format phone number based on country."""
        # Remove non-digits
        digits = ''.join(c for c in phone if c.isdigit())
        
        if country.upper() == "US":
            if len(digits) == 10:
                return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
            elif len(digits) == 11 and digits[0] == '1':
                return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        
        elif country.upper() == "IN":
            if len(digits) == 10:
                return f"+91 {digits[:5]} {digits[5:]}"
        
        elif country.upper() == "UK":
            if len(digits) == 10:
                return f"+44 {digits[:4]} {digits[4:]}"
        
        return digits


# Singleton instance
_autofill_instance: Optional[SmartAutofill] = None


def get_smart_autofill() -> SmartAutofill:
    """Get singleton SmartAutofill instance."""
    global _autofill_instance
    if _autofill_instance is None:
        _autofill_instance = SmartAutofill()
    return _autofill_instance
