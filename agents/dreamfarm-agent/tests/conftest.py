"""Pytest configuration for DreamFarm Agent tests.

Ensures environment variables from .env are loaded for all tests.
"""
from dotenv import load_dotenv


# Load environment variables from .env at session start (non-destructive)
load_dotenv()
