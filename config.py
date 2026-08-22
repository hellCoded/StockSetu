import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # SECRET_KEY must be provided via environment variable at runtime
    # No default/fallback allowed — application will fail to start if missing
    SECRET_KEY = os.getenv('SECRET_KEY')
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/inventory_db')
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'inventory_db')
    TESTING = os.getenv('TESTING', 'False').lower() in ('true', '1', 't')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'True').lower() in ('true', '1', 't')
    PERMANENT_SESSION_LIFETIME = 43200  # 12 hours in seconds (43200s)
    # Upstash Redis (global cache + rate limiting for Vercel serverless)
    UPSTASH_REDIS_REST_URL = os.getenv('UPSTASH_REDIS_REST_URL', '')
    UPSTASH_REDIS_REST_TOKEN = os.getenv('UPSTASH_REDIS_REST_TOKEN', '')

class TestConfig(Config):
    TESTING = True
    DATABASE_NAME = 'inventory_test_db'
    MONGO_URI = 'mongodb://localhost:27017/inventory_test_db'
    SECRET_KEY = 'test-secret-key'
