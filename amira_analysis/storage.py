"""Storage for conversations and analysis results."""

import json
from pathlib import Path
from typing import Any

import polars as pl
from loguru import logger

from .constants import (
    DEFAULT_ANALYSIS_OUTPUT,
    DEFAULT_CONVERSATIONS_OUTPUT,
    JSON_INDENT,
    LogMessage,
    AnalysisKey,
    IssueOutputKey,
    ConversationIssueKey,
)
from .models import Conversation, QualityAnalysis


class ConversationStorage:
    """Handles saving conversations and analysis results to disk."""

    def save_conversations(
        self,
        *,
        conversations: list[Conversation],
        filepath: Path | str = DEFAULT_CONVERSATIONS_OUTPUT,
    ) -> None:
        """Save conversations to a JSON file.

        Converts all conversations to dictionaries and writes them to a JSON file
        with proper indentation. Uses default string conversion for non-serializable types.

        Args:
            conversations: List of Conversation objects to save.
            filepath: Path where the JSON file should be saved.
        """
        filepath = Path(filepath)

        conversations_data = [convo.to_dict() for convo in conversations]

        with filepath.open("w") as f:
            json.dump(conversations_data, f, indent=JSON_INDENT, default=str)

        logger.success(
            LogMessage.SAVED_CONVERSATIONS.format(len(conversations), filepath)
        )

    def save_analysis(
        self,
        *,
        analysis: QualityAnalysis,
        filepath: Path | str = DEFAULT_ANALYSIS_OUTPUT,
    ) -> None:
        """Save quality analysis results to a JSON file.

        Converts the analysis results to a dictionary and writes to a JSON file
        with proper indentation. Uses default string conversion for non-serializable types.

        Args:
            analysis: QualityAnalysis object containing the analysis results.
            filepath: Path where the JSON file should be saved.
        """
        filepath = Path(filepath)

        with filepath.open("w") as f:
            json.dump(analysis.to_dict(), f, indent=JSON_INDENT, default=str)

        logger.success(LogMessage.SAVED_ANALYSIS.format(filepath))

    def save_analysis_csv(
        self,
        *,
        analysis: QualityAnalysis,
        filepath: Path | str | None = None,
    ) -> None:
        """Save quality analysis results to a CSV file using Polars.

        Flattens the nested structure and creates a normalized CSV with one row per issue.

        Args:
            analysis: QualityAnalysis object containing the analysis results.
            filepath: Path where the CSV file should be saved. If None, uses DEFAULT_ANALYSIS_OUTPUT
                     with .csv extension instead of .json.
        """
        if filepath is None:
            filepath = Path(DEFAULT_ANALYSIS_OUTPUT).with_suffix(".csv")
        else:
            filepath = Path(filepath)

        # Collect all issues from all categories
        all_issues = []

        # Iterate through all issue categories
        for category_name in [
            AnalysisKey.REPETITIVE,
            AnalysisKey.UNHELPFUL,
            AnalysisKey.TOO_MANY_TURNS,
            AnalysisKey.DEAD_END,
            AnalysisKey.NEGATIVE_RATING,
            IssueOutputKey.OBVIOUS_WRONG_ANSWERS,
            IssueOutputKey.MISSED_ESCALATION,
            IssueOutputKey.DUMB_QUESTIONS,
            IssueOutputKey.LACK_OF_ENCOURAGEMENT,
        ]:
            issues = getattr(analysis, category_name, [])
            for issue in issues:
                # Flatten the nested structure
                flat_issue: dict[str, Any] = {
                    ConversationIssueKey.CONVERSATION_ID: issue.conversation_id,
                    ConversationIssueKey.ISSUE_TYPE: issue.issue_type,
                    ConversationIssueKey.SEVERITY_SCORE: issue.severity_score,
                    ConversationIssueKey.AI_REASONING: issue.ai_reasoning,
                    ConversationIssueKey.EXCERPT: issue.excerpt,
                }

                # Flatten details dict
                if hasattr(issue, "details") and issue.details:
                    for key, value in issue.details.items():
                        # Convert lists to strings for CSV compatibility
                        if isinstance(value, list):
                            flat_issue[f"details_{key}"] = str(value)
                        else:
                            flat_issue[f"details_{key}"] = value

                all_issues.append(flat_issue)

        if not all_issues:
            logger.warning("No issues found to save to CSV")
            return

        # Create Polars DataFrame
        df = pl.DataFrame(all_issues)

        # Sort by severity score (descending) and then by conversation_id
        df = df.sort(
            [ConversationIssueKey.SEVERITY_SCORE, ConversationIssueKey.CONVERSATION_ID],
            descending=[True, False],
        )

        # Save to CSV
        df.write_csv(filepath)

        logger.success(f"Saved {len(df)} issues to {filepath}")
