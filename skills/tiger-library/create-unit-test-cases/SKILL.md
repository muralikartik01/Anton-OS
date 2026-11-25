---
name: create-unit-test-cases
description: Generate unit test notebooks from actual Databricks notebooks using the unit test template.
---

# Unit Test Notebook Generator Skill

## How to Use This Skill

Read the target notebook, auto-generate inline sample DataFrames from its SQL schemas (no ADLS paths needed), then generate the unit test notebook:

### Generate the Unit Test Notebook

**IMPORTANT:** Create the unit test notebook in the `Output/UnitTesting/` folder with the naming convention `test_{actual_notebook_name}.py`.

**Output Location:** `Output/UnitTesting/test_{actual_notebook_name}.py`

Create a new file with:

#### File Format Requirements:
- **Format**: Databricks Python notebook (.py) with magic commands
- **Structure**: Use `# MAGIC %md` for markdown cells and `# COMMAND ----------` for cell separators
- **Naming**: `test_{actual_notebook_name}.py`

#### Template Structure (7 Steps):

1. **Overview Section** - Auto-populate with:
   - Current date
   - Table name
   - Data asset name
   - Version history

2. **Step 1: Create Test Data** - Build inline sample DataFrames and register as global temp views:
```python
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DateType, TimestampType

# Sample data for source table (schema derived from notebook SQL)
sample_schema = StructType([
    StructField("ColA", StringType(), True),
    StructField("ColB", IntegerType(), True),
])
sample_data = [
    ("val1", 100),
    ("val2", 200),
]
df = spark.createDataFrame(sample_data, schema=sample_schema)
df.createOrReplaceGlobalTempView("source_view_name")
```

**Rules for sample data generation:**
- **Parse every transformation before writing a single row.** Read all `SELECT`, `CASE WHEN`, `COALESCE`, `CONCAT`, `CAST`, `WHERE`, `JOIN ON` clauses in the notebook SQL.
- **Design each row to exercise exactly one rule.** If the notebook has 3 `CASE WHEN` branches, create at least one row that hits each branch.
- **Annotate each row with a `# →` comment** showing what the expected output column value will be for that row. Example: `('PCARD-Corporate', ...)  # → CardCategory = 'PCARD'`
- Use `StructType` / `StructField` with correct PySpark types matching the source schema.
- Create 3–5 rows covering: normal case, null/fallback case, boundary value, join-match, and join-miss where applicable.
- Register each DataFrame as a `global_temp` view matching the alias used in the notebook SQL.
- **Zero ADLS.** Never read from `abfss://`, `dbfs:/`, or any external path. All data must come from `spark.createDataFrame(...)` only.

3. **Step 2: Configure Notebook** — Set `IS_UNIT_TEST = "Y"`, `env = "dev"`, generate `job_id`. Follow pattern in `references/Unit_Test_Template.py`.

4. **Step 3: Execute Target Notebook** — `dbutils.notebook.run(main_notebook_path, 0, {config})`. Follow pattern in `references/Unit_Test_Template.py`.

5. **Step 4: Define Unit Tests** - Generate test functions that:
   - **Always query the `_unit_test` Delta table** — the main notebook writes here when `IS_UNIT_TEST="Y"`. Construct the table name as `{GOLD_DB}.{target_tbl}_unit_test` (e.g. `` `dba-agentic-catalog`.agentic_gold.dim_product_unit_test ``). Assign it to a constant `UNIT_TEST_TABLE` at the top of the step.
   - **Do NOT use `global_temp.final_view`** — temp views are slower for repeated test queries; the `_unit_test` persisted Delta table is faster and avoids temp-view scan overhead.
   - Use `spark.table(UNIT_TEST_TABLE)` for full-table scans and `spark.sql(f"SELECT ... FROM {UNIT_TEST_TABLE} WHERE ...")` for filtered queries.
   - Use **computed expected values** traced directly from the sample data in Step 1
   - **Never use TODO placeholders** — every assert must have a known, pre-computed expected value
   - Validate based on actual notebook logic — one test per transformation rule

6. **Step 5: Execute Tests** — iterate `tests` list with try/except, append `(name, "passed"|"failed: ...")` to `test_results`. Follow pattern in `references/Unit_Test_Template.py`.

7. **Step 6: Aggregate & Return Results** — count passed/failed, call `dbutils.notebook.exit(json.dumps({total, passed, failed, details}))`. Follow pattern in `references/Unit_Test_Template.py`.

### Step 4: Generate Test Functions

Based on notebook analysis, create appropriate test functions. **You MUST trace the transformation for every sample row before writing any assert.**

#### Transformation Tracing Reference Table

