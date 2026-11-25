---
name: code-review
---

# Skill 08: Code Review (Databricks Notebooks)

## Activation Keywords
`code review`, `pull request`, `pr`, `merge request`, `review`, `review code`, `check code`, `validate code`, `code quality`

## Purpose
This skill performs comprehensive code review of Databricks notebooks against Tiger coding standards, best practices, and performance guidelines. It identifies violations, performance issues, and maintenance concerns, then generates a detailed CSV report with actionable recommendations.

## Prerequisites
- Access to the notebook file(s) to be reviewed
- ReviewChecklist.md from `.github/skills/code-review/assets/`
- Copilot instructions with coding standards from `.github/copilot-instructions.md`

## Input Requirements
1. **Notebook Path(s)**: Absolute path to one or more `.py` or `.ipynb` Databricks notebook files
2. **Review Scope** (Optional): Specific areas to focus on (e.g., "performance only", "naming conventions", "all")

## Output Location
`Output/CodeReview/{NotebookName}_CodeReview_v{n}_{timestamp}.csv`

## Workflow

### Phase 1: Initialization and Setup
1. Load the notebook file(s) provided by the user
2. Load ReviewChecklist.md from `.github/skills/code-review/assets/`
3. Initialize review tracking structure with categories:
   - **Notebook Structure & Organization**
   - **Audit Framework Implementation**
   - **Data Quality Framework**
   - **Code Quality & Standards**
   - **Performance & Optimization (Basic)**
   - **PySpark Performance Optimization (Advanced)** ⚡
   - **Security Best Practices** ⚠️
   - **Unity Catalog & Data Handling**
   - **Parameters & Configuration**
   - **Error Handling**
   - **Naming Conventions**
   - **Documentation & Comments**

### Phase 2: Code Analysis
For each notebook, perform line-by-line analysis checking for:

#### 2.1 Notebook Structure (Header Block)
- ✅ Proper notebook naming: `NB_<Sector>_<Functionality>_<Purpose>.py`
- ✅ Complete header block with:
  - High-level description
  - Original creator
  - Creation date
  - Change history with ADO references
  - Gold Table Names Loaded
  - Source and Targets
  - Merge Criteria (Upsert/SCD/Append/Delete-Insert)
  - SystemId and ReportingID
  - STTM Links

#### 2.2 Audit Framework
- ✅ Calls to `log_audit_data()` at start (Status: "I")
- ✅ Calls to `log_audit_data()` at success (Status: "S") with record count
- ✅ Calls to `log_audit_data()` at failure (Status: "F")
- ❌ Missing audit calls in critical sections

#### 2.3 Data Quality Framework
- ✅ DQ framework implementation with:
  - `product_name = 'CTX'`
  - Valid `SectorName`: PBNA, PFNA, LATAM, Europe, AMESA, APAC
  - Full market description in `MarketName`
  - Preload DQ flag for blocking rules
- ✅ DataAsset naming: `<Program>_<Market>_<BLK/TRNS/RECN>_<Table/KPI>`

#### 2.4 Code Quality Standards
- ❌ `display()`, `show()`, or `count()` commands (production code violation)
- ❌ `print()` statements (should use logging)
- ❌ Hardcoded values (SystemId, ReportingUnitId, table names, etc.)
- ❌ Unused imports, variables, or code sections
- ❌ Lines exceeding 120 characters
- ❌ Methods exceeding 200 lines
- ❌ Files exceeding 500 lines
- ❌ Functions with more than 5 parameters
- ✅ PEP8 compliance (indentation, spacing, etc.)
- ❌ Missing docstrings for functions/classes
- ❌ Single-letter variable names (except in loops)

#### 2.5 Performance & Optimization (Basic)
- ❌ UDF usage (should use native Spark functions)
- ❌ Pandas DataFrames (should use Spark DataFrames)
- ❌ DataFrame to RDD conversion
- ❌ Multiple `withColumn()` calls (should use `select()`)
- ❌ `SELECT *` usage
- ❌ Missing broadcast hints for small table joins
- ❌ Data shuffling without necessity
- ❌ Missing partitioning for tables > 1GB
- ❌ Inappropriate partition sizes (should be ~1GB per partition)
- ❌ Recursive functions without break statements

