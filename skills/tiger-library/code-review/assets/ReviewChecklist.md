# Notebook Standards and Coding Guidelines

## 1. Notebook Structure and Organization

### 1.1 Naming and Folder Structure
- **Notebook Naming Convention**: `NB_<Sector>_<Functionality>_<Purpose>.py`
  - Example: `NB_BR_InnerNetworkMoves_LoadsShippedTravelledTransport.py`
- **Folder Structure**: `/Project/Sector/Market/`

### 1.2 Header Block Requirements
Each notebook must have a header block containing:
- High-level description explaining the module's purpose, table names, silver database, etc.
- Original creator
- Creation date
- Serial number of changes, ADO Story/Bug number and change history (with dates and person who performed the change)
- Defect correction explanation (if applicable)
- Gold Table Names Loaded: Comma-separated list of tables loaded by the notebook
- Source and Targets
- Merge Criteria: Upsert/SCD/Append/Delete-Insert
- SystemId and ReportingID information
- STTM Links

## 2. Audit Framework

Implement audit framework for each step:
- Call `log_audit_data()` at:
  - Start of each data load (Status Code: "I")
  - Successful completion (Status Code: "S")
  - Failure/error (Status Code: "F")
- For successful data loads, include the inserted record count

## 3. Data Quality Framework

Implement Data Quality (DQ) framework in notebooks:
- `product_name` should be 'CTX'
- `SectorName` should be one of: 'PBNA', 'PFNA', 'LATAM', 'Europe', 'AMESA', 'APAC'
- `MarketName` should have full description of the Market (no 2-character country codes)
- Preload DQ Flag should check for blocking rules
- **DataAsset Naming Convention**: `<Program>_<Market>_<BLK/TRNS/RECN>_<Table/KPI>`

## 4. Notebook Guidelines

- No `display()` commands in notebooks
- Output run statistics to Log Analytics (Audit) and Delta table
- Avoid Pandas DataFrame when possible; use Spark DataFrame instead
- Use error handling with try/catch blocks
  - Catch should call audit common logging module
  - Log errors to Log Analytics table "NoteBookAuditLog_CL"
  - Propagate exceptions to the calling layer

## 5. Parameters

- Pass all parameters from table, no hardcoding
- Avoid unused parameters
- Follow parameter naming standards in `audit_parameter_standard.py`
- Mandatory parameters for each notebook:
  - `PL_Name`
  - `env`
  - `nb_path`
  - `no_of_periods_to_load`
  - `source_catalog_name`
  - `source_schema_name`
  - `source_table_name`
  - `product_name`
  - `SectorName`
  - `MarketName`
  - `dq_subject_area`
  - `dq_category`
  - `dq_subcategory`
  - `dq_dataset_layer`
  - `dq_dataset_name`
  - `dq_blocking_dataset_name`
  - `dq_dataset_unique_keys`
  - `target_catalog_name`
  - `target_schema_name`
  - `target_table_name`
  - `type_of_load`
  - `dq_flag`

## 6. Data Source & Handling

- Use Unity Catalog tables for all source and target tables (no hive metastore)
- Mandatory data partitioning:
  - Partition size should be approximately 1GB
  - Partitioning not needed if dataset is less than 1GB
  - For larger datasets, partition on lower cardinality columns
  - Example: 5GB data should have 5 partitions
- Avoid data shuffling and use broadcast joins where applicable

## 7. Code Quality & Organization

### 7.1 General Guidelines
- Avoid mutual references between assemblies
- Keep files under 500 lines (excluding machine-generated code)
- Keep methods under 200 lines
- Limit method arguments to 5 or fewer (use structures for multiple arguments)
- Maximum line length: 120 characters
- Avoid UDFs
- Follow PEP8 standards (flake8 should pass)

### 7.2 Code Structure
- Group definitions and declarations into distinct sections with comment headers
- Each section of comments should use markdown language for headers
- Code should be clean, well-organized, efficient, and properly indented
- Thoroughly unit test code before merging to main branch

