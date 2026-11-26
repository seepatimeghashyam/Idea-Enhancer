"""Orchestration service combining retrieval evidence, caching, LLM reasoning, and citation validation."""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from src.enhance.cache import EnhanceCache, compute_cache_key
from src.enhance.contracts import (
    EnhanceRequest,
    EnhanceResponse,
    FacetDetail,
    FacetMap,
    FeasibilityRating,
    NoveltyAssessment,
    SuggestionItem,
    TechStackItem,
)
from src.enhance.llm_client import (
    GeminiLLMClient,
    LLMClientProtocol,
    LLMError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from src.enhance.novelty_scorer import compute_evidence_novelty
from src.enhance.validator import sanitize_grounded_response

logger = logging.getLogger(__name__)


def build_enhancement_prompt(
    idea: str,
    matches: list,
    computed_score: float,
    computed_level: str,
    baseline_reason: str,
) -> str:
    """Build a strongly constrained system prompt for the LLM."""
    match_descriptions = []
    for idx, m in enumerate(matches[:5], start=1):
        match_descriptions.append(
            f"Match #{idx}:\n"
            f"- Project ID: {m.project_id}\n"
            f"- Title: {m.title}\n"
            f"- Domain: {m.domain or 'Unspecified'}\n"
            f"- Technologies: {', '.join(m.technologies) if m.technologies else 'Unspecified'}\n"
            f"- Excerpt: {m.description_excerpt or 'No description provided'}\n"
            f"- Shared Terms: {', '.join(m.shared_elements) if m.shared_elements else 'None'}"
        )

    matches_text = "\n\n".join(match_descriptions) if match_descriptions else "No prior matches retrieved in dataset."
    valid_id_list = ", ".join(repr(m.project_id) for m in matches[:5]) or "None"

    return f"""You are an expert academic project advisor in engineering and computer science.
Analyze the student's project idea against the retrieved prior-art project records from our repository.

STUDENT'S PROPOSAL:
\"\"\"{idea}\"\"\"

RETRIEVED PRIOR-ART MATCHES:
{matches_text}

MANDATORY RULES:
1. STRICT CITATION RULE: You may ONLY cite project IDs from this exact allowed list: [{valid_id_list}]. Never invent project IDs, external papers, or imaginary datasets. Every improvement suggestion must cite one or more valid project IDs.
2. NOVELTY GROUNDING: The evidence-based novelty score is pre-calculated from corpus overlap as {computed_score:.2f} ({computed_level.upper()}). Your task is to provide the engineering justification for this score based on the overlap evidence. Do not alter the score.
3. CONCRETE SUGGESTIONS: Provide 3 to 5 practical, technically sound architectural improvements.
4. FACET ANALYSIS: Assess overlap across problem, domain, method, tech_stack, and data as "none", "partial", or "strong".
5. OUTPUT FORMAT: Respond ONLY with a valid, raw JSON object matching the exact schema below. Do not wrap in markdown quotes if possible, or use standard ```json.

REQUIRED JSON STRUCTURE:
{{
  "overlap_summary": "1-2 sentence high-level summary of overlap with retrieved corpus",
  "facet_map": {{
    "problem": {{"overlap": "none|partial|strong", "details": "reasoning", "matched_project_ids": ["..."]}},
    "domain": {{"overlap": "none|partial|strong", "details": "reasoning", "matched_project_ids": ["..."]}},
    "method": {{"overlap": "none|partial|strong", "details": "reasoning", "matched_project_ids": ["..."]}},
    "tech_stack": {{"overlap": "none|partial|strong", "details": "reasoning", "matched_project_ids": ["..."]}},
    "data": {{"overlap": "none|partial|strong", "details": "reasoning", "matched_project_ids": ["..."]}}
  }},
  "novelty": {{
    "level": "{computed_level}",
    "score": {computed_score},
    "reason": "Detailed justification of this novelty score grounded in evidence"
  }},
  "suggestions": [
    {{
      "title": "Short title of architectural improvement",
      "description": "Specific technical description explaining what to add/change relative to cited project",
      "cites": ["valid_project_id"]
    }}
  ],
  "suggested_tech_stack": [
    {{"name": "Library/Framework/Hardware", "role": "Role in improved architecture"}}
  ],
  "feasibility": {{
    "rating": 4,
    "reasons": ["2-3 practical student feasibility reasons"]
  }}
}}
"""


def _build_response_object(sanitized: dict, idea: str) -> EnhanceResponse:
    """Instantiate strongly typed EnhanceResponse from sanitized dictionary."""
    facet_data = sanitized.get("facet_map", {})
    facet_map = FacetMap(
        problem=FacetDetail(**facet_data.get("problem", {})),
        domain=FacetDetail(**facet_data.get("domain", {})),
        method=FacetDetail(**facet_data.get("method", {})),
        tech_stack=FacetDetail(**facet_data.get("tech_stack", {})),
        data=FacetDetail(**facet_data.get("data", {})),
    )
    novelty = NoveltyAssessment(**sanitized.get("novelty", {}))
    suggestions = [SuggestionItem(**s) for s in sanitized.get("suggestions", [])]
    suggested_tech_stack = [TechStackItem(**t) for t in sanitized.get("suggested_tech_stack", [])]
    feasibility = FeasibilityRating(**sanitized.get("feasibility", {}))

    return EnhanceResponse(
        status=sanitized.get("status", "success"),
        idea=sanitized.get("idea", idea),
        overlap_summary=sanitized.get("overlap_summary", ""),
        facet_map=facet_map,
        novelty=novelty,
        suggestions=suggestions,
        suggested_tech_stack=suggested_tech_stack,
        feasibility=feasibility,
        cached=sanitized.get("cached", False),
    )


class EnhanceService:
    """Service handling caching, evidence computation, LLM generation, and validation."""

    def __init__(
        self,
        llm_client: Optional[LLMClientProtocol] = None,
        cache: Optional[EnhanceCache] = None,
        timeout_seconds: float = 12.0,
    ):
        self.llm_client = llm_client or GeminiLLMClient()
        self.cache = cache or EnhanceCache()
        self.timeout_seconds = timeout_seconds

    def enhance(self, request: EnhanceRequest) -> EnhanceResponse:
        """Run the full enhance pipeline."""
        # 1. Check cache
        cache_key = compute_cache_key(request.idea, request.matches)
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            return _build_response_object(cached_result, request.idea)

        # 2. Compute deterministic evidence novelty
        score, level, baseline_reason = compute_evidence_novelty(request.idea, request.matches)

        # 3. Build prompt
        prompt = build_enhancement_prompt(
            request.idea,
            request.matches,
            computed_score=score,
            computed_level=level,
            baseline_reason=baseline_reason,
        )

        # 4. Invoke LLM client
        try:
            raw_text = self.llm_client.generate_enhancement(prompt, timeout_seconds=self.timeout_seconds)
        except (LLMTimeoutError, LLMUnavailableError):
            raise
        except Exception as err:
            raise LLMUnavailableError(f"LLM generation failed: {err}") from err

        # 5. Extract and parse JSON
        cleaned_text = raw_text.strip()
        json_match = re.search(r"\{.*\}", cleaned_text, re.DOTALL)
        if json_match:
            cleaned_text = json_match.group(0)

        try:
            raw_payload = json.loads(cleaned_text)
        except json.JSONDecodeError as err:
            logger.warning("LLM response was not valid JSON, applying structured fallback: %s", err)
            raw_payload = {}

        # 6. Sanitize, ground citations, and enforce constraints
        sanitized = sanitize_grounded_response(
            raw_payload=raw_payload,
            matches=request.matches,
            computed_novelty_score=score,
            computed_novelty_level=level,
            computed_novelty_reason=baseline_reason,
        )
        sanitized["idea"] = request.idea
        sanitized["status"] = "success"
        sanitized["cached"] = False

        # 7. Store in cache (store un-cached flag in storage)
        self.cache.set(cache_key, sanitized)

        # 8. Return response with explicitly instantiated contract objects
        return _build_response_object(sanitized, request.idea)
