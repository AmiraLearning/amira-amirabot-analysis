"""Data models for report generation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Thresholds:
    """Configurable thresholds for analysis."""

    correctness_first_turn: int = 8  # out of 10
    escalation_good: int = 24  # out of 30 (80%)
    score_high: int = 70
    score_low: int = 50
    loops_fix_now: int = 2


@dataclass
class ConversationTriage:
    """Triaged conversation for priority action."""

    conversation_id: str
    overall_score: int
    overall_verdict: str
    priority: str  # "fix_now", "high", "medium", "low"
    reason: str
    flags: list[dict]
    prize_candidate: bool


@dataclass
class KPIMetrics:
    """Key performance indicators for support quality."""

    total_conversations: int
    pass_rate: float
    fail_rate: float
    avg_score: float
    obvious_answer_first_turn_pct: float
    escalation_within_two_turns_pct: float
    clear_next_step_pct: float
    avg_cycles_without_progress: float
    prize_candidates_count: int
    prize_candidates_pct: float


@dataclass
class PatternAnalysis:
    """Aggregated pattern analysis by issue type."""

    issue_type: str
    count: int
    coverage_pct: float  # % of unique conversations affected
    density: float  # avg flags per affected conversation
    severity_breakdown: dict[str, int]  # low/medium/high counts
    sample_conversations: list[str]  # top 3 conversation IDs
