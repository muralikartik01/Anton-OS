# Skill 08: Code Review

## Overview
Automated code review for Databricks notebooks that validates adherence to Tiger coding standards, identifies performance issues, and provides actionable recommendations for improvement.

## What It Does
- ✅ Analyzes Databricks notebooks (`.py` or `.ipynb` files)
- ✅ Checks compliance with Tiger Data Engineering Standards
- ✅ Identifies performance and optimization opportunities
- ✅ Detects security and maintenance issues
- ✅ Validates proper use of Audit and DQ Frameworks
- ✅ Generates detailed CSV report with line-specific recommendations

## When to Use
- Before submitting a Pull Request (PR)
- After generating code with Skill 07 (Code Build)
- When refactoring existing notebooks
- During regular code quality audits
- Before deploying to production

## How to Use

### Quick Start
Simply provide the notebook path or have it open in your editor:

```
code review databricks/ProductTeardown/NB_PTD_Silver_to_Gold.py
```

Or for multiple notebooks:

```
pr review databricks/SCM/*.py
```

### Activation Commands
Any of these commands will trigger the code review:
- `code review`
- `review code`
- `pr review`
- `pull request`
- `check code quality`
- `validate notebook`

## What Gets Checked

### 1. Notebook Structure & Organization ⚙️
- Proper naming convention: `NB_<Sector>_<Functionality>_<Purpose>.py`
- Complete header block with metadata
- Change history and ADO references
- Gold table names and merge criteria

### 2. Audit Framework 📊
- Audit logging at start, success, and failure points
- Proper status codes ("I", "S", "F")
- Record counts included in success logs

### 3. Data Quality Framework ✅
- DQ framework implementation
- Valid product_name, SectorName, MarketName
- Proper DataAsset naming convention
- Blocking rules validation

### 4. Code Quality & Standards 📝
- No `display()`, `show()`, or `count()` in production code
- No hardcoded values (SystemId, ReportingUnitId, etc.)
- PEP8 compliance (formatting, indentation)
- Proper docstrings and comments
- Meaningful variable names
- Maximum 120 characters per line
- Maximum 200 lines per method
- Maximum 5 function parameters

### 5. Performance & Optimization 🚀
- No UDFs (use native Spark functions)
- No Pandas DataFrames (use Spark DataFrames)
- No DataFrame to RDD conversions
- Use `select()` instead of multiple `withColumn()` calls
- Avoid `SELECT *` in queries
- Proper broadcast joins for small tables
- Appropriate data partitioning (1GB per partition)

### 6. Unity Catalog & Data Handling 🗄️
- Three-part table names: `catalog.schema.table`
- No Hive metastore references
- Proper Unity Catalog usage

### 7. Parameters & Configuration ⚙️
- All mandatory parameters present
- No unused parameters
- No hardcoded configuration values

### 8. Error Handling & Logging 🔍
- Try/catch blocks for error handling
- Errors logged to NoteBookAuditLog_CL
- Exceptions propagated properly
- No `print()` statements (use logging module)

### 9. Security & Best Practices 🔒
- Sensitive data stored in secure vault
- No hardcoded credentials or keys
- SQL statements assigned to variables

## Output

### CSV Report Structure
The code review generates a CSV file with the following columns:

| Column | Description |
|--------|-------------|
| **Category** | Guideline category (e.g., "Code Quality", "Performance") |
| **Criticality** | CRITICAL / HIGH / MEDIUM / LOW |
| **Line_Number** | Exact line number where issue occurs |
| **Issue_Description** | Clear description of the violation |
| **Current_Code** | Code snippet showing the issue |
| **Suggested_Fix** | Recommended code change |
| **Recommendation** | Detailed explanation and best practice reference |

### Criticality Levels

**🔴 CRITICAL** (Must fix before merge):
- Production code with `display()` / `show()` / `count()`
- Hardcoded SystemId or ReportingUnitId
- Missing audit framework
- Security violations
- Hive metastore usage

