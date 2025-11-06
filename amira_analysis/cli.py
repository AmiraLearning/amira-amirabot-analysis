"""CLI interface for Amirabot conversation analysis."""

import asyncio
from pathlib import Path

import typer
from loguru import logger

from .aggregator import aggregate_conversation_analyses, create_full_conversations_csv
from .analyzers.ai import AIConversationAnalyzer
from .analyzers.base import ConversationAnalyzer
from .reports import ReportGenerator
from .constants import (
    AMIRABOT_API_BASE_URL,
    DEFAULT_AI_CONCURRENCY,
    DEFAULT_ANALYSIS_OUTPUT,
    DEFAULT_CONVERSATIONS_OUTPUT,
    DEFAULT_EXCESSIVE_TURNS_THRESHOLD,
    DEFAULT_MAX_PAGES,
    DEFAULT_NEGATIVE_RATING_THRESHOLD,
    EXIT_CODE_ERROR,
    CliHelp,
    LogMessage,
)
from .fetcher import ConversationFetcher
from .storage import ConversationStorage

app = typer.Typer(help=CliHelp.APP)


async def _analyze_async(
    max_pages: int,
    negative_rating_threshold: int,
    excessive_turns_threshold: int,
    conversations_output: Path,
    analysis_output: Path,
    use_ai: bool,
    openai_api_key: str | None,
    ai_concurrency: int,
    no_cache_ai: bool,
    no_cache_conversations: bool,
    report_only: bool,
) -> None:
    """Async implementation of the analyze command."""
    # If report-only mode, skip fetching and analysis
    if report_only:
        logger.info("Report-only mode: Generating reports from existing analyses...")
        analyses_dir = Path("conversation_analyses")

        if not analyses_dir.exists() or not list(analyses_dir.glob("*.json")):
            logger.error(f"No analysis files found in {analyses_dir}/")
            raise typer.Exit(code=EXIT_CODE_ERROR)

        # Create full conversations CSV if conversations.json exists
        conversations_json = Path("conversations.json")
        if conversations_json.exists():
            full_csv_output = Path("conversations_full.csv")
            create_full_conversations_csv(
                conversations_json_path=conversations_json,
                analyses_dir=analyses_dir,
                output_path=full_csv_output,
            )

        # Generate reports - use conversations/ directory
        conversations_dir = Path("conversations")
        report_generator = ReportGenerator(
            analyses_dir=analyses_dir,
            conversations_json_path=conversations_json
            if conversations_json.exists()
            else None,
            conversations_dir=conversations_dir if conversations_dir.exists() else None,
        )

        # Create output directory
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)

        # Generate reports (markdown, JSON, and PDF)
        report_md_path = output_dir / "summary_report.md"
        logger.info(f"Generating reports to {output_dir}...")
        report_generator.generate_report(output_path=report_md_path)

        logger.success("Reports generated successfully!")
        return

    logger.info(LogMessage.FETCHING_ALL)

    fetcher = ConversationFetcher(
        base_url=AMIRABOT_API_BASE_URL, no_cache=no_cache_conversations
    )
    storage = ConversationStorage()

    # Check if we can use cached conversations
    if not no_cache_conversations:
        conversations = fetcher.load_all_from_cache()
        if conversations:
            logger.info(
                f"Using {len(conversations)} cached conversations from conversations/ folder"
            )
        else:
            logger.info("No cached conversations found, fetching from API...")
            conversations = await fetcher.fetch_all(
                include_messages=True, max_pages=max_pages
            )
    else:
        logger.info("--no-cache-conversations set, fetching from API...")
        conversations = await fetcher.fetch_all(
            include_messages=True, max_pages=max_pages
        )

    storage.save_conversations(
        conversations=conversations, filepath=conversations_output
    )

    # Choose analyzer based on flags
    if use_ai:
        if not openai_api_key:
            logger.error(
                "OpenAI API key required for AI analysis. Set OPENAI_API_KEY environment variable or use --openai-api-key flag."
            )
            raise typer.Exit(code=EXIT_CODE_ERROR)

        ai_analyzer = AIConversationAnalyzer(
            api_key=openai_api_key,
            max_concurrency=ai_concurrency,
            no_cache=no_cache_ai,
        )
        # AI analysis saves individual JSONs to conversation_analyses/
        await ai_analyzer.analyze_async(conversations=conversations)

        # Aggregate all individual conversation JSONs into a single CSV
        csv_output = Path(analysis_output).with_suffix(".csv")
        aggregate_conversation_analyses(
            analyses_dir=Path("conversation_analyses"), output_path=csv_output
        )

        # Create full conversations CSV with analysis joined to original text
        full_csv_output = Path("conversations_full.csv")
        create_full_conversations_csv(
            conversations_json_path=conversations_output,
            analyses_dir=Path("conversation_analyses"),
            output_path=full_csv_output,
        )

        # Generate actionable summary report
        conversations_dir = Path("conversations")
        report_generator = ReportGenerator(
            analyses_dir=Path("conversation_analyses"),
            conversations_json_path=conversations_output
            if conversations_output.exists()
            else None,
            conversations_dir=conversations_dir if conversations_dir.exists() else None,
        )

        # Create output directory
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)

        # Save reports to output folder
        report_path = output_dir / "summary_report.md"
        report_generator.generate_report(output_path=report_path)
    else:
        analyzer = ConversationAnalyzer(
            negative_rating_threshold=negative_rating_threshold,
            excessive_turns_threshold=excessive_turns_threshold,
        )
        analysis_result = analyzer.analyze(conversations=conversations)

        # For non-AI analysis, keep the old format
        storage.save_analysis(analysis=analysis_result, filepath=analysis_output)
        csv_output = Path(analysis_output).with_suffix(".csv")
        storage.save_analysis_csv(analysis=analysis_result, filepath=csv_output)


