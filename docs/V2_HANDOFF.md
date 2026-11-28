# Idea Enhancer v2 — Session Handoff

**Prepared:** 2026-11-28  
**Purpose:** Preserve the decisions, implementation work, validation evidence, and unresolved tasks from the Codex v2 search/dependency work so it can be resumed without replaying the full chat.

## 1. Current repository state (verified at handoff)

- The primary checkout is on `main`, at `f547ac9 feat: add evidence-grounded idea enhancement`.
- Local `main` is one commit ahead of `origin/main`. The Enhance commit was fast-forward merged locally; it was **not pushed** to GitHub.
- `codex/ai-enhancer-feature` also points to `f547ac9`.
- `codex/v2-dependency-review` still points to baseline `b97ee6d`; none of the v2 search/dependency implementation has been committed to that branch.
- `v1` and remote `origin/v1` remain at `b97ee6d`. `base-v1` tags the verified baseline.
- `origin/feature/data-labelling` has three documentation-only commits past the baseline (`d963dc5`, `a42bc1d`, `438ee11`), including evidence review for proposed queries. It is not a v2 implementation branch.
- The main checkout has six modified Enhance-related files: `src/core/vector_retriever.py`, `src/enhance/provider.py`, `src/enhance/service.py`, `tests/core/test_core_pipeline_integration.py`, `tests/core/test_vector_retriever.py`, and `tests/test_enhance_service.py`. These appeared after the Enhance merge/current other-chat work. **Do not discard or reset them without checking with their owner.**
- Two Git stashes are present and are the important v2 recovery points:
  - `stash@{1}` — `On codex/v2-dependency-review: preserve search-v2 work before activating main Enhancer checkout`. This contains the v2 benchmark scripts/docs and search changes. Its saved tracked/untracked diff showed 20 files, including the RRF/reranking implementation, evaluation scripts, docs, and tests.
  - `stash@{0}` — `On codex/v2-dependency-review: preserve generated search-v2 evaluation reports`. This contains the generated report files (10 reports, 5,191 lines total).
- **Do not run `git stash pop` blindly.** Both stashes were made against `b97ee6d`, while current `main` contains the Enhance commit and additional work. Inspect each stash first and restore into the intended v2 worktree/branch. The stash order matters: `stash@{1}` is code/docs; `stash@{0}` is reports.
- At the time of this check, `data/evaluation/reports` did not exist in the current main checkout. Its generated reports are in `stash@{0}`. The evaluation annotation artifacts may be ignored/untracked and were not confirmed in the current checkout or in those stash summaries. The original review workbooks are in Downloads and were never modified.

## 2. What happened in this chat

1. The project began from a verified v1 baseline (`b97ee6d`). The user asked for a v2 aimed at better search quality and efficiency, with dependency/model changes treated as measured experiments. The user specifically asked about “recoding/re-encoding RRF”; this was interpreted as likely meaning **reranking**, while distinguishing reranking from re-embedding the corpus.
2. The user supplied a product roadmap: hybrid local/online retrieval, traceable source evidence, honest uncertainty, and a phased direction toward better relevance. The roadmap made finishing human relevance labels the immediate quality gate.
3. The initial v2 implementation added tunable weighted RRF, optional bounded cross-encoder reranking, and evaluation/performance scripts. It was first developed as uncommitted work on `codex/v2-dependency-review`, whose branch pointer itself remained at baseline.
4. A 20-record workbook was inspected. Its grades/rationales/confidence were scattered, so a normalized project CSV was created. It did not match the existing three-query capture’s candidate IDs or URLs; it cannot be added to that capture’s metrics without a matching snapshot.
5. A returned three-query workbook from teammates was inspected. Of the 124 original query/candidate rows, 70 had recoverable grades, rationales, and confidence after correcting the misspelled confidence header. The rest were left unlabeled. A clean annotation CSV was made, and 54 assistant-authored screening assessments were created separately. Those labels are not human ground truth.
6. Assistant screening assessed only the title/description/query and did not independently verify source pages. They were intended for exploration only, never for promotion claims.
7. The Enhance feature was being developed in a separate chat/branch. The user clarified that Enhance belonged on `codex/ai-enhancer-feature`, and search/dependency work belonged on `codex/v2-dependency-review`.
8. Enhance was committed as `f547ac9` and locally fast-forwarded to `main`. A clean worktree of this commit passed 226 tests. No push was performed.
9. During clean-worktree testing an initial error exposed an accidental dependency: the Enhance `src/main.py` shutdown hunk called a v2 `close_search_engine()` helper that was not in the Enhance commit. The commit boundary was corrected so Enhance did not depend on unstaged v2 database changes. A vector-client cleanup was retained with its focused Windows cleanup test. The corrected clean commit then passed.
10. The user’s latest instruction changed from continuing experiments to stopping implementation and writing a detailed handoff because Codex usage was nearly exhausted. No v2 changes were committed or merged.

