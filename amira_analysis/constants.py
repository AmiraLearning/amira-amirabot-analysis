"""Constants and enumerations for Amirabot conversation analysis."""

from enum import StrEnum
from typing import Final


# API Configuration
AMIRABOT_API_BASE_URL: Final[str] = (
    "https://g7ebdvmssc.execute-api.us-east-2.amazonaws.com/prod"
)
API_CONVERSATION_LIST_ENDPOINT: Final[str] = "/conversation/list"

# Default Values
DEFAULT_PAGE_LIMIT: Final[int] = 100
DEFAULT_SORT_BY: Final[str] = "createdAt"
DEFAULT_NEGATIVE_RATING_THRESHOLD: Final[int] = 3
DEFAULT_EXCESSIVE_TURNS_THRESHOLD: Final[int] = 3
DEFAULT_CONVERSATIONS_OUTPUT: Final[str] = "conversations.json"
DEFAULT_ANALYSIS_OUTPUT: Final[str] = "issues.json"
DEFAULT_MAX_PAGES: Final[int] = 5
DEFAULT_AI_MODEL: Final[str] = "gpt-5-mini"
DEFAULT_AI_CONCURRENCY: Final[int] = 500
DEFAULT_AI_MAX_RETRIES: Final[int] = 4

# JSON Serialization
JSON_INDENT: Final[int] = 2

# Empty Values
EMPTY_STRING: Final[str] = ""
EMPTY_LIST: Final[list] = []

# Numeric Constants
EXIT_CODE_ERROR: Final[int] = 1
FIRST_PAGE: Final[int] = 1


class ConversationStatus(StrEnum):
    """Enumeration of possible conversation statuses."""

    OPEN = "open"
    CLOSED = "closed"
    ESCALATED = "escalated"


class SortDirection(StrEnum):
    """Sort direction for API queries."""

    ASC = "asc"
    DESC = "desc"


class MessageRole(StrEnum):
    """Message sender roles."""

    USER = "user"
    ASSISTANT = "assistant"


class ApiResponseKey(StrEnum):
    """API response dictionary keys."""

    FILTERED_CONVOS = "filtered_convos"
    NEXT_PAGE_TOKEN = "next_page_token"
    MESSAGES = "messages"
    ROLE = "sender"
    CONTENT = "message"
    TIMESTAMP = "timestamp"
    ID = "PK"
    CREATED_AT = "createdAt"
    CONVO_STATUS = "convo_status"
    RATING = "rating"


class ApiRequestKey(StrEnum):
    """API request payload keys."""

    FILTER = "filter"
    LIMIT = "limit"
    SORT_BY = "sort_by"
    SORT_DIR = "sort_dir"
    INCLUDE_MESSAGES = "include_messages"
    PAGE_TOKEN = "page_token"


class IssueType(StrEnum):
    """Types of conversation quality issues."""

    REPETITIVE = "repetitive"
    UNHELPFUL = "unhelpful"
    TOO_MANY_TURNS = "too_many_turns"
    DEAD_END = "dead_end"
    NEGATIVE_RATING = "negative_rating"
    OBVIOUS_WRONG_ANSWER = "obvious_wrong_answer"
    MISSED_ESCALATION = "missed_escalation"
    DUMB_QUESTION = "dumb_question"
    LACK_OF_ENCOURAGEMENT = "lack_of_encouragement"
    INTENT_MISRECOGNITION = "intent_misrecognition"


class AnalysisKey(StrEnum):
    """Quality analysis output keys."""

    TOTAL_ANALYZED = "total_analyzed"
    REPETITIVE = "repetitive"
    UNHELPFUL = "unhelpful"
    TOO_MANY_TURNS = "too_many_turns"
    DEAD_END = "dead_end"
    NEGATIVE_RATING = "negative_rating"


class IssueOutputKey(StrEnum):
    """Issue category output keys (plural forms used in JSON output)."""

    OBVIOUS_WRONG_ANSWERS = "obvious_wrong_answers"
    MISSED_ESCALATION = "missed_escalation"
    DUMB_QUESTIONS = "dumb_questions"
    LACK_OF_ENCOURAGEMENT = "lack_of_encouragement"


class ConversationIssueKey(StrEnum):
    """ConversationIssue object field names."""

    CONVERSATION_ID = "conversation_id"
    ISSUE_TYPE = "issue_type"
    SEVERITY_SCORE = "severity_score"
    AI_REASONING = "ai_reasoning"
    EXCERPT = "excerpt"
    DETAILS = "details"


class AIAnalysisDetailKey(StrEnum):
    """AI-specific detail field names."""

    OVERALL_SCORE = "overall_score"
    OVERALL_VERDICT = "overall_verdict"
    MESSAGES_INVOLVED = "messages_involved"
    CONFIDENCE = "confidence"
    RECOMMENDED_FIX = "recommended_fix"


class SummaryStatisticKey(StrEnum):
    """Summary statistics field names."""

    SUMMARY = "summary"
    CONVERSATIONS_WITH_ISSUES = "conversations_with_issues"
    AVERAGE_SEVERITY = "average_severity"
    TOTAL_ISSUES_FOUND = "total_issues_found"
    TOP_OFFENDERS = "top_offenders"


class DetailKey(StrEnum):
    """Issue detail dictionary keys."""

    RATING = "rating"
    MESSAGE_COUNT = "message_count"
    TURNS = "turns"
    STATUS = "status"


class LogMessage(StrEnum):
    """Log message templates."""

    FETCHING_PAGE = "Fetching page {}..."
    RETRIEVED_CONVERSATIONS = "Retrieved {} conversations (total: {})"
    MAX_PAGES_REACHED = "Reached maximum page limit of {}"
    ANALYSIS_HEADER = "=== CONVERSATION ANALYSIS ==="
    TOTAL_ANALYZED = "Total conversations analyzed: {}"
    ISSUES_FOUND = "Issues found:"
    ISSUE_COUNT = "  {}: {} conversations"
    SAVED_CONVERSATIONS = "Saved {} conversations to {}"
    SAVED_ANALYSIS = "Saved issues analysis to {}"
    FETCHING_ALL = "Fetching all Amirabot conversations..."
    ERROR_OCCURRED = "Error occurred: {}"


class CliHelp(StrEnum):
    """CLI help messages."""

    APP = "Amirabot conversation analysis tool"
    MAX_PAGES = "Maximum number of pages to fetch. If not specified, fetches all pages."
    NEGATIVE_THRESHOLD = (
        "Rating threshold below which conversations are flagged as negative."
    )
    TURNS_THRESHOLD = (
        "Message count threshold above which conversations are flagged as excessive."
    )
    CONVERSATIONS_OUTPUT = "Output file path for conversations data."
    ANALYSIS_OUTPUT = "Output file path for analysis results."
    NO_CACHE_AI = "Skip cached AI analysis results and re-run all AI analyses (ignores existing JSON files in conversation_analyses/ folder)."
    NO_CACHE_CONVERSATIONS = "Skip cached conversations and re-fetch from API (ignores existing JSON files in conversations/ folder)."
    ANALYZE_COMMAND = """Fetch and analyze Amirabot conversations for quality issues.

This command fetches conversations from the Amirabot API, analyzes them for
potential quality issues, and saves both the raw conversations and analysis
results to JSON files."""
