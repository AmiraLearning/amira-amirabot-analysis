"""Data models for Amirabot conversation analysis."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from .constants import (
    EMPTY_STRING,
    AnalysisKey,
    ApiResponseKey,
    IssueOutputKey,
    SummaryStatisticKey,
)


@dataclass
class Message:
    """Represents a single message in a conversation.

    Attributes:
        role: The role of the message sender (e.g., 'user', 'assistant').
        content: The text content of the message.
        timestamp: Optional timestamp when the message was created.
    """

    role: str
    content: str
    timestamp: str | None = None

    @classmethod
    def from_dict(cls, *, data: dict[str, Any]) -> "Message":
        """Create a Message from a dictionary.

        Handles both API format (sender/message) and cached format (role/content).

        Args:
            data: Dictionary containing message data.

        Returns:
            Message: A new Message instance populated with data from the dictionary.
        """
        # Try cached format first (role/content), then API format (sender/message)
        role = data.get("role") or data.get(ApiResponseKey.ROLE, EMPTY_STRING)
        content = data.get("content") or data.get(ApiResponseKey.CONTENT, EMPTY_STRING)
        timestamp = data.get("timestamp") or data.get(ApiResponseKey.TIMESTAMP)

        return cls(
            role=role,
            content=content,
            timestamp=timestamp,
        )


@dataclass
class Conversation:
    """Represents a conversation with all its metadata.

    Attributes:
        id: Unique identifier for the conversation.
        messages: List of Message objects in the conversation.
        created_at: Timestamp when the conversation was created.
        status: Current status of the conversation (open, closed, escalated).
        rating: Optional user rating for the conversation.
    """

    id: str
    messages: list[Message]
    created_at: str
    status: str | None = None
    rating: int | None = None

    @classmethod
    def from_dict(cls, *, data: dict[str, Any]) -> "Conversation":
        """Create a Conversation from API response or cached dictionary.

        Handles both API format and cached format.
        Handles parsing of messages which may be provided as either a JSON string
        or a list of dictionaries. Converts each message dictionary to a Message object.

        Args:
            data: Dictionary containing conversation data from API or cache.

        Returns:
            Conversation: A new Conversation instance with parsed messages and metadata.
        """
        # Handle messages - try cached format first, then API format
        messages_data = data.get("messages") or data.get(ApiResponseKey.MESSAGES, [])

        if isinstance(messages_data, str):
            try:
                messages_data = json.loads(messages_data)
            except json.JSONDecodeError:
                messages_data = []

        messages = [
            Message.from_dict(data=msg) if isinstance(msg, dict) else msg
            for msg in messages_data
        ]

        # Try cached format first, then API format for each field
        conv_id = data.get("id") or data.get(ApiResponseKey.ID, EMPTY_STRING)
        created_at = data.get("created_at") or data.get(
            ApiResponseKey.CREATED_AT, EMPTY_STRING
        )
        status = data.get("status") or data.get(ApiResponseKey.CONVO_STATUS)

        # Convert rating to int if it's a string
        rating = data.get("rating") or data.get(ApiResponseKey.RATING)
        if rating is not None and isinstance(rating, str):
            try:
                rating = int(rating)
            except (ValueError, TypeError):
                rating = None

        return cls(
            id=conv_id,
            messages=messages,
            created_at=created_at,
            status=status,
            rating=rating,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert conversation to dictionary for serialization.

        Returns:
            dict[str, Any]: Dictionary representation of the conversation.
        """
        return asdict(self)

    def get_normalized_date(self) -> str:
        """Get normalized date in YYYY-MM-DD format.

        Parses the created_at timestamp and returns just the date portion.
        If parsing fails, returns the original created_at value.

        Returns:
            str: Date in YYYY-MM-DD format, or original created_at if parsing fails.
        """
        if not self.created_at:
            return ""

        try:
            # Try parsing ISO format timestamp
            dt = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            # Try parsing as milliseconds since epoch
            try:
                dt = datetime.fromtimestamp(int(self.created_at) / 1000)
                return dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                # Return original if we can't parse it
                return self.created_at