## 3. v2 changes preserved in `stash@{1}`

These are present in the saved v2 work stash, not in current `main`:

- `src/core/fusion.py`: weighted RRF controls and validation.
- `src/live_search/retrieval.py`: configurable RRF constant/weights and optional cross-encoder reranking limited to a shortlist.
- `src/core/engine.py`: optional RRF parameters and reranker support for local search.
- `src/reranking.py`: lazy CPU cross-encoder scorer and stable injected scorer helper.
- `src/core/vector_retriever.py`, `src/database.py`, `src/main.py`: client shutdown/lifecycle changes (note current Enhance branch now independently has a partial client-close fix; inspect and reconcile rather than blindly applying both copies).
- `scripts/evaluate_live_search.py`: evaluator options for RRF, embedding model, and reranking, with provenance.
- `scripts/offline_evaluation.py`: offline fixed-pool capture, score-free review sheet creation, label validation, nDCG/Recall/MRR evaluation, and paired bootstrap comparisons.
- `scripts/benchmark_search_performance.py`: disposable Offline Demo and saved-capture Live ranking timing/memory benchmark.
- `scripts/validate_chroma_copy.py`: copy/read check for a Chroma directory.
- `docs/SEARCH_V2_BENCHMARK.md`: workflow and promotion thresholds.
- Tests for weighted RRF, reranking, and offline evaluation.
- `requirements.txt` experiment changed ChromaDB from the previous `<1` range to `>=1.5.9,<2`. This is provisional and was never validated on a populated index; do not promote this pin without reconciling it with current `main` requirements.

## 4. Evaluation data and results

### Available datasets

- Fixed Live Research capture: `data/evaluation/captures/three-query-pilot.json`, 3 queries and 124 candidate rows.
- Original neutral annotation sheet: `data/evaluation/annotations/three-query-pilot.csv` (original left untouched).
- Team-returned workbook: `C:\Users\seepa\Downloads\three-query-pilot (1).xlsk.xlsx` (odd extension; original left untouched).
- A clean 124-row team review copy and 54 assistant assessments were generated during the session, but their files were not present in current `main` at final status inspection. Their location must be recovered from `stash@{1}`, `stash@{0}`, ignored files, or reconstructed from the original workbook/capture as needed.
- Separate 20-record workbook: `C:\Users\seepa\Downloads\review_sheet.xlsx`. Its candidate IDs and source URLs did not match the three-query capture; it needs its own query-to-candidate snapshot before ranking evaluation.
- Proposed 15-topic query list: `data/evaluation/queries.example.json` and remote `docs/PROPOSED_QUERY_EVIDENCE_REVIEW.md`. The user had not confirmed/frozen this set. Do not assume approval.

### Label status

- Teammate labels recovered for 70/124 rows: water pipeline 29/50, network anomaly 27/27, indoor delivery robot 14/47.
- Only `network-anomaly-lab` had complete teammate labels. This is the only query appropriate for a human-only baseline in the three-query set.
- 54 assistant labels completed the mixed-origin screening set, with low confidence where metadata was sparse. They are exploratory only.
- The 20-record reviewed set is separate and mismatched to the capture.

### Metrics/reports generated

These were generated and preserved in `stash@{0}`. Their label origin is mixed when covering all 3 queries:

