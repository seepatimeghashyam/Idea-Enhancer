# Idea Enhancer — AI Team Protocol & Role Instructions

**Repository:** https://github.com/seepatimeghashyam/Idea-Enhancer  
**Team:** Four CS students  
**Purpose:** Let each teammate use whichever AI coding agent works for them while keeping the code, interfaces, and decisions compatible.

> **For teammates:** You do not need to read every section manually. Paste **Section 2 (Shared Agent Prompt)** into your coding agent, followed by **only your assigned role prompt from Section 7**. The prompt tells the agent to inspect the actual repo, report what it finds, and stop for clarification when a decision could cause conflicts. All AI agents must be given the current protocol or told to read it from the repository; they do not share the same chat history.

---

## 1. Project definition and current repository context

Idea Enhancer helps engineering students investigate a project idea before investing time in building it. It searches indexed project records, returns traceable matches, checks the evidence for potential overlap, and may generate one constrained improvement suggestion based on retrieved evidence.

The project is not a plagiarism detector and cannot prove universal originality. It can only describe what the current retrieval returned from the indexed sources. Correct wording includes “No records were returned from the current search”; this is not evidence that no similar project exists.

The planned core flow is:

1. Student submits an idea.
2. API validates the request.
3. BM25 retrieves keyword matches.
4. ChromaDB vector search retrieves semantically related projects.
5. Reciprocal Rank Fusion (RRF) combines the ranked lists.
6. Lightweight, explainable rules inspect the evidence for possible false positives.
7. API returns structured results; a separate LLM step may generate a constrained improvement suggestion.

**Important:** RRF scores are ranking-fusion values, not similarity percentages. Do not display `rrf_score = 0.03` as “3% similar,” and do not invent a percentage by normalizing it without a separately designed and evaluated scoring method.

The GitHub issue descriptions currently indicate these intended starting points: frontend `index.html` and `script.js`, FastAPI entrypoint `src/main.py`, core embedding/search work around `src/database.py`, and a cleaned dataset at `data/historical_projects.csv`. Inspect the assigned branch before relying on this as the actual current file layout; report any difference rather than blindly recreating files.

---

## 2. Shared Agent Prompt — use this with EVERY AI coding tool

Copy the whole block, then append only the matching role prompt from Section 7. If your tool already has a project rules file, keep these rules there too.

