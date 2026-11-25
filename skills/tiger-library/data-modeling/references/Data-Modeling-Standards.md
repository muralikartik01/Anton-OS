# Data Modeling Standards

## Overview

This document defines generic data modeling standards for Silver and Gold (or equivalent) layers in a medallion-style data platform. These standards ensure clarity, consistency, and scalability across data models for any organization or project. Naming conventions, audit column names, and governance details below are **defaults** — adjust them to match your project's actual conventions where the technical spec (DAT/DRD or equivalent) provides different values.

---

## 1. General Naming Convention Principles

- **Full-form names** in **PascalCase** (capitalize first letter of each word)
- **No underscores, spaces, or special characters**
- **No plurals** - always use singular form
- **No vague terms** like manage, process
- **Avoid abbreviations** unless names exceed 50 characters
- Abbreviations should come from a **centralized dictionary** when the project maintains one
- Names must be **descriptive yet concise**, max 50 characters, no redundancy

✅ **Acceptable**: CustomerRouteFrequency, ProductionLocation, EightOunceConversionFactor
❌ **Not Acceptable**: Cust_Rte_Freq, PRODUCT LOCATION, Storage-Location, 8OZConversion

---

## 2. Entity/Table Naming Standards

A logical entity name must:
1. Reflect business nature using business terms
2. Be descriptive, singular, clear and self-explanatory
3. Use minimum words that completely and uniquely label the concept
4. Not include source-specific surrogate keys as part of PK
5. Avoid application names unless the entity is application-specific

| Rule | Acceptable Example | Not Acceptable Example |
|------|-------------------|------------------------|
| Fully spell out words (unless > 50 chars) | CustomerRouteFrequency | Cust Rte Freq |
| Begin with alphabetic character | EightOunceConversionFactor | 8OZ Conversion Factor |
| Capitalize first letter of each word | ProductionLocation | PRODUCT LOCATION |
| No special characters | CustomerAccount | Customer's Account |
| PascalCase (no spaces/separators) | StorageLocation | Storage-Location |
| No company/brand names in column names | Location | CompanyLocation |

---

## 3. Entity Definitions

Entity definitions must describe what the entity represents, its business relevance, and a single instance — without restating the name or using vague filler like "This entity contains...".

**Example** — Entity: Route Profile
✅ "A structured business record that captures identifying, contact, and relationship details for a route that engages in customer transactions."

---

## 4. Attribute/Column Naming Standards

**Format**: `PrimeWord + Descriptor(s) + ClassWord`, e.g. `CustomerTaxExemptNumber`.

Attribute names must:
- Reflect business nature, use plain English, singular noun/phrase
- End with an approved class word
- Be clear, concise, and unique within the entity

