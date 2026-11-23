# GitHub plan: Member 2

## Branches (PR into `main`, review by Member 1)
| Branch | Contents |
|---|---|
| `feature/alerts-events` | events, dispatcher, repositories, AlertService, NotificationService, routes, `integration.py`, tests |
| `feature/frontend` | `frontend/` (all pages), `dev/mock_server.py` |
| `feature/devops` | Dockerfile, compose, Jenkinsfile, `k8s/`, docs/diagrams |

## Issues to open (assign yourself, link in PRs with `Closes #n`)
1. Event classes and dispatcher
2. Alert and notification repositories
3. AlertService: validation, evaluation, duplicate prevention
4. Alert and notification REST endpoints
5. Frontend: dashboard, watchlist, portfolio, transactions
6. Frontend: alerts page, notifications, toasts and polling
7. Dockerfile and docker-compose
8. Jenkins pipeline
9. Kubernetes manifests and Minikube deployment
10. Integration with Member 1 refresh hook
11. SDS sections, sequence/deployment diagrams, AI log

## Suggested commit rhythm (shows steady contribution)
`Add price event classes` -> `Add EventDispatcher with tests` -> `Add alert repository` -> `Add AlertService evaluation` ->
`Prevent duplicate triggers with atomic claim` -> `Add alert routes` -> `Add notification routes` -> `Add UI shell and styles` ->
`Add dashboard view` -> `Add alerts view` -> `Add Dockerfile` -> `Add Jenkinsfile` -> `Add k8s manifests` -> `Document integration contract`.

## What to review in Member 1's PRs
- No API key in code, tests or history; read from `ALPHA_VANTAGE_API_KEY`.
- Fallback chain: provider -> cached snapshot -> clear error; response includes `source` and `timestamp`.
- Weighted-average cost; sale reduces cost basis proportionally; oversell rejected; realized P/L accumulates.
- `notify_price_update` called only on fresh prices, after the snapshot is saved.
- Response shapes match `MEMBER1_INTEGRATION.md` section 6.

## Evidence to capture
Commit graph, merged PRs with review comments, Jenkins green build + a deliberately failed build, `docker images`,
`kubectl get pods,svc`, browser screenshots of each page, notification toast, and the data-persistence test.
