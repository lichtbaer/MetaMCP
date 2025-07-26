"""
Helper utilities for MCP Meta-Server

This module contains various utility functions used throughout the application,
including tool embedding generation, schema validation, and other common operations.
"""

import asyncio
import hashlib
import re
from datetime import UTC, datetime
from functools import wraps
from typing import Any

from ..exceptions import EmbeddingError, ValidationError


def create_tool_embedding(tool_description: str, tool_capabilities: list[str]) -> str:
    """
    Create a text representation suitable for embedding generation.

    This function combines tool description and capabilities into a
    comprehensive text that can be used to generate vector embeddings.

    Args:
        tool_description: Description of the tool
        tool_capabilities: List of tool capabilities

    Returns:
        Combined text for embedding generation

    Raises:
        EmbeddingError: If input validation fails
    """
    try:
        if not tool_description or not isinstance(tool_description, str):
            raise EmbeddingError(
                message="Tool description must be a non-empty string",
                error_code="invalid_tool_description",
            )

        if not isinstance(tool_capabilities, list):
            raise EmbeddingError(
                message="Tool capabilities must be a list",
                error_code="invalid_tool_capabilities",
            )

        # Create comprehensive text
        embedding_text_parts = [
            f"Tool Description: {tool_description.strip()}",
        ]

        if tool_capabilities:
            capabilities_text = ", ".join(tool_capabilities)
            embedding_text_parts.append(f"Capabilities: {capabilities_text}")

        embedding_text = " | ".join(embedding_text_parts)

        # Ensure reasonable length (most embedding models have token limits)
        max_length = 2000
        if len(embedding_text) > max_length:
            embedding_text = embedding_text[:max_length] + "..."

        return embedding_text

    except Exception as e:
        if isinstance(e, EmbeddingError):
            raise
        raise EmbeddingError(
            message=f"Failed to create embedding text: {str(e)}",
            error_code="embedding_text_failed",
        ) from e


def validate_tool_schema(tool_data: dict[str, Any]) -> bool:
    """
    Validate tool registration schema.

    Args:
        tool_data: Tool data dictionary to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If schema validation fails
    """
    required_fields = ["name", "description", "endpoint"]

    # Check required fields
    for field in required_fields:
        if field not in tool_data:
            raise ValidationError(
                message=f"Required field '{field}' is missing",
                error_code="missing_required_field",
            )

        if not tool_data[field] or not isinstance(tool_data[field], str):
            raise ValidationError(
                message=f"Required field '{field}' must be a non-empty string",
                error_code="invalid_field_type",
            )

    # Validate name format
    name_pattern = r"^[a-zA-Z0-9_-]+$"
    if not re.match(name_pattern, tool_data["name"]):
        raise ValidationError(
            message="Name must contain only alphanumeric characters, hyphens, and underscores",
            error_code="invalid_name_format",
        )

    # Validate endpoint URL
    if not is_valid_url(tool_data["endpoint"]):
        raise ValidationError(
            message="Endpoint must be a valid URL", error_code="invalid_endpoint_url"
        )

    # Validate optional fields if present
    if "capabilities" in tool_data:
        if not isinstance(tool_data["capabilities"], list):
            raise ValidationError(
                message="Capabilities must be a list",
                error_code="invalid_capabilities_type",
            )

    if "security_level" in tool_data:
        if (
            not isinstance(tool_data["security_level"], int)
            or tool_data["security_level"] < 0
        ):
            raise ValidationError(
                message="Security level must be a non-negative integer",
                error_code="invalid_security_level",
            )

    if "schema" in tool_data:
        if not isinstance(tool_data["schema"], dict):
            raise ValidationError(
                message="Schema must be a dictionary", error_code="invalid_schema_type"
            )

    return True


def is_valid_url(url: str) -> bool:
    """
    Validate if a string is a valid URL.

    Args:
        url: URL string to validate

    Returns:
        True if valid URL
    """
    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    return url_pattern.match(url) is not None


