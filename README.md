# EquiTrack: Stock Portfolio Monitoring Service

EquiTrack provides stock search, watchlists, virtual portfolio transactions,
weighted-average holdings, price alerts, notifications, MongoDB persistence,
Docker, Jenkins and Kubernetes support.

## Run the complete mock-backed app
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m dev.mock_server                              # http://localhost:5000  (in-memory data)
```
The real Flask factory is also available at `app:create_app()`. Set
`STOCK_DATA_PROVIDER=mock` and `ENABLE_PRICE_OVERRIDE=true` for local demos.
Refresh with a forced price, e.g.
`curl -X POST localhost:5000/api/stocks/AAPL/refresh -H "Content-Type: application/json" -d '{"price": 2005}'`.

## Tests and lint
```bash
python -m pytest -v
flake8 app tests dev
```

## Docker
```bash
cp .env.example .env     # add your Alpha Vantage key
docker compose up --build
```

## Kubernetes (Minikube)
```bash
minikube start
docker build -t equitrack:v1 . && minikube image load equitrack:v1
kubectl create secret generic equitrack-secrets \
  --from-literal=ALPHA_VANTAGE_API_KEY=<key> --from-literal=MONGODB_URI=mongodb://mongo:27017/equitrack
kubectl apply -f k8s/
kubectl set image deployment/equitrack-app app=equitrack:v1
minikube service equitrack-service
```

## Jenkins
Create a pipeline job from this repo's `Jenkinsfile`. Add a *Secret text* credential with id `alpha-vantage-key`.
The agent needs Python 3, Docker, `kubectl` and `minikube` on its PATH.