```text
You are an AI coding agent working on Idea Enhancer in this existing GitHub repository:
https://github.com/seepatimeghashyam/Idea-Enhancer

You are not the sole architect. Your job is to deliver one small, understandable, testable change for the role/task assigned to you. Work transparently and distinguish what you verified in the repository from assumptions or recommendations. Do not claim to have read, run, tested, changed, or verified anything unless you actually did.

STEP 1 — INSPECT BEFORE EDITING
1. Inspect the current branch, working-tree status, repository tree, relevant files, and the assigned GitHub issue.
2. Read the README and, if present, docs/PRD.md, docs/DECISIONS.md, docs/ARCHITECTURE.md, docs/API_CONTRACT.md, and docs/AI_TEAM_PROTOCOL.md. If a file is missing, say so; do not invent its contents.
3. Inspect existing code before creating or replacing files. Do not scaffold a second application or rewrite the project just because a clean start seems easier.
4. First return a concise discovery report: what exists, what is missing, relevant conflicts, files you intend to touch, your implementation plan, and how you will test it.
5. Do not begin implementation until the discovery report/plan has been shown. If the decision is already explicit in approved project docs, follow it; otherwise use the stop-and-ask rule below.

MANDATORY STOP-AND-ASK RULE
If an unresolved choice can affect another module, compatibility, or a project-level commitment, STOP BEFORE EDITING dependent code and ask the project owner for a decision. This includes:
- framework/runtime (for example React versus plain HTML/JS), public API topology, endpoint names, request/response fields, shared schemas, database/storage, embedding model, LLM provider, package manager, or any new dependency;
- changing a shared file, build setup, root dependency manifest/lockfile, app entrypoint, environment variable name, module ownership, or folder structure;
- changing retrieval/scoring meaning, confidence labels, evidence verification behavior, source/data scope, or what the system claims to have verified;
- conflict between current code, an issue, this protocol, an architecture document, or a suggestion from a teammate/senior;
- a task that cannot be implemented without deciding one of the above.

Do not pick a familiar option and pretend it was approved. Return a DECISION REQUEST in the exact format below and WAIT for Shyam/project owner approval before implementing anything dependent on it. You may list independent work that can safely continue, but do not perform work that could need to be thrown away after the decision.

DECISION REQUEST FORMAT
- ID / short title:
- What I inspected and found (file/issue evidence):
- Exact decision needed:
- Option A (benefits, drawbacks, compatibility impact):
- Option B (benefits, drawbacks, compatibility impact):
- Option C (only if genuinely necessary):
- Recommendation and reason:
- Files/modules affected:
- Work safe to continue while waiting:
- Exact approval needed from Shyam/project owner:

Do not stop for a small local choice that cannot affect other modules (such as a private helper name). Choose the simplest conventional solution, record the assumption in your final report, and keep it easy to change.

DECISION AUTHORITY
- Shyam/project owner approves decisions affecting the whole project after considering team input.
- Approved project decision docs and the API contract outrank your model's preference.
- Advice from a senior, online source, or another AI is a proposal—not a requirement—unless the project owner approves it.
- Never silently switch the stack or change another teammate's responsibilities.

FILE AND GIT SAFETY
- Edit only the files assigned to your role. If another file must change, explain why and ask before editing it.
- Do not make unrelated formatting/refactoring changes.
- Do not commit secrets, API keys, tokens, passwords, .env files, personal data, or private credentials. Use .env.example with placeholders only.
- Do not perform destructive commands, reset branches, force-push, commit, merge, or push unless the human explicitly authorizes it.
- Do not add a runtime dependency without explaining why, alternatives, and setup/runtime cost; ask for approval first.
- Do not fabricate dataset records, URLs, papers, results, scores, tests, or terminal output. Clearly label fixtures as MOCK/DEMO.

TRANSPARENCY AND HANDOFF
When finished, report:
1. Files changed and why.
2. How the code works, explained in plain language.
3. The input/output contract used.
4. Commands actually run and their observed results. Do not claim tests passed if they were not run.
5. Manual test/demo steps.
6. Assumptions, limitations, unimplemented pieces, and any remaining decisions.
7. Any necessary changes outside your assigned files that need approval.

The human must be able to understand the change. Prefer readable code and small functions over clever or unnecessarily complex code.

If the role-specific task is included in this same message, use it after completing discovery and resolving blockers. If no role/task was supplied, acknowledge these rules and wait for that task. Do not make edits before the discovery/plan gate.
```

---

## 3. Recommended V1 direction — based on the existing repo, not the senior's suggestions

The senior's notes about React, Node.js/Express, MySQL, MongoDB, authentication, rate limiting, and other tools are useful ideas to consider, **not mandatory requirements**. The existing repository README and Issue #4 currently specify HTML5, Tailwind CSS, and JavaScript for the frontend, while Issue #3 specifies Python/FastAPI. To reduce unnecessary changes and avoid conflicting implementations, keep that plan unless the project owner explicitly approves a change.

| Layer | V1 baseline | Notes |
|---|---|---|
| Frontend | HTML5 + Tailwind CSS + vanilla JavaScript | Keep `index.html` and `script.js` as the starting entry points; add small JS modules only when they provide a clear benefit and don't conflict with existing code. |
| API | Python + FastAPI | Public interface/orchestration; do not add Express as a second backend without an explicit decision. |
| Core retrieval | Python + `rank-bm25` + sentence-transformers + ChromaDB + RRF | Core search logic remains separate from HTTP routes and UI. |
| Dataset | `data/historical_projects.csv` initially | Curated records with consistent columns and traceable provenance; broader source support only when actually implemented. |
| Vector index | Local persistent ChromaDB | Rebuildable from the canonical dataset; not the only copy of source records. |
| LLM | One approved provider, called from backend only | Use for a constrained suggestion, not as the sole source of similarity judgments. |
| Structured relational database | Not required for the initial prototype | Add MySQL only if an approved feature needs it. MongoDB is not required merely because a source document was a PDF. |

