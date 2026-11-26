# Research Pilot — Rejected and Deferred Candidates

This log documents candidates inspected during pilot collection (`2026-11-24`) that were **excluded or deferred** rather than included in the 20-record pilot set.

| Candidate / Identifier | Provider | Topic | HTTP Status | Disposition | Reason |
|---|---|---|---|---|---|
| `FarmBot/farmbot-os` | GitHub | Agriculture / Robotics | 404 | Rejected | Repository URL returned HTTP 404 Not Found via GitHub REST API; unreachable. |
| `10.1007/s11276-023-03495-2` | OpenAlex | Cybersecurity / Network IDS | 200 | Rejected | Returned as `RETRACTED ARTICLE: Towards an efficient model for network intrusion detection system (IDS): systematic literature review` with empty abstract (`0` chars) and `unknown` license. |
| `Circuit-Digest/Elderly-Fall-Detection-System` | GitHub | Healthcare / Assistive Tech | 200 | Deferred | GitHub API `description` field is empty; requires manual README inspection before inclusion. |
| `CodeWithAlvin/fallDetection` | GitHub | Healthcare / Assistive Tech | 200 | Deferred | GitHub API `description` field is empty and `license` is `unknown`; requires manual README inspection. |
| `10.3390/agronomy12102377` | OpenAlex | Agriculture / Computer Vision | 200 | Deferred | Returned title (*Assessment of Spray Drift with Various Adjuvants in a Wind Tunnel*) did not match the intended crop-leaf-disease topic. |
| `10.1016/j.teac.2022.e00173` | OpenAlex | Environment / IoT | 200 | Deferred | Abstract missing (`abstract_inverted_index` empty in OpenAlex) and license `unknown`. |
| `10.48550/arxiv.1912.01703` (PyTorch) | OpenAlex | Software Engineering / ML | 200 | Rejected | Returned by citation-sorted search; too broad/foundational as a general deep-learning library rather than a specific project-idea reference. |
| `10.1038/s41586-020-2649-2` (NumPy) | OpenAlex | Software Engineering / ML | 200 | Rejected | Returned by citation-sorted search; foundational numerical library outside pilot project-reference scope. |
| `10.5281/zenodo.24511160` | Zenodo | Agriculture / Environment | 200 | Rejected | Returned by `sort=mostrecent` query; off-topic watershed dataset unrelated to plant disease or intrusion detection. |
