"""Report generation package - generates comprehensive analysis reports.

This package is being refactored from a monolithic reports.py file.

Current structure (Phase 1 - In Progress):
- models.py: Data classes (Thresholds, KPIMetrics, ConversationTriage, PatternAnalysis)
- formatters.py: Conversation text formatting utilities

Planned structure (Phase 2):
- kpi.py: KPI calculation logic
- triage.py: Conversation triage logic
- patterns.py: Pattern analysis logic
- markdown.py: Markdown report generation
- pdf.py: PDF report generation
- generator.py: Main coordinator class

For now, use: from amira_analysis.reports import ReportGenerator
"""

# Export the new refactored modules
from .models import (
    Thresholds,
    ConversationTriage,
    KPIMetrics,
    PatternAnalysis,
)
from .formatters import format_conversation_text, get_date_range

__all__ = [
    "Thresholds",
    "ConversationTriage",
    "KPIMetrics",
    "PatternAnalysis",
    "format_conversation_text",
    "get_date_range",
]
