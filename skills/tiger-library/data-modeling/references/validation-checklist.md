# Validation Checklist

Run these checks before saving the STTM CSV and DDL SQL files.

## STTM CSV Validation

1. **Field count**: Every data row has exactly **28 fields** (27 top-level commas)
2. **View consistency**: All Gold Common View `Data Lake` (col 26) and `Common ViewName` (col 27) entries are identical across all rows
3. **PascalCase class words**: All target column names use PascalCase and end with an approved class word (see `Data-Modeling-Standards.md` §4.4)
4. **Audit columns present**: Mandatory audit columns appear in both STTM and DDL
5. **Primary key completeness**: Primary key includes your project's scoping identifiers (e.g. `SourceSystemId` and `ReportingUnitId`)

## DDL SQL Validation

6. **CREATE TABLE IF NOT EXISTS** syntax used (never ALTER)
7. **USING DELTA** clause present
8. **TBLPROPERTIES** include `delta.autoOptimize.optimizeWrite` and `delta.autoOptimize.autoCompact`
9. **COMMENT** on every column matches the Column Description from STTM
10. **Common View** (`CREATE OR REPLACE VIEW`) appended after the CREATE TABLE