- `three-query-team-network-baseline.json` — human-only single-query baseline, BGE-small + BM25 equal-weight RRF k=60: nDCG@10 0.3997, Recall@10 0.4706, MRR@10 0.3333.
- `three-query-mixed-screening-rrf20.json`, `rrf40.json`, `rrf60.json`, `rrf100.json`, `bm25_1_5.json`, `dense_1_5.json` — three-query mixed-origin screening variants. Dense weight 1.5 lifted water nDCG in assistant labels from ~0.481 to ~0.508 but dropped robotics from ~0.882 to ~0.743; network human metrics stayed unchanged. This is a tradeoff, not a promotion result.
- `v2-live-rank-performance-10.json` — Python 3.12.10, ST 3.4.1; 10 warm requests; p50 ~4.38 s, p95 ~5.00 s; peak RSS null.
- `v2-live-rank-performance-st63-3.json` — Python 3.12.10, ST 6.3.0; 3 warm requests; p50 ~4.77 s, p95 ~5.69 s; peak RSS null. The run is too small/noisy for a performance conclusion.
- `three-query-pilot-label-reconciliation.json` — counts and limitations; assistant-label origin kept separate.

No ranking variant met promotion criteria. Held-out queries were not approved/labeled, and assistant labels cannot qualify a quality change.

## 5. Dependency and runtime findings

- Reference setup: Python 3.12.10. A clean temporary Python 3.12 install of current requirements succeeded; full suite passed at that checkpoint.
- Current tested line at that time: ChromaDB 1.5.9, Sentence Transformers 3.4.1, rank-bm25 0.2.2, NumPy 2.5.5 in clean install (the base environment showed NumPy 2.5.4), Torch 2.15.0.
- A temporary environment installed Sentence Transformers 6.3.0 and BM25S 0.3.16. ST 6.3 loaded the cached `BAAI/bge-small-en-v1.5`; tests passed in that temporary v2 environment. No quality comparison against labels, E5 test, reranker evaluation, ONNX inference comparison, or BM25S timed comparison was completed.
- Python 3.15 Windows install of requirements failed because `onnxruntime` had no compatible Windows wheel. Current upstream check at the time indicated ORT wheels for Python through 3.14. Keep Python 3.12 as reference; 3.15 is not currently a usable runtime for this stack on this machine.
- Chroma disposable-copy script opened ChromaDB 1.5.9 but found collection count 0. Thus this was an empty-index open check, **not** a valid populated-index persistence/migration check. Do not describe populated index compatibility as verified.
- Latest public package versions alone are not a reason to change pins. FastAPI or unrelated packages were not changed for recency.
- Network access to Hugging Face intermittently failed. Cached BGE loads worked in offline mode; performance scripts without `HF_HUB_OFFLINE=1` hung on Hub resolution and had to be interrupted/re-run offline.

## 6. Enhance commit state

Commit `f547ac9` adds:

- Pydantic request/response contracts.
- Injectable Gemini provider boundary and structured-output parsing.
- Server-side retrieval through existing local/live search, evidence ID validation, bounded prompt data, cache keyed by idea/scope/provider/model/prompt version/evidence content, TTL/size bound.
- `POST /enhance` endpoint and UI action/results rendering.
- Disclosure that idea and retrieved excerpts are sent to Gemini when configured; no numeric originality score.
- Offline service/API tests.
- Vector client `close()` plus Windows cleanup test adjustments.

Clean commit test: 226 passed. A live Gemini call was not run (no use/validation of a configured key). Current `main` has additional modified Enhance files from other ongoing work; do not assume `f547ac9` is still the tip of all live Enhance development unless checking status.

## 7. What remains for v2

### Critical sequence

