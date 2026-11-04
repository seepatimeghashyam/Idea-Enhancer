"""Capture full normalized OpenAlex/GitHub candidate pools for human evaluation."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluation_workflow import capture_catalogue, load_query_catalogue, read_json, write_json_new
from src.live_search.service import MAX_CANDIDATES_PER_PROVIDER, LiveSearchService


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True,
            capture_output=True, text=True, timeout=5,
        ).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


async def capture(catalogue: dict, catalogue_sha256: str) -> dict:
    service = LiveSearchService()
    try:
        result = await capture_catalogue(catalogue, service)
    finally:
        await service.close()
    result["provenance"] = {
        "query_catalogue_sha256": catalogue_sha256,
        "git_commit": _git_commit(),
        "provider_names": sorted(provider.name for provider in service.providers),
        "candidate_limit_per_provider": MAX_CANDIDATES_PER_PROVIDER,
        "ranking_performed": False,
        "dense_model_loaded": False,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalogue", type=Path, help="Version-1 proposed query catalogue JSON")
    parser.add_argument("--output", required=True, type=Path, help="New capture JSON path; existing files are never overwritten")
    args = parser.parse_args()
    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")
        catalogue_value, raw = read_json(args.catalogue)
        catalogue = load_query_catalogue(catalogue_value)
        result = asyncio.run(capture(catalogue, hashlib.sha256(raw).hexdigest()))
        write_json_new(args.output, result)
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))
    total = sum(query["candidate_count"] for query in result["queries"])
    print(f"Captured {len(result['queries'])} query cases and {total} normalized provider candidates to {args.output}.")
    for query in result["queries"]:
        states = ", ".join(f"{provider}={status['state']}({status['count']})" for provider, status in query["providers"].items())
        print(f"{query['query_id']}: {states or 'no providers configured'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
