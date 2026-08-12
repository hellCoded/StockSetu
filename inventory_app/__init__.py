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
    @app.context_processor
    def inject_utilities():
        user_id = session.get('user_id')
        user_role = session.get('role', 'staff')
        username = session.get('username', '')
        
        if user_id:
            from inventory_app.services.auth_service import get_user_by_id
            live_user = get_user_by_id(user_id)
            if live_user:
                user_role = live_user.get('role', 'staff')
                username = live_user.get('username', username)
                session['role'] = user_role

        pending_requests_count = 0
        if user_id and user_role == 'admin':
            from inventory_app.services.auth_service import get_all_pending_role_requests
            try:
                pending_requests_count = len(get_all_pending_role_requests())
            except Exception:
                pass

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
            'pending_requests_count': pending_requests_count
        }

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
        return render_template('errors/500.html'), 500

    return app
