# Risks and open questions — mig-example-project-20261125T062515Z
| id | sev | item | handling in this blueprint |
|---|---|---|---|
| OQ1 / R1 | High | `rule-order-amount-reconciles` fails for 4/5 orders as written; line prices look pre-discount (items_total = gross for 4 orders); ORD-5005 matches neither reading. Unresolved mapping row: `fact_orders.is_amount_reconciled`. | Not resolved. Rows kept; flag computed per the rule exactly as written. **Decision needed from the approver** (see blueprint). |
| OQ2 / R2 | Med | No legacy pipeline code in the repo; lineage and schedule unknown. | Silver rules come only from graph rules + profiling. |
| OQ3 / R3 | Low | `order_timestamp` strings carry no zone. | Cast to TIMESTAMP_NTZ; no zone assumed. |
| OQ4 / R4 | Low | Domain violations: quarantine or flag? Graph is silent; none exist today. | Quarantine (not silently dropped), consistent with `rule-referential-integrity`. |
| OQ5 / R5 | Low | Source `_landed_at` is one constant; landing-load overwrites it with the landing load time. | Bronze `_landed_at` = landing load time; source value is not kept. |
| R6 | Med | Warehouse→Postgres JDBC reachability untested (dry run). | Fallback notebook per landing-load skill if registration fails in a real run. |
| R7 | Low | JDBC scope `db-kit-demo`, keys `jdbc-user`/`jdbc-password` are placeholders. | Replace before a real run. |
| R8 | Low | Bronze keeps STRING types; the workflow description mentions "typed casts in Bronze" but `rules/medallion/layer-conventions.md` says preserve source schema. | Rules win: casts + quarantine in Silver. |
Mapping validation: 0 ERROR, 2 WARNING, 1 INFO (see blueprint).
