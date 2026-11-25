# STTM CSV Alignment Rules

Every data row in the STTM CSV must have exactly **28 fields** (27 top-level commas).
Missing empty fields between columns are the most common cause of misaligned `Version` values.

## Column Layout (28 fixed positions)

| Pos | Section | Column Header |
|-----|---------|--------------|
| 1 | SOURCE | Source Name |
| 2 | SOURCE | Source Schema Name |
| 3 | SOURCE | Source Table Name |
| 4 | SOURCE | Column Name* |
| 5 | SOURCE | Column Definition* |
| 6 | SOURCE | Source Data Type* |
| 7 | SOURCE | PK/FK |
| 8 | SOURCE | Allow Nulls* |
| 9 | SOURCE | Example Values |
| 10 | SOURCE | Default Value |
| 11 | SOURCE | Comments |
| 12 | SOURCE | *(spacer)* |
| 13 | GOLD TARGET | Target Data Lake* |
| 14 | GOLD TARGET | Target Table Name* |
| 15 | GOLD TARGET | Target Column* |
| 16 | GOLD TARGET | Target Data Type* |
| 17 | GOLD TARGET | Allow Nulls* |
| 18 | GOLD TARGET | Merge Key |
| 19 | GOLD TARGET | Primary Key |
| 20 | GOLD TARGET | FK Table.columnname |
| 21 | GOLD TARGET | Default Value |
| 22 | GOLD TARGET | Data Transformation Rules* |
| 23 | GOLD TARGET | Comments |
| 24 | GOLD TARGET | Version |
| 25 | GOLD COMMON VIEW | Column Description* |
| 26 | GOLD COMMON VIEW | Data Lake |
| 27 | GOLD COMMON VIEW | Common ViewName |
| 28 | GOLD COMMON VIEW | Common View Column Name |

## Critical Alignment Rules

### Rule 1 — FK populated, Default Value empty
When col 20 (FK Table.columnname) is populated and col 21 (Default Value) is empty, you MUST still emit col 21 as an empty field.

```
✅ CORRECT:   ...,SomeTable.SomeColumn,,"CASE WHEN...",,V1,,,
❌ INCORRECT: ...,SomeTable.SomeColumn,"CASE WHEN...",,V1,,,
```

### Rule 2 — Both FK and Default Value empty
When cols 20 and 21 are both empty, both commas must still appear before col 22.

```
✅ CORRECT:   ...,Yes,Yes,,,"CAST(DocumentPostingDate AS date)",,V1,,,
❌ INCORRECT: ...,Yes,Yes,,"CAST(DocumentPostingDate AS date)",,V1,,,
```

### Rule 3 — Audit/scope columns with Primary Key = Yes
Place `Yes` in col 19 (Primary Key). Col 20 (FK) remains empty. Col 21 (Default Value) holds the system/reporting ID numeric value.

```
✅ CORRECT:   ...,int,NOT NULL,,Yes,,892,"Default value: 892",,V1,,,
❌ INCORRECT: ...,int,NOT NULL,,,Yes,892,"Default value: 892",,V1,,,
```

### Rule 4 — Self-validate before saving
Before saving the CSV, count a sample of rows. Each row must have exactly 27 top-level commas (fields inside double quotes do not count as separators). If any row has fewer than 27 commas, a field is missing — locate it using the column layout table above.

## Common Patterns

### Business column, no FK, no Default Value
```csv
Silver,catalog.schema,SalesOrder,ORDER_DATE,Order date,DATE,,YES,,,,,catalog.schema,TableName,OrderDate,date,NOT NULL,Yes,,,,Direct,,V1,,catalog.schema_vw,TableName_vw,OrderDate
```

### Audit column with default value (no merge/PK for non-key audits)
```csv
,,,,,,,,,,,,catalog.schema,TableName,CreatedTimestamp,timestamp,NOT NULL,,,,,"CURRENT_TIMESTAMP()",,V1,,catalog.schema_vw,TableName_vw,CreatedTimestamp
```

### System ID as Primary Key
```csv
,,,,,,,,,,,,catalog.schema,TableName,SourceSystemId,int,NOT NULL,,Yes,,892,"Default value: 892",,V1,,catalog.schema_vw,TableName_vw,SourceSystemId
```
