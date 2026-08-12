"""
Vercel serverless entrypoint for the StockSetu Flask application.

Vercel auto-detects Flask (WSGI) apps by the presence of a top-level
`app` instance and serves it as a single catch-all serverless function
(the "/api/index" function). All routes are routed here via vercel.json.
"""
from inventory_app import create_app
from config import Config

app = create_app(Config)