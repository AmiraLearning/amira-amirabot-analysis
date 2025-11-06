# Reports Package Refactoring

This package is being refactored from the monolithic `reports.py` file (1480 lines) into a cleaner, more maintainable structure.

## Current Status: Phase 1 (In Progress)

### Completed ✅
- **models.py** - Data classes extracted
  - `Thresholds` - Configuration thresholds
  - `ConversationTriage` - Triage results
  - `KPIMetrics` - Key performance indicators
  - `PatternAnalysis` - Pattern analysis results

- **formatters.py** - Text formatting utilities
  - `format_conversation_text()` - Format conversations with timestamps
  - `get_date_range()` - Calculate first/last conversation dates

### Still in reports.py (Main file)
- `ReportGenerator` class (~1400 lines) containing:
  - Data loading and validation
  - KPI calculation
  - Conversation triage
  - Pattern analysis
  - Actionable fixes generation
  - Markdown report generation
  - PDF report generation

## Planned: Phase 2 (Future Work)

Extract remaining functionality into focused modules:

### kpi.py
- `calculate_kpis()` - KPI calculation logic
- Move KPI-specific logic from ReportGenerator

### triage.py
- `triage_conversations()` - Priority triage logic
- Move triage decision logic

### patterns.py
- `analyze_patterns()` - Pattern detection
- `generate_actionable_fixes()` - Fix recommendations
- `generate_bot_feedback()` - Bot feedback generation

### markdown.py
- `generate_markdown_report()` - Markdown generation
- Move markdown formatting logic

### pdf.py
- `generate_pdf_report()` - PDF generation
- Move ReportLab PDF logic

### generator.py
- `ReportGenerator` class - Slim coordinator
- Orchestrates other modules
- Handles data loading only

## Benefits

### Current (Phase 1)
- ✅ Data models separated and reusable
- ✅ Formatting utilities can be imported independently
- ✅ Clearer package structure

### Future (Phase 2)
- 🔄 Each module <200 lines
- 🔄 Single responsibility per module
- 🔄 Easier testing and maintenance
- 🔄 Faster navigation and comprehension

## Usage

### Current
```python
# Main class still in reports.py
from amira_analysis.reports import ReportGenerator

# New models available in reports package
from amira_analysis.reports import Thresholds, KPIMetrics

# New formatters available
from amira_analysis.reports import format_conversation_text, get_date_range
```

### Future (After Phase 2)
```python
# All functionality in reports package
from amira_analysis.reports import ReportGenerator
from amira_analysis.reports.kpi import calculate_kpis
from amira_analysis.reports.triage import triage_conversations
from amira_analysis.reports.patterns import analyze_patterns
```

## Migration Notes

- Phase 1 is backward compatible - no breaking changes
- `reports.py` file still exists and works as before
- New modules are available but optional
- Phase 2 will require updating imports in cli.py
