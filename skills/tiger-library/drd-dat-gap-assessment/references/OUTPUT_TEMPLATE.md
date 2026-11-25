# DRD/DAT Assessment — {use_case}

## Status: {PASSED|BLOCKED}
## Gate Score: {n}/4

---

## Inputs

| Item | Value |
|------|-------|
| DRD Excel | `{drd_path}` |
| DAT Excel | `{dat_path}` |
| DAT Data Dictionary CSV | `{data_dictionary_path \| NOT FOUND}` |
| Assessment Date | {YYYY-MM-DD} |
| Subject Area | {subject_area} |
| Sector | {sector} |
| Business Unit | {business_unit} |
| Market Unit | {market_unit} |

---

## Required System Identifiers

| Identifier | Value | Source Column |
|------------|-------|--------------|
| SourceSystemId | {sys_id} | {source_column} |
| ReportingUnitId | {reporting_unit_id \| NOT FOUND} | {source_column} |

---

## Critical Findings

### Column Completeness

#### DRD (8 Mandatory / 24 Total)

| # | Column | Status | Fill Rate |
|---|--------|--------|-----------|
| 1 | {column_name} | {✅ PASS \| ⚠️ UNDERFILLED \| ❌ MISSING} | {n%} |

**DRD Total Columns Found:** {n}/24

#### DAT (7 Mandatory / 29 Total)

| # | Column | Status | Fill Rate |
|---|--------|--------|-----------|
| 1 | {column_name} | {✅ PASS \| ⚠️ UNDERFILLED \| ❌ MISSING} | {n%} |

**DAT Total Columns Found:** {n}/29

### Table & Attribute Verification (MCP)

| # | DAT Physical Table | DEV | QA | P2D | PROD | Attributes Verified |
|---|-------------------|-----|-----|-----|------|---------------------|
| 1 | {table_name} | {✅\|❌\|⚠️} | {✅\|❌\|⚠️} | {✅\|❌\|⚠️} | {✅\|❌\|⚠️} | {n/total} |

#### Missing Attributes

| # | Table | Attribute | Environments Checked | Status |
|---|-------|-----------|---------------------|--------|
| 1 | {table} | {attribute} | {envs} | ❌ Not Found |

---

## Recommendations

### UC 3-Part Naming

| # | DAT Physical Table (as-is) | Valid 3-Part? | Recommended UC Path |
|---|---------------------------|---------------|---------------------|
| 1 | {table_name} | {Yes \| No ({n}-part)} | {catalog.schema.table} |

### Business Definition Coverage

| Metric | Count | Percentage |
|--------|-------|------------|
| Attributes with Business Definition | {n} | {n%} |
| Attributes missing Business Definition | {n} | {n%} |
| Attributes with Scenario Assessed | {n} | {n%} |

### Primary Key and Data Type Inference

| # | DAT Table | DAT Attribute | Source | Inferred PK/FK | Inferred Data Type | Gap Exists? | Status |
|---|-----------|---------------|--------|----------------|--------------------|-------------|--------|
| 1 | {table} | {attr} | {Data Dictionary \| DRD Data Grain \| DAT Definition \| NOT INFERRED} | {PK \| FK \| NA \| NOT INFERRED} | {datatype(length,scale) \| datatype \| NOT INFERRED} | {Y/N} | {✅ OK \| ⚠️ WARNING} |

---

## Scorecard

| Metric | Value |
|--------|-------|
| DRD Critical Mandatory (5) | {n}/5 passed |
| DAT Critical Mandatory (4) | {n}/4 passed |
| DRD Total Columns (24) | {n}/24 found |
| DAT Total Columns (29) | {n}/29 found |
| Tables Verified (MCP) | {n}/{total} |
| Attributes Verified (MCP) | {n}/{total} |
| SourceSystemId | {extracted \| NOT FOUND} |
| ReportingUnitId | {extracted \| NOT FOUND} |

---

## Checkpoint

- [ ] drd_template: All 24 DRD columns exist; 5 critical mandatory columns ≥80% fill
- [ ] dat_template: All 29 DAT columns exist; 4 critical mandatory columns ≥80% fill
- [ ] mcp_table_verified: All DAT tables verified in at least one MCP environment
- [ ] system_id_extracted: SourceSystemId successfully extracted
