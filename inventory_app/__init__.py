import os
import json
import logging
from datetime import datetime, timezone
from flask import Flask, render_template, session, request, redirect, url_for, flash
from config import Config
from inventory_app.database import init_db
from inventory_app.utils.validators import generate_csrf_token
from inventory_app.utils.helpers import calculate_stock_status, get_status_badge_class, format_currency, format_datetime, amount_in_words

logger = logging.getLogger(__name__)

# ── Global cache: Upstash Redis (Vercel) or local fallback ──
_cache_store = None
_use_upstash = False


def _get_cache():
    global _cache_store, _use_upstash
    if _cache_store is not None:
        return _cache_store

    upstash_url = os.environ.get('UPSTASH_REDIS_REST_URL', '')
    upstash_token = os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')

    if upstash_url and upstash_token:
        try:
            from upstash_redis import Redis
            _cache_store = Redis(url=upstash_url, token=upstash_token)
            _use_upstash = True
            logger.info("Upstash Redis global cache initialized.")
            return _cache_store
        except Exception as e:
            logger.warning(f"Upstash Redis failed ({e}), falling back to local cache.")

    # Fallback: redislite (in-process) → dict
    try:
        import redislite
        _cache_store = redislite.StrictRedis(dbfilename=':memory:')
        logger.info("Redislite in-process cache initialized (local mode).")
        return _cache_store
    except Exception:
        _cache_store = {}
        logger.warning("Redislite unavailable, using dict cache.")
        return _cache_store


def cache_get(key):
    c = _get_cache()
    if isinstance(c, dict):
        return c.get(key)
    try:
        val = c.get(key)
        return val.decode() if isinstance(val, bytes) else val
    except Exception:
        return None


def cache_set(key, value, ttl=60):
    c = _get_cache()
    if isinstance(c, dict):
        c[key] = value
        return
    try:
        c.setex(key, ttl, str(value))
    except Exception:
        if isinstance(c, dict):
            c[key] = value


def cache_delete(key):
    c = _get_cache()
    if isinstance(c, dict):
        c.pop(key, None)
        return
    try:
        c.delete(key)
    except Exception:
        pass


def cache_flush():
    c = _get_cache()
    if isinstance(c, dict):
        c.clear()
        return
    try:
        c.flushall()
    except Exception:
        pass

