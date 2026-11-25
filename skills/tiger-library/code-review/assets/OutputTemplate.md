# Code Review Output Template

## Template CSV Structure

This file demonstrates the expected format for code review output CSV files.

### Column Definitions

1. **Category**: The guideline category from ReviewChecklist.md
2. **Criticality**: CRITICAL / HIGH / MEDIUM / LOW
3. **Line_Number**: Exact line number(s) where the issue occurs
4. **Issue_Description**: Brief, clear description of what's wrong
5. **Current_Code**: The problematic code snippet (max 3 lines, escaped properly)
6. **Suggested_Fix**: Specific code replacement or fix
7. **Recommendation**: Detailed explanation with best practice reference

---

## Example: NB_Example_Silver_to_Gold_CodeReview_v1_20260222_143022.csv

```csv
Category,Criticality,Line_Number,Issue_Description,Current_Code,Suggested_Fix,Recommendation
Notebook Structure,HIGH,1-10,"Missing required header block","# Databricks notebook source
# Import libraries","# Databricks notebook source
# ==========================================
# Notebook: NB_PTD_Silver_to_Gold
# Description: Load Product Teardown data from Silver to Gold layer
# Creator: John Doe
# Created: 2026-01-15
# Change History: v1.0 - Initial creation (ADO-12345)
# Gold Tables: ptd_gold.product_teardown
# Merge Criteria: Upsert
# SystemId: 101 | ReportingUnitId: 201
# ==========================================","All notebooks must include a comprehensive header block with metadata. See ReviewChecklist.md Section 1.2 for required fields."
Code Quality,CRITICAL,45,"display() command in production code","df_gold.display()","# Remove or replace with logging:
logger.info(f'Gold records loaded: {df_gold.count()}')
# Or comment out for debugging only:
# df_gold.display()  # DEBUG ONLY","Production notebooks must not contain display() commands as they cause execution failures in automated pipelines. Use logging instead. Reference: ReviewChecklist.md Section 4."
Code Quality,CRITICAL,67,"Hardcoded SystemId value","where system_id = 101","where system_id = {SystemId}","SystemId must be passed as a parameter, never hardcoded. This violates Section 5 (Parameters) and Section 9 (Additional Requirements) of ReviewChecklist.md."
Audit Framework,CRITICAL,89,"Missing audit log at completion","df_gold.write.mode('overwrite').saveAsTable(target_table)","# Log successful completion
record_count = df_gold.count()
au.log_audit_data(
    PL_Name=PL_Name,
    nbk_name=nbk_name,
    status='S',
    record_count=record_count,
    error_message=None
)
df_gold.write.mode('overwrite').saveAsTable(target_table)","Every data write operation must be wrapped with audit logging. Call log_audit_data() with status='S' and record count upon successful completion. Reference: ReviewChecklist.md Section 2."
Performance,HIGH,120,"UDF usage detected","@udf(returnType=StringType())
def clean_text(text):
    return text.strip().upper()","# Use native Spark functions instead:
from pyspark.sql.functions import upper, trim
df = df.withColumn('clean_col', upper(trim(col('text_col'))))","UDFs have significant performance overhead. Use built-in Spark functions whenever possible. Reference: ReviewChecklist.md Section 7.1."
Performance,HIGH,145,"Multiple withColumn() calls","df = df.withColumn('col1', lit(1))
df = df.withColumn('col2', lit(2))
df = df.withColumn('col3', lit(3))","df = df.select(
    '*',
    lit(1).alias('col1'),
    lit(2).alias('col2'),
    lit(3).alias('col3')
)","Multiple withColumn() calls create separate transformations. Use a single select() with all columns for better performance. Reference: ReviewChecklist.md Section 8.2."
Unity Catalog,HIGH,178,"Missing Unity Catalog three-part name","df_source = spark.table('silver_table')","df_source = spark.table(f'{source_catalog_name}.{source_schema_name}.silver_table')","All table references must use Unity Catalog three-part naming: catalog.schema.table. Use parameters for catalog and schema names. Reference: ReviewChecklist.md Section 6."
Data Quality,HIGH,201,"Missing DQ framework implementation","df_validated = df_source","# Implement DQ validation
from dq_framework import validate_data
df_validated = validate_data(
    df=df_source,
    product_name='CTX',
    sector_name=SectorName,
    market_name=MarketName,
    dq_flag=dq_flag,
    blocking_rules=dq_blocking_dataset_name
)","All notebooks must implement the Data Quality framework with proper configuration. Reference: ReviewChecklist.md Section 3."
Code Quality,MEDIUM,234,"print() statement found","print(f'Processing {record_count} records')","logger.info(f'Processing {record_count} records')","Use logging module instead of print() statements for production code. Reference: ReviewChecklist.md Section 4."
Code Quality,MEDIUM,256,"Missing docstring for function","def transform_data(df, params):
    # Transform logic
    return df","def transform_data(df, params):
    '''
    Transform source data applying business rules.
    
    Args:
        df (DataFrame): Source Spark DataFrame
        params (dict): Transformation parameters
    
    Returns:
        DataFrame: Transformed DataFrame ready for Gold layer
    '''
    # Transform logic
    return df","All functions must include docstrings explaining purpose, parameters, and return values. Reference: ReviewChecklist.md Section 9."
Naming Convention,MEDIUM,278,"Non-PEP8 function name","def TransformData(df):","def transform_data(df):","Function names must use lowercase_with_underscores format per PEP8. Reference: ReviewChecklist.md Section 8.1."
Code Quality,MEDIUM,301,"Unused import","import pandas as pd
from pyspark.sql.functions import col","from pyspark.sql.functions import col","Remove unused imports. pandas is imported but never used. Also avoid Pandas DataFrames in Spark notebooks. Reference: ReviewChecklist.md Section 7.3."
Code Quality,MEDIUM,345,"Line exceeds 120 characters","df_filtered = df_source.filter((col('status') == 'ACTIVE') & (col('date') >= '2024-01-01') & (col('region').isin(['NORTH', 'SOUTH', 'EAST', 'WEST'])) & (col('amount') > 1000))","# Break into multiple lines
df_filtered = df_source.filter(
    (col('status') == 'ACTIVE') & 
    (col('date') >= '2024-01-01') & 
    (col('region').isin(['NORTH', 'SOUTH', 'EAST', 'WEST'])) & 
    (col('amount') > 1000)
)","Lines should not exceed 120 characters. Break long statements into multiple lines for readability. Reference: ReviewChecklist.md Section 7.1."
Parameters,HIGH,389,"Unused parameter declared","dbutils.widgets.text('unused_param', '')
no_of_periods = dbutils.widgets.get('no_of_periods_to_load')","# Remove unused parameter
no_of_periods = dbutils.widgets.get('no_of_periods_to_load')","Every declared parameter must be used in the notebook. Remove unused_param or implement its usage. Reference: ReviewChecklist.md Section 5."
Error Handling,CRITICAL,423,"Missing try-catch block","df_gold.write.mode('overwrite').saveAsTable(target_table)","try:
    df_gold.write.mode('overwrite').saveAsTable(target_table)
    au.log_audit_data(PL_Name, nbk_name, 'S', df_gold.count(), None)
except Exception as e:
    au.log_audit_data(PL_Name, nbk_name, 'F', 0, str(e))
    raise","All critical operations must be wrapped in try-catch blocks with proper error logging and exception propagation. Reference: ReviewChecklist.md Section 4."
Code Quality,LOW,456,"Single-letter variable in outer scope","x = df_source.count()
if x > 0:","record_count = df_source.count()
if record_count > 0:","Avoid single-letter variable names outside of simple loops. Use meaningful names. Reference: ReviewChecklist.md Section 8.2."
Documentation,LOW,489,"Missing STTM link in header","# Gold Tables: ptd_gold.product_teardown","# Gold Tables: ptd_gold.product_teardown
# STTM: Output/STTM_DDL_creation/ProductTeardown_STTM_v1.csv","Include link to STTM file in header documentation for traceability. Reference: ReviewChecklist.md Section 1.2."
```

