# Managed agent tasks

The local dashboard can submit an agent task, show its progress and result in
the session, and stop the process owned by Synapse. The task uses the same
durable workspace ledger and feedback controls as the rest of the dashboard.

- OpenCode uses the selected model and its stock Build agent in a standalone
  process. It receives the task text. The working directory is temporary and
  the OpenCode policy denies tool use.
- Connect Codex or Claude Code in **Settings → External agents**. The managed
  task uses the installed CLI in read-only mode and runs in the configured
  workspace. In a local-only profile, OpenCode needs
  `SYNAPSE_ALLOW_SELECTED_OPENCODE=1`. Workspace agents also require
  `SYNAPSE_ALLOW_WORKSPACE_AGENTS=1` alongside their individual enable setting.
- The dashboard stores successful outputs and a bounded list of visible action
  categories in the local experience store. Independent acceptance criteria or
  the user's positive feedback make a record eligible for the existing local
  training pipeline. That pipeline owns training and promotion. Stopped and
  failed runs do not supply training pairs.

Set `SYNAPSE_AUTONOMY_TRAIN_MODEL=Qwen/Qwen3-1.7B` to target the downloaded
Qwen model explicitly. The autonomy status reports the target and the count of
verified examples still needed. UIs can confirm an agent answer for training
directly from its task card.

For automatic eligibility, include acceptance criteria in the task's JSON
parameters, for example `{"acceptance_criteria":["output_contains:ready"]}`.
Use criteria that independently verify the result you actually need. The
existing verifier also accepts workspace file checks.

The loopback API exposes executor availability at `GET /api/v1/agent-executors`,
submission at `POST /api/v1/sessions/{id}/agent-tasks`, status at
`GET /api/v1/tasks/{id}`, and cancellation at
`POST /api/v1/tasks/{id}/cancel`. Interrupted jobs age out after their deadline
and can be submitted again from the dashboard.

Run the focused verification with
`python -m pytest tests/unit/test_managed_agent_runs.py tests/unit/test_opencode_provider_quota.py`.
