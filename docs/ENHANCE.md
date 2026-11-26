# Idea Enhancer — AI Enhancement Feature (`docs/ENHANCE.md`)

## 1. Overview

The **Enhance** feature provides engineering students with actionable, architectural improvements to their project ideas based on traceable prior art found in the indexed corpus.

While `POST /search` locates similar existing projects, `POST /enhance` analyzes the overlap across 5 key dimensions (problem, domain, method, tech stack, data), computes an evidence-based novelty score, and generates 3–5 grounded architectural suggestions.

---

## 2. Architecture & Design Principles

```
Student / UI
    │
    ▼ POST /enhance { idea, matches }
FastAPI Router (src/enhance_router.py)
    │
    ▼
EnhanceService (src/enhance/service.py)
    ├── 1. In-Memory Cache (src/enhance/cache.py) — SHA-256 keyed TTL lookup
    ├── 2. Novelty Scorer (src/enhance/novelty_scorer.py) — Evidence-based formula
    ├── 3. LLM Client (src/enhance/llm_client.py) — Gemini REST API / FakeLLMClient
    └── 4. Grounding Validator (src/enhance/validator.py) — Strict citation enforcement
```

### Core Design Rules

1. **Strict Citation Grounding (Anti-Hallucination):**
   * Every suggestion and claim **must cite** a `project_id` that was retrieved in the search matches.
   * The `validator.py` module inspects every suggestion and facet. If an LLM hallucinates an unknown project ID, it is stripped or grounded to the top retrieved match.
   * The LLM is explicitly barred from claiming universal originality or inventing non-existent projects.

2. **Evidence-Based Novelty Calculation:**
   * An LLM alone must **never** decide whether an idea is original.
   * `novelty_scorer.py` deterministically calculates an overlap intensity $O \in [0.0, 1.0]$ based on:
     * Top match RRF score (40% weight)
     * Count of shared lexical elements (35% weight)
     * Density of retrieved matches (25% weight)
   * The novelty score is $1.0 - O$ (clamped between $0.05$ and $0.95$).
   * The score and category (`low`, `medium`, `high`) are passed to the LLM solely to generate the engineering explanation.

3. **Fault Tolerance & Offline Testing:**
   * Gemini API is called with a strict timeout (default 12 seconds).
   * Missing API keys, rate limits, or network errors return standardized `503 Service Unavailable` JSON envelopes instead of crashing the server.
   * Unit tests utilize `FakeLLMClient`, running completely offline without network access or API credentials.

4. **In-Memory Caching:**
   * Repeated submissions of the same idea and matches hit the thread-safe `EnhanceCache`.
   * Results are returned immediately with `"cached": true`, conserving API quotas and delivering sub-millisecond responses.

---

## 3. Integration into `src/main.py`

Per the project protocol, `src/main.py` is owned by the team lead. To mount the router, the lead simply adds:

```python
from src.enhance_router import enhance_router

app.include_router(enhance_router)
```

No search logic is duplicated or modified.

---

## 4. Environment Configuration

In `.env`:
```bash
# Gemini API Key (free tier supported)
GEMINI_API_KEY=your_gemini_api_key_here

# Optional model override (defaults to gemini-2.5-flash)
LLM_MODEL=gemini-2.5-flash
```

---

## 5. Running Tests

Run the test suite:
```bash
python -m pytest tests/enhance -v
```

All enhance tests run offline with zero external network dependencies.