**Embedding-model decision:** the detailed design notes mention `BAAI/bge-small-en-v1.5`, while the existing Issue #2 says to use `sentence-transformers` without naming an exact model. The library and model are different decisions. Before indexing begins, inspect the current branch and the decision docs. If the exact model is not approved, raise a Decision Request. Once selected, use the same model/configuration for every corpus embedding and query embedding; model changes require rebuilding the vector index.

**External sources and research papers:** these remain part of the broader product vision, but do not fake them. First make the local dataset/search path repeatable. Add GitHub or paper-source integrations when their API, terms, data schema, and owner are agreed and the integration is actually implemented.

---

## 4. Anti-conflict rules for the whole team

1. **One owner per module.** A teammate may review another module but should not create a competing implementation in its files.
2. **One source of truth.** Keep approved decisions and the API contract in the repository so every AI tool can read the same facts; do not rely on private chat history.
3. **Contract before integration.** The frontend may not invent backend fields. The API may not assume a search function that the core has not agreed to provide. The core may not assume dataset columns that the data owner has not finalized.
4. **Protected shared files:** `docs/DECISIONS.md`, `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`, any shared schema, `src/main.py` entrypoint decisions, root dependency manifests/lockfiles, and shared environment/config files require project-owner approval.
5. **Branch discipline:** use your existing assigned branch. Don't work directly on `main`; don't make a new competing branch if a designated one already exists. Ask if the correct branch is unclear.
6. **Small PRs:** one coherent feature/fix per pull request, with changed-file list, tests, manual demo and known limitations.
7. **Integrate incrementally:** run a frontend fixture while the backend is under development, connect a real FastAPI response as soon as possible, and replace mock results explicitly. Do not wait until every module is “finished.”
8. **No surprise architecture changes:** no React conversion, Express server, MySQL/MongoDB, new model, new package manager, or new route contract without a Decision Request and approval.
9. **No unsupported novelty claims:** no matching result is not proof of originality; a keyword overlap is not proof that two ideas are identical; an LLM suggestion is not a verified research finding.
10. **Honest progress:** report `implemented`, `partially implemented`, `mocked`, `planned`, or `not implemented` accurately.

### Required module handoff

When one owner hands work to another, provide:
- public function or endpoint name;
- exact request/input and response/output shape;
- one real example or clearly labelled mock fixture;
- errors and edge cases;
- run/test instructions;
- limitations and not-yet-supported behavior.

The receiver must compare this contract with code and docs before coding against it. Raise a Decision Request if they disagree.

---

## 5. API and data contract — must be approved once before integration

The design notes use `/search` and `/enhance`; preserve these routes unless the project owner approves a change. Exact details should be recorded in `docs/API_CONTRACT.md`. The examples below are proposals for the owner to approve, not evidence that the endpoints already exist.

### `POST /search` request

```json
{
  "idea": "An IoT-based crop disease detection system using Raspberry Pi and CNNs",
  "top_k": 5
}
```

- `idea`: required, trimmed, and limited to an agreed maximum length.
- `top_k`: optional, bounded on the server, default `5` for V1.
- Do not offer a frontend source-scope toggle until the backend supports each option.

### `POST /search` response proposal

```json
{
  "status": "success",
  "query": "An IoT-based crop disease detection system using Raspberry Pi and CNNs",
  "matches": [
    {
      "project_id": "sample_001",
      "title": "Example project title",
      "description_excerpt": "Text excerpt from the actual indexed record",
      "source_type": "college_dataset",
      "source_url": "https://example.com/record",
      "domain": "IoT",
      "technologies": ["Raspberry Pi", "CNN"],
      "rank": 1,
      "bm25_rank": 1,
      "vector_rank": 2,
      "rrf_score": 0.03,
      "shared_elements": ["Example shared term supported by the descriptions"],
      "verification_status": "checked"
    }
  ],
  "message": null,
  "warnings": []
}
```

