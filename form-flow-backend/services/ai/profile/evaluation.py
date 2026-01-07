"""
Profile Evaluation & Monitoring

Handles metric tracking and quality evaluation for the profile generation system.
Designed to be compatible with observability tools (Datadog, Prometheus) via structured logging.
"""

import time
import logging
import json
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from datetime import datetime

# Configure a specific logger for metrics to easily filter/forward
metrics_logger = logging.getLogger("profile.metrics")

@dataclass
class ProfileUpdateMetrics:
    user_id: int
    form_type: str
    duration_ms: float
    input_token_count: int  # Estimated or actual
    output_token_count: int # Estimated or actual
    confidence_score: float
    profile_version: int
    success: bool
    error_type: Optional[str] = None
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))

class ProfileEvaluator:
    """
    Evaluates profile quality and tracks system performance.
    """
    
    def __init__(self):
        self.logger = metrics_logger

    def track_update(
        self, 
        user_id: int, 
        start_time: float, 
        success: bool, 
        profile_data: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log structured metrics for a profile update attempt.
        """
        duration = (time.time() - start_time) * 1000
        
        confidence = 0.0
        version = 0
        if profile_data:
            confidence = profile_data.get('confidence_score', 0.0)
            version = profile_data.get('version', 0)
            
        error_type = type(error).__name__ if error else None
        
        # Estimate tokens (very rough approximation: 4 chars / token)
        # In a real scenario, we'd get usage from the LLM response
        input_tokens = 0
        output_tokens = 0
        if metadata:
            input_tokens = metadata.get('input_chars', 0) // 4
            output_tokens = metadata.get('output_chars', 0) // 4

        metrics = ProfileUpdateMetrics(
            user_id=user_id,
            form_type=metadata.get('form_type', 'unknown') if metadata else 'unknown',
            duration_ms=round(duration, 2),
            input_token_count=input_tokens,
            output_token_count=output_tokens,
            confidence_score=confidence,
            profile_version=version,
            success=success,
            error_type=error_type
        )
        
        # Log generic info
        if success:
            self.logger.info(f"Profile Update Success: user={user_id} conf={confidence} ms={duration:.0f}")
        else:
            self.logger.error(f"Profile Update Failed: user={user_id} error={error_type} ms={duration:.0f}")
            
        # Log machine-readable metric event
        self.logger.info(f"[METRIC] {metrics.to_json()}")

    def evaluate_quality(self, profile: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate heuristic quality scores for a profile.
        Returns a dict of sub-scores (0.0 - 1.0).
        """
        if not profile:
            return {"completeness": 0.0, "depth": 0.0}
            
        scores = {}
        
        # 1. Completeness: Does it have all key sections populated?
        required_keys = ["psychological_profile", "behavioral_patterns", "motivation_matrix"]
        present_keys = sum(1 for k in required_keys if profile.get(k))
        scores["completeness"] = present_keys / len(required_keys)
        
        # 2. Depth: Are the specific fields detailed enough?
        # Check 'mindset_analysis' length
        mindset = profile.get("psychological_profile", {}).get("mindset_analysis", "")
        # Arbitrary efficient length: > 200 chars is decent depth
        scores["depth"] = min(len(mindset) / 200, 1.0)
        
        # 3. Evolution Tracking: Does it have interaction history?
        history = profile.get("interaction_history", {})
        scores["evolution_tracked"] = 1.0 if history else 0.0
        
        return scores

    # Singleton instance
    _instance = None
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ProfileEvaluator()
        return cls._instance

# Global helper
evaluator = ProfileEvaluator.get_instance()
