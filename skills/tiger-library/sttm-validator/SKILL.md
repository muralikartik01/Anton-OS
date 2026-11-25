# STTM Validator

## Purpose

This skill validates, reviews, and optionally corrects a Source-to-Target Mapping (STTM) document.

The skill checks:

* Required columns and values
* Source-to-target mapping completeness
* Data Transformation Rules
* Transformation Logic
* Source schema/table/column information
* Target schema/table/column information
* Target data type
* Target nullable indicator
* Primary Key / Foreign Key / Logical Primary Key
* Merge Key
* STTM versioning and dates
* Derived, transformed, direct, and no-mapping classifications
* Formatting and structural consistency

The skill must be **generic and reusable across projects and organizations**. Do not assume any specific company, domain, schema, table, naming convention, or technology unless it is explicitly provided in the STTM or by the user.

---

# When to Use This Skill

Activate this skill when the user asks to:

* Validate an STTM
* Review an STTM
* Check an STTM
* Correct an STTM
* Fix an STTM
* Format an STTM
* Clean an STTM
* Review STTM mappings
* Check source-to-target mappings
* Check transformation logic
* Check STTM version
* Check STTM primary keys
* Check STTM merge keys
* Find missing STTM values
* Identify STTM errors
* Audit an STTM
* Verify STTM completeness
* Validate source and target mappings
* Check whether transformation rules are correct
* Check whether derived columns have transformation logic
* Check STTM consistency
* Perform STTM quality validation

Also activate for similar natural-language requests where the user clearly wants an STTM validation or review.

---

# Input

The skill expects an STTM containing source-to-target mapping information.

The exact STTM column names may vary slightly between projects.

Identify the corresponding columns using their meaning rather than assuming an exact column name.

The important STTM fields are:

### Source Information

* Source Schema Name
* Source Table Name
* Source Column Name

### Target Information

* Target Schema Name
* Target Table Name
* Target Column Name
* Target Data Type
* Allow Nulls in Target
* Target Primary Key
* Version
* Date
* Merge Key

### Transformation Information

* Data Transformation Rules
* Transformation Logic

---

# Validation Rules

## 1. Data Transformation Rules

The `Data Transformation Rules` column must contain one of the following values:

* `Derived`
* `Direct`
* `Transformed`
* `No Mapping`

The validation should be case-insensitive.

For example:

```text
Derived
derived
DERIVED
```

should all be treated as `Derived`.

However, the skill should report inconsistent formatting if the project expects standardized values.

### Allowed values

```text
Derived
Direct
Transformed
No Mapping
```

No other value should be accepted.

Example invalid values:

```text
Transform
Mapping
Direct Mapping
Derivation
NA
N/A
Null
```

unless explicitly allowed by project-specific instructions.

---

# 2. Transformation Logic Validation

## Derived

If `Data Transformation Rules = Derived`:

* `Transformation Logic` must NOT be null or empty.
* The transformation logic must contain an actual derivation rule.
* A meaningful business/technical expression must be present.

Examples of valid derived logic:

```text
CASE WHEN Status = 'A' THEN 1 ELSE 0 END
```

```text
Current timestamp assigned to RecordCreatedDate
```

```text
Generate PipelineRunId from the current pipeline execution
```

```text
CASE
    WHEN Type = 'A' THEN 3
    WHEN Type = 'B' THEN 4
END
```

The skill should flag the following:

```text
Derived + Transformation Logic is null
```

or:

```text
Derived + Transformation Logic = NA
```

or an obviously empty/non-meaningful value.

---

# 3. Transformed

If `Data Transformation Rules = Transformed`:

* `Transformation Logic` must NOT be null or empty.
* The logic should describe the transformation applied to the source column.

A transformation includes changes such as:

* Date format conversion
* Data type conversion
* String manipulation
* Trimming
* Upper/lower casing
* Substring
* Regex replacement
* Mathematical calculation
* Null handling
* Conditional transformation
* Any other direct column-level transformation

Examples:

```text
Convert date from yyyyMMdd to yyyy-MM-dd
```

```text
UPPER(SourceColumn)
```

```text
TRIM(SourceColumn)
```

```text
CAST(SourceColumn AS INTEGER)
```

```text
REGEXP_REPLACE(SourceColumn, '-', '')
```

A transformation can be considered `Transformed` even when the transformation is small.

For example:

