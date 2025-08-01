"""Utility functions for the DreamFarm agent."""

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone


logger = logging.getLogger(__name__)


def get_current_timestamp() -> str:
    """Get current UTC timestamp in ISO format.
    
    Returns:
        ISO formatted timestamp string
    """
    return datetime.now(timezone.utc).isoformat()


def sanitize_user_input(user_input: str, max_length: int = 1000) -> str:
    """Sanitize user input for safety.
    
    Args:
        user_input: Raw user input string
        max_length: Maximum allowed length
        
    Returns:
        Sanitized input string
    """
    if not user_input:
        return ""
    
    # Remove excessive whitespace
    sanitized = " ".join(user_input.split())
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].strip()
        logger.warning(f"User input truncated to {max_length} characters")
    
    return sanitized


def safe_get_nested_value(data: Dict[str, Any], keys: list[str], default: Any = None) -> Any:
    """Safely get nested value from dictionary.
    
    Args:
        data: Dictionary to search
        keys: List of keys to traverse
        default: Default value if key not found
        
    Returns:
        Value if found, default otherwise
    """
    current = data
    try:
        for key in keys:
            current = current[key]
        return current
    except (KeyError, TypeError):
        return default


def format_error_message(error: Exception, context: Optional[str] = None) -> str:
    """Format error message for logging or user display.
    
    Args:
        error: Exception instance
        context: Optional context description
        
    Returns:
        Formatted error message
    """
    error_type = type(error).__name__
    error_msg = str(error)
    
    if context:
        return f"{context}: {error_type} - {error_msg}"
    return f"{error_type}: {error_msg}"
