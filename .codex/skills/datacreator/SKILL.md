---
name: datacreator
description: Create requested non-null data in the PrecisionLender UI, then trace the resulting source file into primary data outputs. Use when a requested field or dataset needs real UI-created data and its application source writer, primary-stage location, and end-to-end data path validated before an ingestion, schema, or pipeline change.
---

# Data Creator

## Local Test-Suite Policy

When working in `di-pipelines`, `di-scheduling`, or `di-pyjobs`, do not run local unit, integration, or full test suites. Use static inspection, targeted non-test checks, and browser, remote, or Alpha evidence instead. Run a local test suite only when the user explicitly requests it.

This skill guides software engineers how to navigate pl-application to create data. The skill takes in prompts in the format:

- We need to create non-null [column1, column2....] for [insert_primary_dataset] for client [CLIENT_GUUID]

Keep data creation isolated from real client data and production resources. Do not write to shared or production systems unless the user explicitly requests it and the target is confirmed.

## Workflow

1. Identify the requested field(s), client/environment, expected non-null behavior, and any known source-file name. Do not begin by installing dependencies or running `uv`, `pytest`, or other local test suites.
2. Locate the primary contract and write path first. In `di-pipelines`, identify the primary metadata class, producing task, exact `raFile` or source path, input and output resources, path conventions, dataset version, and partition keys. Map every requested field to its source-file column and primary output column; explicitly record renames, casts, calculations, and fields that are not written.
3. Trace PL Application source creation second. Search `repositories/pl-application` for each requested field and follow it through the authoritative DTO or contract, mapper/persistence code, and the RA, export, or event writer. Record the exact source field name, type, nullability, identifier, date/run fields, and code path that emits it. Do not infer a source merely from a similarly named property.
4. Use the authenticated browser session to select the confirmed client and navigate to the application UI that creates the requested values. Identify the smallest safe record or scenario that produces every requested field as non-null. Capture the client, record, and relevant parent identifiers before making any change.
5. Create or update that record in the UI with deterministic, plausible values. Use normal user-visible controls only; do not inject data through browser developer tools, direct database access, APIs, local fixtures, or file uploads. Before the final save/submit action, confirm the exact client, environment, record, fields, and values with the user whenever that authorization was not already explicit. Record the resulting URL, entity ID, and saved values.
6. If staging access requires a support login, use the existing authenticated browser session and navigate from the selected client's Admin page to **User Information**, then select the user explicitly named by the requester. Confirm the client GUID, target username, and ticket before submitting **New Support Login**. Enter the reason exactly as `creating data for DE-####`, substituting the supplied ticket key. This creates external access: do not submit it without explicit user authorization for that client, user, and ticket; record the support-login URL and result. Do not reuse the 99b client or `tpulikal@precisionlender.com` identifiers for another request unless they are explicitly supplied again.
7. If the user asks for directions, or browser access is blocked, provide a manual creation guide instead of stopping at a blocked status. The guide must be specific to the traced field(s) and source path:
   - State the exact client/environment and UI area to use.
   - Name the smallest record or scenario to create or update.
   - Give deterministic values to enter, including product/account/scenario choices when known, and explain which value makes each requested field non-null.
   - List the identifiers and URLs the user must capture after saving, such as relationship ID, opportunity ID, scenario ID, account ID, financial statement ID, and top-level parent.
   - Include the exact follow-up validation command or query to run against the RA source file and the expected primary dataset/output path.
   - Clearly mark any step that is inferred from code rather than browser-observed UI, and any value that the user must choose from the client's available configuration.
8. Follow the browser-visible RA/export or job-monitoring flow for the created record. Verify client eligibility and a successful producing run before treating the observed source or output as current. A repository task definition or application contract alone is not proof that a client receives the job.
9. Validate both sides of the primary boundary using the created record's identifiers:
   - Parse the emitted `raFile`; verify the mapped application fields are present, correctly typed, and non-null in the same created row.
   - After the producing job runs, read the expected primary output using its metadata and path convention. Verify the same identifiers and partition reached the expected `DataStudioHistorical` (or task-defined) output, with the expected field names, types, and values.
   - If the source exists but the primary output does not, report the producing task/run and primary write as the failing boundary. If no run is available, report the output validation as pending rather than claiming success.
10. Do not run local test suites for these repositories unless the user explicitly asks for them. Do not claim end-to-end validation from a contract-only or fixture-only check.
11. Report the primary dataset/version/path first, then the application contract and writer evidence, field-to-output mapping, UI-created record URL/identifiers/values or manual creation directions, browser-observed client/job/run evidence, identifiers/partition checked, support-login result when used, validation performed, and any limitation or ambiguity.

## UI Data Creation Rules

- Use explicit deterministic values that are plausible and internally consistent, especially dates, monetary fields, and relationships.
- Do not silently replace a null UI-created value with a synthetic non-null source value.
- Create only the smallest record and field set needed for the requested behavior.
- If the UI cannot create the necessary condition, stop and report the missing UI capability; do not substitute a local fixture, direct write, or fabricated source file unless the user explicitly requests that alternate strategy.
- Treat PL Application contract evidence, emitted-source evidence, and primary-output evidence as separate checks. All three are required to state that a field is published to primary.
- Do not commit credentials, sensitive client records, or large generated files.

## Manual Direction Mode

Use this mode when the user asks how to make the data themselves, when browser automation cannot access the application, or when access to the target client requires a support login that has not been authorized. Manual directions are not a substitute for validation; they are a handoff that lets the user create the record safely through the UI.

The response must include:

- **What to create:** The exact object type and minimum scenario that should populate the requested source columns.
- **Where to create it:** The target client URL, environment, and UI navigation path. If the UI path was inferred from code rather than observed in the browser, say so.
- **Values to use:** Deterministic example values that are plausible for the client and designed to produce non-null output. Prefer small, reversible test records with a recognizable name such as `DE-#### <field-purpose> <date>`.
- **Why it works:** A field-by-field explanation tying the UI values to the source column names and application DTO/mapper fields.
- **What to capture:** The saved record URL and any relationship, opportunity, account, financial-statement, scenario, top-level-parent, run, and date partition identifiers needed to trace the row later.
- **How to validate:** The exact `raFile`, expected columns, primary dataset/version/path convention, and local helper command or storage query to run after the RA/export job has produced a file.

Do not imply that the data exists until the user has created it or you have observed it. Do not claim source-file or primary-output validation from manual directions alone.

## Report

Include exact local paths and line references where possible. Distinguish observed data from generated data, and state what additional source identifier would be needed to reproduce an ambiguous example.
