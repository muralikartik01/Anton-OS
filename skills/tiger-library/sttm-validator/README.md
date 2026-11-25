# STTM Validator

This skill validates STTM documents. Place validation reports (human-readable summaries) in the workspace `Output/sttm-validator/` folder.

Suggested report filename format: `sttm_validation_{filename}.md` where `{filename}` is the source STTM filename.

Example: input `customer_sttm.csv` -> `sttm_validation_customer_sttm.csv.md`

Summary/evaluation entries can be stored in `.github/skills/sttm-validator/evals/evals.json` if desired.
# STTM Validator Skill

This skill validates STTM (Standard Table/Transformation/Mapping) artifacts and checks data dictionary and DDL conformance.

Added folders: `evals/`, `references/`, and `assets/` for evaluation files, reference templates, and auxiliary assets.
