"""
Analytics Router

Provides dashboard analytics and AI-powered insights using Gemini.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import defaultdict
import os

from core.database import get_db
from core.models import User, Submission
from routers.auth import get_current_user
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard")
async def get_dashboard_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive dashboard analytics with charts data and AI insights.
    """
    try:
        # Get user submissions
        submissions = current_user.submissions or []
        
        # === SUMMARY STATS ===
        total_forms = len(submissions)
        successful = [s for s in submissions if s.status == 'Success']
        success_rate = round((len(successful) / total_forms * 100) if total_forms > 0 else 0)
        
        # Estimate time saved (avg 3 min per form)
        avg_time_saved_seconds = total_forms * 180
        
        # Estimate total fields (avg 8 fields per form)
        total_fields_filled = total_forms * 8
        
        summary = {
            "total_forms": total_forms,
            "success_rate": success_rate,
            "avg_time_saved_seconds": avg_time_saved_seconds,
            "total_fields_filled": total_fields_filled,
        }
        
        # === CHART DATA ===
        
        # Submissions by day (last 7 days)
        submissions_by_day = _get_submissions_by_day(submissions)
        
        # Success by form type
        # Success by form type
        success_by_type = _get_success_by_type(submissions)
        
        # Field types filled (mock based on typical form data)
        field_types = [
            {"name": "Text", "value": int(total_fields_filled * 0.35)},
            {"name": "Email", "value": int(total_fields_filled * 0.15)},
            {"name": "Phone", "value": int(total_fields_filled * 0.12)},
            {"name": "Select", "value": int(total_fields_filled * 0.18)},
            {"name": "Checkbox", "value": int(total_fields_filled * 0.10)},
            {"name": "Other", "value": int(total_fields_filled * 0.10)},
        ]
        
        # Top Domains & Activity by Hour
        top_domains = _get_top_domains(submissions)
        activity_by_hour = _get_activity_by_hour(submissions)
        
        charts = {
            "submissions_by_day": submissions_by_day,
            "success_by_type": success_by_type,
            "field_types": field_types,
            "top_domains": top_domains,
            "activity_by_hour": activity_by_hour,
        }
        
        # === AI INSIGHTS ===
        ai_insights = _generate_ai_insights(summary, submissions)
        
        return {
            "summary": summary,
            "charts": charts,
            "ai_insights": ai_insights,
        }
        
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate analytics")


def _get_submissions_by_day(submissions: List[Submission]) -> List[Dict[str, Any]]:
    """Get submission counts grouped by day for the last 7 days."""
    today = datetime.now().date()
    days = []
    
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.strftime("%b %d")
        count = sum(1 for s in submissions 
                   if hasattr(s, 'timestamp') and s.timestamp 
                   and s.timestamp.date() == day)
        days.append({"date": day_str, "count": count})
    
    return days


def _get_success_by_type(submissions: List[Submission]) -> List[Dict[str, Any]]:
    """Categorize submissions by form type and success rate."""
    type_stats = defaultdict(lambda: {"success": 0, "fail": 0})
    
    for s in submissions:
        # Detect form type from URL
        url = getattr(s, 'form_url', '') or ''
        if 'google' in url.lower() or 'forms.gle' in url.lower():
            form_type = "Google Forms"
        elif 'typeform' in url.lower():
            form_type = "Typeform"
        elif 'jotform' in url.lower():
            form_type = "Jotform"
        else:
            form_type = "Standard"
        
        if s.status == 'Success':
            type_stats[form_type]["success"] += 1
        else:
            type_stats[form_type]["fail"] += 1
    
    return [
        {"type": t, "success": d["success"], "fail": d["fail"]}
        for t, d in type_stats.items()
    ]


def _get_top_domains(submissions: List[Submission]) -> List[Dict[str, Any]]:
    """Get top 5 most frequent domains from submissions."""
    from urllib.parse import urlparse
    
    domain_counts = defaultdict(int)
    for s in submissions:
        url = getattr(s, 'form_url', '') or ''
        if not url:
            continue
        try:
            # Extract domain
            if 'http' not in url:
                url = 'http://' + url
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')
            if domain:
                domain_counts[domain] += 1
        except:
            continue
            
    # Sort by count desc and take top 5
    sorted_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return [{"name": domain, "value": count} for domain, count in sorted_domains]


def _get_activity_by_hour(submissions: List[Submission]) -> List[Dict[str, Any]]:
    """Get submission activity count by hour of day (0-23)."""
    hour_counts = defaultdict(int)
    
    for s in submissions:
        if hasattr(s, 'timestamp') and s.timestamp:
            hour_counts[s.timestamp.hour] += 1
            
    # Return all 24 hours
    return [{"hour": h, "count": hour_counts[h]} for h in range(24)]


def _generate_ai_insights(summary: Dict[str, Any], submissions: List) -> str:
    """Generate AI-powered insights about user's form filling patterns."""
    
    # Basic insights without Gemini (quick fallback)
    insights = []
    
    total = summary["total_forms"]
    rate = summary["success_rate"]
    time_saved = summary["avg_time_saved_seconds"] // 60  # minutes
    
    if total == 0:
        return "🚀 Start filling forms to see personalized insights! Voice-powered form filling saves an average of 3 minutes per form."
    
    # Success rate insight
    if rate >= 95:
        insights.append(f"🎯 Outstanding! Your {rate}% success rate is exceptional.")
    elif rate >= 80:
        insights.append(f"✅ Good performance with {rate}% success rate.")
    else:
        insights.append(f"⚠️ Your success rate is {rate}%. Consider using voice input for better accuracy.")
    
    # Time saved insight
    if time_saved > 0:
        hours = time_saved // 60
        mins = time_saved % 60
        if hours > 0:
            insights.append(f"⏱️ You've saved approximately {hours}h {mins}m with voice-powered form filling!")
        else:
            insights.append(f"⏱️ You've saved approximately {mins} minutes with voice-powered form filling!")
    
    # Activity insight
    if total >= 10:
        insights.append(f"📊 Power user! {total} forms completed. You're getting the most out of Form Flow AI.")
    elif total >= 5:
        insights.append(f"📈 Growing usage! {total} forms completed. Keep going!")
    else:
        insights.append(f"🌱 Just getting started! {total} forms completed so far.")
    
    return " ".join(insights)
