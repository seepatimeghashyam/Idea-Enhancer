"""
OpenAlex API Connector for Idea Enhancer Project
Person 2: External Data & Provider Engineering

This module connects directly to the official OpenAlex Works API to search and retrieve
academic research papers. It retrieves core paper metadata, reconstructs inverted-index
abstracts, converts responses into clean Python dictionaries, and handles missing metadata,
timeouts, rate limits, and network errors gracefully.
"""

import os
import time
import requests
from typing import Any, Dict, List, Optional

# Base URL for the official OpenAlex Works API endpoint
OPENALEX_WORKS_URL = "https://api.openalex.org/works"

# Default request timeout in seconds to prevent the application from hanging
DEFAULT_TIMEOUT = 15

# Default polite-pool identifier
# OpenAlex encourages users to provide an email in the User-Agent or mailto parameter
# to join the polite pool for better performance and reliability.
DEFAULT_EMAIL = os.getenv("OPENALEX_MAILTO", "idea-enhancer@example.com")


def reconstruct_abstract(inverted_index: Optional[Dict[str, List[int]]]) -> Optional[str]:
    """
    Reconstructs full human-readable abstract text from OpenAlex's inverted index format.

    OpenAlex does not store plain text abstracts directly. Instead, it provides an
    'abstract_inverted_index', which is a dictionary mapping each word to a list of
    zero-based integer positions where that word appears in the original text.
    Example: {"Quantum": [0], "computing": [1], "uses": [2], "qubits": [3]}

    Args:
        inverted_index: Dictionary of {word: [positions]}, or None if unavailable.

    Returns:
        The reconstructed abstract as a single string, or None if missing or empty.
    """
    if not inverted_index or not isinstance(inverted_index, dict):
        return None

    try:
        # Collect (position, word) tuples from the inverted index dictionary
        position_word_pairs: List[tuple[int, str]] = []
        for word, positions in inverted_index.items():
            if isinstance(positions, list):
                for pos in positions:
                    if isinstance(pos, int):
                        position_word_pairs.append((pos, str(word)))

        if not position_word_pairs:
            return None

        # Sort all words by their positional index in the text
        position_word_pairs.sort(key=lambda pair: pair[0])

        # Join tokens into a single clean string
        return " ".join(word for _, word in position_word_pairs).strip()
    except Exception:
        # In case of any unexpected structure, fail safely without raising an exception
        return None


def extract_authors(authorships: Optional[List[Dict[str, Any]]]) -> List[str]:
    """
    Extracts a list of author display names from the OpenAlex 'authorships' metadata array.

    Args:
        authorships: List of authorship dictionaries returned by OpenAlex.

    Returns:
        List of cleaned author name strings (e.g., ["Alice Smith", "Bob Jones"]).
        Returns an empty list [] if no authors are listed.
    """
    if not authorships or not isinstance(authorships, list):
        return []

    author_names: List[str] = []
    for item in authorships:
        if isinstance(item, dict):
            author_dict = item.get("author")
            if isinstance(author_dict, dict):
                name = author_dict.get("display_name")
                if name and isinstance(name, str) and name.strip():
                    author_names.append(name.strip())

    return author_names