### 7.3 Coding Practices
- Avoid print statements; use logging modules
- Ensure code reusability (use existing components instead of creating redundant functions)
- When using recursive functions with Spark, include appropriate break statements
- Store sensitive information in secure vault and reference via keys
- Assign SQL statements to variables before using in Spark SQL API
- Avoid read serializable
- Avoid converting DataFrame to RDD
- Remove unused code (imports, variables, code sections)
- Use "Format SQL" and "Format Python" options for formatting cells

## 8. Naming Conventions

### 8.1 Python Naming Standards
- **Function**: Lowercase with underscores
  - Example: `function`, `my_function`
- **Variable**: Lowercase with underscores
  - Example: `x`, `var`, `my_variable`
- **Class**: CamelCase/PascalCase
  - Example: `Model`, `MyClass`
- **Method**: Lowercase with underscores
  - Example: `class_method`, `method`
- **Constant**: Uppercase with underscores
  - Example: `CONSTANT`, `MY_CONSTANT`

### 8.2 Variable & Function Best Practices
- Use meaningful variable and function names
- Avoid single-letter variables (except in loops)
- Include proper documentation for functions explaining purpose and arguments
- When creating DataFrames, select only specific required columns
- Use `select()` instead of multiple `withColumn()` calls to derive columns

## 9. Additional Requirements

- No hardcoding of SystemId and ReportingUnitId in queries or notebooks
- Every declared variable must be used
- Use logging instead of print statements (logging.info() or logging.debug())
- Include docstrings for all functions and classes using triple quotes

## 10. Security Best Practices

### 10.1 Credential & Secret Management ⚠️ CRITICAL
- **PROHIBIT hardcoded credentials** in any form (passwords, connection strings, API keys)
- **REQUIRE `dbutils.secrets.get()`** for all sensitive values
- **Validate secret scope naming** follows convention: `{env}-{system}-secrets`
- **Check for secrets in comments** or docstrings
- **Flag Base64-encoded strings** that might hide credentials
- **Example violation**: `password = "MyP@ssw0rd"`
- **Correct approach**: `password = dbutils.secrets.get(scope="key-vault", key="db-password")`

### 10.2 Secrets in Output/Logs ⚠️ CRITICAL
- **PROHIBIT secrets in logging statements** or print statements
- **Require masking in error messages**: `logging.info(f"Password: {'*' * 8}")`
- **Check for secrets in DataFrame display** (even in commented-out code)
- **Validate exception handling** doesn't expose connection strings
- **Flag variables with suspicious names**: `pwd`, `password`, `token`, `key`, `secret`

### 10.3 SQL Injection Prevention ⚠️ CRITICAL
- **PROHIBIT f-strings with external inputs** in `spark.sql()` calls
- **Flag `.format()` or `%` string formatting** in SQL statements
- **REQUIRE parameterized queries** or DataFrame API for dynamic filters
- **Validate all widget inputs** against allowed values before using in queries
- **Example violation**: `spark.sql(f"SELECT * FROM table WHERE id = '{user_input}'")`
- **Correct approach**: `df.filter(col("id") == user_input)` or whitelist validation

### 10.4 PII/Sensitive Data Handling
- **REQUIRE PII masking/hashing** before logging or displaying
- **Check for PII in exception messages** (email, SSN, credit card, health data)
- **Verify column-level encryption** for sensitive columns
- **Flag PII columns in test data** (should use synthetic data)
- **Require data classification tags** in header documentation for tables with PII
- **Validate GDPR/CCPA compliance** markers for regulated data

### 10.5 Dynamic Code Execution Risks ⚠️ CRITICAL
- **PROHIBIT `eval()` and `exec()`** - code injection risk
- **Flag `__import__()` with dynamic module names**
- **Check for `pickle.loads()` on untrusted data** (deserialization attack)
- **Validate `compile()` usage with user-controlled input**

### 10.6 Data Access Control & Authorization
- **Verify Unity Catalog three-part naming**: `catalog.schema.table` (not shorthand)
- **Check for `USE CATALOG` or `USE SCHEMA` commands** (bypass Unity Catalog governance)
- **Flag direct file path access** (bypasses Unity Catalog ACLs):
  - ❌ `spark.read.parquet("/mnt/raw/sensitive_data/")`
  - ✅ `spark.table("catalog.schema.sensitive_data")`
