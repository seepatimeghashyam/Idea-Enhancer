# Operations and deployment checks

## Health endpoint

`GET /health` returns `{"status":"ok"}` when FastAPI is serving requests. It is a liveness check only: it does not query OpenAlex or GitHub, load the embedding model, inspect ChromaDB, or verify the historical index. There is no readiness endpoint. The offline model/index warm-up runs separately and has not been measured on a hosted service, so do not treat liveness as proof that either search mode is ready.

## Request quotas

Live search permits at most four in-flight searches per process, but has no per-caller or global request quota. This concurrency bound does not prevent one visitor from consuming a shared provider quota. For a shared deployment, configure limits at the hosting edge or API gateway. Only trust client identity forwarded by a proxy that the deployment explicitly controls; do not add application limits based on arbitrary `X-Forwarded-For` headers. Choose thresholds after observing legitimate request volume and provider responses.

## GitHub progress-watch data flow

The separate progress-watch workflow runs on pushes to `solo/independent-mvp`. Its helper retrieves metadata and selected textual patches for up to 20 commits through the GitHub API. It caps an individual patch at 5,000 characters and the total patch text at 36,000 characters, omits sensitive-looking paths and directories, and excludes data, binary, generated, and lock files. Recognized secret patterns are redacted. Paths and change metadata may still be included when file contents are withheld.

The helper sends the assembled commit metadata and selected, redacted diffs to the Google Gemini Developer API for classification, using the model configured by the workflow (`gemini-3.8-flash`). If the result meets its evidence and confidence rules, it posts a summary to the repository's persistent progress-watch issue. It does not modify repository source. This documents what the code sends; provider retention and data-use terms are not assessed here. The regular Python CI workflow is separate and does not call the progress-watch helper.

## Staging verification checklist

Before describing a hosted instance as reliable, record results for a clean deployment of the current commit:

- Install the declared dependencies in Python 3.12 and start the service without relying on a developer cache.
- Measure process startup, first Offline Demo request, first Live Research request, and warm-request latency.
- Measure peak memory during first model load and concurrent searches; repeat after a service restart.
- Confirm ChromaDB storage is writable and persists across restarts if Offline Demo is enabled. Test the configured worker count because each process has its own in-memory state and concurrency semaphore.
- Check `/health` during process startup and after startup; verify provider outages do not make liveness fail. Test provider timeout, one-provider failure, both-provider failure, and BM25-only mode separately.
- Confirm the static frontend uses the deployed HTTPS API origin, CORS allows only the intended origin, and secrets remain server-side.
- Configure and exercise hosting-edge request limits; record how 429 responses appear to the user.
- Confirm external provider calls and user-facing privacy wording in the deployed UI. Do not infer provider retention behavior without checking current official terms.

No staging measurements are currently recorded. A successful deployment alone does not establish production readiness.