@app.command()
def analyze(
    max_pages: int = typer.Option(
        DEFAULT_MAX_PAGES, "--max-pages", "-m", help=CliHelp.MAX_PAGES
    ),
    negative_rating_threshold: int = typer.Option(
        DEFAULT_NEGATIVE_RATING_THRESHOLD,
        "--negative-threshold",
        "-n",
        help=CliHelp.NEGATIVE_THRESHOLD,
    ),
    excessive_turns_threshold: int = typer.Option(
        DEFAULT_EXCESSIVE_TURNS_THRESHOLD,
        "--turns-threshold",
        "-t",
        help=CliHelp.TURNS_THRESHOLD,
    ),
    conversations_output: Path = typer.Option(
        DEFAULT_CONVERSATIONS_OUTPUT,
        "--conversations-output",
        "-c",
        help=CliHelp.CONVERSATIONS_OUTPUT,
    ),
    analysis_output: Path = typer.Option(
        DEFAULT_ANALYSIS_OUTPUT, "--analysis-output", "-a", help=CliHelp.ANALYSIS_OUTPUT
    ),
    use_ai: bool = typer.Option(
        False,
        "--ai/--no-ai",
        help="Use AI (GPT-5-mini) for intelligent issue detection instead of simple rules.",
    ),
    openai_api_key: str = typer.Option(
        None,
        "--openai-api-key",
        envvar="OPENAI_API_KEY",
        help="OpenAI API key for AI analysis. Can also be set via OPENAI_API_KEY environment variable.",
    ),
    ai_concurrency: int = typer.Option(
        DEFAULT_AI_CONCURRENCY,
        "--ai-concurrency",
        help=f"Maximum concurrent AI API requests (default: {DEFAULT_AI_CONCURRENCY}). Higher values = faster but may hit rate limits.",
    ),
    no_cache_ai: bool = typer.Option(
        False,
        "--no-cache-ai",
        help=CliHelp.NO_CACHE_AI,
    ),
    no_cache_conversations: bool = typer.Option(
        False,
        "--no-cache-conversations",
        help=CliHelp.NO_CACHE_CONVERSATIONS,
    ),
    report_only: bool = typer.Option(
        False,
        "--report-only",
        help="Skip API fetching and analysis; only generate reports from existing analysis files in conversation_analyses/.",
    ),
) -> None:
    """Fetch and analyze Amirabot conversations for quality issues.

    This command fetches conversations from the Amirabot API, analyzes them for
    potential quality issues, and saves both the raw conversations and analysis
    results to JSON files.
    """
    try:
        asyncio.run(
            _analyze_async(
                max_pages=max_pages,
                negative_rating_threshold=negative_rating_threshold,
                excessive_turns_threshold=excessive_turns_threshold,
                conversations_output=conversations_output,
                analysis_output=analysis_output,
                use_ai=use_ai,
                openai_api_key=openai_api_key,
                ai_concurrency=ai_concurrency,
                no_cache_ai=no_cache_ai,
                no_cache_conversations=no_cache_conversations,
                report_only=report_only,
            )
        )
    except Exception as e:
        logger.exception(LogMessage.ERROR_OCCURRED.format(e))
        raise typer.Exit(code=EXIT_CODE_ERROR)
