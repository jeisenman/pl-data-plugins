---
name: pl-contracts
description: Inspect, explain, validate, and update PrecisionLender data contracts, including dataset schemas, field definitions, versioning, producers, consumers, and compatibility risks. Use when a request concerns a published data contract, contract change, schema evolution, or the lineage and downstream effect of a PrecisionLender dataset field.
---

# PL Contracts

Locate the authoritative contract before proposing a change. Prefer the repository's contract, schema, or data-dictionary source over code that merely consumes the dataset.

For each request:

1. Identify the dataset, fields, version, and requested compatibility behavior.
2. Trace the producer, contract definition, schema, orchestration, and known consumers.
3. Compare the requested change with the current contract and call out breaking changes, backfill requirements, and downstream migrations.
4. Make only the scoped contract and implementation changes required by the request.
5. Validate the changed contract, its producing job, and affected consumers with the repository's available checks.

Report the authoritative source path, contract version, producer, consumers, compatibility assessment, and verification performed. State any ambiguity and the identifier needed to resolve it.
