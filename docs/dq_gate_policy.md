# PQ-03 — Critical vs Warning Gate Policy

## Decision

- **Critical checks (DQ-C01, C02, C03, C04, C12, C13, C14):** block approval/publication of the governed metrics when the issue remains in the post-ETL clean layer or the privacy/freshness control fails. Preserve the run and its evidence so the defect can be investigated; do not hide or delete the failing evidence.
- **Warning checks (DQ-C05 through DQ-C11):** allow the diagnostic pipeline to continue, but log the affected rows, notify the owning team, and require review. ETL should quarantine invalid records where a safe deterministic rule exists; do not silently correct ambiguous business facts.
- **Raw-source diagnostics versus publish gate:** the raw-source DQ report intentionally reports planted defects even when ETL quarantines them. A raw FAIL proves the issue was detected; it does not by itself prove the clean warehouse contains the same bad row. The final publication decision must consider the post-ETL state and unresolved critical reconciliations.

## Current decision for this dataset

**Do not claim final sign-off yet.** The June 2026 payroll-to-ledger difference of INR 18,450 remains after quarantining invalid payroll rows. The DuckDB SQL checks and privacy control were executed: the original baseline passed DQ-C14 with zero violations, and a separate mutation test detected 81 below-threshold groups when suppression was temporarily removed in the test copy. Build artifacts may be generated for review, but the finance metric layer should not be represented as fully reconciled until the difference is explained or formally accepted by the project owner.

## Why this policy

Critical checks protect financial integrity, referential integrity, history correctness, pipeline freshness and privacy. Warnings identify operational or source issues that need review but do not necessarily make all other metrics unusable. The team should record any approved exception with owner, date, rationale and expiry; never change source data merely to make a check pass.
