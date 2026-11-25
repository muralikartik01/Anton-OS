# DRD/DAT Column Schemas & Validation Rules

---

## DRD — All 24 Columns

```
Data Product Requirement #(s)
Product Requirement Version/Date referenced
Subject Area Name
Subject Area Description
Why this is needed
Subject Area Priority in Program/Product
Needed By Date QA
Needed By Date Production
Sector
Business Unit
Market Unit
Lower level Geography Dimension (ex. Country)
History required
Future horizon required (for plan/forecast data)
Update Frequency
Data Retention Period Required
Assumed data source(s) from Conceptual Architecture (may change according to Data Assessment)
Data Grain
Source system Owner
Subject Area Attributes Required
Subject Area Attribute Description
Subject Area Attribute Example(s)
Data Quality Expectations from the Stakeholders
Comments/Notes
```

## DRD — 8 Mandatory Columns (must exist AND have ≥80% filled values)

## DRD — 8 Mandatory Columns

### Critical (gate-blocking: must exist AND ≥80% filled)

| # | Column | Validation Note |
|---|--------|------------------|
| 1 | Sector | |
| 2 | Business Unit | |
| 3 | Market Unit | |
| 4 | Data Grain | **Grain attrs must appear in DAT `Physical Attribute Name`** |
| 5 | Subject Area Attributes Required | Includes table name as directional SAP context |

### Advisory (must exist; fill rate reported as recommendation)

| # | Column | Validation Note |
|---|--------|------------------|
| 6 | Subject Area Attribute Description | |
| 7 | Data Quality Expectations from the Stakeholders | Fill rate is advisory only |
| 8 | Business Rules | Flag if column absent; fill rate is advisory |

---

## DAT — All 29 Columns

```
Data Product Requirement #(s)
Subject Area Name
Subject Area Description
Source of Origin
Data Source for Assessment [Description + Sys ID if relevant]
Table Logical (Business) Name
Physical(Technical) Table Name
Table Data Grain
Physical Attribute Name
Attribute Logical (Business) Name
Attribute Business Definition
Data Classification
Attribute from DRD
Approx # of Records Currently in Source Table
# Assessed Sample
Scenario Assessed, i.e. filters applied (if any) on data per requirements
Does a gap exist? [Y/N]
Gap #
Gap Type
Gap Description
Gap Status
Gap Priority
Remediation Steps
Gap Resolution Description
Gap Resolution Owner
Target Resolution Date
Progress Summary
Key Gap Resolution Stakeholders (Names)
Comments/Notes
```

## DAT — 7 Mandatory Columns

### Critical (gate-blocking: must exist AND ≥80% filled)

| # | Column | Validation Note |
|---|--------|------------------|
| 1 | Source of Origin | Must contain system description + Sys ID |
| 2 | Data Source for Assessment | Description + Sys ID if relevant |
| 3 | Physical(Technical) Table Name | Used for MCP table verification |
| 4 | Physical Attribute Name | Must include grain attributes from DRD `Data Grain` |

### Advisory (must exist; fill rate reported as recommendation)

| # | Column | Validation Note |
|---|--------|------------------|
| 5 | Attribute Logical (Business) Name | |
| 6 | Attribute Business Definition | |
| 7 | Scenario Assessed, i.e. filters applied (if any) on data per requirements | Fill rate is advisory only |

---

## Fill-Value Validation Rules

- **Column exists**: Header row contains the column name (case-insensitive substring match)
- **Filled threshold**: ≥80% of data rows in that column have non-blank, non-whitespace values
- **Scoring**:
  - ✅ PASS — column exists AND ≥80% filled
  - ⚠️ UNDERFILLED — column exists but <80% filled
  - ❌ MISSING — column not found in header row
- **Critical failure**: Any mandatory column scored ❌ MISSING = assessment BLOCKED
