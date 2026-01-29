"""
Plugin Question Optimization Package

Provides question optimization for plugins:
- PluginQuestionOptimizer: Extends FieldClusterer for plugin fields
- QuestionConsolidator: LLM-powered natural question generation
- CostTracker: LLM usage and cost tracking

All components follow DRY principles by extending or reusing
existing infrastructure from services.ai.extraction.
"""

from services.plugin.question.optimizer import (
    PluginQuestionOptimizer,
    OptimizedQuestion,
    get_plugin_optimizer,
)
from services.plugin.question.consolidator import (
    QuestionConsolidator,
    ConsolidatedQuestion,
    get_question_consolidator,
)
from services.plugin.question.cost_tracker import (
    CostTracker,
    LLMUsageLog,
    UsageSummary,
    BudgetAlert,
    get_cost_tracker,
)

__all__ = [
    # Optimizer
    "PluginQuestionOptimizer",
    "OptimizedQuestion",
    "get_plugin_optimizer",
    # Consolidator
    "QuestionConsolidator",
    "ConsolidatedQuestion",
    "get_question_consolidator",
    # Cost Tracking
    "CostTracker",
    "LLMUsageLog",
    "UsageSummary",
    "BudgetAlert",
    "get_cost_tracker",
]
