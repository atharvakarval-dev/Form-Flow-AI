"""
AI Dependency Checker

Validates critical AI dependencies at startup and provides health checks.
Prevents silent degradation by warning loudly when running in fallback mode.
"""

import sys
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DependencyStatus:
    """Status of a single dependency."""
    name: str
    available: bool
    version: Optional[str] = None
    message: Optional[str] = None


class DependencyChecker:
    """
    Check critical AI dependencies at startup.
    
    Provides clear warnings when running in degraded mode.
    """
    
    # Dependencies and their criticality
    CRITICAL_DEPS = ['langchain']
    OPTIONAL_DEPS = ['openai', 'anthropic']
    
    def __init__(self):
        self.results: Dict[str, DependencyStatus] = {}
        self.mode = "intelligent"  # or "fallback"
    
    def check_langchain(self) -> DependencyStatus:
        """Check if LangChain is properly installed."""
        try:
            import langchain
            version = getattr(langchain, '__version__', 'unknown')
            return DependencyStatus(
                name='langchain',
                available=True,
                version=version,
                message=f"LangChain v{version} loaded"
            )
        except ImportError as e:
            return DependencyStatus(
                name='langchain',
                available=False,
                message=f"LangChain not installed: {e}"
            )
        except Exception as e:
            return DependencyStatus(
                name='langchain',
                available=False,
                message=f"LangChain error: {e}"
            )
    
    def check_openai(self) -> DependencyStatus:
        """Check OpenAI SDK."""
        try:
            import openai
            version = getattr(openai, '__version__', 'unknown')
            return DependencyStatus(
                name='openai',
                available=True,
                version=version,
                message=f"OpenAI v{version} loaded"
            )
        except ImportError:
            return DependencyStatus(
                name='openai',
                available=False,
                message="OpenAI not installed (optional)"
            )
    
    def check_google_genai(self) -> DependencyStatus:
        """Check Google GenAI (Gemini)."""
        try:
            from google import genai
            return DependencyStatus(
                name='google-genai',
                available=True,
                message="Google GenAI loaded"
            )
        except ImportError:
            return DependencyStatus(
                name='google-genai',
                available=False,
                message="Google GenAI not installed (optional)"
            )
    
    def check_all(self) -> Dict[str, DependencyStatus]:
        """Check all AI dependencies."""
        self.results = {
            'langchain': self.check_langchain(),
            'openai': self.check_openai(),
            "Profile Service": "services.ai.profile.service",
        }
        
        # Determine mode
        if not self.results['langchain'].available:
            self.mode = "fallback"
        
        return self.results
    
    def validate_and_warn(self) -> str:
        """
        Validate dependencies and log warnings.
        
        Does NOT exit - allows graceful degradation.
        Returns the operating mode.
        """
        self.check_all()
        
        print("\n" + "=" * 60)
        print("🔍 AI Dependency Check")
        print("=" * 60)
        
        for name, status in self.results.items():
            icon = "✅" if status.available else "❌"
            print(f"  {icon} {name}: {status.message}")
        
        print("-" * 60)
        
        if self.mode == "fallback":
            print("⚠️  WARNING: Running in FALLBACK mode (regex extraction only)")
            print("   LangChain is missing - AI capabilities are LIMITED")
            print("")
            print("   To restore full intelligence, run:")
            print("   pip install langchain langchain-community")
            logger.warning("AI running in FALLBACK mode - LangChain not available")
        else:
            print(f"✅ AI running in INTELLIGENT mode")
            logger.info("AI running in INTELLIGENT mode - all dependencies available")
        
        print("=" * 60 + "\n")
        
        return self.mode
    
    def to_dict(self) -> Dict:
        """Convert results to JSON-serializable dict."""
        return {
            "mode": self.mode,
            "dependencies": {
                name: {
                    "available": status.available,
                    "version": status.version,
                    "message": status.message
                }
                for name, status in self.results.items()
            }
        }


# Singleton instance
_checker: Optional[DependencyChecker] = None


def get_dependency_checker() -> DependencyChecker:
    """Get or create singleton dependency checker."""
    global _checker
    if _checker is None:
        _checker = DependencyChecker()
    return _checker


def validate_ai_dependencies() -> str:
    """
    Main entry point - validate dependencies at startup.
    
    Returns:
        "intelligent" or "fallback" mode string
    """
    checker = get_dependency_checker()
    return checker.validate_and_warn()


def get_ai_mode() -> str:
    """Get current AI mode without rechecking."""
    checker = get_dependency_checker()
    if not checker.results:
        checker.check_all()
    return checker.mode
