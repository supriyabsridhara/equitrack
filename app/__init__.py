import os

from dotenv import load_dotenv
from flask import Flask
from pymongo import MongoClient

from app.integration import init_alerts_and_ui
from app.providers.alpha_vantage_provider import AlphaVantageProvider
from app.providers.mock_stock_data_provider import MockStockDataProvider
from app.repositories.portfolio_repository import PortfolioRepository
from app.repositories.stock_repository import StockRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.routes.portfolio_routes import portfolio_bp
from app.routes.stock_routes import stock_bp
from app.routes.watchlist_routes import watchlist_bp
from app.services.portfolio_service import PortfolioService
from app.services.stock_service import StockService
from app.services.watchlist_service import WatchlistService
from app.utils.mongo_utils import utcnow


load_dotenv()


def create_app(test_config=None, db=None, provider=None):
    app = Flask(__name__)
    app.config.from_mapping(
        TESTING=False,
        DEFAULT_USER_ID=os.getenv("DEFAULT_USER_ID", "local-user"),
        DEFAULT_CURRENCY=os.getenv("DEFAULT_CURRENCY", "INR"),
        MONGODB_URI=os.getenv("MONGODB_URI", "mongodb://localhost:27017/equitrack"),
        ALPHA_VANTAGE_API_KEY=os.getenv("ALPHA_VANTAGE_API_KEY"),
        ENABLE_PRICE_OVERRIDE=os.getenv("ENABLE_PRICE_OVERRIDE", "false").lower() in {"1", "true", "yes"},
        STOCK_DATA_PROVIDER=os.getenv("STOCK_DATA_PROVIDER", "auto").lower(),
    )
    if test_config:
        app.config.update(test_config)

    if db is None:
        client = MongoClient(app.config["MONGODB_URI"], serverSelectionTimeoutMS=5000)
        db = client.get_default_database()

    app.extensions["mongo_db"] = db
    app.extensions["mongo_client"] = getattr(db, "client", None)

    stock_repo = StockRepository(db)
    watchlist_repo = WatchlistRepository(db)
    transaction_repo = TransactionRepository(db)
    portfolio_repo = PortfolioRepository(db)

    provider_name = app.config["STOCK_DATA_PROVIDER"]
    if provider is None:
        if provider_name in {"mock", "mock_stock"} or (
            provider_name == "auto" and not app.config["ALPHA_VANTAGE_API_KEY"]
        ):
            provider = MockStockDataProvider()
        else:
            provider = AlphaVantageProvider(app.config["ALPHA_VANTAGE_API_KEY"])

    stock_service = StockService(stock_repo, provider)
    watchlist_service = WatchlistService(watchlist_repo, stock_service)
    portfolio_service = PortfolioService(portfolio_repo, transaction_repo, stock_service,
                                         app.config["DEFAULT_USER_ID"])

    app.extensions["stock_repository"] = stock_repo
    app.extensions["watchlist_repository"] = watchlist_repo
    app.extensions["portfolio_repository"] = portfolio_repo
    app.extensions["transaction_repository"] = transaction_repo
    app.extensions["stock_provider"] = provider
    app.extensions["stock_service"] = stock_service
    app.extensions["watchlist_service"] = watchlist_service
    app.extensions["portfolio_service"] = portfolio_service

    app.register_blueprint(stock_bp)
    app.register_blueprint(watchlist_bp)
    app.register_blueprint(portfolio_bp)
    init_alerts_and_ui(
        app,
        db=db,
        symbol_validator=stock_service.symbol_exists,
    )

    app.extensions["started_at"] = utcnow()
    return app
