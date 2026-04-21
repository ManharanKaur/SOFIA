from __future__ import annotations

import logging
import os
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def _read_env_key(*names: str) -> str:
    """Read the first non-empty env value from candidate names."""

    for name in names:
        value = (os.getenv(name) or "").strip().strip('"').strip("'")
        if value:
            return value
    return ""


# ============================================================================
# PAGE MAP (for "open" command)
# ============================================================================

def _default_page_map() -> dict[str, str]:
    """Return built-in pages used when no external library is available."""

    return {
        "google": "https://www.google.com",
        "youtube": "https://www.youtube.com",
        "you tube": "https://www.youtube.com",
        "spotify": "https://open.spotify.com",
        "github": "https://github.com",
        "gmail": "https://mail.google.com",
    }


def _safe_url(url: str) -> str | None:
    """Return a sanitized HTTP or HTTPS URL, or ``None`` when it is unsafe."""

    parsed_url = urlsplit(url.strip())
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return None

    return urlunsplit(
        (
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.query,
            parsed_url.fragment,
        )
    )


# Try to load optional external page library.
try:
    import Webpage_library as page_lib  # type: ignore
    _raw_page_map = getattr(page_lib, "page", None)
except (ImportError, AttributeError):
    _raw_page_map = None


def _build_page_map() -> dict[str, str]:
    """Build a safe page map from external library and defaults."""

    page_map = _default_page_map()
    if _raw_page_map is None:
        return page_map

    try:
        candidate_map = dict(_raw_page_map)
    except (TypeError, ValueError):
        logger.debug("Ignoring malformed page library data")
        return page_map

    for name, url in candidate_map.items():
        if not isinstance(name, str) or not isinstance(url, str):
            continue
        safe_url = _safe_url(url)
        if safe_url is not None:
            page_map[name.strip().lower()] = safe_url

    return page_map


PAGE_MAP = _build_page_map()


def get_page_map() -> dict[str, str]:
    """Return a copy of the assistant page map."""

    return dict(PAGE_MAP)


def open_url_in_browser(url: str) -> tuple[bool, str]:
    """Open a URL in a new browser tab on the machine running the backend."""

    safe_url = _safe_url(url)
    if safe_url is None:
        return False, "The URL is invalid or unsafe."

    try:
        opened = webbrowser.open_new_tab(safe_url)
        if opened:
            return True, f"Opening: {safe_url}"
        return False, "Could not open the browser tab."
    except Exception as exc:
        logger.exception("Failed to open browser URL")
        return False, f"Failed to open URL: {exc}"


# ============================================================================
# GOOGLE GEMINI API (for "chat" command and AI responses)
# ============================================================================

def ask_ai(prompt: str) -> str:
    """
    Send a prompt to Google Gemini API and return the AI response.
    
    Uses environment variable: GEMINI_API_KEY
    
    Args:
        prompt: The user question or command to send to the AI.
        
    Returns:
        AI response text, or a friendly fallback message if API is not configured
        or fails.
    """

    api_key = _read_env_key("GEMINI_API_KEY", "GOOGLE_API_KEY")
    print(f"Debug: Using API key: {api_key}")
    # If no API key is set, return a helpful message.
    if not api_key:
        return (
            "AI chat is not configured yet. "
            "Set the GEMINI_API_KEY (or GOOGLE_API_KEY) environment variable to enable it.",
            api_key
        )

    try:
        # Import the Google Generative AI library.
        import google.generativeai as genai  # type: ignore
    except ImportError:
        logger.error("google-generativeai library is not installed")
        return (
            "AI library is missing. "
            "Install it with: pip install google-generativeai"
        )

    try:
        # Configure the API with your key.
        genai.configure(api_key=api_key)
        
        # Use currently supported Gemini model names, with simple fallback.
        candidate_models = [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-flash-latest",
        ]

        for model_name in candidate_models:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                return response.text if response.text else "No response from AI."
            except Exception:
                logger.warning("Gemini model failed: %s", model_name)

        return "AI service is temporarily unavailable."
        
    except Exception as exc:
        logger.exception("AI generation failed")
        return f"AI service is temporarily unavailable. Error: {exc}"


# ============================================================================
# NEWS API (for "news" command - optional)
# ============================================================================

def get_news() -> str:
    """
    Fetch top 5 news headlines from the News API.
    
    Uses environment variable: NEWS_API_KEY
    
    Returns:
        A formatted string with news headlines, or a friendly message if API
        is not configured or fails.
    """

    api_key = os.getenv("NEWS_API_KEY")
    
    # If no API key is set, return a helpful message.
    if not api_key:
        return (
            "News service is not configured yet. "
            "Set the NEWS_API_KEY environment variable to enable it."
        )

    try:
        import requests  # type: ignore
    except ImportError:
        logger.error("requests library is not installed")
        return (
            "News library is missing. "
            "Install it with: pip install requests"
        )

    try:
        # Fetch top 5 news headlines from India.
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "country": "in",  # India
            "pageSize": 5,
            "apiKey": api_key,
        }
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()  # Raise error if request failed.
        
        data = response.json()
        
        # Check if we got articles.
        articles = data.get("articles", [])
        if not articles:
            return "No news articles found."
        
        # Format headlines into a readable string.
        headlines = []
        for i, article in enumerate(articles, 1):
            title = article.get("title", "No title")
            source = article.get("source", {}).get("name", "Unknown")
            headlines.append(f"{i}. {title} ({source})")
        
        return "Here are the latest headlines:\n\n" + "\n".join(headlines)
        
    except requests.exceptions.Timeout:
        logger.error("News API request timed out")
        return "News service is taking too long. Please try again."
    except requests.exceptions.RequestException as exc:
        logger.exception("News API request failed")
        return f"News service is temporarily unavailable. Error: {exc}"
    except Exception as exc:
        logger.exception("News parsing failed")
        return f"Failed to process news. Error: {exc}"
