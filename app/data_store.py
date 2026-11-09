from pathlib import Path
from typing import Any

from openpyxl import load_workbook


class CustomerData:
    """Read the three Excel worksheets into ID-keyed in-memory records."""

    def __init__(self, workbook_path: str):
        path = Path(workbook_path)
        if not path.exists():
            raise FileNotFoundError(f"Customer workbook not found: {path}")
        workbook = load_workbook(path, data_only=True, read_only=True)
        self.customers = self._sheet(workbook, "Customers")
        self.orders = self._sheet(workbook, "Orders")
        self.products = self._sheet(workbook, "Products")
        self.orders_by_id = {row["OrderID"]: row for row in self.orders if row.get("OrderID")}
        self.customers_by_id = {row["CustomerID"]: row for row in self.customers if row.get("CustomerID")}
        self.products_by_id = {row["ProductID"]: row for row in self.products if row.get("ProductID")}

    @staticmethod
    def _sheet(workbook: Any, name: str) -> list[dict[str, Any]]:
        if name not in workbook.sheetnames:
            raise ValueError(f"Workbook is missing required worksheet: {name}")
        sheet = workbook[name]
        rows = sheet.iter_rows(values_only=True)
        headers = [str(value).strip() if value is not None else "" for value in next(rows)]
        return [
            {key: value for key, value in zip(headers, row) if key}
            for row in rows if any(value is not None for value in row)
        ]

    def customer(self, customer_id: str) -> dict[str, Any] | None:
        return self.customers_by_id.get(customer_id.upper())

    def orders_for_customer(self, customer_id: str) -> list[dict[str, Any]]:
        return [row for row in self.orders if str(row.get("CustomerID", "")).upper() == customer_id.upper()]

    def order(self, order_id: str) -> dict[str, Any] | None:
        return self.orders_by_id.get(order_id.upper())

    def product(self, product_id: str) -> dict[str, Any] | None:
        return self.products_by_id.get(product_id.upper())

    def customer_orders_with_details(self, customer_id: str) -> list[dict[str, Any]]:
        records = []
        for order in self.orders_for_customer(customer_id):
            record = dict(order)
            record["Product"] = self.product(str(order.get("ProductID", "")))
            records.append(record)
        return records
