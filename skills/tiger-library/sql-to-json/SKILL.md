---
name: sql-to-json
description: Generate JSON configurations from SQL following NorthStar project conventions.
---

# SQL to JSON Configuration Generation Instructions

## Objective

Generate a JSON configuration from the provided SQL query by following the existing project architecture and coding standards. The generated JSON must be compatible with the existing Data Engineering framework and should maximize reusability of the existing transformation functions.

---

## Project Architecture

The JSON configuration consists of the following sections:

1. **data_extract**
2. **data_transform**
3. **data_load**

Follow the same structure as the existing JSON configuration files.

---

## Reference Files

Before generating the JSON configuration, analyze the following project artifacts:

### 1. Existing JSON Configuration Files

- Review the existing JSON configuration files within the same domain.
- Understand the naming conventions.
- Follow the same JSON structure.
- Maintain consistency with existing configuration patterns.
- always when doing the join , make both tables columns either upper or lower and also trim the spaces then do the join.
- when you are renaming the columns to avoid ambuiguity . you can again rename them with correct column names in dataload section. also , you have to refer those renames columns thoruthg the next functions to avoid errors.
---

### 2. Gold Notebook

The Gold notebook is the primary reference.

Before generating the JSON:

- Analyze every transformation function available in the Gold notebook.
- Understand the purpose, input parameters, and output of each function.
- Reuse the existing functions whenever possible.
- Do not create new transformation functions if equivalent functionality already exists.
- If there is a requieremnt to create new function in worst case, always ask user before creating.and use the same structure like other functions 

---

### 3. Utility Notebooks

Also review:

- `env_utils`
- `common_utils`

These notebooks contain reusable utility functions that may be referenced by the Gold notebook or required by the generated configuration.

---

## Project Folder Structure

Follow the existing project folder hierarchy while generating the JSON configuration.

### SQL Files

The input SQL files are available in the `sql` folder.

Locate the corresponding SQL file based on the requested domain and use it as the primary input for generating the JSON configuration.

Example:

```text
sql/
    sales/
        customer.sql
        promotion.sql

    financials/
        invoice.sql
```

---

### JSON Configuration

Generate the JSON configuration in the corresponding `config` folder while maintaining the same subfolder structure as the SQL folder.

Example:

```text
sql/
    sales/
        customer.sql

↓

config/
    sales/
        customer.json
```

Do not change the folder hierarchy or naming convention.

---

### Gold Notebook

The Gold notebook for a domain can be found in the corresponding path under the `gold` folder.

Always locate and analyze the matching Gold notebook before generating the JSON configuration.

Example:

```text
sql/
    promotions/
        promotion.sql

↓

gold/
    promotions/
        promotion.py
```

The Gold notebook is the primary reference for:

- Existing transformation functions
- Expected input dataframe names
- Function execution sequence
- Business transformation logic

Always reuse the existing functions defined in the corresponding Gold notebook whenever possible.
## Function Reusability Rules

### Always reuse existing functions.

Before adding any transformation:

- Check whether the same functionality already exists in the Gold notebook.
- If an existing function satisfies the requirement, use it directly.
- Avoid creating duplicate transformation logic.

---

### Preserve existing dataframe names

This is a mandatory rule.

Use the same input dataframe names expected by the existing Gold notebook functions.

Example:

If an existing function expects

```python
promo_df
```

then use

```python
promo_df
```

inside the generated JSON.

Do **not** rename it to

```python
promo_dataframe
```

or

```python
source_df
```

Changing dataframe names may require creating unnecessary duplicate functions and reduce reusability.

---

## data_extract Section

- Identify all source tables from the SQL.
- Create source dataframe definitions.
- Preserve aliases only when required.
- Follow the same format used in existing JSON configuration files.

---

## data_transform Section

Generate transformation steps by:

- Mapping SQL operations to existing Gold notebook functions.
- Using reusable functions whenever available.
- Preserving the correct execution order.
- Avoiding duplicate logic.

Supported transformations include (but are not limited to):

- Join
- Filter
- Group By
- Aggregate
- Derived Columns
- Window Functions
- Pivot
- Unpivot
- Union
- Lookup
- Expression
- Date Functions
- String Functions

Always prefer an existing reusable function over generating new transformation logic.

---

## data_load Section

Always maintain the same structure used in existing JSON configuration files.

Include:

- Target table
- All mapped target columns
- Datatype

Do not omit any mapped target columns present in the SQL.

---

## Naming Conventions

Maintain the project's existing naming standards.

To avoid ambiguity:

- Use meaningful dataframe names.
- Rename intermediate dataframe columns names only when required to eliminate ambiguity.
- Follow the same naming style as the existing JSON configurations and corresponding gold notebook.

---

## Validation Checklist

Before generating the final JSON, verify that:

- Existing JSON structure is followed.
- Existing Gold notebook functions are reused.
- Existing dataframe names are preserved.
- Utility functions are referenced when applicable.
- No unnecessary transformation functions are introduced.
- All SQL transformations are represented.
- All target columns are included in the data_load section.
- Naming conventions remain consistent.
- The generated JSON follows the project's formatting standards.

---

## If Information Is Missing

If any required information cannot be inferred from the SQL or project references, do not make assumptions.

Instead, ask the user for clarification before generating the final JSON configuration.

Examples include:

- Missing source table information
- Ambiguous join conditions
- Unclear transformation logic
- Missing target table details
- Unclear load strategy

## Dependency & Auto-invoke Behavior

This skill may depend on a generated SQL file for the same market/domain. If a user requests `sql-to-json` but the corresponding SQL is not present and a Source-to-Target Mapping (STTM) is available, the agent SHOULD automatically invoke the `sttm-to-sql` skill first to produce the required SQL, then continue with `sql-to-json`.

Behavior rules:
- Check: If input references an STTM file or the repository contains an STTM for the requested target and no SQL file exists, trigger `sttm-to-sql` automatically.
- Consent: If the user explicitly asked to avoid generating SQL, prompt for confirmation before running `sttm-to-sql`.
- Output: After `sttm-to-sql` completes, re-run the normal `sql-to-json` flow against the newly generated SQL file.
- Failure: If `sttm-to-sql` fails or yields ambiguous input, stop and ask the user for clarification.

Implementation notes for agents:
- Use the repo paths `dataengineering/sttm/` and `dataengineering/sql/` to detect presence of STTM or SQL files.
- When auto-invoking, report back the generated SQL file path(s) to the user before proceeding with JSON generation.
- Preserve transactional safety: do not overwrite existing SQL files unless the user authorizes it.
