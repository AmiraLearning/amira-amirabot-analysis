"""Generate actionable summary reports from conversation analyses."""

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from loguru import logger
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


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


class ReportGenerator:
    """Generate actionable summary reports from conversation analyses."""

    REQUIRED_TOP_KEYS = {"overall_score", "overall_verdict", "flags", "metrics"}

    def __init__(
        self,
        analyses_dir: Path,
        thresholds: Thresholds | None = None,
        conversations_json_path: Path | None = None,
        conversations_dir: Path | None = None,
    ):
        """Initialize report generator.

        Args:
            analyses_dir: Directory containing individual conversation JSONs
            thresholds: Optional custom thresholds for analysis
            conversations_json_path: Optional path to conversations.json for prize candidate details (legacy)
            conversations_dir: Optional directory containing individual conversation JSON files
        """
        self.analyses_dir = analyses_dir
        self.thresholds = thresholds or Thresholds()
        self.conversations_json_path = conversations_json_path
        self.conversations_dir = conversations_dir
        self.conversations = []
        self.conversations_lookup = {}
        self._load_conversations()

        # Load from conversations directory first (new approach), fall back to JSON file (legacy)
        if conversations_dir and conversations_dir.exists():
            self._load_full_conversations_from_dir()
        elif conversations_json_path and conversations_json_path.exists():
            self._load_full_conversations()

    def _validate_conversation(self, data: dict, path: Path) -> dict:
        """Validate and add defaults to conversation data.

        Args:
            data: Raw conversation data
            path: Path to JSON file for logging

        Returns:
            Validated conversation data with defaults
        """
        # Add safe defaults
        data.setdefault("flags", [])
        data.setdefault("metrics", {})
        data.setdefault("overall_score", 0)
        data.setdefault("overall_verdict", "UNKNOWN")
        data.setdefault("cycles_without_progress", 0)
        data.setdefault("has_clear_next_step", False)
        data.setdefault("prize_candidate", False)

        # Log missing required keys
        missing = self.REQUIRED_TOP_KEYS - set(data.keys())
        if missing:
            logger.warning(f"{path.name}: missing keys {missing}")

        return data

    def _load_conversations(self) -> None:
        """Load all conversation analysis JSONs."""
        if not self.analyses_dir.exists():
            logger.error(f"Directory {self.analyses_dir} does not exist")
            return

        json_files = list(self.analyses_dir.glob("*.json"))
        logger.info(f"Loading {len(json_files)} conversation analyses...")

        for json_file in json_files:
            try:
                with json_file.open("r") as f:
                    data = json.load(f)
                    data["conversation_id"] = json_file.stem
                    validated_data = self._validate_conversation(data, json_file)
                    self.conversations.append(validated_data)
            except Exception as e:
                logger.error(f"Error loading {json_file}: {e}")

        logger.info(f"Loaded {len(self.conversations)} conversations")

    def _load_full_conversations(self) -> None:
        """Load full conversation data from conversations.json."""
        if (
            not self.conversations_json_path
            or not self.conversations_json_path.exists()
        ):
            logger.warning(
                f"Conversations JSON file not found at {self.conversations_json_path}, "
                "prize candidates will not have full text"
            )
            return

        try:
            logger.info(
                f"Loading full conversations from {self.conversations_json_path}"
            )
            with self.conversations_json_path.open("r") as f:
                conversations_data = json.load(f)

            if not isinstance(conversations_data, list):
                logger.error(
                    f"Expected conversations.json to contain a list, got {type(conversations_data)}"
                )
                return

            for conv in conversations_data:
                conv_id = conv.get("id")
                if conv_id:
                    self.conversations_lookup[conv_id] = conv

            logger.info(
                f"Loaded {len(self.conversations_lookup)} full conversations into lookup"
            )

            # Debug: Show sample of conversation IDs
            if self.conversations_lookup:
                sample_ids = list(self.conversations_lookup.keys())[:3]
                logger.debug(f"Sample conversation IDs in lookup: {sample_ids}")

        except Exception as e:
            logger.error(f"Error loading conversations.json: {e}")
            raise

    def _load_full_conversations_from_dir(self) -> None:
        """Load full conversation data from individual JSON files in conversations/ directory."""
        if not self.conversations_dir or not self.conversations_dir.exists():
            logger.warning(
                f"Conversations directory not found at {self.conversations_dir}, "
                "prize candidates will not have full text"
            )
            return

        try:
            logger.info(f"Loading full conversations from {self.conversations_dir}/")

            json_files = list(self.conversations_dir.glob("*.json"))
            logger.info(f"Found {len(json_files)} conversation files")

            for json_file in json_files:
                try:
                    with json_file.open("r") as f:
                        conv = json.load(f)

                    conv_id = conv.get("id")
                    if conv_id:
                        self.conversations_lookup[conv_id] = conv
                except Exception as e:
                    logger.error(f"Error loading {json_file}: {e}")
                    continue

            logger.info(
                f"Loaded {len(self.conversations_lookup)} full conversations into lookup"
            )

            # Debug: Show sample of conversation IDs
            if self.conversations_lookup:
                sample_ids = list(self.conversations_lookup.keys())[:3]
                logger.debug(f"Sample conversation IDs in lookup: {sample_ids}")

        except Exception as e:
            logger.error(f"Error loading conversations from directory: {e}")
            raise

    def _format_conversation_text(self, conversation_id: str) -> str:
        """Format conversation messages as readable text with conversation date header.

        Args:
            conversation_id: The conversation ID

        Returns:
            Formatted conversation text with conversation date and role labels with timestamps
        """
        logger.debug(f"Formatting conversation {conversation_id}")
        logger.debug(
            f"Conversations lookup has {len(self.conversations_lookup)} entries"
        )

        conv = self.conversations_lookup.get(conversation_id)
        if not conv:
            logger.error(
                f"Conversation {conversation_id} not found in lookup! "
                f"Available keys sample: {list(self.conversations_lookup.keys())[:5]}"
            )
            return "Conversation text not available"

        messages = conv.get("messages", [])
        if not messages:
            return "No messages in conversation"

        formatted_lines: list[str] = []

        # Add conversation date header
        conv_date_str = ""
        conv_created_at = conv.get("created_at")
        if conv_created_at:
            try:
                # Try parsing ISO format timestamp
                dt = datetime.fromisoformat(conv_created_at.replace("Z", "+00:00"))
                conv_date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, AttributeError):
                # Try parsing as milliseconds since epoch
                try:
                    dt = datetime.fromtimestamp(int(conv_created_at) / 1000)
                    conv_date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    # Fall back to first message timestamp if available
                    if messages:
                        first_msg_created = messages[0].get("created_at")
                        if first_msg_created:
                            try:
                                dt = datetime.fromisoformat(
                                    first_msg_created.replace("Z", "+00:00")
                                )
                                conv_date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                            except (ValueError, AttributeError):
                                try:
                                    dt = datetime.fromtimestamp(
                                        int(first_msg_created) / 1000
                                    )
                                    conv_date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                                except (ValueError, TypeError):
                                    pass

        if conv_date_str:
            formatted_lines.append(f"=== CONVERSATION DATE: {conv_date_str} ===")
            formatted_lines.append("")

        # Format each message with timestamp
        for idx, msg in enumerate(messages, 1):
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")

            # Format timestamp if available
            timestamp_str = ""
            created_at = msg.get("created_at")
            if created_at:
                try:
                    # Try parsing ISO format timestamp
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, AttributeError):
                    # Try parsing as milliseconds since epoch
                    try:
                        dt = datetime.fromtimestamp(int(created_at) / 1000)
                        timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        timestamp_str = str(created_at) if created_at else ""

            # Format message with timestamp
            if timestamp_str:
                formatted_lines.append(f"[{idx}] {timestamp_str} - {role}: {content}")
            else:
                formatted_lines.append(f"[{idx}] {role}: {content}")

        return "\n\n".join(formatted_lines)

    def get_top_prize_candidates(self, limit: int = 10) -> list[dict]:
        """Get top prize candidate conversations with full formatted text.

        Args:
            limit: Number of top prize candidates to return

        Returns:
            List of dicts containing conversation data and formatted text
        """
        prize_candidates = [
            conv for conv in self.conversations if conv.get("prize_candidate", False)
        ]

        # Sort by score (lowest first = worst quality)
        prize_candidates.sort(key=lambda x: x.get("overall_score", 100))

        # Validate that we have conversation data for prize candidates
        if prize_candidates and not self.conversations_lookup:
            logger.error(
                "Prize candidates found but no conversation data loaded! "
                "Ensure conversations.json is available."
            )
            raise ValueError(
                "Cannot generate prize candidates without full conversation data. "
                "conversations.json is required."
            )

        top_candidates = []
        for conv in prize_candidates[:limit]:
            conv_id = conv["conversation_id"]

            # Verify conversation exists in lookup
            if conv_id not in self.conversations_lookup:
                logger.warning(
                    f"Prize candidate {conv_id} not found in conversations.json - skipping. "
                    f"The conversation may have been deleted or is from an older dataset."
                )
                continue

            formatted_text = self._format_conversation_text(conv_id)
            if formatted_text == "Conversation text not available":
                logger.warning(f"Could not format conversation {conv_id} - skipping")
                continue

            top_candidates.append(
                {
                    "conversation_id": conv_id,
                    "overall_score": conv.get("overall_score", 0),
                    "prize_reason": conv.get("prize_reason", ""),
                    "summary": conv.get("summary", ""),
                    "formatted_text": formatted_text,
                }
            )

        return top_candidates

    def triage_conversations(self) -> list[ConversationTriage]:
        """Triage conversations by priority based on severity and impact.

        Returns:
            List of triaged conversations sorted by priority
        """
        triaged = []

        for conv in self.conversations:
            flags = conv.get("flags", [])
            cycles = conv.get("cycles_without_progress", 0)
            prize = conv.get("prize_candidate", False)
            score = conv.get("overall_score", 100)
            has_clear_next_step = conv.get("has_clear_next_step", False)

            # Determine priority using thresholds
            priority = "low"
            reason = "Minor issues"

            # Fix Now: Explicit hard-fail conditions
            if any(
                f.get("severity") == "high"
                and f.get("type") in ["MISSED_ESCALATION", "DEAD_END"]
                for f in flags
            ):
                priority = "fix_now"
                reason = "High-severity MISSED_ESCALATION or DEAD_END"
            elif cycles >= self.thresholds.loops_fix_now:
                priority = "fix_now"
                reason = f"Futile loop: {cycles} cycles without progress"
            elif not has_clear_next_step and any(
                f.get("type") == "DEAD_END" for f in flags
            ):
                priority = "fix_now"
                reason = "Final turn has no clear next step"
            elif any(
                f.get("severity") == "high" and f.get("type") == "OBVIOUS_WRONG_ANSWER"
                for f in flags
            ):
                priority = "fix_now"
                reason = "High-severity OBVIOUS_WRONG_ANSWER"
            elif prize:
                priority = "high"
                reason = "Prize candidate: clear impediment to good support"
            elif score < self.thresholds.score_low:
                priority = "high"
                reason = f"Low quality score: {score}/100"
            elif score < self.thresholds.score_high:
                priority = "medium"
                reason = f"Below-average score: {score}/100"

            triaged.append(
                ConversationTriage(
                    conversation_id=conv["conversation_id"],
                    overall_score=score,
                    overall_verdict=conv.get("overall_verdict", "UNKNOWN"),
                    priority=priority,
                    reason=reason,
                    flags=flags,
                    prize_candidate=prize,
                )
            )

        # Sort by priority
        priority_order = {"fix_now": 0, "high": 1, "medium": 2, "low": 3}
        triaged.sort(key=lambda x: (priority_order[x.priority], x.overall_score))

        return triaged

    def calculate_kpis(self) -> KPIMetrics:
        """Calculate key performance indicators.

        Returns:
            KPIMetrics with calculated values
        """
        if not self.conversations:
            return KPIMetrics(
                total_conversations=0,
                pass_rate=0.0,
                fail_rate=0.0,
                avg_score=0.0,
                obvious_answer_first_turn_pct=0.0,
                escalation_within_two_turns_pct=0.0,
                clear_next_step_pct=0.0,
                avg_cycles_without_progress=0.0,
                prize_candidates_count=0,
                prize_candidates_pct=0.0,
            )

        total = len(self.conversations)
        pass_count = sum(
            1 for c in self.conversations if c.get("overall_verdict") == "PASS"
        )
        fail_count = total - pass_count

        scores = [c.get("overall_score", 0) for c in self.conversations]
        avg_score = sum(scores) / total if total > 0 else 0

        # Use explicit booleans when available; fall back to score heuristics
        obvious_answer_count = sum(
            1
            for c in self.conversations
            if c.get("first_turn_obvious") is True
            or (
                c.get("first_turn_obvious") is None
                and c.get("metrics", {}).get("correctness_score", 0)
                >= self.thresholds.correctness_first_turn
            )
        )

        good_escalation_count = sum(
            1
            for c in self.conversations
            if c.get("escalated_within_two_turns") is True
            or (
                c.get("escalated_within_two_turns") is None
                and c.get("metrics", {}).get("escalation_score", 0)
                >= self.thresholds.escalation_good
            )
        )

        # Clear next step (use explicit boolean)
        clear_next_step_count = sum(
            1 for c in self.conversations if c.get("has_clear_next_step") is True
        )

        # Cycles without progress
        cycles = [c.get("cycles_without_progress", 0) for c in self.conversations]
        avg_cycles = sum(cycles) / total if total > 0 else 0

        # Prize candidates
        prize_count = sum(
            1 for c in self.conversations if c.get("prize_candidate", False)
        )

        return KPIMetrics(
            total_conversations=total,
            pass_rate=pass_count / total if total > 0 else 0,
            fail_rate=fail_count / total if total > 0 else 0,
            avg_score=avg_score,
            obvious_answer_first_turn_pct=obvious_answer_count / total
            if total > 0
            else 0,
            escalation_within_two_turns_pct=good_escalation_count / total
            if total > 0
            else 0,
            clear_next_step_pct=clear_next_step_count / total if total > 0 else 0,
            avg_cycles_without_progress=avg_cycles,
            prize_candidates_count=prize_count,
            prize_candidates_pct=prize_count / total if total > 0 else 0,
        )

    def analyze_patterns(self) -> list[PatternAnalysis]:
        """Analyze patterns by issue type.

        Returns:
            List of pattern analyses sorted by count
        """
        issue_counts = Counter()
        severity_by_type = defaultdict(lambda: {"low": 0, "medium": 0, "high": 0})
        conversations_by_type = defaultdict(list)
        affected_conversations = defaultdict(
            set
        )  # Track unique conversations per issue

        total_conversations = len(self.conversations)

        for conv in self.conversations:
            conv_id = conv["conversation_id"]
            for flag in conv.get("flags", []):
                issue_type = flag.get("type", "UNKNOWN")
                severity = flag.get("severity", "medium")

                issue_counts[issue_type] += 1
                severity_by_type[issue_type][severity] += 1
                conversations_by_type[issue_type].append(
                    (conv_id, conv.get("overall_score", 100))
                )
                affected_conversations[issue_type].add(conv_id)

        patterns = []
        for issue_type, count in issue_counts.most_common():
            # Get top 3 worst conversations for this issue type
            top_convos = sorted(conversations_by_type[issue_type], key=lambda x: x[1])[
                :3
            ]
            sample_ids = [c[0] for c in top_convos]

            # Calculate coverage (unique conversations affected) and density
            unique_convos = len(affected_conversations[issue_type])
            coverage_pct = (
                unique_convos / total_conversations if total_conversations > 0 else 0.0
            )
            density = count / unique_convos if unique_convos > 0 else 0.0

            patterns.append(
                PatternAnalysis(
                    issue_type=issue_type,
                    count=count,
                    coverage_pct=coverage_pct,
                    density=density,
                    severity_breakdown=dict(severity_by_type[issue_type]),
                    sample_conversations=sample_ids,
                )
            )

        return patterns

    def generate_actionable_fixes(
        self, patterns: list[PatternAnalysis]
    ) -> dict[str, dict]:
        """Generate actionable fixes based on patterns.

        Args:
            patterns: List of pattern analyses

        Returns:
            Dictionary mapping issue types to fix recommendations
        """
        fix_map = {
            "OBVIOUS_WRONG_ANSWER": {
                "likely_cause": "Missing/ambiguous FAQ, retrieval misses",
                "fixes": [
                    "Add/clarify FAQ snippet with canonical phrasing",
                    "Add deterministic pattern → answer rule for common questions",
                    "Retrieval tweak: boost exact-match titles/IDs for top intents",
                ],
                "priority": "high",
            },
            "MISSED_ESCALATION": {
                "likely_cause": "Bot keeps trying despite permissions/limited access",
                "fixes": [
                    'Rule: "If blocked ≥1 turn by identity/billing/file access → escalate"',
                    "Add Handoff Macro with who/when/how + checklist",
                    "Instrument: flag any thread where same instruction is repeated twice",
                ],
                "priority": "critical",
            },
            "DUMB_QUESTION": {
                "likely_cause": "Bot not reading prior turns or metadata",
                "fixes": [
                    'Context-check rule: "Before asking, scan last 5 turns for the info"',
                    "Restrict clarifying questions to one specific ask with rationale",
                    "Auto-infer common fields (email, role, district) from header when present",
                ],
                "priority": "high",
            },
            "REPETITIVE": {
                "likely_cause": "No tactic switch after a failed step",
                "fixes": [
                    '"No-repeat" guard: after a repeat, switch to escalation or new path',
                    'Add "If X didn\'t work, try Y" playbooks (device, network, SSO, roster)',
                ],
                "priority": "high",
            },
            "LACK_OF_ENCOURAGEMENT": {
                "likely_cause": "Neutral/defensive tone, no path forward",
                "fixes": [
                    "Add tone snippet bank with encouraging language",
                    "Always pair an apology with a next step or reassuring path",
                ],
                "priority": "medium",
            },
            "DEAD_END": {
                "likely_cause": "Final turn lacks link/step/timeline",
                "fixes": [
                    "Footer macro: one action, one link, one timeline—always",
                    "Guard: every final bot message must have actionable next step",
                ],
                "priority": "critical",
            },
        }

        actionable = {}
        for pattern in patterns:
            if pattern.issue_type in fix_map:
                actionable[pattern.issue_type] = {
                    **fix_map[pattern.issue_type],
                    "occurrence_count": pattern.count,
                    "affected_conversations_pct": f"{pattern.coverage_pct * 100:.1f}%",
                    "severity_breakdown": pattern.severity_breakdown,
                    "sample_conversations": pattern.sample_conversations[:3],
                }

        return actionable

    def _get_date_range(self) -> tuple[str, str]:
        """Get the first and latest conversation dates.

        Returns:
            Tuple of (first_date, latest_date) in YYYY-MM-DD format, or ("N/A", "N/A") if no dates available
        """
        dates = []

        for conv in self.conversations:
            conv_id = conv.get("conversation_id")
            if not conv_id:
                continue

            # Try to get the conversation from lookup
            full_conv = self.conversations_lookup.get(conv_id)
            if not full_conv:
                continue

            # Try conversation-level created_at
            created_at = full_conv.get("created_at")
            if not created_at:
                # Fall back to first message timestamp
                messages = full_conv.get("messages", [])
                if messages:
                    created_at = messages[0].get("created_at")

            if created_at:
                try:
                    # Try parsing ISO format timestamp
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    dates.append(dt)
                except (ValueError, AttributeError):
                    # Try parsing as milliseconds since epoch
                    try:
                        dt = datetime.fromtimestamp(int(created_at) / 1000)
                        dates.append(dt)
                    except (ValueError, TypeError):
                        pass

        if not dates:
            return ("N/A", "N/A")

        dates.sort()
        first_date = dates[0].strftime("%Y-%m-%d")
        latest_date = dates[-1].strftime("%Y-%m-%d")

        return (first_date, latest_date)

    @staticmethod
    def generate_bot_feedback(conv: dict) -> list[dict]:
        """Generate actionable bot feedback items from conversation flags.

        Args:
            conv: Conversation data dictionary

        Returns:
            List of actionable feedback items with rewrites and macros
        """
        items = []
        flags = conv.get("flags", [])
        cycles = conv.get("cycles_without_progress", 0)

        for f in flags:
            issue_type = f.get("type")
            if issue_type == "MISSED_ESCALATION":
                items.append(
                    {
                        "issue": "Missed escalation",
                        "why_it_matters": "User blocked; bot kept churning.",
                        "recommended_rule": "If blocked by permissions/identity/file access, escalate within 1 turn.",
                        "handoff_macro": (
                            "I'm limited by account permissions here. I'll loop in Support now.\n"
                            "What I'll send: your email, district, school, error time, screenshot.\n"
                            "What I need: teacher/student ID and class/section.\n"
                            "You'll hear from a human by today 5pm ET."
                        ),
                        "example_rewrite": (
                            "It looks like I don't have permission to view those class records. I'll escalate this now.\n"
                            "Please share the teacher ID or section code so our agent can resolve this on the first reply."
                        ),
                    }
                )
            elif issue_type == "DEAD_END":
                items.append(
                    {
                        "issue": "Dead end",
                        "why_it_matters": "User has no path forward.",
                        "recommended_rule": "Final bot turn must include one action, one link, one timeline.",
                        "footer_macro": "Next step: [Open the Roster Sync Guide]. If that doesn't work, reply 'human' and I'll hand this to an agent today.",
                        "example_rewrite": (
                            "Try this next: [Roster Sync Guide]. If it doesn't resolve it, reply 'human' and I'll hand this to Support now."
                        ),
                    }
                )
            elif issue_type == "REPETITIVE" and cycles >= 2:
                items.append(
                    {
                        "issue": "Futile loop",
                        "why_it_matters": "Wastes user time and trust.",
                        "recommended_rule": "After repeating an instruction once, switch strategy or escalate.",
                        "example_rewrite": "Since retrying didn't work, let's switch paths: are you using Google, Clever, or ClassLink SSO?",
                    }
                )
            elif issue_type == "DUMB_QUESTION":
                items.append(
                    {
                        "issue": "Unnecessary ask",
                        "why_it_matters": "Asking for info already present.",
                        "recommended_rule": "Scan last 5 turns and headers before asking; restrict to one clarifying question with rationale.",
                        "example_rewrite": "I see you're writing from april.smith@district.org. If a different account is affected, tell me which one.",
                    }
                )
            elif issue_type == "OBVIOUS_WRONG_ANSWER":
                items.append(
                    {
                        "issue": "Wrong answer",
                        "why_it_matters": "Damages user trust and wastes time.",
                        "recommended_rule": "Add FAQ or deterministic rule for this common question.",
                        "example_rewrite": "Review the correct answer and add to knowledge base.",
                    }
                )
            elif issue_type == "LACK_OF_ENCOURAGEMENT":
                items.append(
                    {
                        "issue": "Discouraging tone",
                        "why_it_matters": "No clear path to success for user.",
                        "recommended_rule": "Always pair apology with next step or reassurance.",
                        "example_rewrite": "You're close—we'll get this sorted. If the first step doesn't resolve it, try the next one or reply 'human' and I'll escalate.",
                    }
                )

        return items

    def generate_report(self, output_path: Path) -> None:
        """Generate comprehensive actionable summary report.

        Args:
            output_path: Path where report should be saved
        """
        logger.info("Generating actionable summary report...")

        triaged = self.triage_conversations()
        kpis = self.calculate_kpis()
        patterns = self.analyze_patterns()
        fixes = self.generate_actionable_fixes(patterns)
        first_date, latest_date = self._get_date_range()

        # Generate markdown report
        report_lines = [
            "# Conversation Quality Analysis Report",
            "",
            f"**Total Conversations Analyzed:** {kpis.total_conversations}",
            f"**First Date:** {first_date}",
            f"**Latest Date:** {latest_date}",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            f"- **Overall Pass Rate:** {kpis.pass_rate * 100:.1f}% ({int(kpis.pass_rate * kpis.total_conversations)} PASS / {int(kpis.fail_rate * kpis.total_conversations)} FAIL)",
            f"- **Average Quality Score:** {kpis.avg_score:.1f}/100",
            f"- **Prize Candidates (High-Impact Issues):** {kpis.prize_candidates_count} ({kpis.prize_candidates_pct * 100:.1f}%)",
            "",
            "---",
            "",
            "## Key Performance Indicators",
            "",
            "### Health Metrics",
            "",
            "| Metric | Value | Target |",
            "|--------|-------|--------|",
            f"| Obvious Answer Resolution (≤1 turn) | {kpis.obvious_answer_first_turn_pct * 100:.1f}% | ≥80% |",
            f"| Good Escalation Quality | {kpis.escalation_within_two_turns_pct * 100:.1f}% | ≥90% |",
            f"| Clear Next Step (final turn) | {kpis.clear_next_step_pct * 100:.1f}% | 100% |",
            f"| Avg Cycles Without Progress | {kpis.avg_cycles_without_progress:.2f} | <1.0 |",
            "",
            "---",
            "",
            "## Priority Triage",
            "",
            "### FIX NOW (Critical Issues)",
            "",
        ]

        # Add fix now items
        fix_now = [t for t in triaged if t.priority == "fix_now"]
        if fix_now:
            report_lines.append(
                f"**{len(fix_now)} conversations require immediate attention**"
            )
            report_lines.append("")
            for item in fix_now[:10]:  # Top 10
                report_lines.append(f"- **{item.conversation_id}**")
                report_lines.append(f"  - Score: {item.overall_score}/100")
                report_lines.append(f"  - Reason: {item.reason}")
                report_lines.append(
                    f"  - Issues: {', '.join(f.get('type', 'UNKNOWN') for f in item.flags)}"
                )
                report_lines.append("")
        else:
            report_lines.append("✓ No critical issues requiring immediate fixes")
            report_lines.append("")

        # High priority
        high_priority = [t for t in triaged if t.priority == "high"]
        if high_priority:
            report_lines.extend(
                [
                    "### HIGH Priority",
                    "",
                    f"**{len(high_priority)} conversations** need attention soon",
                    "",
                ]
            )

        # Add pattern analysis
        report_lines.extend(
            [
                "---",
                "",
                "## Pattern Analysis",
                "",
                "### Issues by Type",
                "",
                "| Issue Type | Count | Coverage % | Density | High | Med | Low |",
                "|------------|-------|------------|---------|------|-----|-----|",
            ]
        )

        for pattern in patterns:
            sev = pattern.severity_breakdown
            report_lines.append(
                f"| {pattern.issue_type} | {pattern.count} | {pattern.coverage_pct * 100:.1f}% | {pattern.density:.2f} | {sev.get('high', 0)} | {sev.get('medium', 0)} | {sev.get('low', 0)} |"
            )

        report_lines.extend(["", "---", "", "## Actionable Fixes", ""])

        # Add fixes with priority order
        priority_order = ["critical", "high", "medium"]
        for priority in priority_order:
            priority_fixes = {
                k: v for k, v in fixes.items() if v.get("priority") == priority
            }

            if priority_fixes:
                report_lines.extend([f"### {priority.upper()} Priority Fixes", ""])

                for issue_type, fix_info in priority_fixes.items():
                    report_lines.extend(
                        [
                            f"#### {issue_type}",
                            "",
                            f"**Occurrences:** {fix_info['occurrence_count']} ({fix_info['affected_conversations_pct']} of conversations)",
                            "",
                            f"**Likely Cause:** {fix_info['likely_cause']}",
                            "",
                            "**Recommended Fixes:**",
                            "",
                        ]
                    )

                    for i, fix in enumerate(fix_info["fixes"], 1):
                        report_lines.append(f"{i}. {fix}")

                    report_lines.extend(
                        [
                            "",
                            f"**Sample Conversations:** {', '.join(fix_info['sample_conversations'])}",
                            "",
                            "---",
                            "",
                        ]
                    )

        # Add snippet bank
        report_lines.extend(
            [
                "## Copy-Paste Snippet Bank",
                "",
                "### Escalation Handoff (for MISSED_ESCALATION)",
                "",
                "```",
                "I'm limited by account permissions to proceed here. I'll loop in our Support team now.",
                "What I'll send: your email, district, school, error time, and screenshot (if available).",
                "What I need from you: student/teacher ID and exact class/section.",
                "You'll hear from a human by today 5pm ET at this address.",
                "```",
                "",
                "### Dead-End Guard (for DEAD_END)",
                "",
                "```",
                "Next step: [Open the Guide]. If that doesn't work, reply 'human' and I'll hand this to an agent with your details.",
                "```",
                "",
                "### Encouragement Close (for LACK_OF_ENCOURAGEMENT)",
                "",
                "```",
                "You're close—we'll get this sorted. If the first step doesn't resolve it, try the next one or reply 'human' and I'll escalate.",
                "```",
                "",
                "### Smart Clarifying (for DUMB_QUESTION)",
                "",
                "```",
                "I can fix this if I know which SSO provider you use (Google | ClassLink | Clever). Which is it?",
                "```",
                "",
                "---",
                "",
                "## Next Steps",
                "",
                "1. **Address FIX NOW items** - Review critical conversations and apply fixes",
                f"2. **Implement top {min(3, len(fixes))} actionable fixes** - Focus on critical and high priority",
                "3. **Update bot prompts/policies** - Use snippet bank for consistent responses",
                "4. **Re-run analysis** - Measure improvement after changes",
                "5. **Set up monitoring** - Track KPIs weekly to ensure sustained quality",
                "",
                f"**Report Generated:** {kpis.total_conversations} conversations analyzed",
            ]
        )

        # Save report
        with output_path.open("w") as f:
            f.write("\n".join(report_lines))

        logger.success(f"Report saved to {output_path}")

        # Also save JSON summary for programmatic access
        summary_json = {
            "kpis": {
                "total_conversations": kpis.total_conversations,
                "pass_rate": kpis.pass_rate,
                "fail_rate": kpis.fail_rate,
                "avg_score": kpis.avg_score,
                "obvious_answer_first_turn_pct": kpis.obvious_answer_first_turn_pct,
                "escalation_within_two_turns_pct": kpis.escalation_within_two_turns_pct,
                "clear_next_step_pct": kpis.clear_next_step_pct,
                "avg_cycles_without_progress": kpis.avg_cycles_without_progress,
                "prize_candidates_count": kpis.prize_candidates_count,
                "prize_candidates_pct": kpis.prize_candidates_pct,
            },
            "triage": {
                "fix_now": len([t for t in triaged if t.priority == "fix_now"]),
                "high": len([t for t in triaged if t.priority == "high"]),
                "medium": len([t for t in triaged if t.priority == "medium"]),
                "low": len([t for t in triaged if t.priority == "low"]),
            },
            "patterns": [
                {
                    "issue_type": p.issue_type,
                    "count": p.count,
                    "coverage_pct": p.coverage_pct,
                    "density": p.density,
                    "severity_breakdown": p.severity_breakdown,
                }
                for p in patterns
            ],
            "actionable_fixes": fixes,
        }

        json_path = output_path.with_suffix(".json")
        with json_path.open("w") as f:
            json.dump(summary_json, f, indent=2)

        logger.success(f"Summary JSON saved to {json_path}")

        # Generate PDF report
        pdf_path = output_path.with_suffix(".pdf")
        self.generate_pdf_report(
            output_path=pdf_path,
            kpis=kpis,
            triaged=triaged,
            patterns=patterns,
            fixes=fixes,
            first_date=first_date,
            latest_date=latest_date,
        )

    def generate_pdf_report(
        self,
        output_path: Path,
        kpis: KPIMetrics,
        triaged: list[ConversationTriage],
        patterns: list[PatternAnalysis],
        fixes: dict[str, dict],
        first_date: str = "N/A",
        latest_date: str = "N/A",
    ) -> None:
        """Generate a PDF version of the summary report.

        Args:
            output_path: Path where PDF should be saved
            kpis: KPI metrics
            triaged: Triaged conversations
            patterns: Pattern analyses
            fixes: Actionable fixes
            first_date: First conversation date (YYYY-MM-DD)
            latest_date: Latest conversation date (YYYY-MM-DD)
        """
        logger.info("Generating PDF report...")

        # Create output directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create PDF
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=24,
            textColor=colors.HexColor("#1f77b4"),
            spaceAfter=30,
        )
        heading_style = ParagraphStyle(
            "CustomHeading", parent=styles["Heading2"], fontSize=16, spaceAfter=12
        )
        subheading_style = ParagraphStyle(
            "CustomSubHeading", parent=styles["Heading3"], fontSize=12, spaceAfter=10
        )

        # Build story
        story: list[Flowable] = []

        # Title
        story.append(Paragraph("Conversation Quality Analysis Report", title_style))
        story.append(
            Paragraph(
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 0.3 * inch))

        # Executive Summary
        story.append(Paragraph("Executive Summary", heading_style))
        summary_data = [
            ["Metric", "Value"],
            ["Total Conversations", str(kpis.total_conversations)],
            ["First Date", first_date],
            ["Latest Date", latest_date],
            [
                "Pass Rate",
                f"{kpis.pass_rate * 100:.1f}% ({int(kpis.pass_rate * kpis.total_conversations)} PASS)",
            ],
            [
                "Fail Rate",
                f"{kpis.fail_rate * 100:.1f}% ({int(kpis.fail_rate * kpis.total_conversations)} FAIL)",
            ],
            ["Average Score", f"{kpis.avg_score:.1f}/100"],
            [
                "Prize Candidates",
                f"{kpis.prize_candidates_count} ({kpis.prize_candidates_pct * 100:.1f}%)",
            ],
        ]
        summary_table = Table(summary_data, colWidths=[3.5 * inch, 2.5 * inch])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )
        story.append(summary_table)
        story.append(Spacer(1, 0.3 * inch))

        # KPIs
        story.append(Paragraph("Key Performance Indicators", heading_style))
        kpi_data = [
            ["Metric", "Value", "Target", "Status"],
            [
                "Obvious Answer (≤1 turn)",
                f"{kpis.obvious_answer_first_turn_pct * 100:.1f}%",
                "≥80%",
                "✓" if kpis.obvious_answer_first_turn_pct >= 0.8 else "✗",
            ],
            [
                "Good Escalation Quality",
                f"{kpis.escalation_within_two_turns_pct * 100:.1f}%",
                "≥90%",
                "✓" if kpis.escalation_within_two_turns_pct >= 0.9 else "✗",
            ],
            [
                "Clear Next Step",
                f"{kpis.clear_next_step_pct * 100:.1f}%",
                "100%",
                "✓" if kpis.clear_next_step_pct >= 1.0 else "✗",
            ],
            [
                "Cycles Without Progress",
                f"{kpis.avg_cycles_without_progress:.2f}",
                "<1.0",
                "✓" if kpis.avg_cycles_without_progress < 1.0 else "✗",
            ],
        ]
        kpi_table = Table(
            kpi_data, colWidths=[2.5 * inch, 1.5 * inch, 1.0 * inch, 1.0 * inch]
        )
        kpi_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )
        story.append(kpi_table)
        story.append(Spacer(1, 0.3 * inch))

        # Triage Summary
        story.append(Paragraph("Priority Triage", heading_style))
        fix_now = [t for t in triaged if t.priority == "fix_now"]
        high_priority = [t for t in triaged if t.priority == "high"]
        medium_priority = [t for t in triaged if t.priority == "medium"]

        triage_data = [
            ["Priority", "Count", "% of Total"],
            [
                "FIX NOW (Critical)",
                str(len(fix_now)),
                f"{len(fix_now) / len(triaged) * 100:.1f}%" if triaged else "0%",
            ],
            [
                "High",
                str(len(high_priority)),
                f"{len(high_priority) / len(triaged) * 100:.1f}%" if triaged else "0%",
            ],
            [
                "Medium",
                str(len(medium_priority)),
                f"{len(medium_priority) / len(triaged) * 100:.1f}%"
                if triaged
                else "0%",
            ],
        ]
        triage_table = Table(
            triage_data, colWidths=[3.0 * inch, 1.5 * inch, 1.5 * inch]
        )
        triage_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("BACKGROUND", (0, 1), (-1, 1), colors.Color(1, 0.8, 0.8)),
                ]
            )
        )
        story.append(triage_table)
        story.append(Spacer(1, 0.2 * inch))

        # Top Fix Now Items - Start on new page
        story.append(PageBreak())
        if fix_now:
            story.append(
                Paragraph(
                    f"Top {min(10, len(fix_now))} Critical Issues", subheading_style
                )
            )
            story.append(
                Paragraph(
                    "<i>See Appendix A for full conversation transcripts</i>",
                    styles["Italic"],
                )
            )
            story.append(Spacer(1, 0.2 * inch))
            for i, item in enumerate(fix_now[:10], 1):
                story.append(
                    Paragraph(
                        f"<b>{i}. {item.conversation_id[:20]}...</b> (Score: {item.overall_score}/100)",
                        styles["Normal"],
                    )
                )
                story.append(Paragraph(f"   Reason: {item.reason}", styles["Normal"]))
                story.append(Spacer(1, 0.1 * inch))

        story.append(PageBreak())

        # Pattern Analysis
        story.append(Paragraph("Pattern Analysis", heading_style))
        story.append(Paragraph("Issues by Type", subheading_style))

        pattern_data = [
            ["Issue Type", "Count", "Coverage", "Density", "High", "Med", "Low"]
        ]
        for pattern in patterns[:10]:  # Top 10
            sev = pattern.severity_breakdown
            pattern_data.append(
                [
                    pattern.issue_type,
                    str(pattern.count),
                    f"{pattern.coverage_pct * 100:.1f}%",
                    f"{pattern.density:.2f}",
                    str(sev.get("high", 0)),
                    str(sev.get("medium", 0)),
                    str(sev.get("low", 0)),
                ]
            )

        pattern_table = Table(
            pattern_data,
            colWidths=[
                1.8 * inch,
                0.7 * inch,
                0.7 * inch,
                0.7 * inch,
                0.6 * inch,
                0.6 * inch,
                0.6 * inch,
            ],
        )
        pattern_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )
        story.append(pattern_table)
        story.append(Spacer(1, 0.3 * inch))

        # Actionable Fixes
        story.append(Paragraph("Actionable Fixes", heading_style))

        priority_order = ["critical", "high", "medium"]
        for priority in priority_order:
            priority_fixes = {
                k: v for k, v in fixes.items() if v.get("priority") == priority
            }

            if priority_fixes:
                story.append(
                    Paragraph(f"{priority.upper()} Priority", subheading_style)
                )

                for issue_type, fix_info in priority_fixes.items():
                    story.append(
                        Paragraph(
                            f"<b>{issue_type}</b> ({fix_info['occurrence_count']} occurrences)",
                            styles["Normal"],
                        )
                    )
                    story.append(Spacer(1, 0.05 * inch))
                    story.append(
                        Paragraph(
                            f"<i>Cause:</i> {fix_info['likely_cause']}",
                            styles["Normal"],
                        )
                    )
                    story.append(Spacer(1, 0.05 * inch))
                    story.append(
                        Paragraph("<i>Recommended Fixes:</i>", styles["Normal"])
                    )

                    for fix in fix_info["fixes"]:
                        story.append(Paragraph(f"• {fix}", styles["Normal"]))

                    story.append(Spacer(1, 0.2 * inch))

        # Appendix A: Top 10 Prize Candidates Section
        story.append(PageBreak())
        story.append(
            Paragraph("Appendix A: Top 10 Prize Candidate Conversations", heading_style)
        )
        story.append(
            Paragraph(
                "These conversations demonstrate clear impediments to good support and are candidates for the $500 gift card prize.",
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 0.3 * inch))

        top_candidates = self.get_top_prize_candidates(limit=10)

        if not top_candidates:
            story.append(
                Paragraph(
                    "No prize candidates identified in this analysis.", styles["Italic"]
                )
            )
        else:
            for idx, candidate in enumerate(top_candidates, 1):
                # Add page break before each conversation (except the first)
                if idx > 1:
                    story.append(PageBreak())

                # Candidate header
                story.append(
                    Paragraph(
                        f"Prize Candidate #{idx}: {candidate['conversation_id']}",
                        subheading_style,
                    )
                )

                # Metadata table (using Paragraph for wrapping)
                candidate_data = [
                    [
                        Paragraph("<b>Metric</b>", styles["Normal"]),
                        Paragraph("<b>Value</b>", styles["Normal"]),
                    ],
                    [
                        Paragraph("Quality Score", styles["Normal"]),
                        Paragraph(
                            f"{candidate['overall_score']}/100", styles["Normal"]
                        ),
                    ],
                    [
                        Paragraph("Prize Reason", styles["Normal"]),
                        Paragraph(candidate["prize_reason"], styles["Normal"]),
                    ],
                ]
                candidate_table = Table(candidate_data, colWidths=[2 * inch, 4 * inch])
                candidate_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 10),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                            ("GRID", (0, 0), (-1, -1), 1, colors.black),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ]
                    )
                )
                story.append(candidate_table)
                story.append(Spacer(1, 0.2 * inch))

                # Summary
                if candidate["summary"]:
                    story.append(Paragraph("<b>Summary:</b>", styles["Normal"]))
                    story.append(Paragraph(candidate["summary"], styles["Normal"]))
                    story.append(Spacer(1, 0.2 * inch))

                # Full conversation
                story.append(Paragraph("<b>Full Conversation:</b>", styles["Normal"]))
                story.append(Spacer(1, 0.1 * inch))

                # Format conversation with proper line breaks
                conversation_text = candidate["formatted_text"]
                # Split by double newlines (message separator)
                messages = conversation_text.split("\n\n")
                for message in messages:
                    # Escape HTML special characters and preserve formatting
                    message_escaped = (
                        message.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                    )
                    story.append(
                        Paragraph(
                            f"<font size=9>{message_escaped}</font>",
                            styles["Normal"],
                        )
                    )
                    story.append(Spacer(1, 0.1 * inch))

        # Build PDF
        doc.build(story)
        logger.success(f"PDF report saved to {output_path}")
