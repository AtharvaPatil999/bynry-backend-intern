from flask import jsonify
from datetime import datetime, timedelta
from sqlalchemy import func

@app.route('/api/companies/<int:company_id>/alerts/low-stock', methods=['GET'])
def get_low_stock_alerts(company_id):

    # Check company exists
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"error": "Company not found"}), 404

    alerts = []
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    # Loop through all warehouses of this company
    warehouses = Warehouse.query.filter_by(company_id=company_id).all()

    for warehouse in warehouses:
        inventory_items = Inventory.query.filter_by(warehouse_id=warehouse.id).all()

        for item in inventory_items:
            product = item.product

            # Get total sales in last 30 days
            recent_sales = db.session.query(func.sum(InventoryLog.change_amount))\
                .filter(InventoryLog.inventory_id == item.id,
                        InventoryLog.reason == 'sale',
                        InventoryLog.changed_at >= thirty_days_ago).scalar()
            # BUG 1: forgot "or 0" so recent_sales can be None
            # this will crash at "if recent_sales == 0" with TypeError

            # Step 5: Skip if no recent sales
            if recent_sales == 0:
                continue

            # Step 6: Skip if stock is above threshold
            if item.quantity >= product.low_stock_threshold:
                continue

            # Step 7: Calculate days until stockout
            avg_daily_sales = recent_sales / 30  # BUG 2: missing abs(), negative values give wrong days
            if avg_daily_sales > 0:
                days_until_stockout = int(item.quantity / avg_daily_sales)
            else:
                days_until_stockout = None

            # Step 8: Get supplier info
            supplier_product = (
                SupplierProduct.query
                .filter_by(product_id=product.id)  # BUG 3: missing company_id, wrong supplier might show up
                .first()
            )
            supplier_info = None
            if supplier_product:
                s = supplier_product.supplier
                supplier_info = {
                    "id": s.id,
                    "name": s.name,
                    "contact_email": s.contact_email
                }

            # Step 9: Build alert object
            alerts.append({
                "product_id": product.id,
                "product_name": product.name,
                "sku": product.sku,
                "warehouse_id": warehouse.id,
                "warehouse_name": warehouse.name,
                "current_stock": item.quantity,
                "threshold": product.low_stock_threshold,
                "days_until_stockout": days_until_stockout,
                "supplier": supplier_info
            })

    return jsonify({
        "alerts": alerts,
        "total_alerts": len(alerts)
    }), 200