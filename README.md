# Amirabot Conversation Analysis

AI-powered conversation analysis tool for evaluating Amirabot support quality. Analyzes customer support conversations to identify quality issues, generate actionable insights, and produce comprehensive reports for improving bot performance.

## Features

### 🤖 AI-Powered Analysis
- **Intelligent Conversation Evaluation**: Uses Claude AI to analyze support conversations for quality metrics
- **Multi-Dimensional Scoring**: Evaluates correctness, escalation handling, helpfulness, tone, and more
- **Pattern Detection**: Automatically identifies recurring issues across conversations

### 📊 Comprehensive Reporting
- **PDF Reports**: Professional reports with executive summaries, KPIs, and full conversation transcripts
- **Markdown Reports**: Human-readable text reports with actionable fixes
- **JSON Output**: Machine-readable data for programmatic analysis

### 🎯 Quality Metrics
- **Overall Quality Score**: 0-100 score based on weighted metrics
- **Pass/Fail Verdicts**: Clear quality assessments
- **Prize Candidates**: Identifies worst conversations for incentivized improvement ($500 gift card contest)
- **KPI Tracking**:
  - First-turn resolution rate
  - Escalation quality
  - Clear next steps percentage
  - Cycles without progress

### 🚨 Issue Detection
- **OBVIOUS_WRONG_ANSWER**: Incorrect information provided
- **MISSED_ESCALATION**: Bot failed to escalate when needed
- **DEAD_END**: Conversation ended without clear next steps
- **REPETITIVE**: Bot repeats instructions without progress
- **DUMB_QUESTION**: Bot asks for information already provided
- **LACK_OF_ENCOURAGEMENT**: Discouraging tone or no path forward

### 🎨 Triage & Prioritization
- **Fix Now**: Critical issues requiring immediate attention
- **High Priority**: Significant quality problems
- **Medium Priority**: Below-average conversations
- **Low Priority**: Minor issues

## Installation

### Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager

### Setup

1. Clone the repository:
```bash
git clone https://github.com/AmiraLearning/amira-amirabot-analysis.git
cd amira-amirabot-analysis
```

2. Install dependencies using uv:
```bash
uv sync
```

3. Create a `.env` file with your API keys:
```bash
ANTHROPIC_API_KEY=your_anthropic_api_key_here
INTERCOM_ACCESS_TOKEN=your_intercom_token_here  # Optional, for fetching conversations
```

## Usage

### Basic Workflow

The tool operates in three main stages:

#### 1. Fetch Conversations (Optional)
If you need to fetch conversations from Intercom:

```bash
uv run python main.py fetch --start-date 2024-01-01 --end-date 2024-01-31
```

Options:
- `--start-date`: Start date for conversation fetch (YYYY-MM-DD)
- `--end-date`: End date for conversation fetch (YYYY-MM-DD)
- `--output-dir`: Directory to save conversations (default: `conversations/`)

#### 2. Analyze Conversations

Analyze all conversations and generate individual analysis files:

```bash
uv run python main.py analyze
```

Options:
- `--conversations-dir`: Directory containing conversation JSON files (default: `conversations/`)
- `--output-dir`: Directory to save analyses (default: `conversation_analyses/`)
- `--max-workers`: Number of parallel workers (default: 5)
- `--resume`: Resume from last analyzed conversation

#### 3. Generate Summary Report

Create comprehensive summary reports from all analyses:

```bash
uv run python main.py report
```

Options:
- `--analyses-dir`: Directory containing analysis JSON files (default: `conversation_analyses/`)
- `--conversations-dir`: Directory containing full conversation data (default: `conversations/`)
- `--output-path`: Path for output report (default: `output/summary_report.md`)

The report command generates three files:
- `summary_report.md` - Markdown report
- `summary_report.json` - JSON summary
- `summary_report.pdf` - PDF report with full conversation transcripts

### Complete Example

```bash
# Fetch conversations from Intercom
uv run python main.py fetch --start-date 2024-10-01 --end-date 2024-10-31

# Analyze all conversations
uv run python main.py analyze --max-workers 10

# Generate reports
uv run python main.py report
```

## Configuration

### Custom Thresholds

You can customize quality thresholds by modifying `amira_analysis/reports.py`:

```python
@dataclass(frozen=True)
class Thresholds:
    """Configurable thresholds for analysis."""

    correctness_first_turn: int = 8  # out of 10
    escalation_good: int = 24  # out of 30 (80%)
    score_high: int = 70
    score_low: int = 50
    loops_fix_now: int = 2
```

### Analysis Prompts

Customize the AI analysis prompts in `amira_analysis/analyzers/ai.py` to adjust:
- Scoring criteria
- Issue type definitions
- Prize candidate identification logic

## Output Format

### Analysis JSON Structure

Each analyzed conversation produces a JSON file with:

```json
{
  "conversation_id": "uuid",
  "overall_score": 75,
  "overall_verdict": "PASS",
  "summary": "Conversation summary...",
  "flags": [
    {
      "type": "MISSED_ESCALATION",
      "severity": "high",
      "description": "Bot failed to escalate...",
      "turn": 3
    }
  ],
  "metrics": {
    "correctness_score": 8,
    "escalation_score": 15,
    "helpfulness_score": 7
  },
  "prize_candidate": false,
  "has_clear_next_step": true,
  "cycles_without_progress": 0
}
```

