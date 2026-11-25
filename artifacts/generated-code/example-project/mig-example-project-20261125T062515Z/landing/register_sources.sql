-- landing/register_sources.sql  (Postgres source -> JDBC source tables; metadata only, no data moves)
-- PLACEHOLDERS to replace before a real run: <DB_KIT_PG_HOST>, <DB_KIT_PG_DATABASE> (from the DB_KIT_PG_* env var names),
-- secret scope 'db-kit-demo' and keys 'jdbc-user' / 'jdbc-password'. Credentials only via secret(); never literals.
-- Mapping: source-to-target-mapping.yaml `landing:` section.

-- raw_customers
CREATE TABLE IF NOT EXISTS `retail_demo`.`landing`._jdbc_src_customers
USING JDBC
OPTIONS (
  url 'jdbc:postgresql://<DB_KIT_PG_HOST>:5432/<DB_KIT_PG_DATABASE>?sslmode=require',
  dbtable 'raw_dump.raw_customers',
  user secret('db-kit-demo', 'jdbc-user'), password secret('db-kit-demo', 'jdbc-password')
);

-- raw_products
CREATE TABLE IF NOT EXISTS `retail_demo`.`landing`._jdbc_src_products
USING JDBC
OPTIONS (
  url 'jdbc:postgresql://<DB_KIT_PG_HOST>:5432/<DB_KIT_PG_DATABASE>?sslmode=require',
  dbtable 'raw_dump.raw_products',
  user secret('db-kit-demo', 'jdbc-user'), password secret('db-kit-demo', 'jdbc-password')
);

-- raw_orders
CREATE TABLE IF NOT EXISTS `retail_demo`.`landing`._jdbc_src_orders
USING JDBC
OPTIONS (
  url 'jdbc:postgresql://<DB_KIT_PG_HOST>:5432/<DB_KIT_PG_DATABASE>?sslmode=require',
  dbtable 'raw_dump.raw_orders',
  user secret('db-kit-demo', 'jdbc-user'), password secret('db-kit-demo', 'jdbc-password')
);

-- raw_order_items
CREATE TABLE IF NOT EXISTS `retail_demo`.`landing`._jdbc_src_order_items
USING JDBC
OPTIONS (
  url 'jdbc:postgresql://<DB_KIT_PG_HOST>:5432/<DB_KIT_PG_DATABASE>?sslmode=require',
  dbtable 'raw_dump.raw_order_items',
  user secret('db-kit-demo', 'jdbc-user'), password secret('db-kit-demo', 'jdbc-password')
);