```text
Source: 20260131
Target: 2026-01-31
Rule: Transformed
Logic: Convert date format from yyyyMMdd to yyyy-MM-dd
```

---

# 4. Direct

`Direct` means the target column is populated directly from a source column without a transformation being applied to that column.

A Direct mapping may still involve joins.

For example, assume five source tables are joined:

```text
Table1
Table2
Table3
Table4
Table5
```

If the tables are joined and then a target column is populated directly from a column in Table1:

```text
Table1.CustomerId -> Target.CustomerId
```

then the mapping is:

```text
Data Transformation Rules = Direct
```

The join logic must be documented in the `Transformation Logic` section when joins are required to obtain the source data.

Example:

```text
Join Table1 and Table2 on CustomerId.
Map Table1.CustomerName directly to Target.CustomerName.
```

Important:

**A join by itself does not make the column Transformed.**

If the column value itself is not modified and is simply selected after the required joins, classify it as:

```text
Direct
```

---

# 5. No Mapping

`No Mapping` means:

* The target column exists in the target schema.
* The target column does not need to be populated from a source.
* No source mapping is required.

For `No Mapping` columns:

```text
Source Schema Name = NULL
Source Table Name = NULL
Source Column Name = NULL
```

is allowed.

Example:

```text
Target Column: SomeUnusedColumn
Data Transformation Rules: No Mapping
Source Schema: NULL
Source Table: NULL
Source Column: NULL
```

Do NOT flag missing source information when the target column is explicitly classified as `No Mapping`.

---

# 6. Source Schema / Table / Column Validation

The following source fields normally must NOT be null:

* Source Schema Name
* Source Table Name
* Source Column Name

They should contain the source schema/table/column details.

Example:

```text
Source Schema Name = sales
Source Table Name = customer
Source Column Name = customer_id
```

However, there are two valid exceptions.

## Exception 1: Derived

If the target column is `Derived`, source information may not be required if the target value is generated/calculated rather than directly sourced.

Example:

```text
Target Column = RecordCreatedDate
Rule = Derived
Logic = Current timestamp
```

Source fields can be null.

## Exception 2: No Mapping

If:

```text
Data Transformation Rules = No Mapping
```

source fields can be null.

Therefore, apply this validation logic:

```text
IF source details are NULL
    AND rule is Derived
        -> Valid

ELSE IF source details are NULL
    AND rule is No Mapping
        -> Valid

ELSE IF source details are NULL
    AND rule is Direct
        -> Error

ELSE IF source details are NULL
    AND rule is Transformed
        -> Error

ELSE
    -> Valid
```

---

# 7. Target Schema Name

`Target Schema Name` must NOT be null or empty.

Flag:

```text
Target Schema Name is missing
```

---

# 8. Target Table Name

`Target Table Name` must NOT be null or empty.

Flag:

```text
Target Table Name is missing
```

---

# 9. Target Column Name

`Target Column Name` is mandatory.

It must NOT be null or empty.

Flag:

```text
Target Column Name is missing
```

---

# 10. Target Data Type

`Target Data Type` must NOT be null or empty.

Every mapped target column must have a target datatype.

Example valid values:

```text
STRING
INTEGER
BIGINT
DOUBLE
DECIMAL(18,2)
DATE
TIMESTAMP
BOOLEAN
```

The exact list of supported datatypes may depend on the target technology, so do not reject a datatype merely because it is not in a hard-coded list unless the project provides an allowed datatype list.

Flag:

```text
Target Data Type is missing
```

---

# 11. Allow Nulls in Target

`Allow Nulls in Target` must contain exactly one of:

```text
Y
N
```

The validation should be case-insensitive.

Valid:

```text
Y
y
N
n
```

Invalid:

```text
Yes
No
TRUE
FALSE
NULL
Blank
NA
```

If the project requires uppercase formatting, report lowercase values as a formatting issue rather than a semantic validation failure.

---

# 12. Target Primary Key/Primary Key

The `Target Primary Key` or `Primary Key` field must contain one of:

```text
PK
FK
LPK
NULL
```

The validation is case-insensitive.

Valid:

```text
PK
pk
FK
fk
LPK
lpk
NULL
```

Do not allow other values.

Invalid examples:

```text
Primary Key
Foreign Key
Yes
Y
No
N
Primary
Foreign
```
It should contain atleast one PK

---

# 13. Primary Key Requirement