- **Validate service principal permissions** are documented

### 10.7 Network Security & Connection Encryption
- **REQUIRE SSL/TLS for external connections** (JDBC, REST APIs)
- **Check JDBC connection strings for**:
  - `encrypt=true`
  - `ssl=true`
  - `sslmode=require` (PostgreSQL)
- **Flag HTTP connections** (should be HTTPS)
- **Validate private endpoint usage** for Azure services

### 10.8 Data Exfiltration Prevention
- **Validate write destinations** are within approved Unity Catalog or storage accounts
- **Flag `.coalesce(1)` writes** to external locations (entire dataset in one file)
- **Check for COPY INTO commands** to external stages
- **Require audit logging** for all data exports

### 10.9 Token & Session Management
- **PROHIBIT hardcoded tokens**: Azure SAS tokens, OAuth tokens, API keys
- **Verify token expiration handling** and refresh logic
- **Check for token storage in variables** that could be printed/logged

### 10.10 Input Validation & Sanitization
- **REQUIRE whitelist validation** for all widget inputs
- **Validate numeric ranges** for period/date inputs
- **Check path traversal prevention**:
  - ❌ `path = f"/dbfs/reports/{user_input}"` (Could be `../../../etc/passwd`)
  - ✅ `path = f"/dbfs/reports/{os.path.basename(user_input)}"`
- **Sanitize special characters** in user inputs

### 10.11 Encryption at Rest & Transit
- **Verify Delta tables use encryption** (default in Unity Catalog)
- **Check for unencrypted writes** to external storage
- **Flag temporary file writes** to unencrypted locations

### 10.12 Least Privilege Principle
- **Validate cluster policies** enforce minimum required permissions
- **Require documentation of required permissions** in notebook header
- **Flag wildcard permissions requests**: `GRANT SELECT ON CATALOG.*.*`

### 10.13 Dependency & Library Security
- **Require approved library list** (centrally maintained)
- **Prohibit pip install from untrusted repos**: `%pip install some-unknown-package`
- **Validate library versions** against known CVEs
- **Check for malicious package names** (typosquatting)

## 11. PySpark Performance Optimization

### 11.1 DataFrame Caching & Persistence Strategy
- **Check for appropriate `.cache()` or `.persist()` usage** when DataFrames are reused multiple times
- **Verify `.unpersist()` calls** to release memory after cached DataFrames no longer needed
- **Flag unnecessary caching** of DataFrames used only once (wastes memory)
- **Validate storage levels**: Use `MEMORY_AND_DISK` for large DataFrames, `MEMORY_ONLY` for small
- **Example**: Caching a DataFrame used only in one action is wasteful

### 11.2 Partition Management & Skew Handling
- **Check for `coalesce()` before writing** small result sets (avoid thousands of tiny files)
- **Verify `repartition()` usage** for evenly distributing data before expensive operations
- **Flag missing salting techniques** for join/groupBy on skewed keys
- **Validate partition count**: Should match cluster cores (e.g., 200 partitions for 100 cores)
- **Example violation**: Writing 10 MB DataFrame with default 200 partitions → creates 200 tiny files

### 11.3 Predicate Pushdown & Filter Ordering
- **Verify filters are applied BEFORE joins/aggregations** (not after)
- **Check partition column filtering** in WHERE clauses for Delta tables
- **Flag `SELECT *` followed by `.filter()`** instead of filtered subquery
- **Validate Z-ORDER column usage** in filters (if table uses Z-ordering)
- **Example**: Filtering after join wastes computation on unnecessary data

### 11.4 Broadcast Join Thresholds
- **Verify broadcast hint usage** for joins with tables < 10 MB: `df1.join(broadcast(df2), "key")`
- **Flag missing broadcast** when joining to dimension tables (< 10 MB)
- **Check `spark.sql.autoBroadcastJoinThreshold`** configuration (default 10 MB)
- **Validate against OOM**: Tables > 2 GB should never be broadcasted
- **Example violation**: Sort-merge join on 5 MB lookup table (should be broadcast)