def generate_tool_id(tool_name: str, endpoint: str) -> str:
    """
    Generate a unique tool ID based on name and endpoint.

    Args:
        tool_name: Tool name
        endpoint: Tool endpoint URL

    Returns:
        Unique tool ID
    """
    # Create hash from name and endpoint
    combined = f"{tool_name}:{endpoint}"
    tool_hash = hashlib.sha256(combined.encode()).hexdigest()[:8]

    # Clean name for ID
    clean_name = re.sub(r"[^a-zA-Z0-9_-]", "", tool_name.lower())

    return f"{clean_name}-{tool_hash}"


def sanitize_input(data: Any, max_length: int = 1000) -> Any:
    """
    Sanitize input data for logging and display.

    Args:
        data: Input data to sanitize
        max_length: Maximum length for string data

    Returns:
        Sanitized data
    """
    if isinstance(data, str):
        if len(data) > max_length:
            return data[:max_length] + "..."
        return data

    elif isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            # Skip sensitive fields
            if any(
                sensitive in key.lower()
                for sensitive in ["password", "secret", "token", "key"]
            ):
                sanitized[key] = "***"
            else:
                sanitized[key] = sanitize_input(value, max_length)
        return sanitized

    elif isinstance(data, list):
        return [
            sanitize_input(item, max_length) for item in data[:10]
        ]  # Limit list size

    else:
        return data


def format_timestamp(dt: datetime | None = None) -> str:
    """
    Format timestamp in ISO format.

    Args:
        dt: Datetime object, defaults to current UTC time

    Returns:
        ISO formatted timestamp string
    """
    if dt is None:
        dt = datetime.now(UTC)

    return dt.isoformat()


def extract_domain(url: str) -> str:
    """
    Extract domain from URL.

    Args:
        url: URL string

    Returns:
        Domain name
    """
    pattern = r"https?://([^/]+)"
    match = re.match(pattern, url)
    return match.group(1) if match else url


def retry_async(
    max_retries: int = 3, delay: float = 1.0, exponential_backoff: bool = True
):
    """
    Decorator for async functions with retry logic.

    Args:
        max_retries: Maximum number of retries
        delay: Initial delay between retries
        exponential_backoff: Use exponential backoff for delays
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if attempt < max_retries:
                        await asyncio.sleep(current_delay)
                        if exponential_backoff:
                            current_delay *= 2
                    else:
                        raise last_exception

            raise last_exception

        return wrapper

    return decorator


def chunk_list(lst: list[Any], chunk_size: int) -> list[list[Any]]:
    """
    Split a list into chunks of specified size.

    Args:
        lst: List to chunk
        chunk_size: Size of each chunk

    Returns:
        List of chunks
    """
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def deep_merge_dicts(dict1: dict[str, Any], dict2: dict[str, Any]) -> dict[str, Any]:
    """
    Deep merge two dictionaries.

    Args:
        dict1: First dictionary
        dict2: Second dictionary (takes precedence)

    Returns:
        Merged dictionary
    """
    result = dict1.copy()

    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value

    return result


def calculate_similarity_score(
    embedding1: list[float], embedding2: list[float]
) -> float:
    """
    Calculate cosine similarity between two embeddings.

    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector

    Returns:
        Cosine similarity score (0-1)
    """
    if len(embedding1) != len(embedding2):
        raise ValueError("Embeddings must have the same dimension")

    # Calculate dot product
    dot_product = sum(a * b for a, b in zip(embedding1, embedding2, strict=False))

    # Calculate magnitudes
    magnitude1 = sum(a * a for a in embedding1) ** 0.5
    magnitude2 = sum(b * b for b in embedding2) ** 0.5

    # Avoid division by zero
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    # Calculate cosine similarity
    similarity = dot_product / (magnitude1 * magnitude2)

    # Ensure result is between 0 and 1
    return max(0.0, min(1.0, (similarity + 1) / 2))