| Notebook rule type | How to compute the expected value |
|---|---|
| `CASE WHEN x LIKE 'PCARD%' THEN 'PCARD' ELSE 'Non-PCARD'` | Walk through each sample row's input value and apply the CASE logic — write down the output for each row |
| `COALESCE(col_a, col_b, 'UNK')` | For each row: if `col_a` is non-null use it, else if `col_b` is non-null use it, else `'UNK'` |
| `CONCAT(col_a, '\|', col_b)` | Concatenate the literal values from the sample row |
| `CAST(col AS INT) * rate` | Multiply the sample value by the literal rate |
| `YEAR(date_col)` | Extract the year from the sample date literal |
| Hardcoded literal `'Concur'` | Every row gets that exact string |
| JOIN with reference table | Rows that match the join key get the joined column value; rows that don't match get NULL or the COALESCE fallback |

#### ✅ ALWAYS — Computed expected values with row-level trace:
```python
# Assign the _unit_test table once at the top of Step 4 — use f-string with actual catalog/schema/table
UNIT_TEST_TABLE = "`catalog-name`.schema_name.{target_tbl}_unit_test"

# Sample data used (from Step 1):
#   Row 1: card_type='PCARD-Corporate'  → CardCategory = 'PCARD'
#   Row 2: card_type='Out of Pocket'    → CardCategory = 'Non-PCARD'
#   Row 3: card_type=None               → CardCategory = 'Non-PCARD'  (NULL hits ELSE)
def test_card_category_derivation():
    """CASE WHEN card_type LIKE 'PCARD%' THEN 'PCARD' ELSE 'Non-PCARD'"""
    df = spark.sql(f"SELECT CardCategory FROM {UNIT_TEST_TABLE} ORDER BY CardCategory")
    result = [r.CardCategory for r in df.collect()]
    assert result == ['Non-PCARD', 'Non-PCARD', 'PCARD'], f"Got: {result}"
    print(f"✅ Card category derivation passed: {result}")

# Sample data used:
#   Row 1: market_code_a='PBNA', market_code_b=None  → XTNMarketCode = 'PBNA'
#   Row 2: market_code_a=None,  market_code_b='FLNA' → XTNMarketCode = 'FLNA'
#   Row 3: market_code_a=None,  market_code_b=None   → XTNMarketCode = 'UNK'
def test_market_code_coalesce():
    """COALESCE(market_code_a, market_code_b, 'UNK') AS XTNMarketCode"""
    df = spark.sql(f"SELECT XTNMarketCode FROM {UNIT_TEST_TABLE} ORDER BY XTNMarketCode")
    result = [r.XTNMarketCode for r in df.collect()]
    assert result == ['FLNA', 'PBNA', 'UNK'], f"Got: {result}"
    print(f"✅ Market code coalesce passed: {result}")

# Sample data used: 3 rows inserted → notebook should produce exactly 3 output rows
def test_row_count():
    df = spark.table(UNIT_TEST_TABLE)
    assert df.count() == 3, f"Expected 3 rows, got {df.count()}"
    print("✅ Row count passed")

# Sample data: InvoiceId='INV001', InvoiceLineId='1' → UniqueId = 'INV001|1'
def test_unique_id_concatenation():
    df = spark.sql(f"SELECT UniqueId FROM {UNIT_TEST_TABLE} WHERE InvoiceId = 'INV001'")
    result = df.collect()[0].UniqueId
    assert result == 'INV001|1', f"Got: {result}"
    print(f"✅ UniqueId concatenation passed: {result}")
```

#### ❌ NEVER — These patterns are forbidden:
```python
# FORBIDDEN: vague inequality
assert total_amount > 0

# FORBIDDEN: TODO placeholder — the expected value MUST be computed from your sample data
expected_total = -1832.0  # TODO: Update with actual expected sum from test data

# FORBIDDEN: hardcoded magic number with no trace comment
assert row_count == 5

# FORBIDDEN: reading from ADLS or any external path
df = spark.read.parquet("abfss://container@storage.dfs.core.windows.net/path")
```

## Critical Rules

1. All tests MUST query the **`_unit_test` Delta table** (e.g. `` `catalog`.schema.{target_tbl}_unit_test ``). Assign to a constant `UNIT_TEST_TABLE` at the top of Step 4. **Never query `global_temp.final_view`** — temp views are slower for repeated test scans.
2. **Every expected value MUST be computed from the sample data you created in Step 1.** Trace each row through the transformation logic and write down the output before coding the assert.
3. Output: `.py` file named `test_{actual_notebook_name}.py` with `# MAGIC %md` / `# COMMAND ----------`.
4. **TODO placeholders are forbidden.** If you cannot compute an expected value, revisit the sample data design — never leave `# TODO: Update...`.
5. Generate tests from actual notebook logic, not generic stubs.
6. **Zero ADLS.** No `abfss://`, `dbfs:/`, `spark.read.parquet(path)` anywhere in the test notebook. All test data comes from inline `spark.createDataFrame(...)` only.
7. Every `CASE WHEN` branch, `COALESCE` fallback, and `CONCAT` pattern in the notebook must have at least one test row that covers it.
8. Annotate every sample data row with a `# →` comment showing what output column value it should produce.

