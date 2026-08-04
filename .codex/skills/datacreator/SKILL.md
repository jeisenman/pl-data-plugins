---
name: datacreator
description: Trace PrecisionLender Application fields to primary data outputs and create representative test data or fixtures for data-engineering work. Use when a requested field or dataset needs its application contract, source writer, primary-stage output, and non-null test data validated before an ingestion, schema, or pipeline change can be tested.
---

# Data Creator

Create the smallest representative fixture that proves the requested behavior. Preserve the source format and field names unless the task explicitly asks for transformed or published data.

Keep data creation isolated from real client data and production resources. Do not write to shared or production systems unless the user explicitly requests it and the target is confirmed.

## Workflow

1. Identify the target primary dataset, requested field(s), ticket, client/environment, expected non-null behavior, and any derived consumer.
2. Trace the application contract before creating data. Search `repositories/pl-application` for each requested field and follow it through the authoritative DTO or contract, mapper/persistence code, and the RA, export, or event writer. Record the exact source field name, type, nullability, identifier, date/run fields, and the code path that emits it. Do not infer a source merely from a similarly named property.
3. Locate the primary contract and write path. In `di-pipelines`, identify the primary metadata class, producing task, exact `raFile` or source path, input and output resources, path conventions, dataset version, and partition keys. Map every application field to its expected source-file column and primary output column; explicitly record renames, casts, calculations, and fields that are not written.
4. Verify client eligibility before looking for or creating data: use DataFinder's job-availability gate to confirm the producing task is enabled for the selected client and, for current data, has a recent successful run. Do not treat a repository task definition or application contract as proof that the client receives the job.
5. Choose the fixture strategy:
   - Prefer an existing non-null example when real alpha data is appropriate and access is read-only.
   - Generate synthetic data when the source is unavailable, the value is sensitive, or deterministic edge cases are required.
   - For RA, use the task's exact `raFile`, directory, run shape, and schema; keep downloaded examples temporary and retain only the requested evidence.
   - Do not write a fixture into PL Application, a client database, or ADLS unless the user explicitly authorizes that target and the client/environment is confirmed safe.
6. When creating data directly in a staging client requires a support login, use the existing authenticated browser session and navigate from the selected client's Admin page to **User Information**, then select the user explicitly named by the requester. Confirm the client GUID, target username, and ticket before submitting **New Support Login**. Enter the reason exactly as `creating data for DE-####`, substituting the supplied ticket key. This creates external access: do not submit it without explicit user authorization for that client, user, and ticket; record the support-login URL and result. Do not reuse the 99b client or `tpulikal@precisionlender.com` identifiers for another request unless they are explicitly supplied again.
7. Create the fixture in a clearly scoped temporary or test-data location, or create the authorized staging data through the support session. Include only the rows and columns needed to exercise the behavior, plus required identifiers, date partitions, and RA run fields.
8. Validate both sides of the primary boundary:
   - Parse the source fixture or emitted `raFile`; verify the mapped application fields are present, correctly typed, and non-null in the same eligible row.
   - After the producing job runs, read the expected primary output using its metadata and path convention. Verify the same identifiers and partition reached the expected `DataStudioHistorical` (or task-defined) output, with the expected field names, types, and values.
   - If the source exists but the primary output does not, report the producing task/run and primary write as the failing boundary. If no run is available, report the output validation as pending rather than claiming success.
9. Run the narrowest available schema, mapper, source-reader, or transformation test. Do not claim end-to-end validation from a contract-only or fixture-only test.
10. Report the application contract and writer evidence, field-to-output mapping, client eligibility evidence, primary dataset/version/path, fixture or observed data path, identifiers/partition checked, support-login result when used, validation performed, and any limitation or ambiguity.

## Fixture Rules

- Keep synthetic values plausible and internally consistent, especially foreign keys, client IDs, dates, and monetary fields.
- Use explicit deterministic values when testing calculations or joins; avoid random data unless a seed is recorded.
- Never silently replace a null source value with a synthetic non-null value in an example claimed to be production data.
- Separate source fixtures from published-output fixtures so schema and transformation behavior remain observable.
- Treat PL Application contract evidence, emitted-source evidence, and primary-output evidence as separate checks. All three are required to state that a field is published to primary.
- Do not commit credentials, sensitive client records, or large generated files.

## Report

Include exact local paths and line references where possible. Distinguish observed data from generated data, and state what additional source identifier would be needed to reproduce an ambiguous example.