#### 2.6 PySpark Performance Optimization (Advanced)
**Reference**: ReviewChecklist.md Section 11

**Caching & Persistence**:
- ❌ Missing `.cache()` for DataFrames reused multiple times
- ❌ Missing `.unpersist()` to release cached memory
- ❌ Unnecessary caching of single-use DataFrames
- ❌ Inappropriate storage levels (MEMORY_ONLY vs MEMORY_AND_DISK)

**Partition Management**:
- ❌ Missing `coalesce()` before writing small datasets (tiny file problem)
- ❌ Incorrect partition count relative to cluster cores
- ❌ Missing salting for skewed join keys
- ❌ Unbalanced partitions causing executor OOM

**Predicate Pushdown**:
- ❌ Filters applied after joins instead of before
- ❌ Missing partition column filtering in Delta reads
- ❌ `SELECT *` followed by filter instead of filtered subquery
- ❌ Not utilizing Z-ORDER columns in WHERE clauses

**Broadcast Joins**:
- ❌ Missing `broadcast()` hint for small dimension tables (< 10 MB)
- ❌ Sort-merge join used instead of broadcast join
- ❌ Attempting to broadcast large tables (> 2 GB) causing OOM

**Column Pruning**:
- ❌ Reading full table then selecting columns (should project in read)
- ❌ Selecting columns after join instead of before
- ❌ Not using nested column access for Parquet/Delta

**Window Functions**:
- ❌ Window functions without `partitionBy()` (unbounded window)
- ❌ Redundant window specifications
- ❌ Unbounded row ranges in window functions

**Delta Lake Optimization**:
- ❌ MERGE operations not using indexed columns
- ❌ Missing `OPTIMIZE` and `VACUUM` scheduling
- ❌ Missing partition pruning in MERGE conditions
- ❌ Low cardinality merge keys causing performance issues

**Aggregation & Shuffle**:
- ❌ Multiple aggregation passes that could be combined
- ❌ Using exact `count(distinct())` instead of `approx_count_distinct()`
- ❌ `repartition()` + `sort()` instead of `repartition(n, col)`
- ❌ Excessive shuffles (check via `explain()`)

**Explode Operations**:
- ❌ Multiple sequential `explode()` calls
- ❌ Exploding before filtering (should filter first)
- ❌ No cardinality estimation before explode

**Unnecessary Actions**:
- ❌ `.count()` for existence checks (use `.limit(1)`)
- ❌ `.collect()` on large DataFrames (> 1 GB)
- ❌ `.toPandas()` without row limits
- ❌ Iterative `.collect()` in loops

**Read Optimization**:
- ❌ Not filtering on partition columns during reads
- ❌ Reading entire table for small samples
- ❌ Using CSV instead of Parquet/Delta for large data

#### 2.7 Security Best Practices ⚠️ CRITICAL
**Reference**: ReviewChecklist.md Section 10

**Credential Management**:
- ❌ **CRITICAL**: Hardcoded passwords, API keys, connection strings
- ❌ **CRITICAL**: Not using `dbutils.secrets.get()` for sensitive values
- ❌ Secrets in comments or docstrings
- ❌ Base64-encoded credentials
- ❌ Invalid secret scope naming

**Secrets in Output**:
- ❌ **CRITICAL**: Secrets in logging statements or print
- ❌ Secrets in exception messages
- ❌ Connection strings exposed in error handling
- ❌ Unmasked passwords in debug output

**SQL Injection Prevention**:
- ❌ **CRITICAL**: f-strings with external inputs in `spark.sql()`
- ❌ `.format()` or `%` formatting in SQL with user input
- ❌ Unvalidated widget inputs in queries
- ❌ Missing whitelist validation for dynamic SQL

**PII/Sensitive Data**:
- ❌ PII in logging without masking/hashing
- ❌ PII in exception messages (email, SSN, credit card)
- ❌ Missing data classification tags for PII tables
- ❌ PII columns in test data (should use synthetic)

**Dynamic Code Execution**:
- ❌ **CRITICAL**: Use of `eval()` or `exec()`
- ❌ `__import__()` with dynamic module names
- ❌ `pickle.loads()` on untrusted data
- ❌ `compile()` with user input

