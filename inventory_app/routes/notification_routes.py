from flask import Blueprint, render_template, jsonify
from inventory_app.services.notification_service import get_notifications, get_unread_notifications_count, mark_all_read
from inventory_app.utils.decorators import login_required

notification_bp = Blueprint('notifications', __name__)


@notification_bp.route('/notifications')
@login_required
def list_notifications():
    notes = get_notifications()
    return render_template('notifications/list.html', notifications=notes)


@notification_bp.route('/api/notifications/count')
@login_required
def api_count():
    return jsonify({"count": get_unread_notifications_count()})


@notification_bp.route('/notifications/read-all', methods=['POST'])
@login_required
def api_mark_all_read():
    mark_all_read()
    return jsonify({"ok": True})