### 11.5 Column Pruning Early
- **Flag reading full table then selecting columns**: Should use SQL projection in read
- **Verify minimal column selection BEFORE joins** (not after)
- **Check for nested column access** in Parquet: `select("address.city")` instead of `select("address")`
- **Example violation**: Reading 100 columns, joining, then selecting 5 needed columns

### 11.6 Window Function Optimization
- **Verify `partitionBy()` is always specified** in window functions (never unbounded)
- **Check for redundant window specs** defined multiple times
- **Flag nested window functions** that could be combined
- **Validate row range bounds** (e.g., `rowsBetween(-7, 0)` instead of unbounded)
- **Example**: `Window.orderBy("date")` without partitionBy → single partition shuffle

### 11.7 Delta Lake MERGE Optimization
- **Verify MERGE operations use indexed columns** (partition keys, Z-ORDER columns)
- **Check for `OPTIMIZE` and `VACUUM` command scheduling** for incremental loads
- **Flag missing Delta metadata columns** in merge keys
- **Require partition pruning in MERGE conditions**: `WHEN MATCHED AND date >= '2025-01-01'`
- **Validate MERGE key selectivity** (avoid low cardinality merge keys)

### 11.8 Explode & Lateral View Optimization
- **Flag multiple sequential `explode()` calls** → should use `explode_outer()` or single explode
- **Check cardinality estimation** before exploding nested arrays
- **Verify `explode()` is after filters** (not before)
- **Example violation**: Exploding array of 1000 items then filtering → filter array first

### 11.9 Shuffle & Sort Operations
- **Count and flag excessive shuffles** (use `df.explain()` or Spark UI)
- **Check for `repartition()` + `sort()` combination** → use `repartition(n, "col")` instead
- **Verify `sortWithinPartitions()` over `sort()`** when global order not needed
- **Flag `distinct()` before aggregations** → use `approxCountDistinct()` if exact count not needed

### 11.10 Null Handling in Joins
- **Verify null-safe equality** in joins: `df1.join(df2, df1["key"] <=> df2["key"])`
- **Check for `.na.drop()` before joins** to avoid unintended Cartesian products
- **Flag missing COALESCE** in join keys with nullable columns
- **Example**: Joining on nullable foreign keys without null handling

### 11.11 Unnecessary Actions
- **Flag `.count()` in production** when only existence check needed → use `.limit(1)` instead
- **Prohibit `.collect()` on large DataFrames** (> 1 GB)
- **Check for `.toPandas()`** without row limits → should use `.limit().toPandas()`
- **Validate iterative `.collect()` in loops** → rewrite as Spark operations

### 11.12 Schema Evolution & Enforcement
- **Verify schema enforcement** in Delta writes: `mergeSchema=False` unless intentional
- **Check for explicit schema definition** on reads from external sources
- **Flag implicit type casting** in joins/transforms
- **Require schema validation** before MERGE operations

### 11.13 Aggregation Optimization
- **Check for aggregations before joins** when possible (reduces data volume)
- **Verify use of approximate aggregations** when exact values not needed: `approx_count_distinct()`
- **Flag multiple aggregation passes** that could be combined
- **Validate group by key cardinality** (high cardinality causes skew)

### 11.14 Resource Configuration Validation
- **Check for hardcoded Spark configs** in notebooks (should be parameterized)
- **Verify `spark.sql.shuffle.partitions`** is tuned per job (not default 200)
- **Flag missing `maxRecordsPerFile` setting** for large writes
- **Validate executor memory settings** match data volume

### 11.15 Read Optimization
- **Verify partition column filtering** in read operations for partitioned tables
- **Check for `.option("mergeSchema", "false")`** to avoid expensive schema inference
- **Flag reading entire table for small sample** → use `.sample()` or `.limit()`
- **Validate use of columnar formats** (Parquet/Delta) instead of CSV for large data
