"""Aggregate individual conversation analysis JSONs into a flat CSV."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger


def flatten_conversation_analysis(conversation_id: str, data: dict) -> dict[str, Any]:
    """Flatten a conversation analysis JSON into a single-level dict.

    Args:
        conversation_id: The conversation ID (from filename)
        data: The parsed JSON data

    Returns:
        Flattened dictionary with all nested data at top level
    """
    flat: dict[str, Any] = {"conversation_id": conversation_id}

    # Top-level simple fields
    flat["overall_score"] = data.get("overall_score")
    flat["overall_verdict"] = data.get("overall_verdict")
    flat["summary"] = data.get("summary")
    flat["next_best_step"] = data.get("next_best_step")
    flat["suggested_handoff_message"] = data.get("suggested_handoff_message")
    flat["notes_for_training"] = data.get("notes_for_training")
    flat["prize_candidate"] = data.get("prize_candidate")
    flat["prize_reason"] = data.get("prize_reason")
    flat["cycles_without_progress"] = data.get("cycles_without_progress")
    flat["has_clear_next_step"] = data.get("has_clear_next_step")

    # Flatten metrics
    metrics = data.get("metrics", {})
    flat["metrics_correctness_score"] = metrics.get("correctness_score")
    flat["metrics_escalation_score"] = metrics.get("escalation_score")
    flat["metrics_question_quality_score"] = metrics.get("question_quality_score")
    flat["metrics_progress_score"] = metrics.get("progress_score")
    flat["metrics_tone_encouragement_score"] = metrics.get("tone_encouragement_score")
    flat["metrics_no_dead_end_score"] = metrics.get("no_dead_end_score")

    # Flatten refusal_assessment
    refusal = data.get("refusal_assessment", {})
    flat["refusal_off_topic_count"] = refusal.get("off_topic_refusals_count")
    flat["refusal_on_topic_incorrect_count"] = len(
        refusal.get("on_topic_refusals_incorrect", [])
    )
    flat["refusal_on_topic_incorrect_json"] = json.dumps(
        refusal.get("on_topic_refusals_incorrect", [])
    )

    # Flags - keep as JSON string and add counts by type
    flags = data.get("flags", [])
    flat["flags_count"] = len(flags)
    flat["flags_json"] = json.dumps(flags)

    # Count flags by type
    flag_types = {}
    for flag in flags:
        flag_type = flag.get("type", "UNKNOWN")
        flag_types[flag_type] = flag_types.get(flag_type, 0) + 1

    flat["flags_obvious_wrong_answer"] = flag_types.get("OBVIOUS_WRONG_ANSWER", 0)
    flat["flags_missed_escalation"] = flag_types.get("MISSED_ESCALATION", 0)
    flat["flags_dumb_question"] = flag_types.get("DUMB_QUESTION", 0)
    flat["flags_repetitive"] = flag_types.get("REPETITIVE", 0)
    flat["flags_lack_of_encouragement"] = flag_types.get("LACK_OF_ENCOURAGEMENT", 0)
    flat["flags_dead_end"] = flag_types.get("DEAD_END", 0)

    # Positives - keep as JSON string and add count
    positives = data.get("positives", [])
    flat["positives_count"] = len(positives)
    flat["positives_json"] = json.dumps(positives)

    # Count positives by behavior type
    positive_behaviors = {}
    for positive in positives:
        behavior = positive.get("behavior", "unknown")
        positive_behaviors[behavior] = positive_behaviors.get(behavior, 0) + 1

    flat["positives_fast_obvious_answer"] = positive_behaviors.get(
        "fast_obvious_answer", 0
    )
    flat["positives_clear_escalation"] = positive_behaviors.get("clear_escalation", 0)
    flat["positives_empathetic_tone"] = positive_behaviors.get("empathetic_tone", 0)
    flat["positives_good_constraints_use"] = positive_behaviors.get(
        "good_constraints_use", 0
    )
    flat["positives_concise_steps"] = positive_behaviors.get("concise_steps", 0)

    return flat


def aggregate_conversation_analyses(
    analyses_dir: Path, output_path: Path
) -> pd.DataFrame:
    """Aggregate all conversation analysis JSONs into a single CSV.

    Args:
        analyses_dir: Directory containing individual conversation JSON files
        output_path: Path where the aggregated CSV should be saved

    Returns:
        DataFrame with aggregated data
    """
    if not analyses_dir.exists():
        logger.error(f"Directory {analyses_dir} does not exist")
        return pd.DataFrame()

    json_files = list(analyses_dir.glob("*.json"))
    logger.info(f"Found {len(json_files)} conversation analysis files")

    if not json_files:
        logger.warning("No JSON files found to process")
        return pd.DataFrame()

    rows = []

    for json_file in json_files:
        conversation_id = json_file.stem  # filename without extension

        try:
            with json_file.open("r") as f:
                data = json.load(f)

            flat_row = flatten_conversation_analysis(conversation_id, data)
            rows.append(flat_row)

        except Exception as e:
            logger.error(f"Error processing {json_file}: {e}")
            continue

    # Create DataFrame
    df = pd.DataFrame(rows)

    # Sort by overall_score (lowest first to see failures)
    df = df.sort_values("overall_score", ascending=True)

    # Save to CSV
    df.to_csv(output_path, index=False)

    logger.success(f"Aggregated {len(rows)} conversations to {output_path}")
    logger.info(f"Shape: {df.shape}")

    return df


def create_full_conversations_csv(
    conversations_json_path: Path, analyses_dir: Path, output_path: Path
) -> pd.DataFrame:
    """Join conversation analyses with original full conversation text.

    Args:
        conversations_json_path: Path to conversations.json with full conversation data
        analyses_dir: Directory containing individual conversation analysis JSONs
        output_path: Path where the full CSV should be saved

    Returns:
        DataFrame with analysis joined to full conversation text
    """
    logger.info("Creating full conversations CSV with analysis and text...")

    # Load original conversations
    if not conversations_json_path.exists():
        logger.error(f"Conversations file {conversations_json_path} does not exist")
        return pd.DataFrame()

    with conversations_json_path.open("r") as f:
        conversations_data = json.load(f)

    # Create conversation lookup with formatted text
    conversation_lookup = {}
    for conv in conversations_data:
        conv_id = conv.get("id")
        if not conv_id:
            continue

        # Format messages as readable text
        messages = conv.get("messages", [])
        formatted_messages: list[str] = []
        for msg in messages:
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
                formatted_messages.append(f"{timestamp_str} - {role}: {content}")
            else:
                formatted_messages.append(f"{role}: {content}")

        conversation_text = "\n\n".join(formatted_messages)

        # Normalize the conversation timestamp to YYYY-MM-DD
        normalized_date = ""
        created_at_raw = conv.get("created_at")
        if created_at_raw:
            try:
                dt = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
                normalized_date = dt.strftime("%Y-%m-%d")
            except (ValueError, AttributeError):
                try:
                    dt = datetime.fromtimestamp(int(created_at_raw) / 1000)
                    normalized_date = dt.strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    normalized_date = str(created_at_raw) if created_at_raw else ""

        conversation_lookup[conv_id] = {
            "conversation_id": conv_id,
            "created_at": conv.get("created_at"),
            "normalized_date": normalized_date,
            "full_conversation_text": conversation_text,
            "message_count": len(messages),
            "status": conv.get("status"),
            "rating": conv.get("rating"),
        }

    # Load analyses
    if not analyses_dir.exists():
        logger.error(f"Directory {analyses_dir} does not exist")
        return pd.DataFrame()

    json_files = list(analyses_dir.glob("*.json"))
    logger.info(
        f"Joining {len(json_files)} analyses with {len(conversation_lookup)} conversations..."
    )

    rows = []
    for json_file in json_files:
        conversation_id = json_file.stem

        try:
            with json_file.open("r") as f:
                analysis_data = json.load(f)

            # Get flattened analysis
            flat_analysis = flatten_conversation_analysis(
                conversation_id, analysis_data
            )

            # Get conversation data
            conv_data = conversation_lookup.get(conversation_id, {})

            # Merge them
            full_row = {**conv_data, **flat_analysis}
            rows.append(full_row)

        except Exception as e:
            logger.error(f"Error processing {json_file}: {e}")
            continue

    # Create DataFrame
    df = pd.DataFrame(rows)

    # Sort by overall_score (lowest first to see failures)
    if "overall_score" in df.columns:
        df = df.sort_values("overall_score", ascending=True)

    # Save to CSV
    df.to_csv(output_path, index=False)

    logger.success(
        f"Created full conversations CSV with {len(rows)} rows to {output_path}"
    )
    logger.info(f"Shape: {df.shape}")

    return df