**Data Access Control**:
- ❌ Direct file path access bypassing Unity Catalog ACLs
- ❌ `USE CATALOG` or `USE SCHEMA` commands (governance bypass)
- ❌ Missing three-part naming: `catalog.schema.table`
- ❌ Undocumented service principal permissions

**Network Security**:
- ❌ JDBC connections without `encrypt=true` or `ssl=true`
- ❌ HTTP instead of HTTPS for external APIs
- ❌ Missing private endpoint usage for Azure services

**Data Exfiltration**:
- ❌ Writes to unapproved external locations
- ❌ `.coalesce(1)` writes to external storage
- ❌ COPY INTO commands to external stages
- ❌ Missing audit logging for data exports

**Input Validation**:
- ❌ Missing whitelist validation for widget inputs
- ❌ No path traversal prevention
- ❌ Unvalidated numeric ranges for dates/periods
- ❌ Unsanitized special characters

**Token Management**:
- ❌ Hardcoded Azure SAS tokens or OAuth tokens
- ❌ Missing token expiration handling
- ❌ Tokens stored in variables that could be logged

**Library Security**:
- ❌ `%pip install` from untrusted repos
- ❌ Libraries not on approved list
- ❌ No CVE validation for library versions
- ❌ Typosquatting package names

#### 2.8 Unity Catalog & Data Handling
- ✅ Three-part table names: `catalog.schema.table`
- ❌ Hive metastore references (should use Unity Catalog)
- ❌ Missing Unity Catalog references

#### 2.9 Parameters
- ❌ Missing mandatory parameters (see ReviewChecklist.md section 5)
- ❌ Unused parameters
- ❌ Hardcoded values instead of parameters

#### 2.10 Error Handling
- ❌ Missing try/catch blocks
- ❌ Errors not logged to NoteBookAuditLog_CL
- ❌ Exceptions not propagated to calling layer

#### 2.11 Naming Conventions
- ❌ Function names not in lowercase_with_underscores
- ❌ Class names not in PascalCase
- ❌ Constants not in UPPERCASE_WITH_UNDERSCORES
- ❌ Non-meaningful variable names

### Phase 3: Criticality Assessment
Assign criticality levels based on impact:

**CRITICAL** (Blocking Issues - Security & Data Integrity):
- **Security violations**:
  - Hardcoded credentials, passwords, API keys, tokens
  - SQL injection vulnerabilities (f-strings with user input in spark.sql())
  - Use of `eval()` or `exec()` with user input
  - Secrets in logging or print statements
  - Direct file path access bypassing Unity Catalog ACLs
  - JDBC connections without encryption (encrypt=true)
  - Data writes to unapproved external locations
- **Data compliance**:
  - PII in logs without masking/hashing
  - Missing GDPR/CCPA compliance markers for regulated data
- **System integrity**:
  - Missing audit framework calls (log_audit_data)
  - Missing error handling in critical sections
  - Hive metastore usage instead of Unity Catalog
  - Production code with `display()`, `show()`, or `count()`
  - Hardcoded SystemId or ReportingUnitId

**HIGH** (Performance & Maintenance Risks):
- **Performance issues**:
  - UDF usage (should use native Spark functions)
  - Pandas DataFrames instead of Spark DataFrames
  - Missing partitioning for large tables (>1GB)
  - Multiple `withColumn()` calls instead of `select()`
  - `SELECT *` in production code
  - Missing broadcast hints for small dimension tables (< 10 MB)
  - Sort-merge joins on small tables
  - Filters applied after joins (should be before)
  - Missing `.unpersist()` causing memory leaks
  - `.collect()` on large DataFrames (> 1 GB)
  - Explode operations before filtering
  - Excessive shuffles (> 3 stages)
- **Security concerns**:
  - Unvalidated widget inputs in queries
  - Missing whitelist validation for user inputs
  - Base64-encoded credentials
  - HTTP instead of HTTPS for external APIs
  - `%pip install` from untrusted repos
- **Maintenance issues**:
  - Missing DQ framework implementation
  - Missing mandatory parameters
  - DataFrame to RDD conversion

