"""Amirabot conversation analysis tool - Entry point."""

from dotenv import load_dotenv

from amira_analysis.cli import app

# Load environment variables from .env file
load_dotenv()

if __name__ == "__main__":
    app()