def create_app(config_class=Config, custom_mongo_client=None):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

    # ── Flask-Limiter (rate limiting) ──
    # Upstash uses REST API, not TCP — Flask-Limiter's redis:// won't work.
    # Use in-memory per-instance rate limiting (sufficient for serverless).
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
        limiter = Limiter(
            get_remote_address,
            app=app,
            default_limits=["200 per minute", "50 per second"],
            storage_uri="memory://",
        )
        logger.info("Flask-Limiter: in-memory rate limiting enabled.")
        app.extensions['limiter'] = limiter
    except Exception as e:
        logger.warning(f"Flask-Limiter not available: {e}")
        limiter = None

    # Initialize Database Connection
    init_db(app, custom_client=custom_mongo_client)

    # ── Enforce 12-hour offline/inactivity timeout, auto-deactivation, and logout ──
    @app.before_request
    def check_user_session_and_activity():
        path = request.path
        if path.startswith('/static') or path in ('/health',):
            return None

        # Periodically sweep offline users (inactive for > 12 hours) and mark them inactive
        last_sweep = cache_get("auth:last_inactive_sweep")
        if not last_sweep:
            try:
                from inventory_app.services.auth_service import deactivate_inactive_users
                deactivate_inactive_users(inactivity_hours=12.0)
                cache_set("auth:last_inactive_sweep", "1", ttl=300)
            except Exception:
                pass

        user_id = session.get('user_id')
        if not user_id:
            return None

        now = datetime.now(timezone.utc)
        now_ts = now.timestamp()

        # Check session inactivity (12 hours = 43200 seconds)
        last_active_ts = session.get('last_active_at')
        if last_active_ts:
            try:
                if (now_ts - float(last_active_ts)) > 43200:
                    from inventory_app.services.auth_service import set_user_active_status
                    set_user_active_status(user_id, False)
                    session.clear()
                    flash("You have been logged out due to 12 hours of inactivity, and your account has been set to inactive.", "warning")
                    return redirect(url_for('auth.login'))
            except (ValueError, TypeError):
                pass

        # Check if user has been deactivated in the database
        from inventory_app.services.auth_service import get_user_by_id, record_user_activity
        user = get_user_by_id(user_id)
        if not user or not user.get('is_active', True):
            session.clear()
            flash("Your account has been deactivated. Please contact an administrator.", "danger")
            return redirect(url_for('auth.login'))

        # Update session activity timestamp
        session['last_active_at'] = now_ts

        # Throttle DB sync of last_active_at (once every 2 minutes)
        last_db_sync = session.get('last_db_active_sync', 0)
        try:
            if (now_ts - float(last_db_sync)) > 120:
                record_user_activity(user_id)
                session['last_db_active_sync'] = now_ts
        except (ValueError, TypeError):
            record_user_activity(user_id)
            session['last_db_active_sync'] = now_ts

        return None

    # ── Cache-Control headers for static assets and pages ──
    STATIC_NO_CACHE = {'/health'}
    STATIC_LONG_CACHE = {'.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.eot'}

    @app.after_request
    def optimize_response(response):
        path = request.path
        ext = os.path.splitext(path)[1].lower()

        # Static assets: long cache (1 year, immutable)
        if ext in STATIC_LONG_CACHE:
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        # Health endpoint: no cache
        elif path in STATIC_NO_CACHE:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        # HTML pages: short cache with revalidation
        elif request.accept_mimetypes.accept_html and not path.startswith('/api/'):
            response.headers['Cache-Control'] = 'private, max-age=0, must-revalidate'

        # Security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Gzip response compression for text, CSS, JS, JSON, and SVG > 500 bytes
        accept_encoding = request.headers.get('Accept-Encoding', '')
        if (
            'gzip' in accept_encoding.lower()
            and response.status_code == 200
            and 'Content-Encoding' not in response.headers
        ):
            ctype = response.headers.get('Content-Type', '').lower()
            if any(t in ctype for t in ('text/', 'application/javascript', 'application/json', 'image/svg+xml')):
                response.direct_passthrough = False
                data = response.get_data()
                if len(data) > 500:
                    import gzip
                    compressed = gzip.compress(data, compresslevel=6)
                    response.set_data(compressed)
                    response.headers['Content-Encoding'] = 'gzip'
                    response.headers['Content-Length'] = len(compressed)
                    response.headers['Vary'] = 'Accept-Encoding'

        return response

    # Context Processor for Templates
    # Lightweight global TTL cache to prevent DB reads on every HTTP request.

    @app.context_processor
    def inject_utilities():
        user_id = session.get('user_id')
        user_role = session.get('role', 'staff')
        username = session.get('username', '')

        pending_requests_count = 0
        low_stock_alerts = []
        low_stock_count = 0

        # Skip heavy context queries on routes that don't render sidebar/navbar
        endpoint = request.endpoint or ''
        path = request.path
        _skip_heavy = (
            not user_id
            or path in ('/health',)
            or path.startswith('/export')
            or path.startswith('/transactions')
            or endpoint.startswith('auth.')
            or (request.method == 'POST' and not endpoint.endswith('.index'))
            or request.path.startswith('/billing/bills/')  # detail views
        )

        if not _skip_heavy and user_role in ('admin', 'inventory_manager'):
            cached_entry = cache_get("pending:count")
            if cached_entry:
                try:
                    pending_requests_count = int(cached_entry)
                except (TypeError, ValueError):
                    pending_requests_count = 0
            else:
                try:
                    from inventory_app.database import get_db
                    pending_requests_count = get_db().role_requests.count_documents({"status": "PENDING"})
                    cache_set("pending:count", str(pending_requests_count), ttl=30)
                except Exception:
                    pass

        if not _skip_heavy and user_id:
            cached_alerts = cache_get("alerts:low_stock")
            if cached_alerts:
                try:
                    low_stock_alerts = json.loads(cached_alerts)
                except (TypeError, ValueError):
                    low_stock_alerts = []
            else:
                try:
                    from inventory_app.services.product_service import get_stock_alerts
                    low_stock_alerts = get_stock_alerts(limit=6)
                    cache_set("alerts:low_stock", json.dumps(low_stock_alerts, default=str), ttl=30)
                except Exception:
                    low_stock_alerts = []

            cached_count = cache_get("alerts:low_stock_count")
            if cached_count is not None:
                try:
                    low_stock_count = int(cached_count)
                except (TypeError, ValueError):
                    low_stock_count = 0
            else:
                try:
                    from inventory_app.database import get_db
                    low_stock_count = get_db().products.count_documents(
                        {"is_active": True, "$expr": {"$lte": ["$quantity", {"$ifNull": ["$minimum_stock", 5]}]}}
                    )
                    cache_set("alerts:low_stock_count", str(low_stock_count), ttl=30)
                except Exception:
                    low_stock_count = 0

        return {
            'csrf_token': generate_csrf_token,
            'calculate_stock_status': calculate_stock_status,
            'get_status_badge_class': get_status_badge_class,
            'format_currency': format_currency,
            'format_datetime': format_datetime,
            'amount_in_words': amount_in_words,
            'current_user': {
                'id': user_id,
                'username': username,
                'role': user_role
            },
            'pending_requests_count': pending_requests_count,
            'low_stock_alerts': low_stock_alerts,
            'low_stock_count': low_stock_count
        }

    # Lightweight health check (used by keep-warm pings / uptime monitors).
    # Deliberately avoids DB access so a cold start stays fast.
    @app.get('/health')
    def health():
        return 'OK', 200

    # Register Blueprints
    from inventory_app.routes.auth_routes import auth_bp
    from inventory_app.routes.dashboard_routes import dashboard_bp
    from inventory_app.routes.product_routes import product_bp
    from inventory_app.routes.inventory_routes import inventory_bp
    from inventory_app.routes.user_routes import user_bp
    from inventory_app.routes.billing_routes import billing_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(product_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(billing_bp)

    # Error Handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def internal_error(error):
        logger.exception("Unhandled 500 error")
        return render_template('errors/500.html'), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        logger.exception(f"Unhandled exception: {e}")
        return render_template('errors/500.html'), 500

    return app
