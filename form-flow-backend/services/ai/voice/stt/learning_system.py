"""
Learning System

Learn from user corrections to improve over time.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional

from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CorrectionRecord:
    """Single correction record."""
    heard: str
    actual: str
    timestamp: datetime
    count: int = 1
    context: Dict[str, Any] = field(default_factory=dict)


class LearningSystem:
    """
    Learn from user corrections to improve future recognitions.
    
    Features:
    - Correction tracking
    - Pattern extraction
    - Statistics for monitoring
    """
    
    def __init__(self):
        """Initialize learning system with instance-level state."""
        self.corrections: Dict[str, CorrectionRecord] = {}
        self.pattern_library: Dict[str, List[str]] = defaultdict(list)
        self.total_corrections = 0
    
    def record_correction(
        self,
        heard: str,
        actual: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Record a user correction.
        
        Args:
            heard: What STT heard
            actual: What user corrected to
            context: Additional context (field type, etc.)
        """
        heard_clean = heard.lower().strip()
        actual_clean = actual.lower().strip()
        
        if heard_clean == actual_clean:
            return
        
        # Update or create record
        if heard_clean in self.corrections:
            record = self.corrections[heard_clean]
            record.count += 1
            record.timestamp = datetime.now()
        else:
            record = CorrectionRecord(
                heard=heard_clean,
                actual=actual_clean,
                timestamp=datetime.now(),
                context=context or {}
            )
            self.corrections[heard_clean] = record
        
        self.total_corrections += 1
        
        # Extract patterns
        self._extract_patterns(heard_clean, actual_clean, context)
        
        logger.info(f"Learned: '{heard}' → '{actual}' (count: {record.count})")
    
    def apply_learned_corrections(self, text: str) -> str:
        """
        Apply all learned corrections to text.
        
        Args:
            text: Input text
            
        Returns:
            Text with learned corrections applied
        """
        result = text.lower()
        
        for heard, record in self.corrections.items():
            if heard in result:
                result = result.replace(heard, record.actual)
        
        return result
    
    def _extract_patterns(
        self,
        heard: str,
        actual: str,
        context: Optional[Dict[str, Any]]
    ):
        """
        Extract reusable patterns from correction.
        
        Examples:
        - heard="geemail", actual="gmail" → pattern added
        - heard="at the", actual="@" → pattern added
        """
        # Email @ patterns
        if '@' in actual and '@' not in heard:
            if 'at' in heard.split():
                self.pattern_library['email_at_patterns'].append(heard)
        
        # Domain patterns
        if actual in ['gmail', 'yahoo', 'hotmail', 'outlook']:
            self.pattern_library['domain_patterns'].append(heard)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get learning statistics for monitoring."""
        if not self.corrections:
            return {
                'total_unique_corrections': 0,
                'total_correction_instances': 0,
                'patterns_learned': 0,
                'most_common_corrections': []
            }
        
        sorted_corrections = sorted(
            self.corrections.items(),
            key=lambda x: x[1].count,
            reverse=True
        )
        
        return {
            'total_unique_corrections': len(self.corrections),
            'total_correction_instances': self.total_corrections,
            'patterns_learned': sum(len(v) for v in self.pattern_library.values()),
            'most_common_corrections': [
                {'heard': k, 'actual': v.actual, 'count': v.count}
                for k, v in sorted_corrections[:10]
            ]
        }
    
    def export_corrections(self) -> Dict[str, Any]:
        """Export all corrections for backup/analysis."""
        return {
            'version': '1.0',
            'exported_at': datetime.now().isoformat(),
            'corrections': [
                {
                    'heard': record.heard,
                    'actual': record.actual,
                    'count': record.count,
                }
                for record in self.corrections.values()
            ]
        }
    
    def import_corrections(self, data: Dict[str, Any]):
        """Import corrections from export."""
        for item in data.get('corrections', []):
            self.record_correction(
                heard=item['heard'],
                actual=item['actual']
            )
