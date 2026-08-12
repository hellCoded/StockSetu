# User Roles & Permissions Guide

This guide explains the user roles, access levels, and permissions available in the Inventory Management System.

---

## 1. Role Overview

The system includes three user access levels:

1. **Administrator (`admin`)**: Full system access. Manages users, changes user roles, renames products, and performs all inventory operations.
2. **Inventory Manager (`inventory_manager`)**: Manages the product catalog. Adds new products, edits product details, performs stock count adjustments, and processes stock movements.
3. **Staff (`staff`)**: Warehouse floor access. Looks up products, checks stock levels, and records daily stock-in and stock-out entries.

---

## 2. Permissions Table

| Feature / Action | Administrator | Inventory Manager | Staff |
| :--- | :---: | :---: | :---: |
| **Log In & Log Out** | ✅ | ✅ | ✅ |
| **View Dashboard & Alerts** | ✅ | ✅ | ✅ |
| **Search & View Products** | ✅ | ✅ | ✅ |
| **View Transaction History** | ✅ | ✅ | ✅ |
| **Record Stock In** | ✅ | ✅ | ✅ |
| **Record Stock Out** | ✅ | ✅ | ✅ |
| **Add New Product** | ✅ | ✅ | ❌ |
| **Edit Product Details** | ✅ | ✅ | ❌ |
| **Activate / Deactivate Product** | ✅ | ✅ | ❌ |
| **Adjust Stock Count** | ✅ | ✅ | ❌ |
| **Rename Product** | ✅ | ❌ | ❌ |
| **Manage Users & Roles** | ✅ | ❌ | ❌ |
| **Activate / Deactivate Users** | ✅ | ❌ | ❌ |
| **Change Own Password** | ✅ | ✅ | ✅ |

---

## 3. Role Details

### 👑 Administrator (`admin`)
* **Overview**: Responsible for system administration and overall inventory oversight.
* **Allowed Actions**:
  - Manage users: View registered users, change assigned roles, and activate or deactivate accounts.
  - Rename products: Update product names safely without losing transaction history.
  - Perform all inventory manager and staff actions.

---

### 📦 Inventory Manager (`inventory_manager`)
* **Overview**: Responsible for maintaining the product catalog and physical stock accuracy.
* **Allowed Actions**:
  - Add new products with initial quantity, prices (₹), categories, and warehouse locations.
  - Edit product information (price, category, location, minimum stock level).
  - Activate or deactivate products.
  - Adjust stock counts to match physical inventory audits (requires an audit reason).
  - Process daily stock-in and stock-out entries.
* **Restricted Actions**:
  - Cannot manage user accounts or roles.
  - Cannot rename product names.

---

### 👷 Staff Member (`staff`)
* **Overview**: Responsible for daily warehouse receiving and order fulfillment.
* **Allowed Actions**:
  - Search and view product details, stock levels, and transaction logs.
  - Record incoming stock (`Stock In`).
  - Record outgoing stock (`Stock Out`). The system automatically prevents negative stock.
  - View the main dashboard and inventory alerts.
  - Change personal account password.
  - Submit a formal promotion request to Administrator to upgrade account role to **Inventory Manager**.
* **Restricted Actions**:
  - Cannot add, edit, or rename products.
  - Cannot perform manual stock adjustments.
  - Cannot activate or deactivate products.
  - Cannot manage users.

---

## 4. System Protection & Security

- **Server Enforcement**: All permissions are checked on the server before any action is completed, ensuring users can only perform tasks allowed by their role.
- **Stock Safeguards**: The system automatically verifies available quantities before processing stock removals to prevent negative inventory.
- **Audit Logging**: Important actions such as stock changes, adjustments, and product updates are automatically recorded in the history log.
