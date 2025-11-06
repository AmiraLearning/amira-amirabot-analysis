"""Utilities for formatting conversation data."""

from datetime import datetime

from loguru import logger


def format_conversation_text(conversation_id: str, conversations_lookup: dict) -> str:
    """Format conversation messages as readable text with conversation date header.

    Args:
        conversation_id: The conversation ID
        conversations_lookup: Dictionary mapping conversation IDs to full conversation data

    Returns:
        Formatted conversation text with conversation date and role labels with timestamps
    """
    logger.debug(f"Formatting conversation {conversation_id}")
    logger.debug(f"Conversations lookup has {len(conversations_lookup)} entries")

    conv = conversations_lookup.get(conversation_id)
    if not conv:
        logger.error(
            f"Conversation {conversation_id} not found in lookup! "
            f"Available keys sample: {list(conversations_lookup.keys())[:5]}"
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
                                dt = datetime.fromtimestamp(int(first_msg_created) / 1000)
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


def get_date_range(
    conversations: list[dict], conversations_lookup: dict
) -> tuple[str, str]:
    """Get the first and latest conversation dates.

    Args:
        conversations: List of conversation analysis dicts
        conversations_lookup: Dictionary mapping conversation IDs to full conversation data

    Returns:
        Tuple of (first_date, latest_date) in YYYY-MM-DD format, or ("N/A", "N/A") if no dates available
    """
    dates = []

    for conv in conversations:
        conv_id = conv.get("conversation_id")
        if not conv_id:
            continue

        # Try to get the conversation from lookup
        full_conv = conversations_lookup.get(conv_id)
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