---

## Summary Statistics

At the end of the CSV, include a summary section:

```csv

SUMMARY,,,,,
Total Issues,18,,,,
CRITICAL,4,,,,
HIGH,5,,,,
MEDIUM,6,,,,
LOW,3,,,,
```

---

## File Naming Convention

```
{NotebookName}_CodeReview_v{version}_{timestamp}.csv
```

**Example**: `NB_PTD_Silver_to_Gold_CodeReview_v1_20260222_143022.csv`

**Components**:
- `NotebookName`: Name of the reviewed notebook (without .py/.ipynb extension)
- `version`: Incremental version number (v1, v2, v3, etc.)
- `timestamp`: YYYYMMdd_HHmmss format

---

## CSV Formatting Rules

1. **Escaping**: Escape double quotes in code snippets by doubling them (`""`)
2. **Line Breaks**: Use semicolons or `\n` to represent line breaks within cells
3. **Code Truncation**: If code snippet exceeds 200 characters, truncate with "..."
4. **Sorting**: Sort by Criticality (CRITICAL → HIGH → MEDIUM → LOW), then by Line_Number ascending
5. **Empty Fields**: Use empty string (`""`) for fields with no data, never `NULL` or `N/A`

---

## Integration Notes

### Opening in Excel
- Excel will properly parse CSV with commas and quotes
- Code snippets with line breaks may expand cells
- Apply filters on Criticality column for prioritization

### Importing to Power BI
- Use "Get Data" → "Text/CSV"
- Set delimiter to comma
- Enable "Column headers" in first row

### Processing with Python
```python
import pandas as pd

df_review = pd.read_csv('NB_PTD_Silver_to_Gold_CodeReview_v1_20260222_143022.csv')

# Filter CRITICAL issues
critical = df_review[df_review['Criticality'] == 'CRITICAL']

# Group by Category
by_category = df_review.groupby('Category').size()
```

---

## Version History

- **v1.0** (2026-02-22): Initial template creation
- Aligned with ReviewChecklist.md standards
- Integrated with Skill 08 workflow
