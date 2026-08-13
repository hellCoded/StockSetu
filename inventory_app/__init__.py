import time
from flask import Flask, render_template, session
from config import Config
from inventory_app.database import init_db
from inventory_app.utils.validators import generate_csrf_token
from inventory_app.utils.helpers import calculate_stock_status, get_status_badge_class, format_currency, format_datetime, amount_in_words

def create_app(config_class=Config, custom_mongo_client=None):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Database Connection
    init_db(app, custom_client=custom_mongo_client)

    # Context Processor for Templates
    # Lightweight in-memory TTL cache to prevent DB reads on every HTTP request
    _cache = {}

    @app.context_processor
    def inject_utilities():
        user_id = session.get('user_id')
        user_role = session.get('role', 'staff')
        username = session.get('username', '')

        now = time.time()
        pending_requests_count = 0
        unread_notifications_count = 0

        if user_id:
            # 30-second cached badges to eliminate DB lag on page transitions
            cached_entry = _cache.get(user_id)
            if cached_entry and (now - cached_entry['ts']) < 30:
                pending_requests_count = cached_entry.get('pending', 0)
                unread_notifications_count = cached_entry.get('unread', 0)
            else:
                if user_role == 'admin':
                    from inventory_app.services.auth_service import get_all_pending_role_requests
                    try:
                        pending_requests_count = len(get_all_pending_role_requests())
                    except Exception:
                        pass
                
                from inventory_app.services.notification_service import get_unread_notifications_count
                try:
                    unread_notifications_count = get_unread_notifications_count()
                except Exception:
                    pass

                _cache[user_id] = {
                    'pending': pending_requests_count,
                    'unread': unread_notifications_count,
                    'ts': now
                }

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
            'unread_notifications_count': unread_notifications_count
        }

    # Register Blueprints
    from inventory_app.routes.auth_routes import auth_bp
    from inventory_app.routes.dashboard_routes import dashboard_bp
    from inventory_app.routes.product_routes import product_bp
    from inventory_app.routes.inventory_routes import inventory_bp
    from inventory_app.routes.user_routes import user_bp
    from inventory_app.routes.billing_routes import billing_bp
    from inventory_app.routes.notification_routes import notification_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(product_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(notification_bp)

    # Error Handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500

    return app
