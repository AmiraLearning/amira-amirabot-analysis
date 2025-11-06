"""Conversation fetcher for Amirabot API."""

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
from aiolimiter import AsyncLimiter
from loguru import logger
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)

from .constants import (
    API_CONVERSATION_LIST_ENDPOINT,
    DEFAULT_PAGE_LIMIT,
    DEFAULT_SORT_BY,
    FIRST_PAGE,
    ApiRequestKey,
    ApiResponseKey,
    LogMessage,
    SortDirection,
)
from .models import Conversation


class ConversationFetcher:
    """Handles fetching conversations from the API.

    Attributes:
        base_url: Base URL for the API endpoint.
        semaphore: Asyncio semaphore limiting concurrent API calls to 10.
        rate_limiter: AsyncLimiter limiting API calls to 10 per second.
        cache_dir: Directory for caching individual conversation files.
    """

    def __init__(self, *, base_url: str, no_cache: bool = False):
        """Initialize the ConversationFetcher.

        Args:
            base_url: Base URL for the API endpoint.
            no_cache: If True, ignore cached conversations and always fetch from API.
        """
        self.base_url = base_url
        self.no_cache = no_cache
        # Limit to 10 concurrent requests and 10 requests per second
        self.semaphore = asyncio.Semaphore(10)
        self.rate_limiter = AsyncLimiter(max_rate=10, time_period=1)

        # Create cache directory for individual conversations
        self.cache_dir = Path("conversations")
        self.cache_dir.mkdir(exist_ok=True)

    async def fetch_all(
        self,
        *,
        include_messages: bool = True,
        page_limit: int = DEFAULT_PAGE_LIMIT,
        sort_by: str = DEFAULT_SORT_BY,
        sort_direction: SortDirection = SortDirection.DESC,
        max_pages: int,
    ) -> list[Conversation]:
        """Fetch all conversations from the API with pagination.

        Iterates through all pages of conversations until no more data is available
        or the maximum number of pages is reached.
        Shows progress bar while fetching.

        Args:
            include_messages: Whether to include full message history in the response.
            page_limit: Number of conversations to fetch per page.
            sort_by: Field to sort conversations by.
            sort_direction: Sort direction (asc or desc).
            max_pages: Maximum number of pages to fetch.

        Returns:
            list[Conversation]: List of all fetched Conversation objects.
        """
        url = f"{self.base_url}{API_CONVERSATION_LIST_ENDPOINT}"
        all_conversations: list[Conversation] = []
        page_token: str | None = None
        page_num = FIRST_PAGE

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[green]{task.fields[convos]} conversations"),
        ) as progress:
            task = progress.add_task(
                "Fetching conversations from API...",
                total=max_pages,
                convos=0,
            )

            async with httpx.AsyncClient() as client:
                while True:
                    if page_num > max_pages:
                        logger.debug(LogMessage.MAX_PAGES_REACHED.format(max_pages))
                        break

                    payload = self._build_payload(
                        include_messages=include_messages,
                        limit=page_limit,
                        sort_by=sort_by,
                        sort_dir=sort_direction,
                        page_token=page_token,
                    )

                    # Apply rate limiting
                    async with self.semaphore:
                        async with self.rate_limiter:
                            response = await client.post(url, json=payload)
                            response.raise_for_status()

                    data = response.json()
                    conversations_data = data.get(ApiResponseKey.FILTERED_CONVOS, [])

                    conversations = [
                        Conversation.from_dict(data=convo_data)
                        for convo_data in conversations_data
                    ]

                    # Save each conversation to cache
                    for convo in conversations:
                        self._save_conversation_to_cache(conversation=convo)

                    all_conversations.extend(conversations)

                    # Update progress
                    progress.update(
                        task,
                        advance=1,
                        convos=len(all_conversations),
                    )

                    page_token = data.get(ApiResponseKey.NEXT_PAGE_TOKEN)
                    if not page_token or not conversations:
                        break

                    page_num += 1

        logger.success(
            f"Fetched {len(all_conversations)} conversations from {page_num} pages"
        )
        return all_conversations

    def _build_payload(
        self,
        *,
        include_messages: bool,
        limit: int,
        sort_by: str,
        sort_dir: SortDirection,
        page_token: str | None,
    ) -> dict[str, Any]:
        """Build the API request payload.

        Constructs the payload dictionary with filtering, sorting, and pagination parameters.
        Includes page_token only if provided for subsequent pages.

        Args:
            include_messages: Whether to include messages in the response.
            limit: Maximum number of conversations to return.
            sort_by: Field to sort by.
            sort_dir: Sort direction.
            page_token: Token for fetching the next page, if available.

        Returns:
            dict[str, Any]: Payload dictionary ready for API request.
        """
        payload: dict[str, Any] = {
            ApiRequestKey.FILTER: {},
            ApiRequestKey.LIMIT: limit,
            ApiRequestKey.SORT_BY: sort_by,
            ApiRequestKey.SORT_DIR: sort_dir,
            ApiRequestKey.INCLUDE_MESSAGES: include_messages,
        }

        if page_token:
            payload[ApiRequestKey.PAGE_TOKEN] = page_token

        return payload

    def _save_conversation_to_cache(self, *, conversation: Conversation) -> None:
        """Save individual conversation to cache file.

        Args:
            conversation: Conversation to cache.
        """
        cache_path = self.cache_dir / f"{conversation.id}.json"
        try:
            with cache_path.open("w") as f:
                json.dump(conversation.to_dict(), f, indent=2, default=str)
            logger.debug(f"Cached conversation {conversation.id} to {cache_path}")
        except Exception as e:
            logger.warning(f"Failed to cache conversation {conversation.id}: {e}")

    def _load_conversation_from_cache(
        self, *, conversation_id: str
    ) -> Conversation | None:
        """Load conversation from cache file if it exists.

        Args:
            conversation_id: ID of the conversation to load.

        Returns:
            Conversation if cached file exists, None otherwise.
        """
        cache_path = self.cache_dir / f"{conversation_id}.json"
        if not cache_path.exists():
            return None

        try:
            with cache_path.open("r") as f:
                data = json.load(f)
            conversation = Conversation.from_dict(data=data)
            logger.debug(f"Loaded conversation {conversation_id} from cache")
            return conversation
        except Exception as e:
            logger.warning(f"Failed to load cached conversation {conversation_id}: {e}")
            return None

    def load_all_from_cache(self) -> list[Conversation]:
        """Load all cached conversations from the conversations/ directory.

        Returns:
            list[Conversation]: List of all cached conversations.
        """
        conversations = []
        cache_files = list(self.cache_dir.glob("*.json"))

        if not cache_files:
            return conversations

        logger.info(f"Loading {len(cache_files)} conversations from cache...")

        for cache_file in cache_files:
            try:
                with cache_file.open("r") as f:
                    data = json.load(f)
                conversation = Conversation.from_dict(data=data)
                conversations.append(conversation)
            except Exception as e:
                logger.warning(f"Failed to load {cache_file}: {e}")

        logger.success(f"Loaded {len(conversations)} conversations from cache")
        return conversations