All values here are illustrative schema values; the example URL/project is not a real result. Keep ranking fields distinct; `rrf_score` is not a similarity percentage. Unknown optional fields should be `null` or omitted according to one convention chosen in the API contract.

### `POST /enhance` request proposal

```json
{
  "idea": "An IoT-based crop disease detection system using Raspberry Pi and CNNs",
  "match_project_id": "sample_001"
}
```

The backend should retrieve this ID from the trusted indexed dataset rather than treating arbitrary project text supplied by the browser as verified evidence.

### `POST /enhance` response proposal

```json
{
  "status": "success",
  "match_project_id": "sample_001",
  "suggestion": "Illustrative text only; the implemented service should generate this from the actual idea and retrieved evidence.",
  "basis": ["Actual evidence used by the suggestion"],
  "confidence": "limited"
}
```

This is only an example shape. Before integration, agree on success/error HTTP statuses, validation error format, timeout behavior, missing-match behavior, whether enhancement is optional, and whether the frontend calls `/enhance` separately or the API orchestrates both steps. Agents must not decide these independently.

### Canonical dataset fields

The initial CSV should use one agreed set of columns, at minimum:
- `project_id` (stable unique ID)
- `title` (required)
- `abstract` or `description` (choose one canonical column before processing)
- `tech_stack` (optional; only known facts)
- `domain` (optional)
- `source_type` (required)
- `source_url` (where available)
- `year` (optional; only when known)

The existing Data issue names `title`, `abstract`, and `tech stack`. If an agent wants to rename these to `description`/`technologies`, it must propose a mapping and receive approval before the schema changes. No agent may independently use different field names.

---

## 6. File boundaries

Inspect the current branch before creating folders. This mapping follows the existing issue descriptions and may be refined only with approval.

| Owner | Main files | Must not independently change |
|---|---|---|
| Frontend UI — Shyam | `index.html`, `script.js`, frontend-only assets/modules | `src/main.py`, core search modules, dataset/ingestion, shared API contract, root dependencies |
| API & LLM | `src/main.py`, one agreed LLM service module, API tests | UI, retrieval algorithm, canonical CSV/ingestion, shared schema without approval |
| Core search | `src/database.py` as the planned interface plus any agreed `src/core/` modules and core tests | API routes, UI, canonical dataset/ingestion scripts, shared response contract without approval |
| Data & evaluation | `data/historical_projects.csv`, dataset documentation, validation/cleaning scripts, `tests/evaluation/` | API routes, UI, BM25/Chroma/RRF implementation, shared schema without approval |

The exact new module filenames should be proposed by the relevant owner after inspecting the real tree. Avoid turning `src/database.py` into one giant file: it can expose a small stable public interface and delegate to small internal functions/modules. But do not create a new structure that contradicts existing code without approval.

Shared/configuration files—including dependency manifests, lockfiles, `.env.example`, `src/main.py` routing decisions, shared Pydantic request/response models and project docs—must not be changed by multiple agents without coordination.

---

## 7. Role prompts — append only the prompt for your assigned issue

### A. Frontend UI Lead — Shyam — [Issue #4](https://github.com/seepatimeghashyam/Idea-Enhancer/issues/4)

