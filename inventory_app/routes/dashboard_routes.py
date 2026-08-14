from flask import Blueprint, render_template
from inventory_app.utils.decorators import login_required
from inventory_app import cache_get, cache_set
import json

dashboard_bp = Blueprint('dashboard', __name__)

_DASHBOARD_CACHE_TTL = 30


@dashboard_bp.route('/')
@login_required
def index():
    from inventory_app.services.inventory_service import get_dashboard_metrics
    from inventory_app.services.product_service import (
        get_stock_by_category,
        get_low_stock_by_category,
        get_top_products_stock
    )
    from inventory_app.services.billing_service import _cached_billing_summary
    from inventory_app.services.auth_service import get_role_requests_by_status_count

    cached = cache_get("dashboard:main")
    if cached:
        try:
            data = json.loads(cached)
        except Exception:
            data = None
        if data:
            data['show_role_requests'] = session.get('role', 'staff') == 'admin'
            return render_template('dashboard/index.html', **data)

    metrics = get_dashboard_metrics()
    chart_data = {
        "stock_by_category": get_stock_by_category(),
        "low_stock_by_category": get_low_stock_by_category(),
        "top_products_stock": get_top_products_stock(),
        "role_requests_by_status": get_role_requests_by_status_count()
    }
    billing = _cached_billing_summary()
    data = {
        "metrics": metrics,
        "chart_data": chart_data,
        "billing": billing,
        "show_role_requests": session.get('role', 'staff') == 'admin'
    }

    cache_set("dashboard:main", json.dumps(data, default=str), ttl=_DASHBOARD_CACHE_TTL)

    return render_template('dashboard/index.html', **data)
