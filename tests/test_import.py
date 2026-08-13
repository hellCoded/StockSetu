import io
import pytest
from openpyxl import Workbook
from inventory_app.services.import_service import parse_supplier_bill


class FakeFileStorage:
    """Minimal mock for werkzeug FileStorage."""
    def __init__(self, data: bytes, filename: str):
        self._data = data
        self.filename = filename
        self._pos = 0

    def read(self):
        return self._data

    def seek(self, pos):
        self._pos = pos


def _make_excel(items: list[tuple]) -> bytes:
    """Creates an in-memory .xlsx with columns: Item, Qty."""
    wb = Workbook()
    ws = wb.active
    ws.append(["Item", "Qty"])
    for name, qty in items:
        ws.append([name, qty])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_excel_basic():
    data = _make_excel([("Steel Bolts", 100), ("Copper Wire", 50)])
    fs = FakeFileStorage(data, "bill.xlsx")
    ok, err, items = parse_supplier_bill(fs)
    assert ok is True
    assert err == ""
    assert len(items) == 2
    assert items[0]["item_name"] == "Steel Bolts"
    assert items[0]["quantity"] == 100.0
    assert items[1]["item_name"] == "Copper Wire"
    assert items[1]["quantity"] == 50.0


def test_parse_excel_with_unit_suffix():
    data = _make_excel([("Bolts M10", "200 PCS"), ("Washer", "500 NOS")])
    fs = FakeFileStorage(data, "bill.xlsx")
    ok, err, items = parse_supplier_bill(fs)
    assert ok is True
    assert items[0]["quantity"] == 200.0
    assert items[1]["quantity"] == 500.0


def test_parse_excel_empty():
    data = _make_excel([])
    fs = FakeFileStorage(data, "bill.xlsx")
    ok, err, items = parse_supplier_bill(fs)
    assert ok is False
    assert "No valid items" in err


def test_parse_unsupported_format():
    fs = FakeFileStorage(b"dummy", "bill.txt")
    ok, err, items = parse_supplier_bill(fs)
    assert ok is False
    assert "Unsupported file type" in err


def test_parse_excel_skips_empty_rows():
    data = _make_excel([("Item A", 10), ("", 0), ("Item B", 20)])
    fs = FakeFileStorage(data, "bill.xlsx")
    ok, err, items = parse_supplier_bill(fs)
    assert ok is True
    assert len(items) == 2


def test_parse_excel_mixed_complete_and_incomplete():
    """Rows with metadata, some complete (unit+hsn) and some incomplete (missing fields)."""
    wb = Workbook()
    ws = wb.active
    ws.append(["SUPPLIER INVOICE - MIXED"])
    ws.append(["Invoice #: BM-1", "Date: 2026-08-13"])
    ws.append(["", "", "", ""])
    ws.append(["Item Description", "Quantity", "Unit", "HSN Code"])
    ws.append(["Steel Bolts M10", "500", "PCS", "7318"])   # complete
    ws.append(["Junction Box IP54", "120", "", ""])         # missing unit + hsn
    ws.append(["Cable Tray 300mm", "60", "MTR", ""])        # missing hsn
    buf = io.BytesIO()
    wb.save(buf)

    fs = FakeFileStorage(buf.getvalue(), "mixed_bill.xlsx")
    ok, err, items = parse_supplier_bill(fs)
    assert ok is True
    assert len(items) == 3

    assert items[0] == {"item_name": "Steel Bolts M10", "quantity": 500.0, "unit": "PCS", "hsn_code": "7318"}
    assert items[1] == {"item_name": "Junction Box IP54", "quantity": 120.0, "unit": "", "hsn_code": ""}
    assert items[2] == {"item_name": "Cable Tray 300mm", "quantity": 60.0, "unit": "MTR", "hsn_code": ""}