**MEDIUM** (Code Quality & Standards):
- **Code quality**:
  - PEP8 violations (indentation, spacing)
  - Missing docstrings for functions/classes
  - Lines exceeding 120 characters
  - Methods exceeding 200 lines
  - Unused imports, variables, or code sections
  - Non-standard naming conventions
- **Performance optimization**:
  - Inappropriate partition sizes
  - Missing `coalesce()` before writing small datasets
  - Redundant window specifications
  - Missing partition pruning in MERGE conditions
  - Reading full table then selecting columns
  - Unnecessary caching of single-use DataFrames
- **Code patterns**:
  - `print()` instead of logging
  - Missing input validation for widget parameters
  - Non-meaningful variable names
  - SQL statements not assigned to variables

**LOW** (Documentation & Style):
- **Documentation**:
  - Incomplete header block
  - Missing STTM links
  - Missing data classification tags
  - Undocumented service principal permissions
- **Style & conventions**:
  - Single-letter variable names (outside loops)
  - Code comments not in markdown format
  - Missing schema validation documentation
  - Inconsistent code formatting

### Phase 4: Generate Recommendations
For each violation found, create a recommendation entry with:
1. **Category**: Which guideline category is violated
2. **Criticality**: CRITICAL / HIGH / MEDIUM / LOW
3. **Line Number**: Exact line number(s) where issue occurs
4. **Issue Description**: Clear description of the violation
5. **Current Code**: Code snippet showing the issue (max 3 lines)
6. **Suggested Fix**: Specific code change recommended
7. **Recommendation**: Detailed explanation and best practice reference

### Phase 5: Generate CSV Report
Create a CSV file with the following columns:
```csv
Category,Criticality,Line_Number,Issue_Description,Current_Code,Suggested_Fix,Recommendation
```

**CSV Output Rules**:
- Sort by Criticality (CRITICAL → HIGH → MEDIUM → LOW), then by Line Number
- Escape special characters in code snippets
- Truncate long code snippets with "..." if needed
- Include summary statistics at the bottom: total violations by criticality
- Generate filename: `{NotebookName}_CodeReview_v{n}_{YYYYMMDD_HHMMSS}.csv`
- Save to: `Output/CodeReview/`

### Phase 6: Summary Report
After generating the CSV, provide a text summary:
```
Code Review Summary for: {NotebookName}
===============================================
Total Issues Found: {count}
  - CRITICAL: {count}
  - HIGH: {count}
  - MEDIUM: {count}
  - LOW: {count}

Top 5 Most Critical Issues:
1. [Line {n}] {Issue Description}
2. [Line {n}] {Issue Description}
...

Output saved to: Output/CodeReview/{filename}.csv
```

## Example Usage

**User Request 1**: "Review this notebook"
*User provides path or has notebook open*

**User Request 2**: "code review databricks/ProductTeardown/NB_PTD_Silver_to_Gold.py"

**User Request 3**: "pr review for all notebooks in databricks/SCM/"

## Implementation Notes

### Multi-File Reviews
When multiple notebooks are provided:
1. Review each notebook individually
2. Generate separate CSV for each notebook
3. Optionally generate a consolidated summary CSV

### Context-Specific Rules
Some violations may have exceptions based on context:
- `display()` allowed in exploratory/debugging cells marked with comments
- Single-letter variables acceptable in simple list comprehensions
- Apply judgment when rules conflict with specific valid use cases

### Integration with Other Skills
This skill can be triggered:
- **After Skill 07** (Code Build) to validate generated notebooks
- **Before Skill 11** (Publish to Confluence) to ensure quality documentation
- **During PR reviews** in version control workflows

## Error Handling
If the notebook cannot be read or parsed:
1. Log the error
2. Create a CSV with single entry: "ERROR: Unable to parse notebook file"
3. Provide diagnostic information to user

## Success Criteria
✅ CSV file generated with all violations identified
✅ Each violation includes line number, description, and fix
✅ Criticality levels assigned appropriately
✅ Output saved to `Output/CodeReview/`
✅ Summary provided to user with top issues highlighted

## References
- `.github/skills/code-review/assets/ReviewChecklist.md`
- `.github/copilot-instructions.md` (Coding Standards section)
- PEP 8 Style Guide
- Databricks Best Practices Documentation
