# Test Prompts for Lineage Extraction Skill

## Purpose
These test prompts verify that the lineage-extraction skill correctly queries Databricks audit tables, extracts source lineage, and produces valid hierarchical JSON output.

## Test Coverage

### 1. Single Table Extraction
**Prompt**: "Generate lineage for {gold_schema}.product table"

**Expected Behavior**:
- Reads input_scope.yaml (or creates entry)
- Queries audit_parameters and job_schedule via MCP
- Extracts all source tables (Bronze/Silver/Gold/Parquet)
- Classifies source types correctly
- Extracts system IDs from query or notebook
- Groups by market_code
- Validates output with eval_lineage.py
- Writes to LineageConfigJSON/Example_Lineage_Config.json

**Assertions**:
- Output JSON validates against lineage_schema.json
- At least one market in markets[] array
- Product table present in gold_tables[] under correct market
- All Sources[] have valid Source_Table_Type
- Unity Catalog sources have 3-part Table_Name
- System ID present (or "N/A" for Parquet/Bronze)

---

### 2. Pipeline Extraction
**Prompt**: "Extract lineage for pipeline PL_Example_BU1_US_Product"

**Expected Behavior**:
- Same as Test 1 but scoped to specific pipeline
- May cover multiple markets if pipeline processes multiple regions

**Assertions**:
- Same as Test 1
- Pipeline_Name field matches PL_Example_BU1_US_Product

---

### 3. Incremental Merge
**Prompt**: "Update lineage for {gold_schema}.product table"

**Expected Behavior**:
- Load existing LineageConfigJSON/Example_Lineage_Config.json
- Query fresh data from audit tables
- Generate diff showing changes
- Ask user confirmation before merging
- Preserve existing entries for other tables
- Update metadata.registry_generated_at

**Assertions**:
- Diff displayed to user before merge
- Existing entries not in scope are preserved
- User confirmation requested
- Backup .bak file created before write

---

### 4. Multiple Tables
**Prompt**: "Generate lineage for all PTS tables in input_scope.yaml"

**Expected Behavior**:
- Process all entries in references/input_scope.yaml
- Query audit tables once per entry
- Group all tables by market
- Validate entire output
- Report summary statistics

**Assertions**:
- All entries in input_scope.yaml processed
- Summary shows count: processed, new, updated, skipped
- Output validates successfully
- All markets properly structured

---

### 5. Parquet Source Handling
**Prompt**: "Extract lineage for table with Parquet sources"

**Expected Behavior**:
- Detect ADLS paths (abfss://) in source definitions
- Classify as Source_Table_Type = "Parquet"
- Set SourceSystemId = "N/A" (acceptable for Parquet)
- Include Source_Path field

**Assertions**:
- Parquet sources have Source_Table_Type = "Parquet"
- Source_Path starts with "abfss://"
- System ID set to "N/A" without error

---

### 6. Bronze Staging Table
**Prompt**: "Extract lineage for Gold table reading from Bronze staging"

**Expected Behavior**:
- Detect Bronze catalog/schema pattern
- Classify as Source_Table_Type = "Bronze"
- Accept missing system ID filter (Bronze staging often has no filter)
- Continue processing without error

**Assertions**:
- Bronze sources classified correctly
- System ID = "N/A" accepted for Bronze staging
- No validation errors for missing Bronze filter

---

### 7. Gold-to-Gold Reference
**Prompt**: "Extract lineage for Gold table that reads from another Gold table"

**Expected Behavior**:
- Detect Gold catalog pattern in source
- Classify as Source_Table_Type = "Gold"
- Extract system ID from upstream Gold table or inherit
- Handle cross-market Gold references

**Assertions**:
- Gold source classified as Source_Table_Type = "Gold"
- Table_Name follows 3-part UC naming
- System ID present or inherited

---

### 8. Validation Failure Handling
**Prompt**: "Generate lineage but force validation failure" (by manually corrupting schema)

**Expected Behavior**:
- Run eval_lineage.py
- Detect validation errors
- Print failures clearly
- Ask user: "Validation failed. Write anyway? (Y/N)"
- If N → abort without writing

**Assertions**:
- Validation errors printed
- User prompt displayed
- If user says N → no output written
- If user says Y → output written with warning

---

## Running Tests

To run these tests manually:

1. Create input_scope.yaml with test entries
2. Ensure Databricks MCP server is configured
3. Run test prompts through skill
4. Validate output with:
   ```bash
   python scripts/eval_lineage.py Copilot/LineageConfigJSON/Example_Lineage_Config.json
   ```

## Automated Test Setup

For skill-creator eval runner:

1. Create mock MCP responses for test pipelines
2. Set up test workspace with sample input_scope.yaml
3. Define assertions in evals.json
4. Run via skill-creator eval framework

## Success Criteria

All tests should:
- ✓ Query MCP successfully (or use mock data)
- ✓ Extract sources correctly
- ✓ Classify source types accurately
- ✓ Handle edge cases (Parquet, Bronze, Gold-to-Gold)
- ✓ Validate output schema
- ✓ Produce valid hierarchical JSON
- ✓ Merge incrementally without data loss
- ✓ Report clear errors on failure
