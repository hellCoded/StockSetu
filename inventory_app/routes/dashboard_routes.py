from flask import Blueprint, render_template
from inventory_app.services.inventory_service import get_dashboard_metrics
from inventory_app.services.product_service import (
    get_stock_by_category,
    get_low_stock_by_category,
    get_top_products_stock
)
from inventory_app.services.auth_service import get_role_requests_by_status_count
from inventory_app.utils.decorators import login_required

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    metrics = get_dashboard_metrics()
    chart_data = {
        "stock_by_category": get_stock_by_category(),
        "low_stock_by_category": get_low_stock_by_category(),
        "top_products_stock": get_top_products_stock(),
        "role_requests_by_status": get_role_requests_by_status_count()
    }
    return render_template('dashboard/index.html', metrics=metrics, chart_data=chart_data)
