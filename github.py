"""
GitHub Repository Search API Connector for Idea Enhancer Project
Person 2: External Data & Provider Engineering

This module interacts with the official GitHub REST API repository search endpoint
(https://api.github.com/search/repositories) to search and retrieve open-source
repositories relevant to user-provided project ideas and topics.

It extracts key metadata, normalizes fields into clean Python dictionaries, handles
missing metadata safely, supports optional token-based authentication via environment
variables, and provides robust handling for timeouts, network failures, and API rate limits.
"""

import os
import time
import requests
from typing import Any, Dict, List, Optional

# Official GitHub REST API search repositories endpoint
GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"

# Default request timeout in seconds
DEFAULT_TIMEOUT = 10

# Default number of repositories to retrieve (capped at 5 as per requirement)
DEFAULT_PER_PAGE = 5


def get_github_token(explicit_token: Optional[str] = None) -> Optional[str]:
    """
    Retrieves the GitHub Personal Access Token from an explicit argument or
    standard environment variables (GITHUB_TOKEN or GH_TOKEN).

    Tokens are NEVER hardcoded in source code to adhere to security best practices.

    Args:
        explicit_token: Optional token string passed directly to the function.

    Returns:
        The token string if found, otherwise None (proceeds unauthenticated).
    """
    if explicit_token and explicit_token.strip():
        return explicit_token.strip()

    env_token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if env_token and env_token.strip():
        return env_token.strip()

    return None