**🟠 HIGH** (Fix before production):
- UDF usage instead of native Spark functions
- Pandas DataFrames instead of Spark
- Missing partitioning for large tables
- Missing DQ framework
- `SELECT *` in production code

**🟡 MEDIUM** (Should fix):
- PEP8 violations
- Missing docstrings
- Unused imports/variables
- Non-standard naming conventions
- Lines exceeding 120 characters

**🟢 LOW** (Nice to have):
- Incomplete header documentation
- Missing STTM links
- Minor style improvements

### Output Location
```
Output/CodeReview/{NotebookName}_CodeReview_v1_{timestamp}.csv
```

### Example Output
```csv
Category,Criticality,Line_Number,Issue_Description,Current_Code,Suggested_Fix,Recommendation
Code Quality,CRITICAL,45,"display() command in production code","display(df_gold)","# Remove display() or use logging: logger.info(f'Rows: {df_gold.count()}')","Production notebooks should not use display(). Use logging for debugging info."
Performance,HIGH,78,"Multiple withColumn() calls","df = df.withColumn('col1', ...).withColumn('col2', ...)","df = df.select('*', expr('...').alias('col1'), expr('...').alias('col2'))","Use select() with multiple columns instead of chaining withColumn() for better performance."
```

## Example Scenarios

### Scenario 1: Single Notebook Review
```
User: "code review databricks/ProductTeardown/NB_PTD_Silver_to_Gold.py"

Copilot: [Analyzes notebook]
Code Review Summary for: NB_PTD_Silver_to_Gold.py
===============================================
Total Issues Found: 12
  - CRITICAL: 2
  - HIGH: 4
  - MEDIUM: 5
  - LOW: 1

Top 5 Most Critical Issues:
1. [Line 45] display() command in production code
2. [Line 67] Hardcoded SystemId value
3. [Line 89] Missing audit log call at completion
4. [Line 120] UDF usage - use built-in Spark function
5. [Line 145] Multiple withColumn() calls affecting performance

Output saved to: Output/CodeReview/NB_PTD_Silver_to_Gold_CodeReview_v1_20260222_143022.csv
```

### Scenario 2: Post-Code Generation Review
```
User: "generate notebook for STTM" [Skill 07 generates code]
User: "review the generated code"

Copilot: [Reviews generated notebook and validates against standards]
```

### Scenario 3: PR Review for Multiple Files
```
User: "pr review databricks/SCM/"

Copilot: [Reviews all notebooks in the folder and generates individual CSV reports]
```

## Integration with Other Skills

This skill works seamlessly with:
- **Skill 07 (Code Build)**: Review generated notebooks automatically
- **Skill 11 (Publish to Confluence)**: Ensure code quality before documentation
- **Skill 20 (Code Optimization)**: Identify optimization opportunities

## Best Practices

### Before Submitting PR
1. Run code review on all modified notebooks
2. Address all CRITICAL issues immediately
3. Fix HIGH priority issues before merge
4. Document any intentional exceptions to standards

### Regular Code Quality Checks
- Schedule periodic reviews of existing notebooks
- Track trends in issue types and criticality
- Use reports to identify training needs

### Review Output Usage
- Import CSV into Excel/Power BI for analysis
- Track resolution of issues over time
- Share reports with team for knowledge sharing

## Troubleshooting

**Issue**: "Unable to parse notebook file"
- **Solution**: Ensure the notebook is valid Python/Jupyter format

**Issue**: "No violations found but code clearly has issues"
- **Solution**: Check that ReviewChecklist.md is up to date

**Issue**: "Too many LOW priority items cluttering the report"
- **Solution**: Request focus on specific criticality: "review focusing on CRITICAL and HIGH issues only"

## Support & Feedback

For questions or to report issues with the code review skill:
- Create an ADO work item with tag `code-review-skill`
- Reach out to the Data Engineering Standards team

---

**Last Updated**: February 2026  
**Version**: 1.0  
**Maintained By**: Data Engineering Platform Team
