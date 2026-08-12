import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'inventory-super-secret-key-2026-safe')
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/inventory_db')
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'inventory_db')
    TESTING = os.getenv('TESTING', 'False').lower() in ('true', '1', 't')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() in ('true', '1', 't')
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours in seconds

class TestConfig(Config):
    TESTING = True
    DATABASE_NAME = 'inventory_test_db'
    MONGO_URI = 'mongodb://localhost:27017/inventory_test_db'
    SECRET_KEY = 'test-secret-key'
