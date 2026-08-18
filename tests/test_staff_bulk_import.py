import io
import pytest
import openpyxl
from werkzeug.datastructures import FileStorage
from inventory_app.services.auth_service import import_staff_bulk, generate_staff_template
from inventory_app.database import get_db


def test_generate_staff_template_xlsx():
    mem, filename, mimetype = generate_staff_template(file_format="xlsx")
    assert filename.endswith(".xlsx")
    assert mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    wb = openpyxl.load_workbook(mem)
    sheet = wb.active
    rows = list(sheet.iter_rows(values_only=True))
    assert rows[0] == ("Name", "Surname", "Username", "Email", "Role", "Password")
    assert len(rows) >= 5


def test_generate_staff_template_csv():
    mem, filename, mimetype = generate_staff_template(file_format="csv")
    assert filename.endswith(".csv")
    assert mimetype == "text/csv"
    content = mem.getvalue().decode("utf-8")
    assert "Name,Surname,Username,Email,Role,Password" in content


def test_import_staff_bulk_csv_success(app):
    with app.app_context():
        csv_data = (
            "Name,Surname,Username,Email,Role,Password\n"
            "Alice,Smith,alicesmith,alice@company.com,staff,Secret123\n"
            "Bob,Jones,,bob@company.com,inventory_manager,Secret123\n"
        )
        file_storage = FileStorage(
            stream=io.BytesIO(csv_data.encode("utf-8")),
            filename="staff_import.csv",
            content_type="text/csv"
        )
        success, msg, details = import_staff_bulk(file_storage, imported_by="testadmin")
        assert success is True
        assert details["imported_count"] == 2
        assert details["role_request_count"] == 1
        
        db = get_db()
        user_alice = db.users.find_one({"email": "alice@company.com"})
        assert user_alice is not None
        assert user_alice["username"] == "alicesmith"
        assert user_alice["role"] == "staff"
        assert user_alice["is_active"] is False
        
        user_bob = db.users.find_one({"email": "bob@company.com"})
        assert user_bob is not None
        # Elevated role is NOT assigned directly during bulk import
        assert user_bob["role"] == "staff"
        assert user_bob["is_active"] is False
        assert user_bob["username"].startswith("bob")

        # A pending role request is sent to admin for approval instead
        req = db.role_requests.find_one({"user_id": str(user_bob["_id"]), "status": "PENDING"})
        assert req is not None
        assert req["requested_role"] == "inventory_manager"
        assert req["current_role"] == "staff"


def test_import_staff_bulk_xlsx_success(app):
    with app.app_context():
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Name", "Surname", "Username", "Email", "Role", "Password"])
        ws.append(["Charlie", "Brown", "cbrown", "charlie@company.com", "staff", ""])
        
        excel_bytes = io.BytesIO()
        wb.save(excel_bytes)
        excel_bytes.seek(0)
        
        file_storage = FileStorage(
            stream=excel_bytes,
            filename="staff.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        success, msg, details = import_staff_bulk(file_storage, default_password="DefaultPass123", imported_by="testadmin")
        assert success is True
        assert details["imported_count"] == 1
        
        db = get_db()
        user = db.users.find_one({"email": "charlie@company.com"})
        assert user is not None
        assert user["name"] == "Charlie Brown"


def test_import_staff_bulk_skip_duplicate_and_invalid(app):
    with app.app_context():
        csv_data = (
            "Name,Surname,Username,Email,Role,Password\n"
            "AdminUser,Dup,testadmin,admin@test.com,staff,Staff123\n" # Existing email & username in seeded db
            "InvalidEmail,User,inv,notanemail,staff,Staff123\n"      # Invalid email
            "David,Valid,davidv,david@company.com,staff,Staff123\n"  # Valid
        )
        file_storage = FileStorage(
            stream=io.BytesIO(csv_data.encode("utf-8")),
            filename="mixed.csv",
            content_type="text/csv"
        )
        success, msg, details = import_staff_bulk(file_storage, imported_by="testadmin")
        assert success is True
        assert details["imported_count"] == 1
        assert details["skipped_count"] == 2


def test_bulk_import_route_admin(admin_client):
    csv_data = (
        "Name,Surname,Username,Email,Role,Password\n"
        "Elena,Rostova,erostova,elena@company.com,staff,ElenaPass123\n"
    )
    data = {
        "staff_file": (io.BytesIO(csv_data.encode("utf-8")), "staff.csv"),
        "default_password": "Staff@123"
    }
    resp = admin_client.post("/users/bulk-import", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Successfully imported 1 staff member" in resp.data


def test_download_template_route(admin_client):
    resp = admin_client.get("/users/template?format=xlsx")
    assert resp.status_code == 200
    assert resp.headers["Content-Disposition"].startswith("attachment;")
    assert "StockSetu_Staff_Import_Template.xlsx" in resp.headers["Content-Disposition"]


def test_bulk_import_route_unauthorized(staff_client):
    resp = staff_client.post("/users/bulk-import", data={}, follow_redirects=True)
    assert b"Forbidden" in resp.data or resp.status_code == 403

