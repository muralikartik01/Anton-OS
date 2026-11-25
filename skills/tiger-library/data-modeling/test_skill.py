#!/usr/bin/env python3
"""
Self-contained test script for the data-modeling skill.

Validates:
  1. SKILL.md exists, has valid frontmatter, contains no organization-specific
     terms, and every file listed in its References table actually exists.
  2. The STTM CSV rules documented in references/csv-alignment-rules.md
     (28-field rows, view-column consistency) are correctly enforced by the
     validators below against both passing and failing fixtures.
  3. The DDL rules documented in references/ddl-generation-rules.md
     (CREATE TABLE IF NOT EXISTS, USING DELTA, TBLPROPERTIES, mandatory audit
     columns, view) are correctly enforced against passing and failing fixtures.

Run with: python test_skill.py
Exits 0 on success, 1 on any failure.
"""

import csv
import io
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
SKILL_FILE = SKILL_DIR / "SKILL.md"

BANNED_TERMS = [
    "PepsiCo", "XTNDFSystemId", "XTNDFReportingUnitId", "XTNMarketCode",
    "XTNCreatedTime", "XTNCreatedById", "XTNUpdatedTime", "XTNUpdatedById",
    "EDF", "CTX", "dtv_global_de", "Synapse", "Enterprise Data Foundation",
]
# These lines intentionally show an org-specific column name as an *example*
# of how to adapt the generic default (e.g. "instead of SourceSystemId") --
# they are allowed to mention a banned term for illustration.
ALLOWED_BANNED_TERM_CONTEXT = "instead of"

EXPECTED_FIELD_COUNT = 28
MANDATORY_AUDIT_COLUMNS = [
    "SourceSystemId", "ReportingUnitId",
    "CreatedTimestamp", "CreatedBy", "UpdatedTimestamp", "UpdatedBy",
]

_failures = []
_passed = 0


def check(name, condition, detail=""):
    global _passed
    if condition:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failures.append(name)
        print(f"  FAIL  {name}  {detail}")


# ---------------------------------------------------------------------------
# Validators that mirror the rules documented in the skill's reference files
# ---------------------------------------------------------------------------

def validate_sttm_csv(csv_text):
    """Return a list of validation issues for an STTM CSV body (data rows only, no header)."""
    issues = []
    rows = [r for r in csv_text.splitlines() if r.strip() != ""]
    data_lakes = set()
    view_names = set()
    for i, row in enumerate(rows, start=1):
        fields = next(csv.reader(io.StringIO(row)))
        if len(fields) != EXPECTED_FIELD_COUNT:
            issues.append(
                f"row {i}: expected {EXPECTED_FIELD_COUNT} fields, got {len(fields)}"
            )
            continue
        data_lakes.add(fields[25])   # col 26, 0-indexed 25
        view_names.add(fields[26])  # col 27, 0-indexed 26
    if len(data_lakes) > 1:
        issues.append(f"inconsistent 'Data Lake' (col 26) values across rows: {data_lakes}")
    if len(view_names) > 1:
        issues.append(f"inconsistent 'Common ViewName' (col 27) values across rows: {view_names}")
    return issues


def validate_ddl(ddl_text):
    """Return a list of validation issues for a generated DDL statement."""
    issues = []
    if "CREATE TABLE IF NOT EXISTS" not in ddl_text:
        issues.append("missing 'CREATE TABLE IF NOT EXISTS'")
    if "ALTER TABLE" in ddl_text:
        issues.append("contains forbidden 'ALTER TABLE'")
    if "USING DELTA" not in ddl_text:
        issues.append("missing 'USING DELTA'")
    if "delta.autoOptimize.optimizeWrite" not in ddl_text:
        issues.append("missing TBLPROPERTIES 'delta.autoOptimize.optimizeWrite'")
    if "delta.autoOptimize.autoCompact" not in ddl_text:
        issues.append("missing TBLPROPERTIES 'delta.autoOptimize.autoCompact'")
    for col in MANDATORY_AUDIT_COLUMNS:
        if col not in ddl_text:
            issues.append(f"missing mandatory audit column '{col}'")
    if "CREATE OR REPLACE VIEW" not in ddl_text:
        issues.append("missing consumption view ('CREATE OR REPLACE VIEW')")
    return issues


# ---------------------------------------------------------------------------
# Test fixtures (each row hand-verified to have exactly 28 fields)
# ---------------------------------------------------------------------------

VALID_STTM_ROWS = "\n".join([
    'Silver,catalog.schema,SalesOrder,ORDER_DATE,Order date,DATE,,YES,,,,,catalog.schema,TableName,OrderDate,date,NOT NULL,Yes,,,,Direct,,V1,,catalog.schema_vw,TableName_vw,OrderDate',
    ',,,,,,,,,,,,catalog.schema,TableName,CreatedTimestamp,timestamp,NOT NULL,,,,,"CURRENT_TIMESTAMP()",,V1,,catalog.schema_vw,TableName_vw,CreatedTimestamp',
    ',,,,,,,,,,,,catalog.schema,TableName,SourceSystemId,int,NOT NULL,,Yes,,892,"Default value: 892",,V1,,catalog.schema_vw,TableName_vw,SourceSystemId',
])