def parse_work(raw_work: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts a single raw OpenAlex work item from the API response into a clean,
    standardized Python dictionary containing only the required fields.

    Fields extracted:
      1. paper_id: OpenAlex unique ID (URI)
      2. title: Title of the research paper
      3. publication_year: Year the paper was published
      4. authors: List of author names
      5. doi: Digital Object Identifier URL
      6. abstract: Clean abstract text (reconstructed)
      7. original_url: Landing page URL or paper link

    Args:
        raw_work: Raw dictionary representing one work from OpenAlex.

    Returns:
        Dictionary containing standardized, sanitized metadata fields.
    """
    # 1. OpenAlex paper ID (e.g. "https://openalex.org/W2923051437")
    paper_id = raw_work.get("id")

    # 2. Paper title (fallback to display_name if title is absent)
    title = raw_work.get("title") or raw_work.get("display_name")
    if title and isinstance(title, str):
        title = title.strip()

    # 3. Publication year (integer, e.g. 2021)
    pub_year = raw_work.get("publication_year")

    # 4. Authors (list of strings)
    authors = extract_authors(raw_work.get("authorships"))

    # 5. DOI (e.g. "https://doi.org/10.1002/er.4444")
    doi = raw_work.get("doi")

    # 6. Abstract (reconstructed from inverted index)
    abstract = reconstruct_abstract(raw_work.get("abstract_inverted_index"))

    # 7. Original paper URL (prefer primary_location landing page, fallback to DOI or paper_id)
    primary_location = raw_work.get("primary_location") or {}
    original_url = None
    if isinstance(primary_location, dict):
        original_url = primary_location.get("landing_page_url") or primary_location.get("pdf_url")

    if not original_url:
        original_url = doi or paper_id

    return {
        "paper_id": paper_id,
        "title": title,
        "publication_year": pub_year,
        "authors": authors,
        "doi": doi,
        "abstract": abstract,
        "original_url": original_url,
    }


def search_openalex_works(
    query: str,
    per_page: int = 5,
    mailto: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = 1,
) -> List[Dict[str, Any]]:
    """
    Executes an HTTP GET search query against the official OpenAlex Works API.

    Features:
      - Validates and sanitizes the user search query.
      - Attaches user-agent and polite-pool mailto parameters.
      - Supports optional OpenAlex API key.
      - Configures request timeout to prevent hanging.
      - Handles HTTP errors, network disconnects, timeouts, and rate limits (429).
      - Converts valid responses into clean Python dictionaries.

    Args:
        query: Search term or keywords entered by the user.
        per_page: Number of papers to retrieve (default: 5, clamped between 1 and 50).
        mailto: User email address for polite-pool access (optional).
        api_key: OpenAlex API key (optional, can also be set via OPENALEX_API_KEY env var).
        timeout: Request timeout in seconds (default: 15).
        max_retries: Number of automatic retries if OpenAlex returns rate limit 429 (default: 1).

    Returns:
        List of standardized paper dictionaries. Returns empty list [] on error or no match.
    """
    if not query or not query.strip():
        print("[Warning] Search query cannot be empty.")
        return []

    # Clamp per_page to a reasonable range
    safe_per_page = max(1, min(per_page, 50))

    # Determine email for OpenAlex polite pool
    email = (mailto or DEFAULT_EMAIL).strip()

    # Determine API key if provided via argument or environment variable
    resolved_api_key = api_key or os.getenv("OPENALEX_API_KEY")

    # Build query parameters
    params: Dict[str, Any] = {
        "search": query.strip(),
        "per_page": safe_per_page,
    }
    if email:
        params["mailto"] = email
    if resolved_api_key:
        params["api_key"] = resolved_api_key

    # Build HTTP headers
    headers = {
        "User-Agent": f"IdeaEnhancer/1.0 (mailto:{email})",
        "Accept": "application/json",
    }
    if resolved_api_key:
        headers["api-key"] = resolved_api_key

    # Attempt the request (with automatic retry for transient 429 rate limit if applicable)
    attempts = 0
    while attempts <= max_retries:
        attempts += 1
        try:
            # Send HTTP GET request
            response = requests.get(
                OPENALEX_WORKS_URL,
                params=params,
                headers=headers,
                timeout=timeout,
            )

            # Handle HTTP 429: Rate limit exceeded or search cluster under high load
            if response.status_code == 429:
                retry_after_sec = 15
                details = "Anonymous search is temporarily rate-limited."
                try:
                    payload = response.json()
                    if "message" in payload:
                        details = payload["message"]
                    if "retryAfter" in payload and isinstance(payload["retryAfter"], (int, float)):
                        retry_after_sec = int(payload["retryAfter"])
                except Exception:
                    pass

                # If retries remain and wait time is reasonable, wait and retry once
                if attempts <= max_retries and retry_after_sec <= 30:
                    print(f"[Notice] OpenAlex search cluster busy. Waiting {retry_after_sec}s to retry...")
                    time.sleep(retry_after_sec)
                    continue
                else:
                    print(f"[HTTP 429] Rate limit reached: {details}")
                    print("Tip: Provide a free OpenAlex API key or try again in a few moments.")
                    return []

            # Raise HTTPError if status code is 4xx or 5xx
            response.raise_for_status()

            # Parse JSON body
            data = response.json()
            raw_works = data.get("results", [])

            # Transform raw items into clean Python dictionaries
            parsed_papers = [
                parse_work(work) for work in raw_works if isinstance(work, dict)
            ]
            return parsed_papers

        except requests.exceptions.Timeout:
            print(f"[Error] Request timed out after {timeout} seconds while reaching OpenAlex.")
            return []
        except requests.exceptions.ConnectionError:
            print("[Error] Network connection error. Please check your internet connection or DNS.")
            return []
        except requests.exceptions.HTTPError as http_err:
            print(f"[HTTP Error] Status {response.status_code}: {http_err}")
            return []
        except requests.exceptions.RequestException as req_err:
            print(f"[Request Error] An unexpected network error occurred: {req_err}")
            return []
        except ValueError:
            print("[Error] Failed to parse JSON response from OpenAlex.")
            return []

    return []


def print_research_papers(papers: List[Dict[str, Any]]) -> None:
    """
    Prints retrieved research papers in a clear, readable format.

    Args:
        papers: List of paper dictionaries returned by search_openalex_works.
    """
    if not papers:
        print("\nNo research papers found.")
        return

    separator = "=" * 80
    sub_sep = "-" * 80

    print(f"\n{separator}")
    print(f" Found {len(papers)} Research Paper(s) from OpenAlex")
    print(separator)

    for idx, paper in enumerate(papers, start=1):
        title = paper.get("title") or "Untitled Paper"
        year = paper.get("publication_year")
        year_str = str(year) if year is not None else "N/A"

        authors = paper.get("authors") or []
        authors_str = ", ".join(authors) if authors else "Unknown / Not specified"

        doi_str = paper.get("doi") or "N/A"
        url_str = paper.get("original_url") or "N/A"
        id_str = paper.get("paper_id") or "N/A"

        abstract = paper.get("abstract")
        if not abstract:
            abstract_str = "No abstract available in OpenAlex metadata."
        else:
            # Neatly truncate long abstracts to ~350 characters for clean terminal display
            max_len = 350
            if len(abstract) > max_len:
                abstract_str = abstract[:max_len].rstrip() + "... [truncated]"
            else:
                abstract_str = abstract

        print(f"\n[Result {idx}]")
        print(f"  Title:            {title}")
        print(f"  Publication Year: {year_str}")
        print(f"  Authors:          {authors_str}")
        print(f"  DOI:              {doi_str}")
        print(f"  Original URL:     {url_str}")
        print(f"  OpenAlex ID:      {id_str}")
        print(f"  Abstract:         {abstract_str}")
        print(sub_sep)


def main() -> None:
    """
    Main interactive entry point for testing and executing the OpenAlex connector.
    """
    print("=" * 80)
    print(" Idea Enhancer - OpenAlex Research Paper Connector")
    print(" Person 2: External Data & Provider Engineering")
    print("=" * 80)

    try:
        user_query = input("\nEnter research topic or keywords (e.g., 'deep learning healthcare'): ").strip()
        if not user_query:
            print("No query entered. Exiting.")
            return

        print(f"\nSending GET request to OpenAlex for query: '{user_query}'...")
        papers = search_openalex_works(query=user_query, per_page=5)
        print_research_papers(papers)

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user. Goodbye!")


if __name__ == "__main__":
    main()