1. **Recover safely:** inspect `stash@{1}` and `stash@{0}`. Create/use a dedicated v2 worktree based on the current main commit `f547ac9`, not baseline. Preserve all current modifications. Cherry-pick/reapply only search/dependency changes from the stash and reconcile overlaps (`src/main.py`, `src/core/vector_retriever.py`, `src/database.py`, tests). Do not pop stashes until the restored work is verified; retain stashes until merge.
2. **Reconcile manifests:** current `main` requirements and v2’s provisional Chroma range need inspection. Keep Python 3.12 as benchmark reference. Do not make Chroma 1.5.9 permanent until populated index persistence/read is verified on a disposable copy. The main checkout’s current enhancement files have additional unstaged edits, which must remain untouched.
3. **Finish human labels:** have reviewers fill remaining 54 rows in the returned 124-row sheet. Validate IDs, query, context, confidence, rationales and completeness against the frozen capture. Keep reviewer copies separate, inspect disagreements, then establish a consensus/adjudication policy. Do not substitute assistant labels for missing human judgments.
4. **Include the 20-record review separately:** establish a fixed candidate snapshot that actually contains those same candidates and their query/topic context. Do not join these records to the three-query capture by guesswork.
5. **Use approved queries:** user must confirm the proposed 15-topic set before treating it as tuning/held-out. Suggested separation in the old plan: three pilot topics for tuning, the rest for held-out confirmation—but do not freeze until explicit approval.
6. **Run comparisons on frozen human-labeled pools:** baseline BM25 + BGE-small + equal RRF k=60; sweep k and weights; BGE query instruction; E5-small-v2 with `query:` / `passage:` prefixes; MiniLM cross-encoder on top 30. Report per-query nDCG@10, Recall@10, MRR@10 and paired CIs. Add confidence sensitivity. Keep Live provider captures fixed; do not claim provider discovery completeness.
7. **Dependency speed trials:** measure BM25S vs rank-bm25 with identical tokenization/corpus/settings; ST 3.4 vs ST 6.3; only compare ONNX if embedding inference bottleneck is repeatably measured. Record warm p50/p95 and peak memory on same machine. Do not add BM25S/ONNX deps to standard requirements unless thresholds pass.
8. **Benchmark offline correctly:** use fixed query catalogue and disposable Chroma directory. The current production/local `chroma_db` inspected earlier appeared empty to validation script, while a previous historical check mentioned 1,998 records; resolve path/index identity before claiming persistence validation.
9. **Promotion thresholds (previously agreed):** ranking change needs at least +0.01 absolute pilot macro nDCG@10, same direction on held-out human labels, and <=0.01 drop in Recall@10/MRR@10; <=25% warm p95 and peak memory increase. Speed-only change requires repeatable >=10% p95 improvement with <=0.01 quality drop. Full suite + clean install + populated disposable Chroma read/persistence checks before retention.
10. **Commit/merge:** only after v2 restore/reconciliation, tests, labels, and accepted results. Merge v2 into current main based on `f547ac9`; do not overwrite or reset the present main working tree.

## 8. Recommended immediate resume commands

Run from PowerShell, inspect output carefully, and do not apply either stash over dirty main:

```powershell
git status --short --branch
git stash list
git stash show --stat --include-untracked 'stash@{1}'
git stash show --stat --include-untracked 'stash@{0}'
git worktree add ..\Idea-Enhancer-v2 codex/v2-dependency-review
```

Because the v2 branch is still based on `b97ee6d`, first fast-forward or rebase a dedicated v2 branch/worktree onto `f547ac9` only after confirming the selected strategy and preserving all dirty files. Then restore `stash@{1}` by applying selected paths/patches, not a blind pop. Restore report stash only after the code/data layout is ready.

## 9. Important guardrails and current user intent

- User wants Enhance on its own feature/main path and v2 search/dependency work separate.
- User explicitly said not to spend remaining Codex usage on more dependency experimentation and then prioritized a detailed handoff. Therefore, this document is the endpoint for this session; do not start more experiments unless asked.
- Preserve current uncommitted Enhance edits, both v2 stashes, original workbooks, production Chroma index, and public API contracts.
- Never promote mixed-origin scores as measured search-quality improvement.
- Python 3.12 is the stable comparison target for now; Python 3.15 compatibility is blocked by Windows ONNX Runtime wheel availability.
- No remote push was performed. Local `main` has the Enhance commit only.