### Summary Report Structure

The summary report includes:

1. **Executive Summary**: High-level metrics and pass/fail rates
2. **Key Performance Indicators**: Health metrics with targets
3. **Priority Triage**: Conversations grouped by urgency
4. **Pattern Analysis**: Issue type frequency and severity
5. **Actionable Fixes**: Specific recommendations by issue type
6. **Snippet Bank**: Copy-paste responses for common issues
7. **Appendix A (PDF only)**: Full transcripts of top 10 prize candidates

## Project Structure

```
amira-amirabot-analysis/
├── amira_analysis/
│   ├── __init__.py
│   ├── aggregator.py       # Data aggregation utilities
│   ├── cli.py              # Command-line interface
│   ├── constants.py        # Configuration constants
│   ├── fetcher.py          # Intercom API integration
│   ├── models.py           # Data models
│   ├── reports.py          # Report generation (PDF, MD, JSON)
│   ├── storage.py          # File I/O operations
│   └── analyzers/
│       ├── __init__.py
│       ├── base.py         # Base analyzer class
│       └── ai.py           # AI-powered conversation analyzer
├── main.py                 # Main entry point
├── normalize_to_csv.py     # CSV export utility
├── output/                 # Generated reports
│   ├── summary_report.md
│   ├── summary_report.json
│   └── summary_report.pdf
├── pyproject.toml          # Project dependencies
├── .gitignore
└── README.md
```

## How It Works

### 1. Conversation Fetching
- Connects to Intercom API
- Fetches conversations within date range
- Saves individual conversation JSON files

### 2. AI Analysis Pipeline
For each conversation:
1. **Load Conversation**: Read messages and metadata
2. **AI Evaluation**: Send to Claude for analysis
3. **Extract Metrics**: Parse scores, flags, and verdicts
4. **Save Analysis**: Write JSON output

### 3. Report Generation
1. **Load All Analyses**: Aggregate individual results
2. **Calculate KPIs**: Compute averages and percentages
3. **Triage Conversations**: Prioritize by severity
4. **Pattern Analysis**: Identify recurring issues
5. **Generate Fixes**: Map issues to actionable solutions
6. **Create Reports**: Output in multiple formats

### Scoring Algorithm

Overall score is calculated using weighted metrics:

```python
overall_score = (
    (correctness_score / 10) * 30 +      # 30% weight
    (escalation_score / 30) * 20 +       # 20% weight
    (helpfulness_score / 10) * 20 +      # 20% weight
    (tone_score / 10) * 15 +             # 15% weight
    (efficiency_score / 10) * 15         # 15% weight
)
```

- **PASS**: Score ≥ 70
- **FAIL**: Score < 70

## Development

### Running Tests

```bash
uv run pytest
```

### Code Quality

Pre-commit hooks are configured for:
- Code formatting (black, isort)
- Linting (ruff)
- Type checking (mypy)

Install hooks:
```bash
uv run pre-commit install
```

### Adding New Analyzers

To create a custom analyzer:

1. Inherit from `BaseAnalyzer` in `amira_analysis/analyzers/base.py`
2. Implement the `analyze()` method
3. Return `ConversationAnalysis` object

Example:
```python
from amira_analysis.analyzers.base import BaseAnalyzer
from amira_analysis.models import ConversationAnalysis

class CustomAnalyzer(BaseAnalyzer):
    def analyze(self, conversation: dict) -> ConversationAnalysis:
        # Your analysis logic here
        return ConversationAnalysis(
            conversation_id=conversation["id"],
            overall_score=85,
            overall_verdict="PASS",
            # ... other fields
        )
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Use Cases

### Quality Assurance
- **Monitor Support Quality**: Track conversation quality metrics over time
- **Identify Training Gaps**: Find patterns in bot failures
- **Benchmark Performance**: Compare quality across time periods

### Bot Improvement
- **Prioritize Fixes**: Focus on highest-impact issues first
- **Test Changes**: Measure quality improvements after updates
- **A/B Testing**: Compare bot versions using quality scores

### Team Collaboration
- **Share Insights**: PDF reports for stakeholders
- **Track Progress**: JSON data for dashboards
- **Contest Management**: Identify prize candidate conversations

## Troubleshooting

### Common Issues

**Issue**: "No conversations found"
- **Solution**: Ensure conversations are in the correct directory and are valid JSON files

**Issue**: "API rate limit exceeded"
- **Solution**: Reduce `--max-workers` or add delays between requests

**Issue**: "Prize candidates missing conversation text"
- **Solution**: Ensure `--conversations-dir` points to directory with full conversation data

**Issue**: "Missing timestamps in PDF"
- **Solution**: Ensure conversation messages have `created_at` fields

## Performance

- **Analysis Speed**: ~5-10 seconds per conversation (depends on conversation length)
- **Parallel Processing**: Supports concurrent analysis with configurable workers
- **Memory Usage**: ~100MB per 1000 conversations
- **Report Generation**: ~1-5 seconds for 1000 conversations

## License

[Add your license here]

## Acknowledgments

- Built with [Claude](https://claude.ai) by Anthropic
- Uses [ReportLab](https://www.reportlab.com/) for PDF generation
- Powered by [uv](https://github.com/astral-sh/uv) for dependency management

## Support

For issues, questions, or contributions, please open an issue on GitHub.

---

**Built for AMira Learning** | AI-Powered Support Quality Analysis