def extract_license(license_info: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Safely extracts the human-readable license name or SPDX identifier from GitHub's
    nested license object.

    Args:
        license_info: Nested license dictionary from the GitHub API response,
                      or None if no license is detected.

    Returns:
        License name string (e.g., 'MIT License', 'Apache-2.0'), or None if absent.
    """
    if not license_info or not isinstance(license_info, dict):
        return None

    # Prefer the full display name, fallback to the standard spdx_id
    license_name = license_info.get("name") or license_info.get("spdx_id")
    if license_name and isinstance(license_name, str) and license_name.strip():
        # Filter out placeholders like 'NOASSERTION'
        if license_name.strip().upper() == "NOASSERTION":
            return None
        return license_name.strip()

    return None


def extract_owner(owner_info: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Safely extracts the repository owner's username (login) from GitHub's nested
    owner dictionary.

    Args:
        owner_info: Nested owner dictionary from the GitHub API response.

    Returns:
        Owner username string (e.g., 'torvalds'), or None if absent.
    """
    if not owner_info or not isinstance(owner_info, dict):
        return None

    login = owner_info.get("login")
    if login and isinstance(login, str) and login.strip():
        return login.strip()

    return None


def parse_repository(raw_repo: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms a raw GitHub repository item from the API response into a clean,
    standardized Python dictionary containing only the required fields.

    Extracted fields:
      1. Repository ID
      2. Repository name
      3. Full name (owner/name)
      4. Description
      5. Programming language
      6. Repository URL
      7. Licence
      8. Owner username
      9. Creation date
      10. Last updated date
      11. Number of stars
      12. Default branch

    Args:
        raw_repo: Raw repository dictionary from GitHub API's 'items' list.

    Returns:
        A standardized Python dictionary with sanitized metadata.
    """
    repo_id = raw_repo.get("id")
    name = raw_repo.get("name")
    full_name = raw_repo.get("full_name")
    description = raw_repo.get("description")
    language = raw_repo.get("language")
    url = raw_repo.get("html_url")
    license_name = extract_license(raw_repo.get("license"))
    owner = extract_owner(raw_repo.get("owner"))
    created_at = raw_repo.get("created_at")
    updated_at = raw_repo.get("updated_at")
    stars = raw_repo.get("stargazers_count")
    default_branch = raw_repo.get("default_branch")

    return {
        "id": repo_id,
        "name": name.strip() if isinstance(name, str) else name,
        "full_name": full_name.strip() if isinstance(full_name, str) else full_name,
        "description": description.strip() if isinstance(description, str) else description,
        "language": language.strip() if isinstance(language, str) else language,
        "url": url.strip() if isinstance(url, str) else url,
        "license": license_name,
        "owner": owner,
        "created_at": created_at,
        "updated_at": updated_at,
        "stars": stars if isinstance(stars, int) else 0,
        "default_branch": default_branch.strip() if isinstance(default_branch, str) else default_branch,
    }


def search_github_repositories(
    query: str,
    per_page: int = DEFAULT_PER_PAGE,
    token: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> List[Dict[str, Any]]:
    """
    Searches GitHub repositories using the official GitHub REST API repository search endpoint.

    Features:
      - Validates the query and handles empty/whitespace inputs gracefully.
      - Sets required GitHub headers (User-Agent, Accept, API version).
      - Attaches optional Bearer token authentication if available.
      - Enforces request timeout to prevent hanging.
      - Detects and handles GitHub API rate limits (HTTP 403/429) with reset time calculation.
      - Catches network, connection, and HTTP errors without crashing.
      - Converts valid response items into clean Python dictionaries.

    Args:
        query: Search term or keywords entered by the user.
        per_page: Number of repositories to retrieve (default: 5, max: 5).
        token: Optional GitHub Personal Access Token (defaults to env vars).
        timeout: Request timeout in seconds (default: 10).

    Returns:
        List of standardized repository dictionaries. Returns empty list [] if
        the query is empty, no results are found, or an error occurs.
    """
    # 1. Handle empty search queries
    if not query or not query.strip():
        print("[Warning] Search query cannot be empty. Please provide valid keywords.")
        return []

    clean_query = query.strip()

    # 2. Clamp per_page to maximum 5 as per requirement
    safe_per_page = max(1, min(per_page, 5))

    # 3. Build query parameters
    params: Dict[str, Any] = {
        "q": clean_query,
        "per_page": safe_per_page,
    }

    # 4. Build HTTP headers
    # GitHub requires a User-Agent header; requests without it are rejected with HTTP 403
    headers: Dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "IdeaEnhancer-GitHubConnector/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # 5. Optional authentication via environment variable or argument
    auth_token = get_github_token(token)
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    # A single retry is the safe default. Callers may increase it, but retries
    # are always bounded and never continue indefinitely.
    max_retries = 1

    for attempt in range(max_retries + 1):
        try:
            # 6. Send HTTP GET request
            response = requests.get(
                GITHUB_SEARCH_URL,
                params=params,
                headers=headers,
                timeout=timeout,
            )

            # 7. Detect primary/secondary rate limits.
            if response.status_code in (403, 429):
                rate_limit_remaining = response.headers.get("x-ratelimit-remaining")
                reset_timestamp = response.headers.get("x-ratelimit-reset")
                retry_after = response.headers.get("Retry-After") or response.headers.get("retry-after")

                details = ""
                try:
                    error_payload = response.json()
                    details = error_payload.get("message", "") if isinstance(error_payload, dict) else ""
                except (ValueError, TypeError):
                    pass

                is_rate_limited = (
                    response.status_code == 429
                    or rate_limit_remaining == "0"
                    or "rate limit" in details.lower()
                )

                if is_rate_limited:
                    wait_seconds = None

                    # Retry-After is the preferred instruction for secondary limits.
                    if retry_after:
                        try:
                            wait_seconds = max(0, int(float(retry_after)))
                        except (ValueError, TypeError):
                            wait_seconds = None

                    # For primary limits, wait until the reset timestamp.
                    if wait_seconds is None and reset_timestamp:
                        try:
                            wait_seconds = max(0, int(reset_timestamp) - int(time.time()))
                        except (ValueError, TypeError):
                            wait_seconds = None

                    # Do not sleep for an excessive period in an interactive search.
                    # If GitHub asks for more than 60 seconds, fail clearly instead.
                    if attempt < max_retries and wait_seconds is not None and wait_seconds <= 60:
                        print(f"[Rate limit] GitHub asked us to wait {wait_seconds} seconds. Retrying once...")
                        time.sleep(wait_seconds)
                        continue

                    reset_info = f" (retry wait: {wait_seconds}s)" if wait_seconds is not None else ""
                    print(f"[HTTP {response.status_code}] GitHub API rate limit exceeded{reset_info}.")
                    if details:
                        print(f"Details: {details}")
                    if not auth_token:
                        print("Tip: Authenticate with a personal GITHUB_TOKEN environment variable to increase your rate limit.")
                    return []

            # 8. Raise for non-rate-limit HTTP errors (not retried).
            response.raise_for_status()

            # 9. Parse JSON response.
            data = response.json()
            raw_items = data.get("items", [])

            # 10. Transform into clean dictionaries.
            return [
                parse_repository(item) for item in raw_items if isinstance(item, dict)
            ]

        except requests.exceptions.Timeout:
            print(f"[Error] Request timed out after {timeout} seconds while connecting to GitHub API.")
            return []
        except requests.exceptions.ConnectionError:
            print("[Error] Failed to connect to GitHub. Please check your network connection or DNS settings.")
            return []
        except requests.exceptions.HTTPError as http_err:
            print(f"[HTTP Error] GitHub API returned status {response.status_code}: {http_err}")
            return []
        except requests.exceptions.RequestException as req_err:
            print(f"[Request Error] An unexpected error occurred while communicating with GitHub: {req_err}")
            return []
        except ValueError:
            print("[Error] Failed to decode JSON response from GitHub API.")
            return []

    return []


def print_repositories(repositories: List[Dict[str, Any]]) -> None:
    """
    Displays the retrieved GitHub repositories in a clear, formatted, human-readable layout.

    Args:
        repositories: List of standardized repository dictionaries.
    """
    if not repositories:
        print("\nNo repositories found.")
        return

    separator = "=" * 80
    sub_sep = "-" * 80

    print(f"\n{separator}")
    print(f" Retrieved {len(repositories)} GitHub Repository(ies)")
    print(separator)

    for idx, repo in enumerate(repositories, start=1):
        full_name = repo.get("full_name") or repo.get("name") or "Unnamed Repository"
        repo_id = repo.get("id")
        repo_id_str = str(repo_id) if repo_id is not None else "N/A"
        owner = repo.get("owner") or "Unknown"
        url = repo.get("url") or "N/A"
        description = repo.get("description") or "No description provided."
        language = repo.get("language") or "Not specified"
        stars = repo.get("stars", 0)
        license_str = repo.get("license") or "No license specified"
        branch = repo.get("default_branch") or "N/A"
        created_at = repo.get("created_at") or "N/A"
        updated_at = repo.get("updated_at") or "N/A"

        print(f"\n[Result {idx}]")
        print(f"  Repository Name:  {full_name}")
        print(f"  Repository ID:    {repo_id_str}")
        print(f"  Owner:            {owner}")
        print(f"  Repository URL:   {url}")
        print(f"  Description:      {description}")
        print(f"  Language:         {language}")
        print(f"  Stars:            {stars:,}")
        print(f"  Licence:          {license_str}")
        print(f"  Default Branch:   {branch}")
        print(f"  Created At:       {created_at}")
        print(f"  Last Updated:     {updated_at}")
        print(sub_sep)


def main() -> None:
    """
    Interactive command-line entry point. Prompts the user for a search query,
    calls the GitHub repository search connector, and prints formatted results.
    """
    print("=" * 80)
    print(" Idea Enhancer - GitHub Repository Search Connector")
    print(" Person 2: External Data & Provider Engineering")
    print("=" * 80)

    # Check for authentication status notification
    token_present = bool(get_github_token())
    if token_present:
        print("[Auth] GitHub token detected in environment. Using authenticated requests.")
    else:
        print("[Auth] No GitHub token detected. Running unauthenticated (10 search requests/min).")

    try:
        user_query = input("\nEnter search keywords (e.g., 'machine learning fake news'): ").strip()

        print(f"\nSearching GitHub for: '{user_query}'...")
        results = search_github_repositories(query=user_query, per_page=5)
        print_repositories(results)

    except KeyboardInterrupt:
        print("\n\nSearch cancelled by user. Goodbye!")


if __name__ == "__main__":
    main()
