import os
import csv
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sample_import_files')
os.makedirs(SAMPLE_DIR, exist_ok=True)

# 1. Staff Import Files
staff_headers = ["Employee ID", "Full Name", "Phone No", "Email"]
staff_rows = [
    ["EMP-1001", "Rajesh Kumar", "9876543210", "rajesh.kumar@stocksetu.com"],
    ["EMP-1002", "Priya Sharma", "9876543211", "priya.sharma@stocksetu.com"],
    ["EMP-1003", "Amit Patel", "9876543212", "amit.patel@stocksetu.com"],
    ["EMP-1004", "Sneha Verma", "9876543213", "sneha.verma@stocksetu.com"],
    ["EMP-1005", "Vikram Singh", "9876543214", "vikram.singh@stocksetu.com"],
]

# CSV Staff
staff_csv_path = os.path.join(SAMPLE_DIR, "staff_bulk_import_sample.csv")
with open(staff_csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(staff_headers)
    writer.writerows(staff_rows)

# XLSX Staff
staff_xlsx_path = os.path.join(SAMPLE_DIR, "staff_bulk_import_sample.xlsx")
wb_staff = openpyxl.Workbook()
ws_staff = wb_staff.active
ws_staff.title = "Staff Import"
ws_staff.append(staff_headers)

header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
thin_border = Border(
    left=Side(style='thin', color='CBD5E1'),
    right=Side(style='thin', color='CBD5E1'),
    top=Side(style='thin', color='CBD5E1'),
    bottom=Side(style='thin', color='CBD5E1')
)

for col_num, cell in enumerate(ws_staff[1], 1):
    cell.fill = header_fill
    cell.font = header_font
    cell.alignment = Alignment(horizontal="center", vertical="center")

for row in staff_rows:
    ws_staff.append(row)

for row in ws_staff.iter_rows(min_row=2, max_row=len(staff_rows)+1, min_col=1, max_col=4):
    for cell in row:
        cell.border = thin_border
        cell.alignment = Alignment(vertical="center")

ws_staff.column_dimensions['A'].width = 16
ws_staff.column_dimensions['B'].width = 22
ws_staff.column_dimensions['C'].width = 16
ws_staff.column_dimensions['D'].width = 30
wb_staff.save(staff_xlsx_path)


# 2. Product Import / Supplier Bill Files
prod_headers = ["Item Name", "Quantity", "Unit", "Price", "GST Rate (%)", "HSN Code", "Category", "Description"]
prod_rows = [
    ["UltraTech Cement 50kg", 100, "bags", 380.00, 28, "2523", "Cement", "Portland Pozzolana Cement grade 53"],
    ["Tata Tiscon 12mm TMT Bar", 50, "pcs", 620.50, 18, "7214", "Building Materials", "High strength thermo-mechanically treated bar"],
    ["Havells 2.5 sq mm Copper Wire", 25, "rolls", 1450.00, 18, "8544", "Electrical", "Flame retardant 90m insulated copper wire"],
    ["Supreme 1 Inch PVC Pipe (3m)", 80, "pcs", 210.00, 18, "3917", "Plumbing", "Heavy duty pressure plumbing pipe"],
    ["Asian Paints Apex Ultima White (20L)", 15, "liters", 4200.00, 18, "3209", "Paints & Chemicals", "Exterior weather proof emulsion paint"],
    ["Bosch 13mm Impact Drill Machine", 10, "pcs", 2850.00, 18, "8467", "Tools & Equipment", "550W professional corded hammer drill"],
]

# CSV Products
prod_csv_path = os.path.join(SAMPLE_DIR, "products_stock_in_sample.csv")
with open(prod_csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(prod_headers)
    writer.writerows(prod_rows)

# XLSX Products
prod_xlsx_path = os.path.join(SAMPLE_DIR, "products_stock_in_sample.xlsx")
wb_prod = openpyxl.Workbook()
ws_prod = wb_prod.active
ws_prod.title = "Products Stock-In"
ws_prod.append(prod_headers)

header_fill_prod = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
for col_num, cell in enumerate(ws_prod[1], 1):
    cell.fill = header_fill_prod
    cell.font = header_font
    cell.alignment = Alignment(horizontal="center", vertical="center")

for row in prod_rows:
    ws_prod.append(row)

for row in ws_prod.iter_rows(min_row=2, max_row=len(prod_rows)+1, min_col=1, max_col=len(prod_headers)):
    for cell in row:
        cell.border = thin_border
        cell.alignment = Alignment(vertical="center")

ws_prod.column_dimensions['A'].width = 38
ws_prod.column_dimensions['B'].width = 12
ws_prod.column_dimensions['C'].width = 10
ws_prod.column_dimensions['D'].width = 14
ws_prod.column_dimensions['E'].width = 14
ws_prod.column_dimensions['F'].width = 14
ws_prod.column_dimensions['G'].width = 22
ws_prod.column_dimensions['H'].width = 45
wb_prod.save(prod_xlsx_path)

print(f"Created sample files in: {SAMPLE_DIR}")
