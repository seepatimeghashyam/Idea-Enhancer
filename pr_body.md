## Summary
- **VectorRetriever**: Adds index signature validation for ChromaDB reuse, supports legacy collections by content verification
- **GeminiProvider**: Implements model fallback chain (tries models in order, skips failed ones with cooldown), request timeouts, response schema validation, thought-part filtering
- **EnhanceService**: Async provider calls, response field clipping, stricter overlap validation
- **Frontend**: Fixes enhancement race conditions (mode/idea switching), increases timeout to 120s
- **Tests**: Updated for new vector retriever behavior and async provider interface

## Changes
- `src/core/vector_retriever.py`: Index signature + legacy collection validation
- `src/enhance/provider.py`: Complete rewrite with fallback chain, httpx, schema enforcement
- `src/enhance/service.py`: Async calls, clipping, validation
- `script.js`: Race condition fixes
- `.env.example`: Updated for GEMINI_MODELS config
- New test file: `tests/test_gemini_fallback.py`
- New script: `scripts/check_gemini_models.py`
- New doc: `docs/V2_HANDOFF.md`