At least **one target column must be marked as `PK`** in the STTM.

If no column has:

```text
Target Primary Key = PK
```

report:

```text
ERROR: No Primary Key (PK) is defined in the STTM.
At least one target column must be marked as PK.
```

Do not consider `FK` or `LPK` as satisfying the PK requirement.

---

# 14. Version Validation

The `Version` column defines STTM revisions.

Expected format:

```text
V1
V2
V3
V4
...
```

The version:

* Must start with `V`
* Must end with a number
* The number must be positive
* Version numbering should be sequential where applicable

Valid:

```text
V1
V2
V3
V10
```

Invalid:

```text
1
Version1
v-one
V
V-
VERSION1
```

The validation should be case-insensitive for `V`, but standardized formatting should preferably be uppercase.

---

# 15. Version Date Validation

Each STTM version must have a corresponding date.

Example:

```text
Version    Date
V1         2026-01-10
V1         2026-01-10
V1         2026-01-10
V2         2026-02-15
V2         2026-02-15
V3         2026-04-01
```

### Rule

All rows belonging to the same version must have the same date.

Therefore:

```text
V1 -> one unique date
V2 -> one unique date
V3 -> one unique date
```

is valid.

But:

```text
V1 -> 2026-01-10
V1 -> 2026-01-12
```

is invalid.

---

# 16. Version Date Ordering

Version dates must increase as the version increases.

Example:

```text
V1 -> 2026-01-10
V2 -> 2026-02-15
V3 -> 2026-04-01
```

is valid.

But:

```text
V1 -> 2026-02-10
V2 -> 2026-01-10
```

is invalid.

The rule is:

```text
Date(V2) > Date(V1)
Date(V3) > Date(V2)
Date(V4) > Date(V3)
```

If a version has the same date as the previous version, flag it unless the user explicitly states that same-day versions are allowed.

---

# 17. Merge Key

The `Merge Key` field may contain only:

```text
Y
NULL
```

The validation is case-insensitive.

Valid:

```text
Y
y
NULL
```

Invalid:

```text
N
No
Yes
TRUE
FALSE
1
0
```

unless project-specific rules explicitly allow them.

---

# 18. Merge Key Requirement

At least one target column must have:

```text
Merge Key = Y
```

If no column has `Y`, report:

```text
ERROR: No Merge Key is defined.
At least one target column must be marked as Y.
```

---

# 19. Consistency Between Transformation Rule and Source Information

Validate the relationship between:

```text
Data Transformation Rules
Source Schema Name
Source Table Name
Source Column Name
Transformation Logic
```

Use the following matrix:

| Rule        | Source Schema | Source Table | Source Column | Transformation Logic               |
| ----------- | ------------- | ------------ | ------------- | ---------------------------------- |
| Direct      | Required      | Required     | Required      | Optional / required if joins exist |
| Transformed | Required      | Required     | Required      | Required                           |
| Derived     | May be NULL   | May be NULL  | May be NULL   | Required                           |
| No Mapping  | May be NULL   | May be NULL  | May be NULL   | Usually NULL                       |

Flag inconsistent combinations.

Examples:

```text
Direct + Source Column NULL
```

→ Error

```text
Transformed + Transformation Logic NULL
```

→ Error

```text
Derived + Transformation Logic NULL
```

→ Error

```text
No Mapping + Source details populated
```

→ Potential inconsistency/warning depending on project conventions.

---

# 20. Derived Column Identification

The skill should recognize common derived target columns.

Examples include:

```text
RecordCreatedDate
RecordUpdatedDate
PipelineRunId
IngestionControlId
CreatedTimestamp
UpdatedTimestamp
LoadDate
LoadTimestamp
```

However, do not assume that these names are always derived.

The classification must primarily depend on the `Data Transformation Rules` value and transformation logic.

For example:

```text
RecordCreatedDate
Rule = Derived
Logic = Current timestamp
```

is valid.

---

# 21. Transformation Classification Guidance

Use these definitions when validating or suggesting corrections.

### Direct

Source value is mapped directly to target without modifying the value.

```text
Source.CustomerId -> Target.CustomerId
```

### Transformed

A source column is modified before being populated into the target.

Examples:

```text
Date format conversion
CAST
TRIM
UPPER
LOWER
REGEXP_REPLACE
SUBSTRING
Mathematical calculation
Null handling
```

### Derived