**Class words** are mandatory on every target column. Reference `references/Classwords.csv` in this skill (or your project's own class-word dictionary). Common ones: `Amount`, `Date`, `Time`, `Code`, `Name`, `Number`, `Quantity`, `Indicator`, `Text`, `Id`, `Timestamp`, `Description`.

---

## 5. Attribute Definitions

Definitions must describe what the attribute is (not just where it's used), avoid restating the attribute name, include sample values for codes/flags, and identify derivation formulas for derived attributes.

**Flags**: Y/N. **Indicators**: fixed domain `Y`/`N`/`U`/`Z`/`-` (Yes/No/Unknown/Not Applicable/null).

---

## 6. Gold (Target) Table Naming Scenarios

| Scenario | Rule | Example |
|---|---|---|
| Reuse of Silver table | View in target schema with any required scoping filter | Silver `CustomerCore` → Gold `CustomerCore` |
| Derived from Silver table(s) | `{SubjectName}{Grain}{Summary}` | `InvoiceCustomerDailySummary` |
| Region/market/business-unit specific | `{Scope}{SubjectName}{Grain}{Summary}` | `RegionSalesCustomerMaterialMonthlySummary` |
| Bypasses Silver (system-specific) | Requires an approved architecture/governance exception | — |
| Manual file load | `{Manual}{Scope}{App}{SubjectArea}{Process}{TimeDimension}` | `ManualRegionSalesOrderDaily` |
| Third-party app round-trip | `{App}{SubjectArea}{Process}{TimeDimension}` | — |
| UI backend (staging) | `{App}{SubjectArea}{Process}{TimeDimension}` | — |

---

## 7. Keys and Identifiers

- Gold entities may reuse Silver business keys or define their own per requirement
- **Avoid creating new surrogate keys** in Gold unless the project explicitly requires them
- Primary Keys must be `NOT NULL` and uniquely identify the source record
- If the project uses system/reporting-unit scoping columns (e.g. `SourceSystemId`, `ReportingUnitId`), include them in the Primary Key; otherwise use a scope column such as `MarketCode`
- Partition keys: scoping columns (`MarketCode`, `SourceSystemId`, `ReportingUnitId`) plus a date column for larger tables; target ~1GB per partition; skip partitioning under 1GB

---

## 8. Mandatory Audit Columns (Defaults)

Replace these names with your project's existing audit-column convention if one is defined in the DAT/DRD or repo standards.

| Column Name | Type | Required | Purpose |
|-------------|------|----------|---------|
| **CountryIso2Code** | String | Recommended for transaction tables | Two-character ISO country code |
| **MarketCode** | String | Optional — if project scopes by market/region | Market/region/business-unit identifier |
| **SourceSystemId** | String/Int | Recommended | Identifier of the originating source system |
| **ReportingUnitId** | String/Int | Recommended | Reporting-unit identifier |
| **CreatedTimestamp** | Timestamp | Mandatory | Record creation timestamp |
| **CreatedBy** | String | Mandatory | User/process that created the record |
| **UpdatedTimestamp** | Timestamp | Mandatory | Record last-update timestamp |
| **UpdatedBy** | String | Mandatory | User/process that last updated the record |

These are audit columns, not business columns, and must be populated by the data engineering pipeline.

---

## 9. Common Model Guidelines

- Gold models should be usable across regions/markets/business units when requirements align; include `MarketCode`/`CountryIso2Code` even if only one scope is targeted initially
- **Common tables** apply to multiple scopes at the same grain (e.g. Order, Invoice)
- **Scope-specific tables** are created only when grain, meaning, or business process genuinely differs by scope

---

## 10. Views

- A **common/consumption view** (straight `SELECT *`, same column names) is recommended for every Gold table
- Scope/application-specific views are optional, for custom column sets or naming

---

## 11. Metadata

Capture business meaning, lineage, transformation logic, and grain for every entity/attribute — in whatever modeling tool the project uses. Automate data-dictionary updates via the deployment pipeline where possible.

---

## 12. Governance

- Scoping/audit column values should be maintained by the project's designated data governance function
- All Gold models should be reviewed and approved by designated reviewers, with changes tracked via the project's issue/ticket tracker
- Exceptions (e.g. bypassing Silver) require sign-off from the project's architecture team

---

## 13. Data Architecture Layers

| Layer | Purpose |
|-------|---------|
| **Source Systems** | Internal and external systems providing data |
| **Landing** | Raw files ingested as-is |
| **Bronze** | Historical archive, minimal transformation |
| **Silver** | Conformed, industry/domain-standard data model |
| **Gold** | Application-specific aggregated/transformed data |
| **Consumption** | End-user access layer |

---

## 14. Quick Reference

### Default Audit Columns
`CountryIso2Code`, `MarketCode`, `SourceSystemId`, `ReportingUnitId`, `CreatedTimestamp`, `CreatedBy`, `UpdatedTimestamp`, `UpdatedBy`

### Common Mistakes to Avoid
❌ Underscores, plurals, ALL CAPS, spaces, special characters, numeric prefixes, vague terms (`ManageCustomer`)
✅ PascalCase, singular, full words, descriptive business terms
