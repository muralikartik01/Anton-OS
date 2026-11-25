#!/usr/bin/env python3
"""
eval_lineage.py — Evaluation harness for Program lineage JSON (DO NOT MODIFY).

Validates hierarchical lineage JSON against Program schema. This file contains
ground-truth evaluation checks. The agent runs this after every generation
attempt but NEVER edits it.

Usage:
    python3 eval_lineage.py <lineage_json>

    <lineage_json>  Path to the Program lineage JSON file to validate

Output:
    Prints check results to stdout.
    Appends a TSV row to lineage_eval_results.tsv in the current directory.

Exit codes:
    0 = all checks passed
    1 = one or more checks failed
    2 = critical error (invalid JSON, missing file, etc.)
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Constants — evaluation schema (do not modify)
# ---------------------------------------------------------------------------

REQUIRED_METADATA_KEYS = {
    "version", "created_date", "description", "project", "project_full_name",
}

REQUIRED_MARKET_KEYS = {
    "market_code", "market_name", "business_unit_name", "business_unit_key", "gold_tables",
}

REQUIRED_GOLD_TABLE_KEYS = {
    "gold_table_name", "gold_table_full_name", "pipeline_name", "sector_name",
    "market_name", "load_type", "workflow_name", "notebook_path", "schedule",
    "module", "table_type", "dq_config", "SourceSystemId", "ReportingUnitId", "Sources",
}

REQUIRED_SCHEDULE_KEYS = {"frequency", "day", "hour", "minute"}

REQUIRED_DQ_CONFIG_KEYS = {"dq_flag"}

VALID_SOURCE_TYPES = {"Silver", "Gold", "Bronze", "Parquet", "Reference"}
VALID_LOAD_TYPES = {"upsert", "append", "overwrite_partition", "overwrite", "scd2", "delete_insert", "parquet_overwrite"}
VALID_TABLE_TYPES = {"Dimension", "Fact", "Reference"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Eval Checks
# ---------------------------------------------------------------------------

def check_1_metadata_structure(data):
    """Validate lineage_metadata section."""
    failures = []
    
    if "lineage_metadata" not in data:
        failures.append("Missing 'lineage_metadata' top-level key")
        return failures
    
    metadata = data["lineage_metadata"]
    missing_keys = REQUIRED_METADATA_KEYS - set(metadata.keys())
    if missing_keys:
        failures.append(f"lineage_metadata missing required keys: {missing_keys}")
    
    # Validate version format
    version = metadata.get("version", "")
    if not re.match(r'^\d+\.\d+$', version):
        failures.append(f"lineage_metadata.version '{version}' must match format 'X.Y'")
    
    # Validate created_date format
    created_date = metadata.get("created_date", "")
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', created_date):
        failures.append(f"lineage_metadata.created_date '{created_date}' must match format 'YYYY-MM-DD'")
    
    # Validate project field is present (rename to match your organization's naming convention)
    project = metadata.get("project", "")
    if not project:
        failures.append("lineage_metadata.project must not be empty")
    
    return failures


def check_2_markets_structure(data):
    """Validate markets array structure."""
    failures = []
    
    if "markets" not in data:
        failures.append("Missing 'markets' top-level key")
        return failures
    
    markets = data["markets"]
    if not isinstance(markets, list):
        failures.append("'markets' must be an array")
        return failures
    
    if len(markets) == 0:
        failures.append("'markets' array is empty")
    
    for i, market in enumerate(markets):
        missing_keys = REQUIRED_MARKET_KEYS - set(market.keys())
        if missing_keys:
            failures.append(f"Market {i} (code={market.get('market_code','?')}) missing keys: {missing_keys}")
        
        # Validate gold_tables is an array
        if "gold_tables" in market and not isinstance(market["gold_tables"], list):
            failures.append(f"Market {i} (code={market.get('market_code','?')}): gold_tables must be an array")
    
    return failures


def check_3_gold_tables_structure(data):
    """Validate gold_tables array structure within each market."""
    failures = []
    
    markets = data.get("markets", [])
    for market_idx, market in enumerate(markets):
        market_code = market.get("market_code", "?")
        gold_tables = market.get("gold_tables", [])
        
        for table_idx, table in enumerate(gold_tables):
            table_name = table.get("gold_table_name", "?")
            pipeline_name = table.get("pipeline_name", "?")
            
            # Check required keys
            missing_keys = REQUIRED_GOLD_TABLE_KEYS - set(table.keys())
            if missing_keys:
                failures.append(f"Market={market_code}, Table={table_name}, Pipeline={pipeline_name}: missing keys {missing_keys}")
            
            # Validate pipeline_name starts with PL_
            if "pipeline_name" in table and not table["pipeline_name"].startswith("PL_"):
                failures.append(f"Market={market_code}, Table={table_name}: pipeline_name must start with 'PL_'")
            
            # Validate load_type is valid
            load_type = table.get("load_type", "")
            if load_type and load_type not in VALID_LOAD_TYPES:
                failures.append(f"Market={market_code}, Table={table_name}: invalid load_type '{load_type}'")
            
            # Validate table_type is valid
            table_type = table.get("table_type", "")
            if table_type and table_type not in VALID_TABLE_TYPES:
                failures.append(f"Market={market_code}, Table={table_name}: invalid table_type '{table_type}'")
            
            # Validate schedule structure
            schedule = table.get("schedule", {})
            if isinstance(schedule, dict):
                missing_sched_keys = REQUIRED_SCHEDULE_KEYS - set(schedule.keys())
                if missing_sched_keys:
                    failures.append(f"Market={market_code}, Table={table_name}: schedule missing keys {missing_sched_keys}")
            
            # Validate dq_config structure
            dq_config = table.get("dq_config", {})
            if isinstance(dq_config, dict):
                missing_dq_keys = REQUIRED_DQ_CONFIG_KEYS - set(dq_config.keys())
                if missing_dq_keys:
                    failures.append(f"Market={market_code}, Table={table_name}: dq_config missing keys {missing_dq_keys}")
                
                dq_flag = dq_config.get("dq_flag", "")
                if dq_flag and dq_flag not in ("Y", "N"):
                    failures.append(f"Market={market_code}, Table={table_name}: dq_flag must be 'Y' or 'N'")
            
            # Validate Sources is an array
            if "Sources" in table and not isinstance(table["Sources"], list):
                failures.append(f"Market={market_code}, Table={table_name}: Sources must be an array")
    
    return failures


def check_4_sources_structure(data):
    """Validate Sources array structure and source table types."""
    failures = []
    
    markets = data.get("markets", [])
    for market in markets:
        market_code = market.get("market_code", "?")
        gold_tables = market.get("gold_tables", [])
        
        for table in gold_tables:
            table_name = table.get("gold_table_name", "?")
            sources = table.get("Sources", [])
            
            if len(sources) == 0:
                failures.append(f"Market={market_code}, Table={table_name}: has zero sources (orphaned table)")
            
            for source_idx, source in enumerate(sources):
                # Validate Source_Table_Type is present and valid
                source_type = source.get("Source_Table_Type", "")
                if not source_type:
                    failures.append(f"Market={market_code}, Table={table_name}, Source {source_idx}: missing Source_Table_Type")
                elif source_type not in VALID_SOURCE_TYPES:
                    failures.append(f"Market={market_code}, Table={table_name}, Source {source_idx}: invalid Source_Table_Type '{source_type}'")
                
                # For Unity Catalog sources (Silver/Gold/Bronze), validate Table_Name
                if source_type in ("Silver", "Gold", "Bronze"):
                    table_name_field = source.get("Table_Name", "")
                    if not table_name_field:
                        failures.append(f"Market={market_code}, Table={table_name}, Source {source_idx}: Unity Catalog source missing Table_Name")
                    elif not re.match(r'^{env}_[\w]+_\d+\.[\w]+\.[\w]+$', table_name_field):
                        failures.append(f"Market={market_code}, Table={table_name}, Source {source_idx}: Table_Name '{table_name_field}' does not match 3-part UC naming")
                
                # For Parquet sources, validate Source_Path
                if source_type == "Parquet":
                    source_path = source.get("Source_Path", "")
                    if not source_path:
                        failures.append(f"Market={market_code}, Table={table_name}, Source {source_idx}: Parquet source missing Source_Path")
                    elif not source_path.startswith("abfss://"):
                        failures.append(f"Market={market_code}, Table={table_name}, Source {source_idx}: Source_Path should start with 'abfss://'")
                
                # Validate Filters_Used is an array (if present)
                if "Filters_Used" in source and not isinstance(source["Filters_Used"], list):
                    failures.append(f"Market={market_code}, Table={table_name}, Source {source_idx}: Filters_Used must be an array")
    
    return failures


def check_5_system_id_reference(data):
    """Validate system_id_reference structure."""
    failures = []
    
    if "system_id_reference" not in data:
        # This section is optional, so just warn
        return []
    
    sys_id_ref = data["system_id_reference"]
    if "system_ids" in sys_id_ref:
        system_ids = sys_id_ref["system_ids"]
        if not isinstance(system_ids, list):
            failures.append("system_id_reference.system_ids must be an array")
        else:
            for idx, sys_id_entry in enumerate(system_ids):
                if "SourceSystemId" not in sys_id_entry:
                    failures.append(f"system_id_reference.system_ids[{idx}]: missing SourceSystemId")
                if "ReportingUnitId" not in sys_id_entry:
                    failures.append(f"system_id_reference.system_ids[{idx}]: missing ReportingUnitId")
    
    return failures


# ---------------------------------------------------------------------------
# Results tracking
# ---------------------------------------------------------------------------

def append_results_tsv(run_results, notes=""):
    """Append a row to lineage_eval_results.tsv."""
    tsv_path = "lineage_eval_results.tsv"
    header = "run_id\ttimestamp\tcheck_1_metadata\tcheck_2_markets\tcheck_3_gold_tables\tcheck_4_sources\tcheck_5_sys_id_ref\tstatus\tnotes\n"

    # Determine run_id
    run_id = 1
    if os.path.exists(tsv_path):
        with open(tsv_path, "r") as f:
            lines = f.readlines()
            # Count non-header, non-empty lines
            data_lines = [l for l in lines[1:] if l.strip()]
            run_id = len(data_lines) + 1
    else:
        with open(tsv_path, "w") as f:
            f.write(header)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    c1 = "PASS" if run_results["check_1"] == 0 else f"FAIL({run_results['check_1']})"
    c2 = "PASS" if run_results["check_2"] == 0 else f"FAIL({run_results['check_2']})"
    c3 = "PASS" if run_results["check_3"] == 0 else f"FAIL({run_results['check_3']})"
    c4 = "PASS" if run_results["check_4"] == 0 else f"FAIL({run_results['check_4']})"
    c5 = "PASS" if run_results["check_5"] == 0 else f"FAIL({run_results['check_5']})"

    all_pass = all(v == 0 for v in run_results.values())
    status = "pass_all" if all_pass else "partial" if any(v == 0 for v in run_results.values()) else "fail"

    row = f"{run_id}\t{timestamp}\t{c1}\t{c2}\t{c3}\t{c4}\t{c5}\t{status}\t{notes}\n"
    with open(tsv_path, "a") as f:
        f.write(row)

    return run_id, status


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <lineage_json>")
        print(f"  Example: {sys.argv[0]} Copilot/LineageConfigJSON/Example_Lineage_Config.json")
        sys.exit(2)

    json_path = sys.argv[1]

    if not os.path.isfile(json_path):
        print(f"ERROR: Lineage JSON not found: {json_path}")
        sys.exit(2)

    try:
        data = load_json(json_path)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}")
        sys.exit(2)

    print(f"Loaded lineage JSON from {json_path}")
    print("=" * 70)

    # Run checks
    c1_failures = check_1_metadata_structure(data)
    c2_failures = check_2_markets_structure(data)
    c3_failures = check_3_gold_tables_structure(data)
    c4_failures = check_4_sources_structure(data)
    c5_failures = check_5_system_id_reference(data)

    # Count gold tables
    total_tables = sum(len(m.get("gold_tables", [])) for m in data.get("markets", []))
    
    # Print results
    print(f"\nTotal Markets: {len(data.get('markets', []))}")
    print(f"Total Gold Tables: {total_tables}")
    print("=" * 70)
    
    print(f"\nCheck 1 — Metadata Structure: {'PASS' if not c1_failures else f'FAIL ({len(c1_failures)} issues)'}")
    for f in c1_failures[:10]:
        print(f"  {f}")
    if len(c1_failures) > 10:
        print(f"  ... and {len(c1_failures) - 10} more")

    print(f"\nCheck 2 — Markets Structure: {'PASS' if not c2_failures else f'FAIL ({len(c2_failures)} issues)'}")
    for f in c2_failures[:10]:
        print(f"  {f}")
    if len(c2_failures) > 10:
        print(f"  ... and {len(c2_failures) - 10} more")

    print(f"\nCheck 3 — Gold Tables Structure: {'PASS' if not c3_failures else f'FAIL ({len(c3_failures)} issues)'}")
    for f in c3_failures[:10]:
        print(f"  {f}")
    if len(c3_failures) > 10:
        print(f"  ... and {len(c3_failures) - 10} more")

    print(f"\nCheck 4 — Sources Structure: {'PASS' if not c4_failures else f'FAIL ({len(c4_failures)} issues)'}")
    for f in c4_failures[:10]:
        print(f"  {f}")
    if len(c4_failures) > 10:
        print(f"  ... and {len(c4_failures) - 10} more")

    print(f"\nCheck 5 — System ID Reference: {'PASS' if not c5_failures else f'FAIL ({len(c5_failures)} issues)'}")
    for f in c5_failures[:10]:
        print(f"  {f}")
    if len(c5_failures) > 10:
        print(f"  ... and {len(c5_failures) - 10} more")

    # Summary
    run_results = {
        "check_1": len(c1_failures),
        "check_2": len(c2_failures),
        "check_3": len(c3_failures),
        "check_4": len(c4_failures),
        "check_5": len(c5_failures),
    }

    all_pass = all(v == 0 for v in run_results.values())

    print("\n" + "=" * 70)
    if all_pass:
        print("✓ ALL CHECKS PASSED")
    else:
        print(f"✗ {sum(1 for v in run_results.values() if v > 0)} / 5 checks FAILED")

    # Record results
    run_id, status = append_results_tsv(run_results, notes=os.path.basename(json_path))
    print(f"Results logged to lineage_eval_results.tsv (run_id={run_id}, status={status})")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()

def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <lineage_json> <configs_dir>")
        print(f"  Example: {sys.argv[0]} gold_to_silver_lineage_ND.json databricks-de/Configs")
        sys.exit(2)

    json_path = sys.argv[1]
    configs_dir = sys.argv[2]

    if not os.path.isfile(json_path):
        print(f"ERROR: Lineage JSON not found: {json_path}")
        sys.exit(2)

    if not os.path.isdir(configs_dir):
        print(f"ERROR: Configs directory not found: {configs_dir}")
        sys.exit(2)

    data = load_json(json_path)
    if not isinstance(data, list):
        print("ERROR: Lineage JSON root must be a list")
        sys.exit(2)

    print(f"Loaded {len(data)} entries from {json_path}")
    print(f"Scanning configs in {configs_dir}")
    print("=" * 70)

    # Run checks
    c1_failures = check_1_project_name(data)
    c2_failures = check_2_schema_compliance(data)
    c3_failures = check_3_mandatory_ids(data)
    c4_failures, c4_info, config_count, json_count, file_count = check_4_completeness(data, configs_dir)

    # Print results
    print(f"\nCheck 1 — Project Name Populated: {'PASS' if not c1_failures else f'FAIL ({len(c1_failures)} issues)'}")
    for f in c1_failures[:10]:
        print(f"  {f}")

    print(f"\nCheck 2 — Schema Compliance: {'PASS' if not c2_failures else f'FAIL ({len(c2_failures)} issues)'}")
    for f in c2_failures[:10]:
        print(f"  {f}")

    print(f"\nCheck 3 — Mandatory IDs: {'PASS' if not c3_failures else f'FAIL ({len(c3_failures)} issues)'}")
    for f in c3_failures[:10]:
        print(f"  {f}")

    print(f"\nCheck 4 — Completeness: {'PASS' if not c4_failures else f'FAIL ({len(c4_failures)} missing)'}")
    for f in c4_failures[:10]:
        print(f"  {f}")
    for info in c4_info[:5]:
        print(f"  (info) {info}")
    print(f"  Config (table,market) pairs: {config_count}")
    print(f"  JSON (table,market) pairs:   {json_count}")
    print(f"  Config files scanned:        {file_count}")

    # Summary
    print("\n" + "=" * 70)
    all_pass = not any([c1_failures, c2_failures, c3_failures, c4_failures])
    if all_pass:
        print("RESULT: ALL 4 CHECKS PASSED")
        print("\n>>> NEXT STEP: Proceed to Phase 3 (IMPROVE) — update references/learnings.md")
        print("    with any new edge cases, catalog mappings, or project name confirmations")
        print("    discovered during this run.")
    else:
        failed = []
        if c1_failures: failed.append("1-Project")
        if c2_failures: failed.append("2-Schema")
        if c3_failures: failed.append("3-MandatoryIDs")
        if c4_failures: failed.append("4-Completeness")
        print(f"RESULT: FAILED checks: {', '.join(failed)}")

        # Actionable hints for the agent
        print("\n>>> HINTS FOR NEXT ITERATION:")
        if c1_failures:
            print("  [Check 1] Ask the user to confirm Project and SubProject names.")
            print("            Then update all entries and re-run eval.")
        if c2_failures:
            print("  [Check 2] Some entries have missing keys. Review the JSON schema at")
            print("            references/lineage_schema.json and ensure every entry has")
            print("            all required top-level and Source-level keys.")
        if c3_failures:
            print("  [Check 3] Sources with empty SourceSystemId or ReportingUnitId:")
            print("            1. Re-read the config file's prod filter string")
            print("            2. Try regex: SourceSystemId\\s*=\\s*'?(\\d+)")
            print("            3. Fall back to config-level SourceSystemId / ReportingUnitId")
            print("            4. If still empty → ASK USER for those specific entries")
            print("            5. Document the fix in references/learnings.md")
        if c4_failures:
            print("  [Check 4] Config files exist that have no matching JSON entry.")
            print("            Re-read the missed config files and add entries.")
            print("            Watch for the datatype_cast trap: filter out matches where")
            print("            the value is a Python type ('string','int','double','date','timestamp').")

    # Log to TSV
    run_results = {
        "check_1": len(c1_failures),
        "check_2": len(c2_failures),
        "check_3": len(c3_failures),
        "check_4": len(c4_failures),
    }
    notes_parts = []
    if c3_failures:
        notes_parts.append(f"Missing IDs: {c3_failures[0]}")
    if c4_failures:
        notes_parts.append(f"Missing tables: {c4_failures[0]}")
    run_id, status = append_results_tsv(run_results, "; ".join(notes_parts)[:200])
    print(f"\nLogged as run_id={run_id}, status={status} in lineage_eval_results.tsv")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
