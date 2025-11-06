"""AI-powered conversation analyzer using GPT-5-mini."""

import asyncio
import json
from enum import Enum
from pathlib import Path

import httpx
import instructor
from loguru import logger
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
)
from tenacity import retry, stop_after_attempt, wait_exponential

from ..constants import (
    DEFAULT_AI_CONCURRENCY,
    DEFAULT_AI_MAX_RETRIES,
    DEFAULT_AI_MODEL,
    IssueType,
    DetailKey,
    AIAnalysisDetailKey,
)
from ..models import Conversation, ConversationIssue, QualityAnalysis


class IssueTypeEnum(str, Enum):
    """Enum for issue types that the AI can identify."""

    OBVIOUS_WRONG_ANSWER = "OBVIOUS_WRONG_ANSWER"
    MISSED_ESCALATION = "MISSED_ESCALATION"
    DUMB_QUESTION = "DUMB_QUESTION"
    REPETITIVE = "REPETITIVE"
    LACK_OF_ENCOURAGEMENT = "LACK_OF_ENCOURAGEMENT"
    DEAD_END = "DEAD_END"


class SeverityLevel(str, Enum):
    """Severity levels for issues."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConfidenceLevel(str, Enum):
    """Confidence levels for issue identification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class VerdictEnum(str, Enum):
    """Overall conversation verdict."""

    PASS = "PASS"
    FAIL = "FAIL"


class PositiveBehavior(str, Enum):
    """Types of positive behaviors to recognize."""

    FAST_OBVIOUS_ANSWER = "fast_obvious_answer"
    CLEAR_ESCALATION = "clear_escalation"
    EMPATHETIC_TONE = "empathetic_tone"
    GOOD_CONSTRAINTS_USE = "good_constraints_use"
    CONCISE_STEPS = "concise_steps"


class OnTopicRefusalIncorrect(BaseModel):
    """Details about an incorrect refusal of an on-topic question."""

    messages: list[int] = Field(description="Message indices involved")
    evidence: str = Field(description="Short quote showing the refusal")
    why_incorrect: str = Field(
        description="1-2 sentence reason why this refusal was incorrect"
    )


class RefusalAssessment(BaseModel):
    """Assessment of how the bot handled question refusals."""

    off_topic_refusals_count: int = Field(
        default=0, description="Count of appropriate off-topic refusals"
    )
    on_topic_refusals_incorrect: list[OnTopicRefusalIncorrect] = Field(
        default_factory=list,
        description="List of incorrect refusals of legitimate Amira questions",
    )


class IssueFlag(BaseModel):
    """Represents a flagged issue in the conversation."""

    type: IssueTypeEnum = Field(description="Type of Tier-0 failure")
    severity: SeverityLevel = Field(description="Severity level")
    confidence: ConfidenceLevel = Field(description="Confidence in this assessment")
    messages: list[int] = Field(description="Message indices involved")
    evidence: str = Field(description="Short quotes showing the issue")
    why_it_matters: str = Field(description="Impact on user/time/trust")
    recommended_fix: str = Field(
        description="Concise, actionable rewrite or step; include example handoff text if relevant"
    )


class PositiveNote(BaseModel):
    """Represents a positive behavior observed."""

    behavior: PositiveBehavior = Field(description="Type of positive behavior")
    messages: list[int] = Field(description="Message indices where this occurred")
    evidence: str = Field(description="Short quote demonstrating the positive")


class MetricsBreakdown(BaseModel):
    """Detailed scoring breakdown - reweighted to prioritize Tier 0 behaviors over correctness."""

    correctness_score: int = Field(
        ge=0, le=10, description="Correctness on obvious questions"
    )
    escalation_score: int = Field(
        ge=0, le=30, description="Appropriate escalation & handoff quality"
    )
    question_quality_score: int = Field(
        ge=0, le=20, description="Question quality (no dumb asks)"
    )
    progress_score: int = Field(
        ge=0, le=20, description="Progress (non-repetitive, forward motion)"
    )
    tone_encouragement_score: int = Field(
        ge=0, le=15, description="Tone & encouragement"
    )
    no_dead_end_score: int = Field(
        ge=0, le=5, description="Avoids dead ends (clear next step)"
    )


