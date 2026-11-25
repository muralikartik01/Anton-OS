# Databricks Cost Estimator - Baseline Reference

## Overview

This document provides the methodology, formulas, and pricing baselines for estimating annual compute and storage costs on Databricks (Azure) for your organization's workloads.

**Basis:** All rates and throughput estimates are derived from your organization's actual billing data (`system.billing.list_prices` and `system.billing.usage`) and observed historical run patterns. Replace the numbers in this document with your own exported values.

---

## Pricing Baseline

**Source:** `system.billing.list_prices` (your organization's Azure account)

| SKU | Rate | Unit | Region |
|-----|------|------|--------|
| PREMIUM_JOBS_COMPUTE | $0.30 | per DBU | All Azure regions |
| PREMIUM_JOBS_COMPUTE_(PHOTON) | $0.30 | per DBU | All Azure regions |
| PREMIUM_JOBS_SERVERLESS_COMPUTE_US_EAST | $0.45 | per DBU | US East |
| PREMIUM_ALL_PURPOSE_COMPUTE | $0.55 | per DBU | All Azure regions |
| PREMIUM_ALL_PURPOSE_SERVERLESS_COMPUTE_US_EAST | $0.95 | per DBU | US East |
| PREMIUM_DATABRICKS_STORAGE_US_EAST | $0.026 | per GB-month (DSU) | US East |
| PREMIUM_DATABRICKS_STORAGE_US_SOUTH_CENTRAL | $0.023 | per GB-month (DSU) | US South Central |
| PREMIUM_DATABRICKS_STORAGE_US_EAST_2 | $0.023 | per GB-month (DSU) | US East 2 |

### Observed Usage Patterns (Primary SKUs)
- **PREMIUM_JOBS_COMPUTE** — most heavily used SKU (~8.9M DBUs/month)
- **PREMIUM_ALL_PURPOSE_COMPUTE** — ~2.5M DBUs/month
- **PREMIUM_JOBS_COMPUTE_(PHOTON)** — ~1.1M DBUs/month
- **Primary storage region:** US East (highest DSU consumption)
- Pricing effective as of 2024-09-23 with no end date

---

## Throughput Baselines

Observed/estimated DBU consumption per GB of data processed, based on historical runs:

| Workload Type | DBUs per GB | Notes |
|---------------|-------------|-------|
| Simple read + write (no transformation) | 3.0 | INSERT INTO / INSERT OVERWRITE, Delta-to-Delta |
| Light transformation (filters, renames, casts) | 4.0 | SELECT with column expressions |
| Medium transformation (joins, aggregations) | 6.0 | Multi-table joins, GROUP BY |
| Heavy transformation (complex UDFs, ML) | 10.0+ | UDFs, window functions, iterative logic |
| DELETE / purge (partitioned) | 0.3 | Per GB of data scanned for delete predicate |

> These baselines are the authoritative source for `throughput_baselines.csv`. Do not edit
> either file independently — keep them in sync.

---

## Formulas

All calculations are per-table/per-workload, then summed for totals.

### Data Volume
```
total_volume_mb = vol_source_1_mb + vol_source_2_mb + ...
```

### Annual Data Processed
```
annual_data_processed_gb = total_volume_mb × refreshes_per_year / 1024
```

### Overhead (optional, for maintenance operations)
```
overhead_gb = annual_data_processed_gb × overhead_pct
total_annual_processed_gb = annual_data_processed_gb × (1 + overhead_pct)
```

### Storage at Steady State
```
storage_steady_state_gb = total_volume_mb × retention_days / 1024
```

> For non-daily refresh schedules, use retained_snapshots instead of retention_days:
> `storage_steady_state_gb = total_volume_mb / 1024 × retained_snapshots`

### Compute (DBUs)
```
annual_dbus = total_annual_processed_gb × dbus_per_gb
```

### Cost
```
annual_compute_cost = annual_dbus × rate_per_dbu
monthly_storage_cost = storage_steady_state_gb × storage_rate_per_gb_month
annual_storage_cost = monthly_storage_cost × 12
total_annual_cost = annual_compute_cost + annual_storage_cost
```

---

## How to Estimate

### Step-by-step

1. **Identify workloads** — List tables/pipelines that need costing
2. **Measure volume** — Get per-refresh data volume in MB from source systems
3. **Define schedule** — Determine refresh frequency (daily, weekly, adhoc, etc.)
4. **Set retention** — Define how long data is retained (affects storage cost)
5. **Classify complexity** — Pick the appropriate DBU-per-GB baseline from the throughput table
6. **Add overhead** — Include maintenance costs (purge, optimize, vacuum) if applicable
7. **Pull latest pricing** — Run the SQL queries below to confirm current rates
8. **Apply formulas** — Calculate per-workload costs
9. **Sum totals** — Aggregate for total annual cost

### When to Re-estimate
- New tables or pipelines added to scope
- Data volumes grow significantly (>20% change)
- Refresh frequency changes
- Databricks pricing is updated (check `price_end_time IS NULL`)
- Cluster type or sizing changes (affects DBU-per-GB throughput)

---

## Example Calculation

**Workload:** Daily snapshot of a 500 MB table, 90-day retention, no transformation

```
total_volume_mb          = 500 MB
refreshes_per_year       = 365
retention_days           = 90
dbus_per_gb              = 3.0 (simple read+write)
overhead_pct             = 0.10 (purge)
compute_rate             = $0.30/DBU (Classic Jobs)
storage_rate             = $0.026/GB-month (US East)

annual_data_processed_gb = 500 × 365 / 1024 = 178.22 GB
overhead_gb              = 178.22 × 0.10 = 17.82 GB
total_processed_gb       = 178.22 × 1.10 = 196.04 GB
storage_steady_state_gb  = 500 × 90 / 1024 = 43.95 GB
annual_dbus              = 196.04 × 3.0 = 588.13 DBUs
annual_compute           = 588.13 × $0.30 = $176.44
annual_storage           = 43.95 × $0.026 × 12 = $13.71

TOTAL ANNUAL COST        = $176.44 + $13.71 = $190.15/year
```

---

## SQL Queries for Latest Pricing

```sql
-- Pull current Databricks pricing for Azure (your organization's account)
-- Run this in any Databricks SQL warehouse

-- Storage pricing (all regions)
SELECT
  sku_name,
  cloud,
  currency_code,
  usage_unit,
  pricing.default AS list_price,
  pricing.effective_list.default AS effective_price,
  price_start_time
FROM system.billing.list_prices
WHERE cloud = 'AZURE'
  AND lower(sku_name) LIKE '%storage%'
  AND price_end_time IS NULL
ORDER BY sku_name;

-- Compute pricing (all types)
SELECT
  sku_name,
  cloud,
  currency_code,
  usage_unit,
  pricing.default AS list_price,
  pricing.effective_list.default AS effective_price,
  price_start_time
FROM system.billing.list_prices
WHERE cloud = 'AZURE'
  AND usage_unit = 'DBU'
  AND (lower(sku_name) LIKE '%us_east%'
       OR sku_name IN ('PREMIUM_JOBS_COMPUTE', 'PREMIUM_JOBS_COMPUTE_(PHOTON)',
                       'PREMIUM_ALL_PURPOSE_COMPUTE', 'PREMIUM_ALL_PURPOSE_COMPUTE_(PHOTON)'))
  AND price_end_time IS NULL
ORDER BY sku_name;

-- Verify actual usage patterns (last 30 days)
SELECT
  sku_name,
  usage_unit,
  SUM(usage_quantity) AS total_consumed,
  COUNT(DISTINCT usage_date) AS active_days,
  ROUND(SUM(usage_quantity) / COUNT(DISTINCT usage_date), 2) AS avg_per_day
FROM system.billing.usage
WHERE cloud = 'AZURE'
  AND usage_unit = 'DBU'
  AND usage_date >= current_date - INTERVAL 30 DAYS
GROUP BY sku_name, usage_unit
ORDER BY total_consumed DESC
LIMIT 10;
```

---

## Key Considerations

1. **DBU-per-GB is an estimate** — actual consumption varies with cluster size, data format, and query complexity. Validate against observed runs when possible.
2. **Storage compression** — Delta Lake typically compresses 2-5x vs. raw source size. The formulas use raw source volume for worst-case estimation. Multiply by 0.45 for a tighter (compressed) estimate.
3. **Cluster startup time** — not included in these estimates. Serverless eliminates this; classic clusters may add 2-5 min of idle DBUs per job.
4. **Region matters** — storage and serverless compute rates vary by region. Always use the region where your data resides.
5. **Photon** — same DBU rate as classic but processes faster, meaning fewer DBU-hours consumed per GB. If using Photon, reduce `dbus_per_gb` by ~30-50%.
6. **Retention vs. snapshots** — storage steady state depends on both per-snapshot volume AND how many snapshots are retained simultaneously. For non-daily cadences use `retained_snapshots` not `retention_days` directly.

---

*Last updated: June 2026*
*Pricing source: system.billing.list_prices (your organization's Azure account)*
*Throughput baselines: derived from observed historical runs — replace with your own*