## Quality Checklist (verify before writing the file)

- [ ] Every source table has inline `spark.createDataFrame(...)` — no ADLS paths
- [ ] Each sample row has a `# →` trace comment for the column being tested
- [ ] Every `CASE WHEN` has a row hitting each branch (WHEN and ELSE)
- [ ] Every `COALESCE` has a non-null row, a null-with-fallback row, and an all-null→default row
- [ ] Every assert uses an exact value computed from the sample data (no `> 0`, no TODOs)
- [ ] Row count assert equals the number of rows actually inserted across source tables (accounting for JOIN cardinality)
- [ ] `UNIT_TEST_TABLE` constant is defined at the top of Step 4 pointing to `{GOLD_DB}.{target_tbl}_unit_test`
- [ ] **No `global_temp.final_view` references** anywhere in the test notebook — all queries use `UNIT_TEST_TABLE`

## Execution Steps

1. Read `references/Unit_Test_Template.py`.
2. Read the full target notebook from top to bottom.
3. **Parse ALL transformations:** List every `CASE WHEN`, `COALESCE`, `CONCAT`, `CAST`, `YEAR()`, hardcoded literal, and JOIN condition. This is your transformation inventory.
4. **Design sample rows from the inventory:** For each transformation, create one row per branch/path that exercises it. Annotate with `# →` comments.
5. **Compute expected values:** Walk every sample row through the full transformation SQL and record what the output will be for each output column. Do this BEFORE writing any test function.
6. Build inline `spark.createDataFrame(...)` DataFrames (zero ADLS) and register as `global_temp` views.
7. Extract notebook name from path for file naming.
8. Generate test functions — one per transformation rule — using only the pre-computed expected values from Step 5.
9. **Replace template variables:**
   - `{{CURRENT_DATE}}` → today
   - `{{TABLE_NAME}}` → from config/notebook
   - `{{DATA_ASSET_NAME}}` → from config
   - `{{MAIN_NOTEBOOK_PATH}}` → user-provided
   - `{{ACTUAL_NOTEBOOK_NAME}}` → extracted notebook name
   - `{{SAMPLE_DATA_FRAMES}}` → generated inline DataFrame code
   - `{{NOTEBOOK_CONFIG}}` → JSON config (auto-detected or user-provided)
   - `{{TEST_FUNCTIONS}}` → generated test function code
   - `{{ADDITIONAL_TESTS}}` → comma-separated test names
7. Write to `Output/UnitTesting/test_{notebook_name}.py`

## Reference Files

This skill uses:
- `references/Unit_Test_Template.py` - Base template with placeholders (only reference needed)

---

## Evals

Test cases for this skill live in `evals/evals.json`. Read that file when:
- Verifying output quality after generating a test notebook
- Checking whether a new transformation pattern (CASE WHEN, COALESCE, SCD2) is covered
- Adding a new test case after encountering an edge case

### Eval Schema (per Anthropic skill-creator spec)

```json
{
  "skill_name": "create-unit-test-cases",
  "evals": [
    {
      "id": 1,
      "prompt": "User's task prompt exactly as typed",
      "expected_output": "Human-readable description of what a passing output looks like",
      "assertions": [
        { "text": "Specific, objectively verifiable check on the output file", "type": "content_check|file_exists|negative_check" }
      ],
      "files": ["path/to/target/notebook.py"]
    }
  ]
}
```

### Current Eval Coverage (`evals/evals.json`)

| ID | Scenario | Key Risk Tested | Key Assertions |
|---|---|---|---|
| 1 | Notebook with CASE WHEN + COALESCE transformations | Branch coverage completeness | All CASE branches exercised, no TODO placeholders, no ADLS paths |
| 2 | Notebook with JOIN producing NULLs on miss | JOIN miss coverage | Null-producing row present, `global_temp.final_view` used, exact expected values |
| 3 | Notebook with hardcoded audit columns (`XTNDFSystemId`, `XTNDFReportingUnitId`) | Audit column assertions | Audit column values traced from sample data, row count assert present |
| 4 | Notebook with SCD2 merge logic | SCD2 expiry path | Test covers `is_current=False` expiry row and `is_current=True` insert row |
| 5 | Multi-source notebook with two input tables | Inline DataFrame per table | Both tables have separate `createDataFrame`, zero ADLS references |

### Adding a New Eval

Add to `evals/evals.json` following the schema above. Good test prompts are:
- Realistic — name an actual notebook file or describe a real transformation pattern
- Discriminating — would fail if the skill generates TODO placeholders or reads from ADLS
- Branch-focused — each eval should target one specific transformation type or edge case