class ConversationAnalysisResult(BaseModel):
    """Complete analysis result for a single conversation."""

    overall_score: int = Field(ge=0, le=100, description="Overall quality score 0-100")
    overall_verdict: VerdictEnum = Field(description="PASS or FAIL")
    summary: str = Field(
        description="2-4 sentence executive summary of key strengths and issues"
    )
    metrics: MetricsBreakdown = Field(description="Detailed scoring breakdown")
    refusal_assessment: RefusalAssessment = Field(
        description="Assessment of question refusal handling"
    )
    flags: list[IssueFlag] = Field(
        default_factory=list, description="List of identified issues"
    )
    positives: list[PositiveNote] = Field(
        default_factory=list, description="List of positive behaviors"
    )
    next_best_step: str = Field(
        description="Single most helpful next action the bot should take now"
    )
    suggested_handoff_message: str | None = Field(
        default=None,
        description="Polished, user-facing handoff paragraph if escalation is advisable",
    )
    notes_for_training: str = Field(
        description="1-3 bullets for bot tuning; avoid chain-of-thought"
    )
    prize_candidate: bool = Field(
        description="True if this conversation is a clear example of being an impediment to good support (prize-worthy)"
    )
    prize_reason: str | None = Field(
        default=None,
        description="1 sentence explaining why this is a clear impediment to support (if prize_candidate=True)",
    )
    cycles_without_progress: int = Field(
        ge=0,
        description="Count of back-and-forth loops where no new action/resource was provided",
    )
    has_clear_next_step: bool = Field(
        description="True if final bot turn includes action/link/escalation/timeframe"
    )


class AIConversationAnalyzer:
    """Analyzes conversations using GPT-5-mini for intelligent issue detection.

    This analyzer uses OpenAI's GPT-5-mini model to identify Tier 0 support failures
    including obvious wrong answers, missed escalations, dumb questions, futile loops,
    and lack of encouragement.

    The analyzer is optimized for high-throughput parallel processing with configurable
    concurrency limits. HTTP connection pooling is tuned to match the concurrency limit
    to prevent bottlenecks.

    Attributes:
        client: Instructor-patched AsyncOpenAI client for API calls.
        model: Model name to use for analysis.
        max_concurrency: Maximum number of concurrent API requests (default 500).
        semaphore: Asyncio semaphore limiting concurrent API calls.
        no_cache: Whether to ignore cached results.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_AI_MODEL,
        max_concurrency: int = DEFAULT_AI_CONCURRENCY,
        no_cache: bool = False,
    ):
        """Initialize the AI analyzer.

        Args:
            api_key: OpenAI API key.
            model: Model name to use (default: gpt-5-mini).
            max_concurrency: Maximum concurrent requests (default 500).
            no_cache: If True, ignore cached results and always re-run analyses.
        """
        # Configure httpx client with higher connection limits for true parallelism
        # This is critical - default httpx limit is ~100, which bottlenecks parallel requests
        http_client = httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=max_concurrency,
                max_keepalive_connections=max_concurrency,
            ),
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

        # Patch AsyncOpenAI with instructor for structured outputs
        self.client = instructor.from_openai(
            AsyncOpenAI(
                api_key=api_key,
                http_client=http_client,
                max_retries=0,  # We handle retries with tenacity
            )
        )
        self.model = model
        self.max_concurrency = max_concurrency
        self.no_cache = no_cache

        # Semaphore to limit concurrent API calls
        self.semaphore = asyncio.Semaphore(max_concurrency)

        # Create output directory for individual conversation analyses
        self.output_dir = Path("conversation_analyses")
        self.output_dir.mkdir(exist_ok=True)

    def _load_cached_analysis(
        self, *, conversation_id: str
    ) -> ConversationAnalysisResult | None:
        """Load cached conversation analysis result from JSON file.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            ConversationAnalysisResult if cached file exists, None otherwise.
        """
        cache_path = self.output_dir / f"{conversation_id}.json"

        if not cache_path.exists():
            return None

        try:
            with cache_path.open("r") as f:
                data = json.load(f)
            result = ConversationAnalysisResult.model_validate(data)
            logger.debug(
                f"Loaded cached analysis for conversation {conversation_id} from {cache_path}"
            )
            return result
        except Exception as e:
            logger.warning(
                f"Failed to load cached analysis for conversation {conversation_id}: {e}"
            )
            return None

    def _save_conversation_analysis(
        self, *, conversation_id: str, result: ConversationAnalysisResult
    ) -> None:
        """Save individual conversation analysis result to JSON file.

        Args:
            conversation_id: ID of the conversation.
            result: Pydantic analysis result to save.
        """
        output_path = self.output_dir / f"{conversation_id}.json"

        try:
            with output_path.open("w") as f:
                # Use pydantic's model_dump to convert to dict, then save as JSON
                json.dump(result.model_dump(mode="json"), f, indent=2, default=str)
            logger.debug(
                f"Saved analysis for conversation {conversation_id} to {output_path}"
            )
        except Exception as e:
            logger.warning(
                f"Failed to save analysis for conversation {conversation_id}: {e}"
            )

    def _build_analysis_prompt(self, *, conversation: Conversation) -> str:
        """Build the analysis prompt for GPT-5-mini.

        Args:
            conversation: Conversation to analyze.

        Returns:
            str: Formatted prompt for the AI.
        """
        # Format the conversation for analysis with indices
        convo_text: list[str] = []
        for idx, msg in enumerate(conversation.messages):
            line = "[" + str(idx) + "] " + str(msg.role) + ": " + str(msg.content)
            convo_text.append(line)
        conversation_str = "\n".join(convo_text)

        return f"""SYSTEM ROLE: Tier-0 Support Quality Evaluator (for Amira's email/web chatbot)

OBJECTIVE
Evaluate a single customer-support conversation for Tier-0 quality issues and return a structured, actionable report. Focus on whether the bot quickly provides obvious answers, knows when to escalate, avoids wasting the user's time, and keeps the user encouraged and moving forward.

CONTEXT (READ CAREFULLY)
- Product: Amira (K-12 literacy platform). Channel: online/email support chatbot.
- Capabilities: LIMITED file access. Knowledge is scoped to Amira; the bot should *refuse off-topic questions.*
- Refusals are **good/expected** when the user's question is unrelated to Amira (e.g., "What's 1+1?", "What's the biggest planet?").
- Only flag refusals as issues if the question **was relevant to Amira** and the bot incorrectly refused.

INPUT
{conversation_str}

TIER-0 "GOOD" DEFINITION (what success looks like)
- Fast, obvious answers when they exist.
- Helpful handoff or human escalation when the answer isn't obvious or requires privileged actions.
- No "dumb" questions (asking for info the bot already has or is irrelevant).
- No futile back-and-forth (repetition, circular replies, no progress).
- Encouraging, facilitating tone that helps the user succeed (suggests next steps, links, checklists, or escalation).

ANTI-PATTERNS TO FLAG (use these exact labels)
1) OBVIOUS_WRONG_ANSWER — Incorrect reply to a simple, obvious question.
2) MISSED_ESCALATION — Complex/blocked issue should have been escalated; bot kept churning.
3) DUMB_QUESTION — Bot asks for info already in the thread (email, role, school, district, error text, prior steps) or that's obviously irrelevant.
4) REPETITIVE — Circular, redundant replies to **LEGITIMATE AMIRA QUESTIONS** with no forward motion (count these as cycles_without_progress).
   **CRITICAL: It is CORRECT and EXPECTED for the bot to repeat "I can only answer questions about Amira" for off-topic/irrelevant questions.**
   **ONLY flag REPETITIVE when the bot repeats unhelpful responses to VALID Amira-related questions without making progress.**
