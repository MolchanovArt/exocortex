"""OpenAI client wrapper for classification and summarization."""

import logging
from typing import Literal, Optional

from openai import OpenAI

from exocortex.core.config import config
from exocortex.core.models import UserProfile

logger = logging.getLogger(__name__)

# Classification prompt
CLASSIFICATION_PROMPT = """You are a helpful assistant that classifies text items into one of four categories:

- task: Something that requires action or completion
- idea: A thought, concept, or suggestion worth remembering
- note: Reference information or documentation
- noise: Unimportant or irrelevant content

Classify the following text into exactly one category: task, idea, note, or noise.

Respond with ONLY the category name (task, idea, note, or noise), nothing else."""

# Summarization prompt template
SUMMARIZATION_PROMPT_TEMPLATE = """Summarize the following text in 1-2 sentences. Focus on the key information or action item.

Text to summarize:
{text}"""


def get_openai_client() -> OpenAI:
    """
    Get an initialized OpenAI client.

    Returns:
        OpenAI client instance

    Raises:
        ValueError: If OPENAI_API_KEY is not set
    """
    if not config.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set in configuration")

    return OpenAI(api_key=config.openai_api_key)


def classify_timeline_item(text: str, user_profile: Optional[UserProfile] = None) -> Literal["task", "idea", "note", "noise"]:
    """
    Classify a timeline item text into one of: task, idea, note, noise.

    Args:
        text: The text content to classify
        user_profile: Optional user profile for context (not used in current implementation)

    Returns:
        One of: "task", "idea", "note", "noise"

    Raises:
        ValueError: If OpenAI API key is not configured
        Exception: If OpenAI API call fails
    """
    client = get_openai_client()

    try:
        response = client.chat.completions.create(
            model=config.openai_model,
            messages=[
                {"role": "system", "content": CLASSIFICATION_PROMPT},
                {"role": "user", "content": text[:2000]},  # Limit text length
            ],
            temperature=0.3,  # Lower temperature for more consistent classification
            max_tokens=10,  # We only need the category name
        )

        category = response.choices[0].message.content.strip().lower()

        # Validate and normalize the response
        valid_categories = ["task", "idea", "note", "noise"]
        if category not in valid_categories:
            logger.warning(f"OpenAI returned invalid category '{category}', defaulting to 'note'")
            return "note"

        return category  # type: ignore

    except Exception as e:
        logger.error(f"Error classifying timeline item: {e}")
        raise


def summarize_timeline_item(text: str, user_profile: Optional[UserProfile] = None) -> str:
    """
    Generate a short summary of a timeline item text.

    Args:
        text: The text content to summarize
        user_profile: Optional user profile for context (not used in current implementation)

    Returns:
        A short summary (1-2 sentences)

    Raises:
        ValueError: If OpenAI API key is not configured
        Exception: If OpenAI API call fails
    """
    client = get_openai_client()

    # Build prompt with user context if available
    prompt = SUMMARIZATION_PROMPT_TEMPLATE.format(text=text[:2000])  # Limit text length

    if user_profile:
        # Add user context to help with summarization
        context = f"User context: {user_profile.name}, {', '.join(user_profile.roles[:2])}"
        prompt = f"{context}\n\n{prompt}"

    try:
        response = client.chat.completions.create(
            model=config.openai_model,
            messages=[
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=150,  # Limit summary length
        )

        summary = response.choices[0].message.content.strip()
        return summary

    except Exception as e:
        logger.error(f"Error summarizing timeline item: {e}")
        raise
