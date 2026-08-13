import io
import re
import openpyxl
import pdfplumber


def parse_supplier_bill(file_storage) -> tuple[bool, str, list[dict]]:
    """
    Parses a supplier bill file (PDF or Excel) and extracts line items.
    Returns (success, error_message, items) where each item is:
        {"item_name": str, "quantity": float}
    """
    filename = (file_storage.filename or "").lower()
    file_bytes = file_storage.read()
    file_storage.seek(0)

    if filename.endswith('.pdf'):
        return _parse_pdf(file_bytes)
    elif filename.endswith(('.xlsx', '.xls')):
        return _parse_excel(file_bytes)
    else:
        return False, "Unsupported file type. Please upload a PDF or Excel (.xlsx) file.", []


def _parse_pdf(file_bytes: bytes) -> tuple[bool, str, list[dict]]:
    """Extracts item name + quantity from a PDF using pdfplumber table detection."""
    items = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    header_idx, name_idx, qty_idx, unit_idx, hsn_idx = _find_header_and_columns(table)
                    if name_idx is None or qty_idx is None:
                        continue
                    for row in table[header_idx + 1:]:
                        if not row or len(row) <= max(name_idx, qty_idx):
                            continue
                        item_name = _clean_text(row[name_idx])
                        qty_raw = _clean_text(row[qty_idx])
                        if not item_name or not qty_raw:
                            continue
                        qty = _parse_quantity(qty_raw)
                        if qty is not None and qty > 0:
                            item = {"item_name": item_name, "quantity": qty}
                            if unit_idx is not None and len(row) > unit_idx:
                                item["unit"] = _clean_text(row[unit_idx])
                            if hsn_idx is not None and len(row) > hsn_idx:
                                item["hsn_code"] = _clean_text(row[hsn_idx])
                            items.append(item)
    except Exception as e:
        return False, f"Failed to parse PDF: {str(e)}", []

    if not items:
        return False, "No valid items found in the PDF. Ensure the bill has a table with product names and quantities.", []
    return True, "", items


def _parse_excel(file_bytes: bytes) -> tuple[bool, str, list[dict]]:
    """Extracts item name + quantity from an Excel workbook."""
    items = []
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        for sheet in wb.worksheets:
            rows = list(sheet.iter_rows(values_only=True))
            if len(rows) < 2:
                continue
            header_idx, name_idx, qty_idx, unit_idx, hsn_idx = _find_header_and_columns(rows)
            if name_idx is None or qty_idx is None:
                continue
            for row in rows[header_idx + 1:]:
                if not row or len(row) <= max(name_idx, qty_idx):
                    continue
                item_name = _clean_text(row[name_idx])
                qty_raw = _clean_text(row[qty_idx])
                if not item_name or not qty_raw:
                    continue
                qty = _parse_quantity(qty_raw)
                if qty is not None and qty > 0:
                    item = {"item_name": item_name, "quantity": qty}
                    if unit_idx is not None and len(row) > unit_idx:
                        item["unit"] = _clean_text(row[unit_idx])
                    if hsn_idx is not None and len(row) > hsn_idx:
                        item["hsn_code"] = _clean_text(row[hsn_idx])
                    items.append(item)
        wb.close()
    except Exception as e:
        return False, f"Failed to parse Excel file: {str(e)}", []

    if not items:
        return False, "No valid items found in the Excel file. Ensure the bill has a table with product names and quantities.", []
    return True, "", items


def _find_header_and_columns(rows: list) -> tuple:
    """
    Scans the first rows to find a header row containing item/quantity keywords.
    Returns (header_row_index, name_idx, qty_idx, unit_idx, hsn_idx) or (-1, None, None, None, None).
    """
    name_keywords = ['item', 'product', 'name', 'description', 'material', 'article', 'goods', 'part', 'component']
    qty_keywords = ['qty', 'quantity', 'nos', 'pcs', 'units', 'count']
    unit_keywords = ['unit', 'uom', 'measure', 'type']
    hsn_keywords = ['hsn', 'hsn code', 'hsncode', 'sac']

    for idx, row in enumerate(rows[:15]):
        if not row:
            continue
        name_idx = None
        qty_idx = None
        unit_idx = None
        hsn_idx = None
        for i, cell in enumerate(row):
            cell_text = _clean_text(cell).lower()
            if not cell_text:
                continue
            if name_idx is None and any(kw in cell_text for kw in name_keywords):
                name_idx = i
            if qty_idx is None and any(kw in cell_text for kw in qty_keywords):
                qty_idx = i
            if unit_idx is None and any(kw in cell_text for kw in unit_keywords):
                unit_idx = i
            if hsn_idx is None and any(kw in cell_text for kw in hsn_keywords):
                hsn_idx = i
        if name_idx is not None and qty_idx is not None:
            return idx, name_idx, qty_idx, unit_idx, hsn_idx

    return -1, None, None, None, None


def _parse_quantity(raw) -> float | None:
    """Parses a quantity value from various formats (e.g., '50', '50.0', '1,200', '50 PCS')."""
    if raw is None:
        return None
    text = str(raw).strip()
    text = re.sub(r'[a-zA-Z]+', '', text).strip()
    text = text.replace(',', '')
    try:
        val = float(text)
        return val if val > 0 else None
    except (ValueError, TypeError):
        return None


def _clean_text(val) -> str:
    """Cleans a cell value to a stripped string."""
    if val is None:
        return ""
    return str(val).strip()