5) LACK_OF_ENCOURAGEMENT — Discouraging tone or no pathways to success.
6) DEAD_END — Conversation stalls with no clear next step (no link, no form, no escalation, no timeline). Check has_clear_next_step.

IMPORTANT EVALUATION RULES
- **Repeating "I can only answer questions about Amira" for off-topic questions is CORRECT BEHAVIOR. Do NOT flag as REPETITIVE.**
- Do **not** penalize on-topic refusals that respect the bot's limitations or policy.
- **Do** penalize repetitive unhelpful responses to **valid Amira questions** (same answer, no new info, no progress).
- **Do** penalize refusals of legitimate Amira questions.
- Consider limited file access/knowledge scope when judging whether a step was feasible.
- Prefer solutions that offer: (a) a direct answer, (b) a concrete next step, or (c) a clear, warm escalation.

WHEN TO EXPECT ESCALATION (heuristics)
- Permissions/identity/account work, billing/security, school/district data.
- Repeated failures to locate required info due to limited access.
- Two or more back-and-forth turns without progress on a complex issue.
- System errors the bot cannot fix.

SCORING RUBRIC (0–100) — REWEIGHTED FOR TIER 0 BEHAVIORS
- Correctness on obvious questions: 10
- Appropriate escalation & handoff quality: 30
- Question quality (no "dumb" asks): 20
- Progress (non-repetitive, forward motion): 20
- Tone & encouragement: 15
- Avoids dead ends (clear next step): 5

