"""
Field Clusterer

Semantic field grouping for natural question batching.
Groups related fields together for efficient form filling.
"""

import re
from typing import Dict, List, Any
from utils.logging import get_logger

logger = get_logger(__name__)


class FieldClusterer:
    """
    Semantic field clustering for natural question batching.
    
    Groups fields by semantic similarity (identity, professional, etc.)
    and respects complexity limits to avoid overwhelming users.
    """
    
    # Field name patterns for clustering
    CLUSTERS = {
        'identity': [
            r'name', r'first.*name', r'last.*name', r'full.*name',
            r'email', r'mail', r'phone', r'mobile', r'tel'
        ],
        'professional': [
            r'experience', r'years', r'company', r'employer', r'organization',
            r'title', r'position', r'role', r'job', r'occupation'
        ],
        'location': [
            r'address', r'city', r'state', r'country', r'zip', r'postal',
            r'street', r'region', r'province'
        ],
        'education': [
            r'education', r'degree', r'university', r'college', r'school',
            r'graduate', r'major', r'qualification'
        ],
        'personal': [
            r'age', r'birth', r'gender', r'nationality', r'marital'
        ],
        'social': [
            r'linkedin', r'twitter', r'github', r'portfolio', r'website', r'url'
        ],
    }
    
    # Complexity by field type
    COMPLEXITY_MAP = {
        'simple': ['text', 'number', 'checkbox', 'radio'],
        'moderate': ['email', 'tel', 'date', 'select'],
        'complex': ['textarea', 'file', 'url', 'address'],
    }
    
    # Maximum complexity budget per batch
    MAX_BATCH_COMPLEXITY = 8
    MAX_FIELDS_PER_BATCH = 4
    
    def __init__(self):
        """Initialize clusterer with compiled regex patterns."""
        self._compiled_patterns = {}
        for cluster_name, patterns in self.CLUSTERS.items():
            self._compiled_patterns[cluster_name] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
    
    def get_field_cluster(self, field: Dict[str, Any]) -> str:
        """
        Determine which cluster a field belongs to.
        
        Args:
            field: Field definition with name, label, type
            
        Returns:
            Cluster name or 'other'
        """
        field_name = (field.get('name') or '').lower()
        field_label = (field.get('label') or '').lower()
        combined = f"{field_name} {field_label}"
        
        for cluster_name, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(combined):
                    return cluster_name
        
        return 'other'
    
    def get_field_complexity(self, field: Dict[str, Any]) -> int:
        """
        Determine field complexity for batching.
        
        Args:
            field: Field definition
            
        Returns:
            Complexity score (1=simple, 2=moderate, 3=complex)
        """
        field_type = (field.get('type') or 'text').lower()
        field_name = (field.get('name') or '').lower()
        
        # Check explicit complexity
        if field_type in self.COMPLEXITY_MAP['simple']:
            base = 1
        elif field_type in self.COMPLEXITY_MAP['moderate']:
            base = 2
        elif field_type in self.COMPLEXITY_MAP['complex']:
            base = 3
        else:
            base = 2
        
        # Email and phone are always moderate+ due to precision needs
        if 'email' in field_name or field_type == 'email':
            base = max(base, 2)
        if 'phone' in field_name or field_type == 'tel':
            base = max(base, 2)
        
        return base
    
    def get_optimal_batch_size(self, fields: List[Dict[str, Any]]) -> int:
        """
        Determine optimal batch size based on field complexity.
        
        Simple fields (text, checkbox) can be grouped into larger batches,
        while complex fields (dates, addresses) need smaller batches.
        
        Args:
            fields: List of fields to batch
            
        Returns:
            Optimal batch size (3-5)
        """
        if not fields:
            return self.MAX_FIELDS_PER_BATCH
        
        # Calculate average complexity
        total_complexity = sum(self.get_field_complexity(f) for f in fields)
        avg_complexity = total_complexity / len(fields)
        
        # Low avg complexity (mostly simple) -> larger batches
        if avg_complexity < 1.5:
            return 5
        elif avg_complexity < 2.0:
            return 4
        else:
            return 3
    
    def create_batches(
        self, 
        fields: List[Dict[str, Any]],
        max_complexity: int = None,
        max_fields: int = None
    ) -> List[List[Dict[str, Any]]]:
        """
        Create intelligent question batches from remaining fields.
        
        Groups fields by cluster and respects complexity limits.
        
        Args:
            fields: List of remaining fields
            max_complexity: Override default complexity budget
            max_fields: Override default max fields per batch
            
        Returns:
            List of batches, each batch is a list of fields
        """
        if not fields:
            return []
        
        max_complexity = max_complexity or self.MAX_BATCH_COMPLEXITY
        max_fields = max_fields or self.MAX_FIELDS_PER_BATCH
        
        logger.info(f"[CLUSTERER] create_batches called: {len(fields)} fields, max_fields={max_fields}, max_complexity={max_complexity}")
        
        # Group by cluster
        clustered = {}
        for field in fields:
            cluster = self.get_field_cluster(field)
            if cluster not in clustered:
                clustered[cluster] = []
            clustered[cluster].append(field)
        
        # Priority order for clusters
        priority = ['identity', 'professional', 'location', 'education', 'personal', 'social', 'other']
        
        batches = []
        for cluster in priority:
            if cluster not in clustered:
                continue
            
            # Create batches within cluster
            current_batch = []
            current_complexity = 0
            
            for field in clustered[cluster]:
                complexity = self.get_field_complexity(field)
                
                # Check if adding this field would exceed limits
                if (current_complexity + complexity > max_complexity or 
                    len(current_batch) >= max_fields):
                    if current_batch:
                        batches.append(current_batch)
                    current_batch = [field]
                    current_complexity = complexity
                else:
                    current_batch.append(field)
                    current_complexity += complexity
            
            if current_batch:
                batches.append(current_batch)
        
        logger.info(f"[CLUSTERER] Created {len(batches)} batches. First batch has {len(batches[0]) if batches else 0} fields")
        return batches
    
    def format_batch_question(self, batch: List[Dict[str, Any]]) -> str:
        """
        Format a batch of fields as a natural language question.
        
        Args:
            batch: List of fields to ask about
            
        Returns:
            Natural language question string
        """
        if not batch:
            return ""
        
        labels = [f.get('label', f.get('name', 'value')) for f in batch]
        
        if len(labels) == 1:
            return f"What's your {labels[0]}?"
        elif len(labels) == 2:
            return f"What's your {labels[0]} and {labels[1]}?"
        else:
            leading = ', '.join(labels[:-1])
            return f"What's your {leading}, and {labels[-1]}?"