```text
ROLE: FRONTEND UI LEAD. Work only on Issue #4 and frontend-owned files.

The current GitHub issue specifically calls for index.html and script.js with an idea input, loading state, result cards and Tailwind CSS. Keep HTML + Tailwind + vanilla JavaScript as the baseline. Do not convert the frontend to React/Vite/TypeScript unless Shyam explicitly approves that architecture change after reviewing the existing files.

MISSION
Build the smallest complete student journey: input idea → client validation → loading state → request through a single frontend API adapter → render matches/evidence → optionally request/show an enhancement → clear error/retry states.

OWNERSHIP
Modify index.html, script.js and frontend-only files/modules. You may split JS into small ES modules if useful, but keep the entrypoint clear and ensure the project runs without an unapproved build system. Do not implement BM25, ChromaDB, RRF, evidence rules, LLM prompts or backend routes. Do not embed secrets in browser code. Do not invent response fields.

REQUIREMENTS
- Accessible, labelled form and readable responsive layout.
- Validate empty/too-short input according to the approved API contract.
- Prevent accidental repeated submissions while a request is pending.
- Handle loading, success, no matches, API error, timeout, missing optional fields and enhancement failure.
- Display real source links only when supplied and valid.
- Keep demo fixtures in a separate clearly labelled MOCK/DEMO file; never present those as live results.
- Do not display RRF score as a similarity percentage.

Before coding, inspect the existing page/JS, current branch and API contract. If the stack or API schema is unresolved, return the required Decision Request. Finish by listing changed files, commands actually run, observed test results, and manual demo steps. Explain the browser-to-API-to-result data flow in plain English.
```

### B. API & LLM Integration Lead — [Issue #3](https://github.com/seepatimeghashyam/Idea-Enhancer/issues/3)

```text
ROLE: API & LLM INTEGRATION LEAD. Work only on Issue #3 and API/LLM-owned files.

MISSION
Implement the FastAPI request layer, coordinate calls to the core search interface, and provide the approved structured LLM suggestion. The API validates and orchestrates; it must not duplicate search logic.

OWNERSHIP
Own src/main.py and the agreed LLM service/orchestration module plus API tests. Agree exact imports/function signatures with the Core owner before using them. Do not implement BM25/embeddings/RRF or modify the UI or canonical dataset. Do not change public routes/response fields without approval.

LLM RULES
- Provider API keys stay in environment variables; never expose them to the browser or commit them.
- The model may generate a constrained improvement suggestion from the submitted idea and an actual retrieved record. It must not invent source URLs, papers, match records, or claim it proved originality.
- Validate the model's output; handle malformed output, missing credentials, rate limits and timeouts gracefully.
- If no relevant record exists, report insufficient evidence instead of fabricating a comparison.
- Keep LLM failure from crashing basic search results where the contract permits a partial response.

TESTING
Add tests with mocked core results and mocked LLM responses. Test valid request, invalid request, no match, malformed model output and provider failure. Do not require a live paid API to run the basic test suite. Report tests honestly and do not change dependency files without approval.
```

### C. Core Backend & Search Lead — [Issue #2](https://github.com/seepatimeghashyam/Idea-Enhancer/issues/2)

```text
ROLE: CORE BACKEND & SEARCH LEAD. Work only on Issue #2 and core-search-owned files.

MISSION
Build a deterministic retrieval pipeline: load/validate the approved dataset or index → BM25 keyword retrieval → ChromaDB semantic retrieval with the approved embedding model → RRF fusion → top-K project matches → transparent rule/evidence checks. Return structured records to FastAPI; do not build HTTP endpoints or call the LLM directly.

OWNERSHIP
Own src/database.py as the planned public interface plus agreed core modules and tests. Consume the Data owner's canonical CSV; do not independently rename its fields or write a competing dataset/ingestion workflow. Coordinate expected function signatures and output fields with the API owner before implementing them.

TECHNICAL RULES
- Use one approved embedding model consistently for corpus and query embeddings. If it is not settled in docs/DECISIONS.md, stop and ask before indexing.
- Keep BM25 rank, vector rank, RRF score and any future calibrated similarity metric distinct.
- Do not convert RRF score to a percentage.
- Preserve project ID/title/source URL so matches are traceable.
- Handle empty query, empty dataset, duplicate IDs, missing optional metadata, missing index and no-result cases.
- Exact keyword checks provide limited evidence; do not describe them as proof of semantic novelty.
- Make index creation/rebuild repeatable and explain how to run it.

TESTING
Create small deterministic fixtures for exact keyword overlap, paraphrased/synonymous ideas, unrelated ideas, missing metadata and an empty dataset. Report what works and known limitations. Do not claim hybrid retrieval is better than a baseline until the labeled evaluation has actually been run.
```

