# Production readiness

**Дата проверки:** 2026-11-04
**Ветка:** `feat/v3.4.2-reliable-execution-and-learning`
**Статус:** pre-production; этот документ описывает evidence, а не намерения.

## Что проверено

| Область | Evidence | Статус |
|---|---|---|
| Локальный API/UI | FastAPI запущен на `127.0.0.1:8000`; `/health` и `/api/v1/status` ответили HTTP 200; UI открыт встроенным браузером; `README.md` успешно прочитан через `POST /api/v1/tasks` с `status=completed` | подтверждено |
| Runtime container | `synapse/runtime/container.py`; health агрегирует workspace, credentials, router и worker backend | подтверждено частично |
| Dynamic skills | Stage A acceptance: AST manifest без импорта в control-plane, capabilities и subprocess worker | подтверждено тестами |
| Provider transport | OpenAI-compatible и Ollama adapters; unsupported modes fail closed | подтверждено тестами |
| Task/run ledger | SQLite WorkEngine с явными переходами, optimistic version/revision, lease recovery и event ledger | подтверждено unit-тестами |
| HTTP task invocation | API task создаёт durable Task/Run, lease, проходит через `InvocationService`, сохраняет `invocation_receipt` и terminal state; approval без доступного container остаётся unavailable | подтверждено `tests/test_real_task_execution.py` |
| Canonical experience evidence | `ExperienceRecord`/`ExperienceStore` сохраняет immutable-at-write hash, provenance и разделяет `execution_success` от независимого `verifier_passed`; HTTP task записи пока `inconclusive` до verifier | подтверждено unit-тестом; verified dataset ещё не включён |
| Dataset snapshot boundary | `DatasetSnapshotStore` принимает только verified+eligible records, сохраняет manifest hash и disjoint train/dev/holdout split; пустой verified набор блокируется | подтверждено unit-тестом; trainer/serving ещё не включены |
| Unified invocation boundary | `InvocationService` существует и проверяет auth/capabilities/approval/budget; интеграция всех execution paths ещё не завершена | частично подтверждено |
| Codex CLI | `codex-cli 0.166.0`, `codex exec --help` доступны | live read-only smoke: `returncode=0`, 17 events; safe policy блокировала shell branch check, output это отразил |
| Claude Code CLI | `Claude Code 2.1.316` доступен | live read-only smoke: `returncode=0`, 4 events; safe mode, без edits/bash |
| Credentials | env backend доступен; внешние LLM credentials не использовались | blocked для live provider smoke |
| GPU/training | GPU и compatible open-weight model не проверялись | blocked |
| Full Windows suite | clean full-suite pass не получен | blocked/не подтверждено |

## Локальный запуск

```powershell
$env:SYNAPSE_WORKSPACE_ROOT = (Get-Location).Path
$env:SYNAPSE_UI_DB_PATH = "$PWD\.synapse\workspace.sqlite3"
$env:SYNAPSE_DB_PATH = "$PWD\.synapse\memory.sqlite3"
$env:SYNAPSE_VECTOR_DIR = "$PWD\.synapse\vectors"
.\.venv\Scripts\python.exe -m uvicorn synapse.api.app:app --host 127.0.0.1 --port 8000
```

Открыть:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/providers.html`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/api/v1/status`

## Тесты

Целевой regression/acceptance набор:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\acceptance\test_stage_a_acceptance.py `
  tests\unit\providers `
  tests\unit\test_skills_library.py `
  tests\unit\work\test_work_engine.py `
  -q --basetemp=.pytest_temp\production-readiness
```

Перед заявлением о полном suite нужно выполнить отдельный clean run с новым `--basetemp` и сохранить полный stdout/stderr. Ошибки Windows cleanup нельзя трактовать как pass.

## Executor smoke policy

Проверка наличия бинарников безопасна и выполняется так:

```powershell
codex --version
codex exec --help
claude --version
claude --help
```

Реальный `codex exec` или `claude -p` должен запускаться только с:

1. явным opt-in оператора;
2. отдельным disposable workspace;
3. argv-only параметрами и ограниченным `cwd`;
4. таймаутом и process-tree cleanup;
5. сохранением JSONL/events и execution receipt;
6. без `--dangerously-bypass-approvals-and-sandbox`.

Наличие CLI не является evidence успешного model execution: нужны credentials, network policy и smoke receipt.

## Что ещё не готово

- production-safe Codex/Claude executor adapters с полным JSONL event contract, cancel/resume и receipt;
- единое подключение `InvocationService` ко всем HTTP/UI/slash/MCP/plugin/browser/patch paths;
- verified-only dataset snapshots с immutable manifest/hash и независимой верификацией;
- настоящий torch/transformers/peft/trl LoRA/QLoRA trainer и serving path;
- независимые held-out eval, promotion gates и rollback registry;
- доказанный full Windows suite pass;
- deployment smoke в Docker/production profile с реальными credentials.

До появления соответствующего evidence эти пункты намеренно имеют статус `blocked` или `not verified`.
