SQL-to-JSON Skill

Purpose
- Convert a SQL file into the project's JSON configuration format (`data_extract`, `data_transform`, `data_load`).

Usage
- Place SQL file path and target config path in the request.
- The skill reuses `gold/` notebook functions and follows `common_utils` for expressions.

Basic example
- Trigger phrase: `generate json from sql` or `sql to json`.

Location
- Skill files: `dataengineering/.github/copilot/skills/sql-to-json`