### D. Data Collection & Ingestion Lead — [Issue #1](https://github.com/seepatimeghashyam/Idea-Enhancer/issues/1)

```text
ROLE: DATA COLLECTION & INGESTION LEAD. Work only on Issue #1 and dataset/ingestion/evaluation-owned files.

MISSION
Prepare a clean, traceable data/historical_projects.csv file with consistent records that the core owner can load repeatedly. The deliverable is useful data and reproducible validation, not just a high row count.

OWNERSHIP
Own data/historical_projects.csv, dataset notes, cleaning/validation scripts and evaluation fixtures. Do not implement the search engine, API routes or frontend. Do not change canonical fields without a Decision Request and approval.

DATA RULES
- Preserve stable project IDs and source provenance/URLs where possible.
- Use the exact approved columns. The current issue mentions title, abstract and tech stack; do not rename those fields independently.
- Remove obvious duplicate, empty or unusable rows and document the cleaning rules.
- Never invent title, abstract, technologies, year, source URL or other facts. Unknown fields stay blank/null under the agreed convention.
- Keep the dataset legally and ethically usable; respect source terms and rate limits for any external collection. Do not collect unnecessary personal data.
- Make the data validation/cleaning process reproducible. The Core owner should not need to manually edit records inside search code.

EVALUATION
Create a small set of queries and hand-label which dataset records are relevant where practical. Include exact keywords, paraphrases, unrelated ideas and no-match cases. Document the judgment criteria and ambiguity. A target of around 20–30 labeled cases is a pilot if time permits, not statistically conclusive proof.

HANDOFF
Report actual row count, duplicates removed, missing-field counts, provenance coverage, validation command and observed output. Clearly state data limitations. Do not claim a target dataset size before it exists.
```

---

## 8. Shyam's project-owner checklist

Before agents generate large amounts of code:

- [ ] Confirm the current repository/assigned branches are the source of truth; ask agents to inspect their branch rather than assume files exist.
- [ ] Create or approve `docs/DECISIONS.md`, `docs/ARCHITECTURE.md`, and `docs/API_CONTRACT.md` when the relevant decisions are settled.
- [ ] Keep the current HTML/Tailwind/JavaScript + FastAPI plan unless there is a deliberate, approved reason to switch to React or add another server.
- [ ] Approve one embedding model and canonical CSV columns before the index is built.
- [ ] Approve route names, request/response fields, no-match behavior and error format once; every agent uses the same contract.
- [ ] Require the agent's discovery report and plan before substantial edits.
- [ ] Require small PRs and review diffs; never merge code solely because an agent says it is done.
- [ ] Integrate the first full request/response path early using an explicitly labelled fixture, then switch to real search results.
- [ ] Ask each teammate to explain their code, show what tests ran and identify what is still incomplete.

### Decision log template

```text
Decision ID:
Date:
Question:
Decision approved:
Options considered:
Reason:
Affected files/modules:
Approved by:
Condition to revisit:
```

---

## 9. Pull-request / handoff checklist

Each PR should state:

1. Purpose and issue/acceptance criteria addressed.
2. Files changed and why.
3. Input/output contract and downstream dependencies.
4. Commands actually run and observed test results.
5. Manual demo steps.
6. Mocks, limitations, incomplete features and unsupported inputs.
7. Any AI-generated changes that the author reviewed or modified, plus any assumptions that remain.
8. Confirmation that no unapproved stack/schema/dependency/API changes or cross-owner edits were made.

**A module is not done just because code was generated.** It is complete for the current milestone when its owner can explain it, run it, demonstrate the agreed acceptance criteria, and hand it over through the agreed interface.
