# Transformation Document — `{notebook_filename}`

---

## 1. Overview

| Field | Details |
|---|---|
| **Notebook** | `{notebook_filename}` |
| **Location** | `{notebook_path}` |
| **Layer** | `{layer_name}` |
| **Sector / Domain** | `{sector}` |
| **Created By** | `{created_by}` |
| **Created Date** | `{created_date}` |
| **Last Updated** | `{last_updated_date}` |

---

## 2. Source Tables

| # | Catalog Variable | Schema Variable | Table Name | Alias | Description |
|---|---|---|---|---|---|
| 1 | `{catalog_var_1}` | `{schema_var_1}` | `{table_name_1}` | `{alias_1}` | `{description_1}` |
| 2 | `{catalog_var_2}` | `{schema_var_2}` | `{table_name_2}` | `{alias_2}` | `{description_2}` |

> **Note:** Add or remove rows as required. Only include physical tables with defined catalog/schema (exclude CTEs/temp views). Catalog and schema values are resolved at runtime from `db_mapping` / `initial_setup`.

---

## 3. Target Load Configuration

### 3.1 Target Table

| Field | Value |
|---|---|
| **Database Variable** | `{target_db_name}` |
| **Resolved Database** | `{resolved_database_name}` |
| **Table Name** | `{target_table_name}` |
| **Step** | `{step}` |

### 3.2 Load Type

| Property | Value |
|---|---|
| **Load Type** | `{load_type}` |
| **Load Changed Data Only** | `{load_changed_data}` |

### 3.3 Key Columns

These columns uniquely identify a record and drive the merge / SCD2 behaviour:

| # | Column |
|---|---|
| 1 | `{key_column_1}` |
| 2 | `{key_column_2}` |

> Add or remove rows to match `target_key_columns` in `target_config`.

### 3.4 Merge / Compare Columns (Excluded from Change Detection)

Updates to these columns alone will **not** trigger a new version or update:

| # | Excluded Column |
|---|---|
| 1 | `{exclude_compare_column_1}` |
| 2 | `{exclude_compare_column_2}` |

> Sourced from `exclude_compare_columns` in `target_config`. Use `None` if not configured.

### 3.5 Delete Condition

| Property | Value |
|---|---|
| **Delete Condition** | `{delete_criteria}` |
| **Partition Filter** | `{target_partition_filter}` |
| **Exclude Update Columns** | `{exclude_update_columns}` |

> Sourced from `delete_criteria`, `target_partition_filter` and `exclude_update_columns` in `target_config`.

---

## 4. Filter Conditions

### 4.1 {Filter_Condition_Name_1}

Brief description of what this filter achieves and which table it is applied to.

| Parameter / Variable | Filter Applied |
|---|---|
| `{param_1}` | `{filter_expression_1}` |
| `{param_2}` | `{filter_expression_2}` |

### 4.2 {Filter_Condition_Name_2}

Brief description.

```sql
-- Example: Deduplication QUALIFY clause
QUALIFY ROW_NUMBER() OVER (PARTITION BY {partition_column} ORDER BY {order_column}) = 1
```

> Add sub-sections (4.3, 4.4, ...) for each distinct filter type. Remove unused sub-sections.

---

## 5. Join Logic

| Join Type | Left Table | Right Table | Join Condition |
|---|---|---|---|
| `{join_type}` | `{left_table} ({left_alias})` | `{right_table} ({right_alias})` | `{join_condition}` |

> Add rows for each JOIN in the notebook SQL.

---

## 6. Transformation Logic

### 6.1 Conditional Mappings/Case conditions

Columns that are selected differently based on runtime parameters or market/condition logic:

| Condition | Source Column | Target Column | Notes |
|---|---|---|---|
| `{condition_1}` | `{source_col_1}` | `{target_col_1}` | `{notes_1}` |
| All others | `{source_col_default}` | `{target_col_1}` | Default mapping |

### 6.2 SCD2 / Lifecycle Control Columns

System-generated columns to manage record versioning:

| Target Column | Transformation | Notes |
|---|---|---|
| `{scd_col_1}` | `{transformation_1}` | `{notes_1}` |
| `{scd_col_2}` | `{transformation_2}` | `{notes_2}` |

> Remove this sub-section if load type is not `scd_type2`.

### 6.3 Direct Column Mappings

Columns passed through from source without transformation:

| Target Column | Source Column |
|---|---|
| `{target_col}` | `{source_alias}.{source_col}` |

### 6.4 Cast / Type Conversion Columns

| Target Column | Source | Cast Logic | Notes |
|---|---|---|---|
| `{target_col}` | `{source}` | `{cast_expression}` | `{notes}` |

### 6.5 Lookup / Reference Columns

Columns sourced from a joined reference table:

| Target Column | Source | Notes |
|---|---|---|
| `{target_col}` | `{alias}.{source_col}` | `{notes}` |

### 6.6 Hardcoded / Defaulted Columns

Literal values assigned directly in the SELECT:

| Target Column | Value | Reason |
|---|---|---|
| `{target_col}` | `'{literal_value}'` | `{reason}` |

### 6.7 Audit / Lineage Columns

Runtime-injected metadata columns:

| Target Column | Source Variable | Description |
|---|---|---|
| `{audit_col_1}` | `{python_var_1}` | `{description_1}` |
| `{audit_col_2}` | `{python_var_2}` | `{description_2}` |