@dataclass
class ConversationIssue:
    """Represents an identified issue in a conversation.

    Attributes:
        conversation_id: ID of the conversation with the issue.
        issue_type: Type of issue identified (e.g., 'repetitive', 'unhelpful').
        details: Additional details about the issue.
        severity_score: Severity rating from 1-10 (AI-generated, optional).
        ai_reasoning: Explanation from AI about why this is an issue (optional).
        excerpt: Relevant conversation snippet demonstrating the issue (optional).
    """

    conversation_id: str
    issue_type: str
    details: dict[str, Any]
    severity_score: int | None = None
    ai_reasoning: str | None = None
    excerpt: str | None = None


@dataclass
class QualityAnalysis:
    """Results of conversation quality analysis.

    Attributes:
        total_analyzed: Total number of conversations analyzed.
        repetitive: List of conversations with repetitive bot responses.
        unhelpful: List of conversations with unhelpful responses.
        too_many_turns: List of conversations with excessive back-and-forth.
        dead_end: List of conversations that reached a dead end.
        negative_rating: List of conversations with negative user ratings.
        obvious_wrong_answers: List of conversations where obvious questions were answered incorrectly.
        missed_escalation: List of conversations where human escalation should have happened.
        dumb_questions: List of conversations where Amirabot asked inappropriate questions.
        lack_of_encouragement: List of conversations where Amirabot discouraged users.
    """

    total_analyzed: int
    repetitive: list[ConversationIssue]
    unhelpful: list[ConversationIssue]
    too_many_turns: list[ConversationIssue]
    dead_end: list[ConversationIssue]
    negative_rating: list[ConversationIssue]
    obvious_wrong_answers: list[ConversationIssue]
    missed_escalation: list[ConversationIssue]
    dumb_questions: list[ConversationIssue]
    lack_of_encouragement: list[ConversationIssue]

    def to_dict(self) -> dict[str, Any]:
        """Convert analysis to dictionary for serialization.

        Returns:
            dict[str, Any]: Dictionary representation of the quality analysis results.
        """
        base: dict[str, Any] = {
            AnalysisKey.TOTAL_ANALYZED: self.total_analyzed,
            AnalysisKey.REPETITIVE: [asdict(issue) for issue in self.repetitive],
            AnalysisKey.UNHELPFUL: [asdict(issue) for issue in self.unhelpful],
            AnalysisKey.TOO_MANY_TURNS: [
                asdict(issue) for issue in self.too_many_turns
            ],
            AnalysisKey.DEAD_END: [asdict(issue) for issue in self.dead_end],
            AnalysisKey.NEGATIVE_RATING: [
                asdict(issue) for issue in self.negative_rating
            ],
            IssueOutputKey.OBVIOUS_WRONG_ANSWERS: [
                asdict(issue) for issue in self.obvious_wrong_answers
            ],
            IssueOutputKey.MISSED_ESCALATION: [
                asdict(issue) for issue in self.missed_escalation
            ],
            IssueOutputKey.DUMB_QUESTIONS: [
                asdict(issue) for issue in self.dumb_questions
            ],
            IssueOutputKey.LACK_OF_ENCOURAGEMENT: [
                asdict(issue) for issue in self.lack_of_encouragement
            ],
        }

        # Add summary statistics if AI analysis was performed
        all_issues = (
            self.repetitive
            + self.unhelpful
            + self.too_many_turns
            + self.dead_end
            + self.negative_rating
            + self.obvious_wrong_answers
            + self.missed_escalation
            + self.dumb_questions
            + self.lack_of_encouragement
        )

        if all_issues and any(issue.severity_score is not None for issue in all_issues):
            scored_issues = [
                issue for issue in all_issues if issue.severity_score is not None
            ]
            base[SummaryStatisticKey.SUMMARY] = {
                SummaryStatisticKey.CONVERSATIONS_WITH_ISSUES: len(
                    set(issue.conversation_id for issue in all_issues)
                ),
                SummaryStatisticKey.AVERAGE_SEVERITY: (
                    sum(
                        i.severity_score if i.severity_score is not None else 0
                        for i in scored_issues
                    )
                    / len(scored_issues)
                    if scored_issues
                    else 0
                ),
                SummaryStatisticKey.TOTAL_ISSUES_FOUND: len(all_issues),
            }

            # Add top offenders across all categories
            top_offenders = sorted(
                [issue for issue in all_issues if issue.severity_score is not None],
                key=lambda x: x.severity_score if x.severity_score is not None else 0,
                reverse=True,
            )[:20]
            base[SummaryStatisticKey.TOP_OFFENDERS] = [
                asdict(issue) for issue in top_offenders
            ]

        return base
