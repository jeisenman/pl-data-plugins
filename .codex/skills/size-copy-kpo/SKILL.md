---
name: size-copy-kpo
description: Investigate a failed client copy task, measure its last month of L3 Historical date partitions, choose an evidence-based KubernetesPodOperator (KPO) resource override, implement the client-specific change, and prepare it for GitHub review. Use when a `_copy` or `copy_client` job fails from likely resource pressure and needs a client-specific KPO sizing change.
---

# Size Copy KPO

Keep all production investigation read-only until the user authorizes the code change. Do not clear, retry, or rerun Airflow tasks.

## 1. Identify one candidate

Use the read-only failure helper to list failed copy tasks for the requested day (default: previous local day):

```bash
python3 .codex/skills/size-copy-kpo/scripts/find_copy_failures.py --date YYYY-MM-DD
```

Select one task with a client DAG ID in the form `l3-main-<guid>`. Confirm the task is a copy task and that its failure suggests a resource problem (for example, OOM or a killed pod); do not size unrelated functional failures. Resolve the full GUID through `resource-discovery` before using a client name. Preserve the task ID, DAG ID, failure timestamps, and error evidence.

Run the helper again with `--dag-id` and `--task-id` to obtain the exact count for the review date. The count is failures, not retries or distinct DAG runs.

## 2. Locate the exact source

In `repositories/di-pipelines`, find the `OperatorFactory` with the selected `job_name`. Record its `dataset`, `datasetStage`, `datasetVersion`, `inputResource`, `inputPathConvention`, `fileFormat`, and runner (`job_reference`). Follow the active task's code path, including a job-specific `ClientArgOverrides` or conditional `compute` selection.

For `DataStudioHistorical`, construct the source root from the discovered values:

```text
ClientId=<guid>/L3/v1.0/<datasetStage>/<provider>/<group>/<dataset-name>/InstancePartition=<guid>/VersionPartition=<datasetVersion>
```

Do not infer the path from the task name. Use the literal activity arguments or the metadata/path convention that the task uses.

## 3. Measure the last month

Ask for Azure-enabled execution before accessing ADLS. Require a human Azure CLI login; do not put credentials in files or environment variables. Obtain the correct storage account from client/resource configuration rather than guessing from the Airflow region.

```bash
python3 .codex/skills/size-copy-kpo/scripts/measure_date_partitions.py \
  --account <storage-account> \
  --path '<L3 Historical source root>' \
  --days 31
```

The script lists only `DatePartition=` children, totals files in each partition, and reports latest, largest, and total retained bytes. Use `largest_gib` as the copy-size evidence, because one copy run processes one date partition. Report the matching `DatePartition` alongside it. If fewer than 31 partitions exist, state the actual count; do not treat missing history as zero-sized data.

## 4. Choose and implement the override

Find the exact resource-allocation mechanism used by this job. In the current pipeline this is commonly a `ClientArgOverrides` entry whose `container_resources` changes the compute from `batch` to `k8s_pod`; other jobs use a job-local `cond_compute` plus `copy_csv_resources`. Preserve that job's established pattern and imports.

Choose the worker tier by comparing the measured largest partition with existing overrides for the same runner, input format, output conversion, and chunking behavior. Use only an existing resource constant from `dag-utils/resource_allocation.py` (such as `RESOURCES_2CPU_6G`, `RESOURCES_2CPU_16G`, `RESOURCES_2CPU_30G`, `RESOURCES_2CPU_40G`, or `RESOURCE_2CPU_56G`). Do not generalize a threshold from another job family: parquet-to-CSV expansion and memory use are job-specific. If no comparable override provides a defensible tier, stop and ask the user rather than inventing one.

Add only the affected GUID to the particular job's `client_overrides`, with the resolved client name and measured largest partition GiB in the inline comment when the surrounding file uses that convention. Confirm that `.args(client_id=guid)` contains `container_resources` and that `.compute(client_id=guid)` returns `k8s_pod`, or confirm the equivalent conditional branch. Inspect the resulting diff; do not run local test suites for `di-pipelines` unless the user explicitly asks.

## 5. Prepare review

Before posting for review, verify that the diff changes only the intended client's copy-job allocation. Use this exact GitHub description, with values derived from the investigation:

```markdown
The <job> is failing for <client> (<first-three-guid>). It has failed <N> number of times on <MM/DD>.

The copy job is copying from `<L3 Historical path>`. The size of the copy is <largest-partition GiB> GiB. Therefore, we size the job at <worker size>.
```

Use the complete L3 Historical source root in the code span, the first three characters of the GUID only in parentheses, and the selected resource constant plus its memory amount for `<worker size>` (for example, `RESOURCES_2CPU_16G (2 CPU, 16 GiB)`). Do not claim a PR was posted until the GitHub action succeeds.

After the implementation and description are confirmed, use the `github:yeet` workflow for the entire publish step. It must refresh clean worktrees and block lint or branch-only unreachable/dead code before intentionally staging the override, committing it, pushing the branch, and opening a draft PR for review. Do not push directly from this skill. Paste the description exactly as generated above.
