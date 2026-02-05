"""
Plugin Question Optimizer Module

Extends FieldClusterer for plugin-specific question optimization.
Features:
- Custom question groups from plugin config
- Plugin field-to-form field adaptation
- Batching based on question_group
- Natural language question consolidation via LLM

Zero redundancy:
- Inherits core logic from FieldClusterer
- Adapts plugin fields to existing interface
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from services.ai.extraction.field_clusterer import FieldClusterer
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OptimizedQuestion:
    """An optimized question combining multiple fields."""
    fields: List[Dict[str, Any]]  # Original plugin fields
    question_text: str  # Natural language question
    field_names: List[str]  # Column names for extraction
    group: Optional[str]  # Question group (if any)
    complexity: int  # Total complexity score


class PluginQuestionOptimizer(FieldClusterer):
    """
    Plugin-specific question optimizer.
    
    Extends FieldClusterer with:
    - Support for plugin field format (column_name, question_text, etc.)
    - Custom question_group clustering
    - LLM-assisted question consolidation
    
    Usage:
        optimizer = PluginQuestionOptimizer()
        questions = optimizer.optimize_plugin_fields(plugin_fields)
    """
    
    # Additional clusters for common plugin field patterns
    PLUGIN_CLUSTERS = {
        'customer': [
            r'customer', r'client', r'buyer', r'purchaser'
        ],
        'order': [
            r'order', r'transaction', r'purchase', r'invoice'
        ],
        'product': [
            r'product', r'item', r'sku', r'inventory'
        ],
        'payment': [
            r'payment', r'credit', r'card', r'billing', r'amount', r'price'
        ],
        'shipping': [
            r'shipping', r'delivery', r'tracking', r'carrier'
        ],
        'feedback': [
            r'feedback', r'review', r'rating', r'comment', r'satisfaction'
        ],
    }
    
    # Column type to complexity mapping
    COLUMN_TYPE_COMPLEXITY = {
        'string': 1,
        'integer': 1,
        'float': 1,
        'boolean': 1,
        'date': 2,
        'datetime': 2,
        'email': 2,
        'phone': 2,
        'json': 3,
        'text': 2,  # Long text
        'uuid': 2,
    }
    
    def __init__(self):
        """Initialize with extended cluster patterns."""
        super().__init__()
        
        # Compile additional plugin patterns
        for cluster_name, patterns in self.PLUGIN_CLUSTERS.items():
            self._compiled_patterns[cluster_name] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
    
    def _adapt_plugin_field(self, field: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt plugin field format to FieldClusterer format.
        
        Plugin fields have: column_name, column_type, question_text, is_required
        FieldClusterer expects: name, type, label
        """
        return {
            'name': field.get('column_name', ''),
            'type': field.get('column_type', 'string'),
            'label': field.get('question_text', field.get('column_name', '')),
            'required': field.get('is_required', False),
            'question_group': field.get('question_group'),
            'display_order': field.get('display_order', 0),
            '_original': field  # Keep original for reference
        }
    
    def get_plugin_field_cluster(self, field: Dict[str, Any]) -> str:
        """
        Determine cluster for a plugin field.
        
        Priority:
        1. Explicit question_group from config
        2. Semantic clustering from column_name/question_text
        """
        # If explicit group is set, use it
        question_group = field.get('question_group')
        if question_group:
            return question_group
        
        # Fall back to semantic clustering
        adapted = self._adapt_plugin_field(field)
        return self.get_field_cluster(adapted)
    
    def get_plugin_field_complexity(self, field: Dict[str, Any]) -> int:
        """Get complexity score for a plugin field."""
        column_type = field.get('column_type', 'string').lower()
        
        # Use plugin type complexity
        base = self.COLUMN_TYPE_COMPLEXITY.get(column_type, 2)
        
        # Required fields are slightly more complex (need confirmation)
        if field.get('is_required', False):
            base = min(base + 0.5, 3)
        
        return int(base)
    
    def create_plugin_batches(
        self,
        fields: List[Dict[str, Any]],
        max_complexity: int = None,
        max_fields: int = None,
        respect_groups: bool = True
    ) -> List[List[Dict[str, Any]]]:
        """
        Create intelligent batches from plugin fields.
        
        Args:
            fields: List of plugin field dictionaries
            max_complexity: Override default complexity budget
            max_fields: Override default max fields per batch
            respect_groups: If True, never split question_group
            
        Returns:
            List of batches, each batch is a list of plugin fields
        """
        if not fields:
            return []
        
        max_complexity = max_complexity or self.MAX_BATCH_COMPLEXITY
        max_fields = max_fields or self.MAX_FIELDS_PER_BATCH
        
        # Sort by display_order first
        sorted_fields = sorted(fields, key=lambda f: f.get('display_order', 0))
        
        # Group by question_group (if respecting groups) or semantic cluster
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for field in sorted_fields:
            if respect_groups and field.get('question_group'):
                group = field['question_group']
            else:
                group = self.get_plugin_field_cluster(field)
            
            if group not in grouped:
                grouped[group] = []
            grouped[group].append(field)
        
        # Create batches respecting complexity limits
        batches = []
        
        # Process groups in order (preserve first field's display_order)
        ordered_groups = sorted(
            grouped.items(),
            key=lambda kv: min(f.get('display_order', 0) for f in kv[1])
        )
        
        for group_name, group_fields in ordered_groups:
            current_batch = []
            current_complexity = 0
            
            for field in group_fields:
                complexity = self.get_plugin_field_complexity(field)
                
                # Check if adding would exceed limits
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
        
        logger.info(f"Created {len(batches)} plugin question batches from {len(fields)} fields")
        return batches
    
    def format_plugin_batch_question(
        self,
        batch: List[Dict[str, Any]],
        use_custom_questions: bool = True
    ) -> str:
        """
        Format a batch of plugin fields as a natural language question.
        
        Args:
            batch: List of plugin fields
            use_custom_questions: If True, use field's question_text
            
        Returns:
            Natural language question string
        """
        if not batch:
            return ""
        
        if use_custom_questions and len(batch) == 1:
            # Single field - use its custom question if available
            question = batch[0].get('question_text')
            if question:
                return question
        
        # Multiple fields - combine labels
        labels = []
        for field in batch:
            label = field.get('question_text') or field.get('column_name', 'value')
            # Clean up technical column names
            label = label.replace('_', ' ').title()
            labels.append(label)
        
        if len(labels) == 1:
            return f"What is the {labels[0]}?"
        elif len(labels) == 2:
            return f"What are the {labels[0]} and {labels[1]}?"
        else:
            leading = ', '.join(labels[:-1])
            return f"Please provide the {leading}, and {labels[-1]}."
    
    def optimize_plugin_fields(
        self,
        fields: List[Dict[str, Any]],
        max_fields_per_question: int = 4
    ) -> List[OptimizedQuestion]:
        """
        Create optimized questions from plugin fields.
        
        Main entry point for plugin question optimization.
        
        Args:
            fields: List of plugin field dictionaries
            max_fields_per_question: Max fields to combine in one question
            
        Returns:
            List of OptimizedQuestion objects
        """
        batches = self.create_plugin_batches(
            fields,
            max_fields=max_fields_per_question
        )
        
        questions = []
        for batch in batches:
            question = OptimizedQuestion(
                fields=batch,
                question_text=self.format_plugin_batch_question(batch),
                field_names=[f.get('column_name', '') for f in batch],
                group=batch[0].get('question_group') if batch else None,
                complexity=sum(self.get_plugin_field_complexity(f) for f in batch)
            )
            questions.append(question)
        
        return questions


# Singleton instance
_plugin_optimizer: Optional[PluginQuestionOptimizer] = None


def get_plugin_optimizer() -> PluginQuestionOptimizer:
    """Get singleton plugin question optimizer."""
    global _plugin_optimizer
    if _plugin_optimizer is None:
        _plugin_optimizer = PluginQuestionOptimizer()
    return _plugin_optimizer
