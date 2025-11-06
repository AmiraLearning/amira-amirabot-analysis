"""Rule-based conversation analyzer."""

from loguru import logger

from ..constants import (
    DEFAULT_EXCESSIVE_TURNS_THRESHOLD,
    DEFAULT_NEGATIVE_RATING_THRESHOLD,
    DetailKey,
    IssueType,
    LogMessage,
)
from ..models import Conversation, ConversationIssue, QualityAnalysis


class ConversationAnalyzer:
    """Analyzes conversations for quality issues using simple rules.

    Evaluates conversations against Tier 0 support criteria:
    - Provides obvious answers when available
    - Facilitates worthwhile human interaction when answer isn't obvious
    - Doesn't ask dumb questions
    - Avoids futile back & forth
    - Encourages users to get their question answered

    Attributes:
        negative_rating_threshold: Rating below which is considered negative.
        excessive_turns_threshold: Number of messages above which is considered excessive.
    """

    def __init__(
        self,
        *,
        negative_rating_threshold: int = DEFAULT_NEGATIVE_RATING_THRESHOLD,
        excessive_turns_threshold: int = DEFAULT_EXCESSIVE_TURNS_THRESHOLD,
    ):
        """Initialize the ConversationAnalyzer.

        Args:
            negative_rating_threshold: Rating threshold below which conversations are flagged.
            excessive_turns_threshold: Message count threshold above which conversations are flagged.
        """
        self.negative_rating_threshold = negative_rating_threshold
        self.excessive_turns_threshold = excessive_turns_threshold

    def analyze(self, *, conversations: list[Conversation]) -> QualityAnalysis:
        """Analyze conversations to identify potential issues with Tier 0 support.

        Performs multiple checks on each conversation:
        - Negative ratings below threshold
        - Excessive back-and-forth turns indicating futile conversation

        Additional sophisticated analysis is planned for future implementation:
        - Detection of repetitive bot responses
        - Identification of unhelpful responses
        - Detection of dead-end conversations

        Args:
            conversations: List of conversations to analyze.

        Returns:
            QualityAnalysis: Object containing all identified issues categorized by type.
        """
        logger.info(LogMessage.ANALYSIS_HEADER)

        repetitive: list[ConversationIssue] = []
        unhelpful: list[ConversationIssue] = []
        too_many_turns: list[ConversationIssue] = []
        dead_end: list[ConversationIssue] = []
        negative_rating: list[ConversationIssue] = []

        for convo in conversations:
            if (
                convo.rating is not None
                and convo.rating < self.negative_rating_threshold
            ):
                negative_rating.append(
                    ConversationIssue(
                        conversation_id=convo.id,
                        issue_type=IssueType.NEGATIVE_RATING,
                        details={
                            DetailKey.RATING: convo.rating,
                            DetailKey.MESSAGE_COUNT: len(convo.messages),
                        },
                    )
                )

            if len(convo.messages) > self.excessive_turns_threshold:
                too_many_turns.append(
                    ConversationIssue(
                        conversation_id=convo.id,
                        issue_type=IssueType.TOO_MANY_TURNS,
                        details={
                            DetailKey.TURNS: len(convo.messages),
                            DetailKey.STATUS: convo.status,
                        },
                    )
                )

        analysis = QualityAnalysis(
            total_analyzed=len(conversations),
            repetitive=repetitive,
            unhelpful=unhelpful,
            too_many_turns=too_many_turns,
            dead_end=dead_end,
            negative_rating=negative_rating,
            obvious_wrong_answers=[],
            missed_escalation=[],
            dumb_questions=[],
            lack_of_encouragement=[],
        )

        self._print_summary(analysis=analysis)

        return analysis

    def _print_summary(self, *, analysis: QualityAnalysis) -> None:
        """Print a summary of the analysis results.

        Logs the total number of conversations analyzed and counts for each issue type.
        Only displays issue types that have at least one occurrence.

        Args:
            analysis: QualityAnalysis object containing the analysis results.
        """
        logger.info(LogMessage.TOTAL_ANALYZED.format(analysis.total_analyzed))
        logger.info(LogMessage.ISSUES_FOUND)

        issue_counts = {
            IssueType.REPETITIVE: len(analysis.repetitive),
            IssueType.UNHELPFUL: len(analysis.unhelpful),
            IssueType.TOO_MANY_TURNS: len(analysis.too_many_turns),
            IssueType.DEAD_END: len(analysis.dead_end),
            IssueType.NEGATIVE_RATING: len(analysis.negative_rating),
        }

        for issue_type, count in issue_counts.items():
            if count > 0:
                logger.info(LogMessage.ISSUE_COUNT.format(issue_type, count))
