import json
import polars as pl

from amira_analysis.constants import (
    AnalysisKey,
    IssueOutputKey,
    ConversationIssueKey,
    DetailKey,
)

# Read the JSON file
with open("issues.json", "r") as f:
    data = json.load(f)

# Collect all issues from all categories
all_issues = []

# Categories to extract
categories = [
    AnalysisKey.REPETITIVE,
    AnalysisKey.UNHELPFUL,
    AnalysisKey.TOO_MANY_TURNS,
    AnalysisKey.DEAD_END,
    AnalysisKey.NEGATIVE_RATING,
    IssueOutputKey.OBVIOUS_WRONG_ANSWERS,
    IssueOutputKey.MISSED_ESCALATION,
    IssueOutputKey.DUMB_QUESTIONS,
    IssueOutputKey.LACK_OF_ENCOURAGEMENT,
]

for category in categories:
    if category in data:
        for issue in data[category]:
            # Flatten the nested structure
            flat_issue = {
                ConversationIssueKey.CONVERSATION_ID: issue.get(
                    ConversationIssueKey.CONVERSATION_ID
                ),
                ConversationIssueKey.ISSUE_TYPE: issue.get(
                    ConversationIssueKey.ISSUE_TYPE
                ),
                ConversationIssueKey.SEVERITY_SCORE: issue.get(
                    ConversationIssueKey.SEVERITY_SCORE
                ),
                ConversationIssueKey.AI_REASONING: issue.get(
                    ConversationIssueKey.AI_REASONING
                ),
                ConversationIssueKey.EXCERPT: issue.get(ConversationIssueKey.EXCERPT),
                # Flatten details dict
                DetailKey.MESSAGE_COUNT: issue.get(
                    ConversationIssueKey.DETAILS, {}
                ).get(DetailKey.MESSAGE_COUNT),
                DetailKey.STATUS: issue.get(ConversationIssueKey.DETAILS, {}).get(
                    DetailKey.STATUS
                ),
                DetailKey.RATING: issue.get(ConversationIssueKey.DETAILS, {}).get(
                    DetailKey.RATING
                ),
                DetailKey.TURNS: issue.get(ConversationIssueKey.DETAILS, {}).get(
                    DetailKey.TURNS
                ),
            }
            all_issues.append(flat_issue)

# Create Polars DataFrame
df = pl.DataFrame(all_issues)

# Sort by severity score (descending) and then by conversation_id
df = df.sort(
    [ConversationIssueKey.SEVERITY_SCORE, ConversationIssueKey.CONVERSATION_ID],
    descending=[True, False],
)

# Save to CSV
df.write_csv("issues_normalized.csv")

print(f"Normalized {len(df)} issues to issues_normalized.csv")
print(f"\nDataFrame shape: {df.shape}")
print("\nFirst few rows:")
print(df.head())