HARD-FAIL TRIGGERS (set overall_verdict="FAIL" and prize_candidate=true regardless of score)
- Any high-severity MISSED_ESCALATION flag.
- ≥2 cycles of REPETITIVE with no new action or resource (cycles_without_progress ≥ 2).
- Final bot turn lacks action/link/escalation/timeframe (has_clear_next_step=false and DEAD_END flagged).
- Bot asks for info already in thread or obvious from context (DUMB_QUESTION with high severity).

WORTHWHILE HUMAN INTERACTION (explicit requirement)
- If blocked by permissions/identity/billing/limited file access for >1 turn,
  MUST provide a clear, warm escalation with: who to contact, when, how, and what info to have ready.
- Escalation quality matters more than correctness. A polite "let me connect you to someone who can help" beats
  multiple failed attempts.

PRIZE CANDIDATE CRITERIA ($500 gift card for identifying impediments to good support)
Set prize_candidate=true and provide prize_reason when the conversation clearly demonstrates:
- Bot was an impediment to user getting good support (not just a wrong answer)
- Violated core Tier 0 principles: futile back-and-forth, dumb questions, missed escalation, lack of encouragement
- User likely frustrated or time wasted due to bot behavior
- Clear, specific example that could drive actionable improvements

PROGRESS TRACKING
- Count cycles_without_progress: back-and-forth loops where bot provides same/similar response without new action
- Check has_clear_next_step: final bot message must include at least one of: actionable step, link/form, timeframe, human handoff

