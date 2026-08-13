from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from inventory_app.services.notification_service import (
    get_notifications, get_unread_notifications_count,
    mark_notification_as_read, mark_all_notifications_as_read
)
from inventory_app.utils.decorators import login_required, csrf_protected

notification_bp = Blueprint('notifications', __name__)

@notification_bp.route('/notifications', methods=['GET'])
@login_required
def list_notifications():
    notifications = get_notifications()
    unread_count = get_unread_notifications_count()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('format') == 'json':
        return jsonify({
            "success": True,
            "unread_count": unread_count,
            "notifications": notifications
        })
    return render_template('notifications/index.html', notifications=notifications, unread_count=unread_count)

@notification_bp.route('/notifications/<notification_id>/read', methods=['POST'])
@login_required
@csrf_protected
def read_notification(notification_id):
    mark_notification_as_read(notification_id)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"success": True})
    return redirect(url_for('notifications.list_notifications'))

@notification_bp.route('/notifications/read-all', methods=['POST'])
@login_required
@csrf_protected
def read_all_notifications():
    count = mark_all_notifications_as_read()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"success": True, "count": count})
    flash(f"Marked {count} notifications as read.", "success")
    return redirect(url_for('notifications.list_notifications'))
