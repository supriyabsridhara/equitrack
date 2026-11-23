# AI usage and validation log: Member 2

Fill one row per AI interaction as you work (rubric: Documentation & Viva). Examples of what to record are pre-listed
in the validation column; replace with what you actually did.

| Date | Task | Tool | Prompt (summary) | Output used? | How I validated it | Issues found / changes made |
|---|---|---|---|---|---|---|
| | Event classes + dispatcher | | | | Read every line; ran `tests/test_events_and_notifications.py`; checked MRO-based dispatch | |
| | AlertService + duplicate prevention | | | | Ran TC-14..TC-17 tests; reasoned about atomic claim; tried two quick refreshes manually | |
| | Alert/notification routes | | | | curl each endpoint incl. invalid bodies; checked status codes | |
| | Frontend (HTML/CSS/JS) | | | | Clicked every page and form; tested empty states, errors, mobile width, keyboard navigation | |
| | Dockerfile / Compose | | | | `docker build`, `docker compose up`, restart test, confirmed no secrets in `docker history` | |
| | Jenkinsfile | | | | Ran build; broke a test on purpose to confirm the pipeline fails | |
| | Kubernetes manifests | | | | `kubectl apply`, `get pods`, deleted pod to confirm data persists | |

## Limitations observed (add yours)
* AI output was written against an *assumed* API shape; the contract with Member 1 had to be agreed explicitly.
* Generated code needs review for secrets, edge cases (NaN/negative prices, booleans as numbers) and idempotency.