EVIDENCE & INDEXING
- Number turns sequentially from the conversation start. Use [#] like [3] to reference messages.
- Quote minimally (≤20 words per quote). Do not include private/internal reasoning.

QUALITY BAR
- Be strict. Only flag genuine Tier-0 failures.
- Prefer actionable fixes (rewrite a reply, propose a targeted question, or include a clear escalation template).
- Never invent facts not present in the conversation.

CONSTRAINTS
- No chain-of-thought in the output; keep rationales brief and evidence-based.
- Use only information present in the conversation.
- If **no issues**, set "overall_verdict": "PASS" and include at least 2 "positives"."""

    def _result_to_issues(
        self, *, conversation: Conversation, result: ConversationAnalysisResult
    ) -> list[ConversationIssue]:
        """Convert a ConversationAnalysisResult to a list of ConversationIssue.

        Args:
            conversation: The conversation that was analyzed.
            result: The analysis result.

        Returns:
            list[ConversationIssue]: List of identified issues.
        """
        issues = []
        issue_type_map = {
            IssueTypeEnum.OBVIOUS_WRONG_ANSWER: IssueType.OBVIOUS_WRONG_ANSWER,
            IssueTypeEnum.MISSED_ESCALATION: IssueType.MISSED_ESCALATION,
            IssueTypeEnum.DUMB_QUESTION: IssueType.DUMB_QUESTION,
            IssueTypeEnum.REPETITIVE: IssueType.REPETITIVE,
            IssueTypeEnum.LACK_OF_ENCOURAGEMENT: IssueType.LACK_OF_ENCOURAGEMENT,
            IssueTypeEnum.DEAD_END: IssueType.DEAD_END,
        }

        # Map severity to numeric score (low=3, medium=6, high=9)
        severity_map = {
            SeverityLevel.LOW: 3,
            SeverityLevel.MEDIUM: 6,
            SeverityLevel.HIGH: 9,
        }

        for flag in result.flags:
            issue_type = issue_type_map.get(flag.type, IssueType.UNHELPFUL)
            severity_score = severity_map.get(flag.severity, 5)

            issues.append(
                ConversationIssue(
                    conversation_id=conversation.id,
                    issue_type=issue_type,
                    details={
                        DetailKey.MESSAGE_COUNT: len(conversation.messages),
                        DetailKey.STATUS: conversation.status,
                        DetailKey.RATING: conversation.rating,
                        AIAnalysisDetailKey.OVERALL_SCORE: result.overall_score,
                        AIAnalysisDetailKey.OVERALL_VERDICT: result.overall_verdict.value,
                        AIAnalysisDetailKey.MESSAGES_INVOLVED: flag.messages,
                        AIAnalysisDetailKey.CONFIDENCE: flag.confidence.value,
                        AIAnalysisDetailKey.RECOMMENDED_FIX: flag.recommended_fix,
                    },
                    severity_score=severity_score,
                    ai_reasoning=f"{flag.why_it_matters} | {flag.recommended_fix}",
                    excerpt=flag.evidence,
                )
            )

        return issues

    @retry(
        stop=stop_after_attempt(DEFAULT_AI_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _analyze_single_conversation(
        self, *, conversation: Conversation
    ) -> list[ConversationIssue]:
        """Analyze a single conversation using GPT-5-mini with retries.

        Args:
            conversation: Conversation to analyze.

        Returns:
            list[ConversationIssue]: List of identified issues.
        """
        # Check for cached result first (unless --no-cache is set)
        if not self.no_cache:
            cached_result = self._load_cached_analysis(conversation_id=conversation.id)
            if cached_result is not None:
                logger.trace(
                    f"Using cached analysis for conversation {conversation.id}"
                )
                # Convert cached result to issues
                return self._result_to_issues(
                    conversation=conversation, result=cached_result
                )

        logger.trace(f"Starting API call for conversation {conversation.id}")
        async with self.semaphore:
            logger.trace(f"Acquired semaphore slot for conversation {conversation.id}")
            prompt = self._build_analysis_prompt(conversation=conversation)

            try:
                # Use instructor to get structured response
                result = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a Tier-0 Support Quality Evaluator expert at analyzing customer support conversations.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_model=ConversationAnalysisResult,
                )

                logger.trace(f"Completed API call for conversation {conversation.id}")

                # Immediately save the full analysis result
                self._save_conversation_analysis(
                    conversation_id=conversation.id, result=result
                )

                # Convert result to issues and return
                return self._result_to_issues(conversation=conversation, result=result)

            except Exception as e:
                logger.error(f"Error analyzing conversation {conversation.id}: {e}")
                return []

    async def analyze_async(
        self, *, conversations: list[Conversation]
    ) -> QualityAnalysis:
        """Analyze all conversations asynchronously using GPT-5-mini.

        Args:
            conversations: List of conversations to analyze.

        Returns:
            QualityAnalysis: Complete analysis with AI-identified issues.
        """
        logger.info(
            f"Starting AI analysis of {len(conversations)} conversations with max {self.max_concurrency} concurrent requests..."
        )

        # Process all conversations in parallel with progress tracking
        results = []
        completed_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
        ) as progress:
            task_id = progress.add_task(
                "Analyzing conversations with AI...",
                total=len(conversations),
            )

            # Create all tasks and gather them with better parallelism
            tasks = [
                self._analyze_single_conversation(conversation=convo)
                for convo in conversations
            ]

            # Use as_completed for true parallelism
            for coro in asyncio.as_completed(tasks):
                result = await coro
                results.append(result)
                completed_count += 1
                progress.update(task_id, completed=completed_count)

        # Categorize all issues
        obvious_wrong_answers = []
        missed_escalation = []
        dumb_questions = []
        repetitive = []
        lack_of_encouragement = []
        dead_end = []
        unhelpful = []

        for issues_list in results:
            for issue in issues_list:
                if issue.issue_type == IssueType.OBVIOUS_WRONG_ANSWER:
                    obvious_wrong_answers.append(issue)
                elif issue.issue_type == IssueType.MISSED_ESCALATION:
                    missed_escalation.append(issue)
                elif issue.issue_type == IssueType.DUMB_QUESTION:
                    dumb_questions.append(issue)
                elif issue.issue_type == IssueType.REPETITIVE:
                    repetitive.append(issue)
                elif issue.issue_type == IssueType.LACK_OF_ENCOURAGEMENT:
                    lack_of_encouragement.append(issue)
                elif issue.issue_type == IssueType.DEAD_END:
                    dead_end.append(issue)
                else:
                    unhelpful.append(issue)

        # Sort each category by severity
        for issue_list in [
            obvious_wrong_answers,
            missed_escalation,
            dumb_questions,
            repetitive,
            lack_of_encouragement,
            dead_end,
            unhelpful,
        ]:
            issue_list.sort(key=lambda x: x.severity_score or 0, reverse=True)

        analysis = QualityAnalysis(
            total_analyzed=len(conversations),
            repetitive=repetitive,
            unhelpful=unhelpful,
            too_many_turns=[],
            dead_end=dead_end,
            negative_rating=[],
            obvious_wrong_answers=obvious_wrong_answers,
            missed_escalation=missed_escalation,
            dumb_questions=dumb_questions,
            lack_of_encouragement=lack_of_encouragement,
        )

        logger.success(
            f"AI analysis complete! Found {len(obvious_wrong_answers + missed_escalation + dumb_questions + repetitive + lack_of_encouragement + dead_end + unhelpful)} total issues"
        )

        return analysis