The target value is generated using business logic, conditions, calculations, system-generated values, or multiple inputs.

Examples:

```text
CASE WHEN ...
Current timestamp
Pipeline Run ID
Ingestion Control ID
Business rule calculation
```

### No Mapping

Target column exists but is intentionally not populated.

---

# 22. Join Logic

When a Direct mapping requires joins between multiple source tables:

* Keep the Data Transformation Rules as `Direct` if the mapped source column itself is not transformed.
* Document the join condition in `Transformation Logic`.

Example:

```text
Data Transformation Rules: Direct

Transformation Logic:
Join customer and account tables using CustomerId.
Map customer.CustomerName directly to Target.CustomerName.
```

Do not automatically classify a column as `Transformed` simply because a join is involved.

---

# 23. Null and Blank Handling

Treat the following as missing values where applicable:

```text
NULL
null
blank
empty string
whitespace-only string
```

Do not treat text such as:

```text
NA
N/A
Not Applicable
None
```

as valid null representations unless the project explicitly defines them as such.

Report them as formatting/data-quality issues where the field requires a real null.

---

# 24. Duplicate Target Columns

Check whether the same target column is mapped multiple times for the same target table.

Example:

```text
Target Table = customer
Target Column = CustomerId
```

appearing more than once should be flagged.

Error:

```text
Duplicate target column mapping detected.
```

Exception: If the STTM format explicitly supports multiple source mappings for the same target column, follow the provided project rules.

---

# 25. Duplicate Source-to-Target Mapping

Allow the same source (same source schema/table/column) to appear multiple times when it maps to different target columns — this may be intentional in some STTM formats.

However, the same target column for the same target table must not be mapped more than once. If the same target column appears multiple times for the same target table, flag it as an ERROR unless the STTM explicitly documents support for multiple source mappings to a single target column.

Checks:

```text
- Duplicate source entries mapping to different target columns: INFO/WARNING (may be valid)
- Same target table + same target column appearing multiple times: ERROR (duplicate target column mapping detected)
```

Report duplicates separately from duplicate target columns.

---

# 26. Target Table Consistency

Within a logical STTM section, verify that:

* Target schema is consistent.
* Target table is consistent.
* Target column names are unique.
* Target datatype is present for every target column.
* Target PK/FK/LPK classification is valid.
* Merge Key values are valid.

If multiple target tables exist in one STTM, perform these validations independently for each target table.

---

# Validation Severity

Classify findings into:

## ERROR

The STTM violates a mandatory rule.

Examples:

```text
Missing Target Column Name
Missing Target Data Type
Invalid Primary Key value
No PK present
No Merge Key present
Derived column without transformation logic
Transformed column without transformation logic
Direct mapping without source details
Version date inconsistency
```

## WARNING

The STTM may technically work but has a potential quality or consistency issue.

Examples:

```text
Lowercase PK/FK/LPK
Lowercase transformation rule
Unusual datatype formatting
Potentially unnecessary source information for No Mapping
```

## INFO

Informational observation that does not indicate an error.

Examples:

```text
5 target columns are derived.
3 columns are No Mapping.
Current STTM version is V3.
```

---

# Validation Process

When the skill is invoked, follow this sequence.

## Step 1 — Understand the STTM structure

Identify:

* Header row
* Target information
* Source information
* Transformation information
* Version information
* Key information

Do not assume the first row is always the header if the file contains title rows or metadata.

---

## Step 2 — Validate mandatory fields

Check:

```text
Target Schema Name
Target Table Name
Target Column Name
Target Data Type
Allow Nulls in Target
```

---

## Step 3 — Validate transformation rules

Check that:

```text
Data Transformation Rules
```

contains an allowed value.

---

## Step 4 — Validate transformation logic

Apply the rules for:

```text
Derived
Transformed
Direct
No Mapping
```

---

## Step 5 — Validate source information

Check source schema/table/column according to the transformation classification.

---

## Step 6 — Validate keys

Check:

```text
Target Primary Key
Merge Key
```

Then verify:

```text
At least one PK exists.
At least one Merge Key exists.
```

---

## Step 7 — Validate versions

Check:

```text
Version format
Version date presence
Same date within a version
Increasing dates across versions
```

---

## Step 8 — Validate duplicates

Check target-column duplicates and suspicious duplicate mappings.

---

## Step 9 — Generate validation report

Return a clear summary.

Recommended format:

```text
STTM Validation Summary

Status: FAILED

Total Rows: 125
Errors: 7
Warnings: 3
Info: 4
```

Then provide:

```text
Errors
1. Row 12 - Target Data Type is missing.
2. Row 18 - Derived column has no Transformation Logic.
3. Row 24 - Invalid Merge Key value 'N'.
4. No PK is defined for target table customer.
...
```

Then:

```text
Warnings
1. Row 15 - Target Primary Key value 'pk' should preferably be standardized to 'PK'.
...
```

Then:

```text
Passed Checks
✓ Target schema populated
✓ Target table populated
✓ Target column populated
✓ Target datatype populated
✓ At least one PK exists
✓ At least one Merge Key exists
...
```

---

# Correction Mode

The skill must distinguish between:

```text
Validate
```

and:

```text
Correct
```

## Validate Mode

When the user asks:

```text
Validate this STTM
Review this STTM
Check this STTM
```

Do NOT modify the STTM.

Only report findings.

---

## Correction Mode

When the user explicitly asks:

```text
Correct the STTM
Fix the STTM
Update the STTM
```

the skill may correct clear and deterministic issues.

Examples:

```text
pk -> PK
fk -> FK
lpk -> LPK
y -> Y
```

or missing transformation logic when the logic can be unambiguously determined from the available source/target information.

---

# Ambiguous Corrections

Never invent source mappings, transformation logic, primary keys, merge keys, or business rules.

If a correction requires assumptions, ask the user before changing it.

Example:

```text
Target column: CustomerSegment
Source details are missing.
Transformation Rule: Direct

I cannot determine the correct source column from the available information.

Please provide the source mapping before I correct this row.
```

Do not guess.

---

# Output Requirements

The validation output should be concise but complete.

Always include:

1. Overall status
2. Number of rows checked
3. Number of errors
4. Number of warnings
5. all the issues in detail
6. Row/column reference for every issue where possible
7. Passed checks
8. Recommended corrections
9. each check should be clearly labeled as `PASSED`, `FAILED`, `WARNING`, or `INFO`

Example:

```text
STTM VALIDATION RESULT
======================

Status: FAILED

Rows Checked : 150
Errors       : 5
Warnings     : 3

ERRORS
------
Row 21:
- Data Transformation Rules = Derived
- Transformation Logic is missing.

Row 35:
- Allow Nulls in Target = YES
- Expected Y or N.

Row 49:
- Target Primary Key = PRIMARY
- Expected PK, FK, LPK, or NULL.

GLOBAL ERRORS
-------------
- No PK is defined.
- No Merge Key is defined.

WARNINGS
--------
...

PASSED
------
✓ Target Schema Name
✓ Target Table Name
✓ Target Column Name
✓ Target Data Type
✓ Version format
...
```
And share the report in a human-readable format such as Markdown or csv in the agenticskillsdemo\agenticskillsdemo\output\sttm-validator folder.
---

# Important Principles

1. Do not invent information.
2. Do not assume a source mapping when it is missing.
3. Do not classify a column as Derived merely because a join exists.
4. A join with an unchanged source column can still be Direct.
5. Any column-level transformation should generally be classified as Transformed.
6. Derived columns require transformation logic.
7. Transformed columns require transformation logic.
8. No Mapping allows missing source information.
9. At least one PK must exist.
10. At least one Merge Key must exist.
11. Version dates must be consistent within a version.
12. Later version dates must be greater than earlier version dates.
13. Target mandatory fields must not be null.
14. Ask the user before making ambiguous corrections.
15. Keep the skill generic and independent of any specific organization, project, schema, database, or technology.
16. Preserve the original STTM structure and formatting when correcting unless the user explicitly requests reformatting.

---


# Success Criteria

The STTM is considered `PASSED` only when all mandatory validation rules are satisfied.

The STTM should be marked:

```text
PASSED
```

when:

* Mandatory target fields are populated.
* Transformation rules are valid.
* Required source details are populated.
* Derived/transformed columns have transformation logic.
* Allow Nulls contains Y/N.
* Primary Key values are valid.
* At least one PK exists.
* Merge Key values are valid.
* At least one Merge Key exists.
* Version format is valid.
* Version dates are consistent.
* Version dates increase chronologically.
* No mandatory structural errors are detected.

Otherwise:

```text
FAILED
```

with all issues clearly listed.
