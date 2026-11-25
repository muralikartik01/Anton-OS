---
name: data-modeling
description: Creates target data models from technical specifications, including STTM mapping guidance and optional DDL generation. Use for creating tables, Gold tables, Gold modelling, and data models from technical specs.
---

# Data Modeling — STTM + DDL Generation

Generates a structured **STTM mapping** and optional **DDL SQL** for target Delta tables from technical specification files. No MCP or live database connection required.

## What This Skill Does

- Reads DAT and DRD CSV files from manifest-backed paths under `specs/{use_case}/csv/`
- Produces the structured mapping needed for a caller to write `specs/{use_case}/sttm.csv` or another manifest-backed STTM artifact
- Can also generate companion DDL when the caller requests schema output
- Applies repository modeling standards such as PascalCase columns, required audit fields, class words, and three-part naming when applicable

## Input Document Roles

| Document | Role | What to Extract |
|----------|------|----------------|
| **DAT** (Data Assessment Template) | **Primary — authoritative column source** | Physical column names, source table/schema, data types, nullability, example values, gap assessment results |
| **DRD** (Data Requirements Document) | **Supporting reference only — does not define columns** | Business transformation rules, attribute definitions (for comments), data quality expectations, business rules, filter conditions, merge keys, primary key constraints |

## When To Use

- Converting a technical spec or DRD/DAT analysis into an STTM and DDL
- Designing a new Gold table schema
- Creating source-to-target column mappings for an ETL pipeline

---

## Workflow

**Prerequisite**: Read the DAT and DRD CSV files from `specs/{use_case}/csv/` (as listed in the manifest) before proceeding.

### Step 1 — Parse the Technical Specification

Extract from the spec, cross-referencing **DAT** (attributes) and **DRD** (transformation rules):

- **From DAT**: Source system names, required identifier values such as `SourceSystemId` and `ReportingUnitId` (or your project's equivalent, e.g. `XTNDFSystemId`) when present, physical table names + schemas (`{catalog}.{schema}.{table}` or equivalent), column names (→ PascalCase target columns), data types, nullability, example values, gap status, target metadata, volume estimates. **The DAT is the sole authority for the final column list.**
- **From DRD** *(supporting context only — do NOT add or remove columns based on this document)*: attribute definitions (→ DDL COMMENTs), transformation rules (CAST/CASE WHEN/derive), data quality expectations (NOT NULL, valid values), filter/JOIN conditions, merge keys, business rules

### Step 2 — Determine Target Schema

- Use the target catalog, schema, and table metadata from the DAT, manifest, or other input specifications when those values are explicitly provided.
- If the specification only provides a base target schema, derive the Common View schema by appending `_vw` to that base schema.
- If target metadata is missing or ambiguous, stop and ask the user to confirm the target catalog and schema before generating outputs.

### Step 3 — Generate the STTM CSV

Read these references before writing:
- `references/STTM_Template.csv` — exact 28-column layout
- `references/sttm-field-mappings.md` — source/target column mappings, mandatory audit columns, and target-view consistency rules
- `references/csv-alignment-rules.md` — row alignment rules, FK/Default Value edge cases, worked examples

### Step 4 — Generate the DDL SQL

Read `references/ddl-generation-rules.md` for the CREATE TABLE template, partitioning strategy (volume-based), ZORDER guidance, and target-view pattern.

### Step 5 — Validate Before Saving

Read `references/validation-checklist.md` and verify all 10 checks pass before writing output files.

---

## References

| File | When to Read |
|------|-------------|
| `references/STTM_Template.csv` | Always — exact 28-column STTM layout |
| `references/sttm-field-mappings.md` | Step 3 — source/target/audit column mappings and view consistency rules |
| `references/csv-alignment-rules.md` | Step 3 — CSV row alignment, FK/Default Value edge cases, worked examples |
| `references/ddl-generation-rules.md` | Step 4 — CREATE TABLE template, partitioning, ZORDER, Common View |
| `references/validation-checklist.md` | Step 5 — 10-point validation checklist for STTM + DDL |
| `references/Data-Modeling-Standards.md` | As needed — naming conventions, class words, entity/attribute standards |
