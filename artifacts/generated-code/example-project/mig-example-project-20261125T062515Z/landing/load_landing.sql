-- landing/load_landing.sql  (JDBC source -> landing; full reload; run register_sources.sql first)
-- Source _landed_at is NOT copied; landing _landed_at = load time (risk R5). Order: parents before children.

-- raw_customers
CREATE OR REPLACE TABLE `retail_demo`.`landing`.raw_customers AS
SELECT customer_id, full_name, email, loyalty_tier, signup_date, region, current_timestamp() AS _landed_at
FROM `retail_demo`.`landing`._jdbc_src_customers;

-- raw_products
CREATE OR REPLACE TABLE `retail_demo`.`landing`.raw_products AS
SELECT sku, product_name, category, unit_cost, list_price, is_active, current_timestamp() AS _landed_at
FROM `retail_demo`.`landing`._jdbc_src_products;

-- raw_orders
CREATE OR REPLACE TABLE `retail_demo`.`landing`.raw_orders AS
SELECT order_id, customer_id, store_id, order_timestamp, order_status, payment_method, gross_amount, discount_amount, current_timestamp() AS _landed_at
FROM `retail_demo`.`landing`._jdbc_src_orders;

-- raw_order_items
CREATE OR REPLACE TABLE `retail_demo`.`landing`.raw_order_items AS
SELECT item_id, order_id, sku, quantity, unit_sold_price, current_timestamp() AS _landed_at
FROM `retail_demo`.`landing`._jdbc_src_order_items;