# Row 1 is missing one field (col 21 Default Value dropped before the DTR column)
INVALID_STTM_ROWS_MISSING_FIELD = "\n".join([
    'Silver,catalog.schema,SalesOrder,ORDER_DATE,Order date,DATE,,YES,,,,,catalog.schema,TableName,OrderDate,date,NOT NULL,Yes,,,Direct,,V1,,catalog.schema_vw,TableName_vw,OrderDate',
])

# Second row's view schema doesn't match the first row's
INVALID_STTM_ROWS_VIEW_MISMATCH = "\n".join([
    'Silver,catalog.schema,SalesOrder,ORDER_DATE,Order date,DATE,,YES,,,,,catalog.schema,TableName,OrderDate,date,NOT NULL,Yes,,,,Direct,,V1,,catalog.schema_vw,TableName_vw,OrderDate',
    ',,,,,,,,,,,,catalog.schema,TableName,CreatedTimestamp,timestamp,NOT NULL,,,,,"CURRENT_TIMESTAMP()",,V1,,catalog.other_vw,TableName_vw,CreatedTimestamp',
])

VALID_DDL = """
CREATE TABLE IF NOT EXISTS catalog.schema.TableName (
    OrderDate            date        NOT NULL  COMMENT 'Order date',
    SourceSystemId       int         NOT NULL  COMMENT 'Source system identifier',
    ReportingUnitId      int         NOT NULL  COMMENT 'Reporting unit identifier',
    CreatedTimestamp     timestamp   NOT NULL  COMMENT 'Record creation timestamp',
    CreatedBy            string      NOT NULL  COMMENT 'Created by user/process',
    UpdatedTimestamp     timestamp   NOT NULL  COMMENT 'Last update timestamp',
    UpdatedBy            string      NOT NULL  COMMENT 'Updated by user/process'
)
USING DELTA
PARTITIONED BY (SourceSystemId, ReportingUnitId)
COMMENT 'Table description from spec'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true'
);

CREATE OR REPLACE VIEW catalog.schema_vw.TableName_vw AS
SELECT * FROM catalog.schema.TableName;
"""

INVALID_DDL_MISSING_PIECES = """
ALTER TABLE catalog.schema.TableName ADD COLUMN Foo string;
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_skill_file_structure():
    print("SKILL.md structure")
    check("SKILL.md exists", SKILL_FILE.exists(), str(SKILL_FILE))
    if not SKILL_FILE.exists():
        return
    text = SKILL_FILE.read_text(encoding="utf-8")

    check("has YAML frontmatter delimiters", text.startswith("---"))
    check("frontmatter declares name: data-modeling", "name: data-modeling" in text)
    check("frontmatter declares description:", "description:" in text.split("---")[1])

    # Flag banned terms unless the line is clearly an illustrative
    # "your default (e.g. XTNDFSystemId instead of SourceSystemId)" example.
    bad_hits = []
    for term in BANNED_TERMS:
        for line in text.splitlines():
            if term.lower() in line.lower() and ALLOWED_BANNED_TERM_CONTEXT not in line:
                bad_hits.append((term, line.strip()))
    check("no organization-specific terms (outside adapt-your-own examples)", not bad_hits, bad_hits)

    # Every reference path mentioned in the References table must exist on disk.
    ref_paths = sorted(set(re.findall(r"`(references/[\w.\-]+)`", text)))
    check("References table is non-empty", len(ref_paths) > 0, ref_paths)
    missing = [p for p in ref_paths if not (SKILL_DIR / p).exists()]
    check("every referenced file exists on disk", not missing, missing)


def test_sttm_validator():
    print("STTM CSV validation rules")
    check("valid fixture passes", validate_sttm_csv(VALID_STTM_ROWS) == [])
    issues = validate_sttm_csv(INVALID_STTM_ROWS_MISSING_FIELD)
    check("missing-field fixture is rejected", len(issues) > 0, issues)
    issues = validate_sttm_csv(INVALID_STTM_ROWS_VIEW_MISMATCH)
    check("view-mismatch fixture is rejected", len(issues) > 0, issues)


def test_ddl_validator():
    print("DDL validation rules")
    check("valid DDL fixture passes", validate_ddl(VALID_DDL) == [])
    issues = validate_ddl(INVALID_DDL_MISSING_PIECES)
    check("invalid DDL fixture is rejected", len(issues) >= 5, issues)


def main():
    test_skill_file_structure()
    test_sttm_validator()
    test_ddl_validator()

    print()
    total = _passed + len(_failures)
    print(f"{_passed}/{total} checks passed")
    if _failures:
        print("Failures:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
