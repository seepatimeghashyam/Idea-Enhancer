# Human-labelled live-search evaluation workflow

This workflow builds a fixed, reproducible benchmark from actual OpenAlex and GitHub results, then compares provider-native ordering, BM25, dense BGE, and hybrid RRF against human-entered relevance grades. It does not generate labels, infer originality, or establish that an idea is novel.

## Before collecting data

Review and approve [`data/evaluation/queries.example.json`](../data/evaluation/queries.example.json) as a project owner. It is a proposed version-1 catalogue of 15 realistic queries in 15 topical slices. It contains no candidate records or labels. Change the catalogue only as a reviewed versioned input; the capture records its SHA-256 hash.

The capture utility calls the same live-search service discovery operation and production OpenAlex/GitHub adapters as `/live-search`. It preserves normalized records and each provider's native discovery rank before local retrieval. It captures up to 25 candidates per provider for each query, including empty or failed provider states. It does not call the public `/live-search` route, load BGE, rank, or use the historical-project dataset. The public endpoint returns only fused `top_k` results, so repeated public calls cannot reconstruct the full provider pool or a provider's original order.

## 1. Capture a provider snapshot

Use Python with the project's declared dependencies installed. Set `GITHUB_TOKEN` in the environment if desired; it is optional and is never written to the capture. `.env` is loaded locally when present.

PowerShell:

```powershell
$capture = "data/evaluation/captures/run-2026-11-05.json"
python scripts/capture_live_snapshot.py data/evaluation/queries.example.json --output $capture
```

Linux/macOS or WSL:

```bash
capture=data/evaluation/captures/run-2026-11-05.json
python scripts/capture_live_snapshot.py data/evaluation/queries.example.json --output "$capture"
```

Captures are local and ignored by Git by default. The output path must be new; the tool refuses to overwrite it. Keep the original capture immutable. Its structure records format/version, catalogue hash, commit, provider names, timestamps, candidate limit, provider states/counts, warnings, and full candidate metadata. Capture content naturally changes when upstream providers change.

## 2. Export a neutral annotation sheet

PowerShell:

```powershell
$annotations = "data/evaluation/annotations/run-2026-11-05.csv"
python scripts/export_live_annotations.py $capture --output $annotations
```

Linux/macOS or WSL:

```bash
annotations=data/evaluation/annotations/run-2026-11-05.csv
python scripts/export_live_annotations.py "$capture" --output "$annotations"
```

The CSV includes query and candidate identity, type, title, description, source URL/provider, and blank grade/rationale/confidence fields. It deliberately omits all ranking positions and scores. Review each row against the query and available source information. Do not treat a provider failure as a set of irrelevant candidates, or an empty response as evidence that no relevant work exists.

Use the same 0–3 scale for every candidate:

| Grade | Meaning |
|---|---|
| 0 | Not relevant: no meaningful connection to the problem, goal, or technical approach. |
| 1 | Weakly related: shared terms or adjacent domain, with limited practical relevance. |
| 2 | Substantially related: meaningful overlap in problem, domain, or approach; useful to investigate. |
| 3 | Highly relevant: strong overlap with the core problem or technical approach. |

Enter a grade for every candidate, including explicit `0` for reviewed non-relevant candidates. A blank means pending review and is rejected. Add a concise rationale. Set confidence to `low`, `medium`, or `high`; leave it blank when not recorded. Flag ambiguous candidates for a second reviewer instead of guessing.

## 3. Build the reviewed snapshot

Keep the capture unchanged and save completed annotations as a separate file. Matching uses `(query_id, candidate_id)`, never row order. Unknown/duplicate rows, changed query text, invalid grades, or any unreviewed candidate stop the build.

PowerShell:

```powershell
$reviewed = "data/evaluation/reviewed/run-2026-11-05.json"
python scripts/build_reviewed_snapshot.py $capture $annotations --output $reviewed
```

Linux/macOS or WSL:

```bash
reviewed=data/evaluation/reviewed/run-2026-11-05.json
python scripts/build_reviewed_snapshot.py "$capture" "$annotations" --output "$reviewed"
```

The reviewed snapshot is also ignored by default. It preserves the complete candidate pools, provider states/ranks, capture provenance, human grades, rationale, and confidence. No grades are filled automatically. Optional discovery recall is supported by the evaluator only when `known_relevant_ids` is supplied from a separately reviewed, explicitly defined inventory; the workflow does not infer that inventory.

## 4. Evaluate and inspect

Run the full evaluator with dense BGE enabled:

```powershell
$report = "data/evaluation/reviewed/run-2026-11-05-report.json"
if (Test-Path $report) { throw "Choose a new report path; this workflow preserves existing reports." }
python scripts/evaluate_live_search.py $reviewed | Set-Content -Encoding utf8 $report
```

For a BM25-only comparison that does not initialize BGE:

```powershell
$report = "data/evaluation/reviewed/run-2026-11-05-bm25-report.json"
if (Test-Path $report) { throw "Choose a new report path; this workflow preserves existing reports." }
python scripts/evaluate_live_search.py $reviewed --bm25-only | Set-Content -Encoding utf8 $report
```

In Linux/macOS or WSL, choose a new report path before running:

```bash
report=data/evaluation/reviewed/run-2026-11-05-report.json
test ! -e "$report" || { echo "Choose a new report path; existing reports are preserved." >&2; exit 1; }
python scripts/evaluate_live_search.py "$reviewed" > "$report"
```

The JSON report includes reviewed query/candidate totals, label distribution, provider state and candidate counts, metrics by method and topical slice, exclusions, dense evaluation state, and case-level limitations. If dense encoding fails, dense and hybrid rankings are omitted for that case and only BM25 is reported; a BM25 fallback is never labelled as a dense or hybrid result.

## What the metrics mean

- **Provider discovery coverage** concerns which candidates a provider returned. Provider-native Recall@10 is measured only over the captured, human-labelled candidate universe; candidates outside that pool are unknown. Optional discovery recall needs a separately reviewed known-relevant inventory.
- **Provider-native ordering** evaluates each provider independently by its own discovery rank. Provider lists are never concatenated into a fictional shared ranking. Missing ranks exclude that provider's native-order metric for the case and are reported.
- **Candidate-pool ranking quality** compares BM25, dense, and hybrid RRF over the same complete captured pool and same human labels. Dense order uses dense rank; hybrid order uses the actual RRF output.
- **Final live top-k quality** concerns what a live request returns after provider discovery and fusion. This fixed snapshot helps inspect that ranking, but is not a representative estimate of all future web results.

Precision@5 divides by 5 even when fewer than five records exist. Recall@10 uses every grade-above-zero candidate in the reviewed pool as its denominator. nDCG@10 uses graded 0–3 relevance. MRR@10 uses the first grade-above-zero candidate. Empty-pool and no-positive-label cases remain visible but are excluded from aggregate metric means. Provider failures are not represented as empty rankings. The report describes only this capture and reviewed benchmark; a higher score does not prove improved general live-web search quality, originality, or completeness.

## Reproducibility and review

Archive the original capture, completed annotations, reviewed snapshot, and report together outside ordinary source commits unless the project owner approves a reviewed benchmark artifact. Record the catalogue hash, code commit, capture date, provider status, and any manual review protocol. Compare the individual queries and slices as well as aggregate metrics. Review the query catalogue and grading consistency before drawing conclusions. Human review is mandatory; the tools provide no originality or prior-art guarantee.
