(() => {
  'use strict';
  const {api, element: el, clear, notify, json, date} = window.synapse;
  const $ = id => document.getElementById(id);

  const RISK_HELP = {
    1: 'Разрешено только чтение. Synapse не изменяет файлы и не запускает команды без отдельного разрешения.',
    2: 'Чтение и работа с файлами проекта. Запись ограничена рабочим пространством.',
    3: 'Действия с записью, Shell и сетью требуют подтверждения человеком.',
    4: 'Дополнительно подтверждаются действия в браузере и автоматизация интерфейса.',
    5: 'Максимальная автономность: подтверждения запрашиваются только для самых опасных операций.',
  };
  const AGENT_INFO = {
    codex: {title: 'OpenAI Codex CLI', role: 'Внешний исполнитель для задач в кодовой базе. Возвращает отчёт и работает в безопасном режиме.'},
    claude_code: {title: 'Claude Code', role: 'CLI-агент Anthropic для работы с файлами проекта. По умолчанию — только чтение.'},
  };
  const MODEL_STATUS = {
    declared: {text: 'Объявлена, веса не скачаны', variant: 'badge-warn'},
    downloaded: {text: 'Скачана', variant: 'badge-ok'},
    verified: {text: 'Проверена', variant: 'badge-ok'},
    failed: {text: 'Ошибка загрузки', variant: 'badge-bad'},
  };
  const BLOCKER_LABELS = {
    missing_training_dependencies: 'Не установлены зависимости обучения',
    verified_dataset_snapshot_required: 'Нужен verified snapshot датасета',
    non_empty_holdout_required: 'В датасете нет holdout-выборки',
    frozen_open_weight_base_model_required: 'Нужна скачанная open-weight модель',
    base_model_path_not_found: 'Путь к весам модели не найден',
    cuda_gpu_required: 'Нужен GPU с CUDA',
    torch_runtime_required_for_gpu_check: 'PyTorch не установлен — проверка GPU невозможна',
    bitsandbytes_required_for_qlora: 'Для QLoRA нужен bitsandbytes',
    unsupported_training_mode: 'Режим обучения не поддерживается',
    verified_records_require_non_empty_training_text: 'В обучающих записях нет текста',
    holdout_records_require_non_empty_training_text: 'В holdout-записях нет текста',
    holdout_metric_unavailable: 'Не удалось вычислить holdout-метрику',
  };
  const SYSTEM_LABELS = {
    system: 'Система', security: 'Безопасность', memory: 'Память', connectors: 'Соединители',
  };
  const FIELD_LABELS = {
    log_level: 'Уровень логирования',
    require_approval_for_risk: 'Подтверждение при риске',
    rate_limit_per_minute: 'Лимит запросов в минуту',
    sql_db: 'База данных',
    persistent: 'Постоянное хранение',
    vector_db: 'Векторное хранилище',
    semantic_retrieval: 'Семантический поиск',
    'telegram.enabled': 'Telegram включён',
    'telegram.token_configured': 'Токен Telegram задан',
  };

  let baseline = {};
  let revision = null;
  let dirty = false;
  let suppress = false;

  function badge(text, variant, withDot) {
    const node = el('span', undefined, `badge${variant ? ` ${variant}` : ''}`);
    if (withDot) node.append(el('span', undefined, 'dot'));
    node.append(document.createTextNode(text));
    return node;
  }

  function emptyState(title, message) {
    const box = el('div', undefined, 'empty-state');
    box.append(el('strong', title), el('span', message));
    return box;
  }

  function setMetric(name, value, note) {
    const node = document.querySelector(`[data-metric="${name}"]`);
    if (node) node.textContent = value;
    if (note) {
      const noteNode = document.querySelector(`[data-metric="${name}-note"]`);
      if (noteNode) noteNode.textContent = note;
    }
  }

  function formatBytes(value) {
    const bytes = Number(value) || 0;
    if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1).replace('.', ',')} МБ`;
    if (bytes >= 1024) return `${Math.round(bytes / 1024)} КБ`;
    return `${bytes} байт`;
  }

  function humanValue(value) {
    if (value === true) return 'Да';
    if (value === false) return 'Нет';
    if (value === null || value === undefined || value === '') return '—';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }

  function blockerText(raw) {
    const [key, detail] = String(raw).split(':');
    return `${BLOCKER_LABELS[key] || key}${detail ? ` (${detail})` : ''}`;
  }

  function kvGroup(title, rows) {
    const group = el('div', undefined, 'kv-group');
    group.append(el('h3', title));
    const list = el('dl', undefined, 'kv-list');
    for (const [label, value, mono] of rows) {
      const row = el('div', undefined, 'kv-row');
      row.append(el('dt', label), el('dd', humanValue(value), mono ? 'mono' : undefined));
      list.append(row);
    }
    group.append(list);
    return group;
  }

  function setSaveState(kind, message) {
    const root = $('save-state');
    const text = $('save-state-text');
    if (root) root.className = `save-state${kind ? ` ${kind}` : ''}`;
    if (text) text.textContent = message;
  }

  function updateRiskHelp() {
    const help = $('cfg-approval-help');
    const select = $('cfg-approval-risk');
    if (help && select) help.textContent = RISK_HELP[select.value] || '';
  }

  const CONFIG_FIELD_IDS = [
    'cfg-pref-tier', 'cfg-latency-budget', 'cfg-fallback-order', 'cfg-domain-autoselect',
    'cfg-success-threshold', 'cfg-failure-trigger', 'cfg-export-format', 'cfg-sliding-window',
    'cfg-approval-risk', 'cfg-sandbox-isolation', 'cfg-allowed-domains',
  ];

  function applyConfig(values) {
    suppress = true;
    const setValue = (id, value, fallback) => {
      const input = $(id);
      if (!input) return;
      if (input.type === 'checkbox') input.checked = value === undefined ? fallback : Boolean(value);
      else input.value = value === undefined || value === null || value === '' ? fallback : value;
    };
    setValue('cfg-pref-tier', values.model_tier, 'balanced');
    setValue('cfg-latency-budget', values.latency_budget_ms, 15000);
    setValue('cfg-fallback-order', values.fallback_order, 'claude-sonnet-5-5 -> gpt-4o -> llama3.2');
    setValue('cfg-domain-autoselect', values.domain_autoselect, true);
    setValue('cfg-success-threshold', values.success_threshold, 80);
    setValue('cfg-failure-trigger', values.failure_trigger, 3);
    setValue('cfg-export-format', values.export_format, 'chatml');
    setValue('cfg-sliding-window', values.sliding_window_days, 7);
    setValue('cfg-approval-risk', values.approval_risk_level, 3);
    setValue('cfg-sandbox-isolation', values.sandbox_isolation, 'pluggable');
    setValue('cfg-allowed-domains', values.allowed_domains, 'localhost, 127.0.0.1, example.com, github.com, pypi.org, docs.python.org');
    suppress = false;
    dirty = false;
    updateRiskHelp();
  }

  function collectConfig() {
    const number = id => Number($(id)?.value);
    return {
      model_tier: $('cfg-pref-tier')?.value || 'balanced',
      latency_budget_ms: number('cfg-latency-budget'),
      success_threshold: number('cfg-success-threshold'),
      failure_trigger: number('cfg-failure-trigger'),
      export_format: $('cfg-export-format')?.value || 'chatml',
      sliding_window_days: number('cfg-sliding-window'),
      fallback_order: $('cfg-fallback-order')?.value || '',
      domain_autoselect: Boolean($('cfg-domain-autoselect')?.checked),
      allowed_domains: $('cfg-allowed-domains')?.value || '',
      approval_risk_level: number('cfg-approval-risk'),
      sandbox_isolation: $('cfg-sandbox-isolation')?.value || 'pluggable',
    };
  }

  async function loadLocalConfig() {
    try {
      const remote = await api('/runtime-config');
      baseline = remote.values || {};
      revision = remote.revision;
      applyConfig(baseline);
      setMetric('revision', revision ?? '—', 'растёт после каждого сохранения');
      setSaveState('saved', `Сохранено · ревизия ${revision ?? '—'}`);
    } catch (error) {
      setSaveState('dirty', 'Не удалось загрузить настройки — проверьте подключение к серверу.');
      notify(`Не удалось загрузить конфигурацию: ${error.message}`, true);
    }
  }

  document.querySelectorAll(CONFIG_FIELD_IDS.map(id => `#${id}`)).forEach(input => {
    const markDirty = () => {
      if (suppress) return;
      dirty = true;
      updateRiskHelp();
      setSaveState('dirty', 'Есть несохранённые изменения');
    };
    input.addEventListener('input', markDirty);
    input.addEventListener('change', markDirty);
  });

  $('save-local-cfg-btn')?.addEventListener('click', async event => {
    const button = event.currentTarget;
    button.disabled = true;
    setSaveState('', 'Сохраняю настройки…');
    try {
      const saved = await api('/runtime-config', {method: 'PUT', body: JSON.stringify(collectConfig())});
      baseline = saved.values || collectConfig();
      revision = saved.revision;
      applyConfig(baseline);
      setMetric('revision', revision ?? '—', 'растёт после каждого сохранения');
      setSaveState('saved', `Сохранено · ревизия ${revision ?? '—'}`);
      notify(`Настройки сохранены, ревизия ${revision}.`);
    } catch (error) {
      setSaveState('dirty', 'Не сохранено — исправьте ошибку и повторите.');
      notify(`Не удалось сохранить настройки: ${error.message}`, true);
    } finally {
      button.disabled = false;
    }
  });

  $('reset-local-cfg-btn')?.addEventListener('click', () => {
    applyConfig(baseline);
    setSaveState('saved', `Изменения отменены · ревизия ${revision ?? '—'}`);
    notify('Несохранённые изменения отменены.');
  });

  async function loadApiAuthInfo() {
    const card = $('api-auth-card');
    const help = $('api-auth-help');
    if (!card || !help) return;
    try {
      const info = await api('/runtime-info');
      card.hidden = !info.api_auth_required;
      help.textContent = info.api_auth_description;
    } catch (_) {
      card.hidden = true;
    }
  }

  async function loadBackups() {
    const root = $('backups');
    const counter = $('backups-count');
    if (!root) return;
    try {
      const data = await api('/settings/backups');
      const backups = [...(data.backups || [])].sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
      setMetric('backups', backups.length, backups.length ? 'снимки памяти и задач' : 'ещё не созданы');
      if (counter) counter.textContent = backups.length ? `${backups.length} шт.` : 'пусто';
      clear(root);
      if (!backups.length) {
        root.append(emptyState('Резервных копий пока нет', 'Нажмите «Создать копию», чтобы сохранить текущее состояние памяти, опыта и задач.'));
        return;
      }
      const makeRow = (backup, index) => {
        const row = el('div', undefined, 'list-row');
        const main = el('div', undefined, 'list-row-main');
        main.append(
          el('strong', date(backup.created_at)),
          el('small', `${backup.backup_id} · ${formatBytes(backup.size_bytes)}`),
        );
        const actions = el('div', undefined, 'list-row-actions');
        actions.append(badge(index === 0 ? 'Самая свежая' : 'Сохранена', index === 0 ? 'badge-ok' : 'badge-muted'));
        row.append(main, actions);
        return row;
      };
      const recent = backups.slice(0, 5);
      recent.forEach((backup, index) => root.append(makeRow(backup, index)));
      if (backups.length > recent.length) {
        const details = el('details', undefined, 'tech-details backup-more');
        details.append(el('summary', `Показать все копии · ещё ${backups.length - recent.length}`));
        const list = el('div', undefined, 'list-rows');
        backups.slice(recent.length).forEach((backup, index) => list.append(makeRow(backup, index + recent.length)));
        details.append(list);
        root.append(details);
      }
    } catch (error) {
      clear(root).append(el('p', `Не удалось загрузить копии: ${error.message}`, 'error'));
    }
  }

  async function loadModels() {
    const root = $('models');
    const counter = $('models-count');
    if (!root) return;
    try {
      const data = await api('/runtime-config/models');
      const models = data.models || [];
      setMetric('models', models.length, models.length ? 'manifest’ы локальных весов' : 'ещё не объявлены');
      if (counter) counter.textContent = models.length ? `${models.length} шт.` : 'пусто';
      clear(root);
      if (!models.length) {
        root.append(emptyState('Модели не объявлены', 'Добавьте manifest выше, чтобы Synapse знал, какие веса можно скачать для локального обучения.'));
        return;
      }
      for (const model of models) {
        const status = MODEL_STATUS[model.status] || {text: model.status || 'неизвестно', variant: 'badge-muted'};
        const card = el('article', undefined, 'model-card');
        const top = el('div', undefined, 'card-top');
        const title = el('div');
        title.append(el('h3', model.model_id), el('div', `${model.revision || 'main'} · ${model.source || model.model_id}`, 'model-id'));
        top.append(title, badge(status.text, status.variant, true));
        card.append(top);
        const meta = el('div', undefined, 'card-meta');
        if (model.license) meta.append(badge(`Лицензия: ${model.license}`, 'badge'));
        meta.append(badge(model.local_path ? 'Веса на диске' : 'Весов на диске нет', model.local_path ? 'badge-ok' : 'badge-muted'));
        card.append(meta);
        if (model.local_path) card.append(el('div', model.local_path, 'model-id'));
        const foot = el('div', undefined, 'card-foot');
        if (model.status !== 'downloaded' && model.status !== 'verified') {
          const download = el('button', 'Скачать веса', 'small-button');
          download.type = 'button';
          download.addEventListener('click', async () => {
            download.disabled = true;
            download.textContent = 'Скачиваю…';
            try {
              try {
                await api('/runtime-config/models/download', {
                  method: 'POST',
                  body: JSON.stringify({model_id: model.model_id}),
                });
              } catch (bodyError) {
                // Older servers only expose the path form; retry it before giving up.
                if (bodyError.status !== 404) throw bodyError;
                await api(`/runtime-config/models/${encodeURIComponent(model.model_id)}/download`, {method: 'POST'});
              }
              notify(`Модель ${model.model_id} скачана.`);
              await loadModels();
            } catch (error) {
              notify(`Не удалось скачать модель: ${error.message}`, true);
              download.disabled = false;
              download.textContent = 'Скачать веса';
            }
          });
          foot.append(download);
        } else {
          foot.append(badge('Готова к обучению', 'badge-ok'));
        }
        card.append(foot);
        root.append(card);
      }
    } catch (error) {
      clear(root).append(el('p', `Не удалось загрузить модели: ${error.message}`, 'error'));
    }
  }

  $('model-declare-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    const status = $('model-form-status');
    const modelId = $('model-id')?.value.trim();
    if (!modelId) {
      if (status) { status.className = 'form-status bad'; status.textContent = 'Укажите Model ID, например Qwen/Qwen2.5-0.5B-Instruct.'; }
      return;
    }
    const submit = event.currentTarget.querySelector('button[type=submit]');
    if (submit) submit.disabled = true;
    if (status) { status.className = 'form-status'; status.textContent = 'Сохраняю manifest…'; }
    try {
      await api('/runtime-config/models', {method: 'POST', body: JSON.stringify({
        model_id: modelId,
        source: modelId,
        revision: $('model-revision')?.value.trim() || 'main',
      })});
      if (status) { status.className = 'form-status ok'; status.textContent = 'Manifest сохранён. Теперь веса можно скачать.'; }
      notify('Manifest модели сохранён.');
      await loadModels();
    } catch (error) {
      if (status) { status.className = 'form-status bad'; status.textContent = `Не удалось сохранить manifest: ${error.message}`; }
      notify(error.message, true);
    } finally {
      if (submit) submit.disabled = false;
    }
  });

  async function loadReplication() {
    const root = $('replica-status');
    if (!root) return;
    try {
      const [status, bundles] = await Promise.all([api('/replication/status'), api('/replication/bundles')]);
      clear(root);
      root.append(kvGroup('Состояние репликации', [
        ['Режим', status.status || '—'],
        ['Описание', status.description || '—'],
        ['Каталог bundle', status.directory || '—', true],
      ]));
      const list = bundles.bundles || [];
      const group = el('div', undefined, 'kv-group');
      group.append(el('h3', `Экспортированные bundle · ${list.length}`));
      if (!list.length) {
        group.append(el('p', 'Snapshot’ов пока нет. Экспорт создаст переносимый архив без секретов.', 'hint'));
      } else {
        const rows = el('div', undefined, 'list-rows');
        for (const bundle of list) {
          const row = el('div', undefined, 'list-row');
          const main = el('div', undefined, 'list-row-main');
          main.append(el('strong', bundle.name), el('small', `${formatBytes(bundle.size_bytes)} · ${bundle.path}`));
          row.append(main, el('div', undefined, 'list-row-actions'));
          row.lastChild.append(badge('Portable snapshot', 'badge-info'));
          rows.append(row);
        }
        group.append(rows);
      }
      root.append(group);
    } catch (error) {
      clear(root).append(el('p', `Не удалось загрузить состояние репликации: ${error.message}`, 'error'));
    }
  }

  $('replica-export')?.addEventListener('click', async event => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const result = await api('/replication/export', {method: 'POST'});
      notify(`Snapshot экспортирован: ${result.path}`);
      await loadReplication();
    } catch (error) {
      notify(error.message, true);
    } finally {
      button.disabled = false;
    }
  });
  $('replica-refresh')?.addEventListener('click', loadReplication);

  function renderSnapshotList(snapshots, root) {
    const group = el('div', undefined, 'kv-group');
    group.append(el('h3', `Verified snapshots · ${snapshots.length}`));
    const rows = el('div', undefined, 'list-rows');
    snapshots.forEach(snapshot => {
      const row = el('div', undefined, 'list-row');
      const main = el('div', undefined, 'list-row-main');
      main.append(
        el('strong', snapshot.snapshot_id),
        el('small', `${date(snapshot.created_at)} · train ${(snapshot.train_ids || []).length} · dev ${(snapshot.dev_ids || []).length} · holdout ${(snapshot.holdout_ids || []).length}`),
      );
      const actions = el('div', undefined, 'list-row-actions');
      actions.append(badge('verified', 'badge-ok'));
      row.append(main, actions);
      rows.append(row);
    });
    group.append(rows);
    root.append(group);
  }

  async function loadTraining() {
    const root = $('training-status');
    if (!root) return;
    try {
      const data = await api('/training/snapshots');
      const snapshots = data.snapshots || [];
      clear(root);
      if (!snapshots.length) {
        root.append(emptyState('Verified snapshot ещё не создан', 'Нажмите «Создать verified snapshot». Если подходящего опыта нет, сервер вернёт понятную причину — это нормально и не является ошибкой интерфейса.'));
        return;
      }
      renderSnapshotList(snapshots, root);
    } catch (error) {
      clear(root).append(el('p', `Не удалось загрузить snapshots: ${error.message}`, 'error'));
    }
  }

  $('create-snapshot')?.addEventListener('click', async event => {
    const button = event.currentTarget;
    button.disabled = true;
    const root = $('training-status');
    if (root) { clear(root).append(el('p', 'Создаю verified snapshot из подтверждённого опыта…', 'muted')); }
    try {
      const result = await api('/training/snapshots', {method: 'POST', body: JSON.stringify({seed: 0})});
      notify(`Snapshot ${result.snapshot.snapshot_id} создан.`);
      await loadTraining();
    } catch (error) {
      if (root) {
        clear(root).append(el('div', undefined, 'callout warn'));
        root.lastChild.append(el('span', `Snapshot не создан: ${error.message}. Нужен хотя бы один verified-запись опыта.`));
      }
      notify(error.message, true);
    } finally {
      button.disabled = false;
    }
  });

  async function selectedTrainingInputs() {
    const models = await api('/runtime-config/models');
    const downloaded = models.models.find(model => model.status === 'downloaded' || model.status === 'verified');
    const snapshots = await api('/training/snapshots');
    const snapshot = snapshots.snapshots[0];
    if (!downloaded) throw new Error('Сначала скачайте open-weight модель в разделе «Модели».');
    if (!snapshot) throw new Error('Сначала создайте verified snapshot из подтверждённого опыта.');
    return {model_id: downloaded.model_id, snapshot_id: snapshot.snapshot_id};
  }

  function renderTrainingOutcome(root, title, payload) {
    clear(root);
    const blockers = payload.blockers || [];
    const status = payload.ready === true || payload.status === 'completed'
      ? {text: 'Готово', variant: 'badge-ok'}
      : {text: payload.status || 'Есть блокеры', variant: blockers.length ? 'badge-warn' : 'badge-info'};
    const group = el('div', undefined, 'kv-group');
    const head = el('div', undefined, 'card-top');
    head.append(el('h3', title), badge(status.text, status.variant, true));
    group.append(head);
    const rows = [];
    if (payload.mode) rows.push(['Режим', payload.mode]);
    if (payload.steps) rows.push(['Шагов', payload.steps]);
    if (payload.final_loss !== undefined && payload.final_loss !== null) rows.push(['Final loss', payload.final_loss]);
    if (payload.holdout_loss_after !== undefined && payload.holdout_loss_after !== null) rows.push(['Holdout loss', payload.holdout_loss_after]);
    if (payload.adapter_path) rows.push(['Адаптер', payload.adapter_path, true]);
    if (payload.error) rows.push(['Ошибка', payload.error]);
    if (rows.length) {
      const list = el('dl', undefined, 'kv-list');
      rows.forEach(([label, value, mono]) => {
        const row = el('div', undefined, 'kv-row');
        row.append(el('dt', label), el('dd', humanValue(value), mono ? 'mono' : undefined));
        list.append(row);
      });
      group.append(list);
    }
    if (blockers.length) {
      group.append(el('p', 'Что мешает запуску:', 'hint'));
      const ul = el('ul', undefined, 'hint');
      for (const blocker of blockers) ul.append(el('li', blockerText(blocker)));
      group.append(ul);
    }
    root.append(group);
    const details = el('details', undefined, 'tech-details');
    details.append(el('summary', 'Полный ответ сервера'));
    const pre = el('pre');
    pre.textContent = json(payload);
    details.append(pre);
    root.append(details);
  }

  $('training-preflight')?.addEventListener('click', async event => {
    const button = event.currentTarget;
    button.disabled = true;
    const root = $('training-status');
    if (root) { clear(root).append(el('p', 'Проверяю готовность: зависимости, GPU, snapshot и веса модели…', 'muted')); }
    try {
      const input = await selectedTrainingInputs();
      const result = await api('/training/preflight', {method: 'POST', body: JSON.stringify({...input, require_gpu: true})});
      renderTrainingOutcome(root, 'Preflight', result);
      notify(result.ready ? 'Preflight пройден — можно запускать обучение.' : 'Preflight нашёл блокеры.', !result.ready);
    } catch (error) {
      if (root) clear(root).append(el('div', undefined, 'callout warn'));
      if (root) root.lastChild.append(el('span', `Preflight не выполнен: ${error.message}`));
      notify(error.message, true);
    } finally {
      button.disabled = false;
    }
  });

  $('run-training')?.addEventListener('click', async event => {
    const button = event.currentTarget;
    button.disabled = true;
    const root = $('training-status');
    if (root) { clear(root).append(el('p', 'Запускаю один шаг LoRA. Это может занять время…', 'muted')); }
    try {
      const input = await selectedTrainingInputs();
      const result = await api('/training/run', {method: 'POST', body: JSON.stringify({...input, steps: 1, require_gpu: true})});
      renderTrainingOutcome(root, 'Результат обучения', result.training || result);
      notify(result.training?.status === 'completed' ? 'Шаг обучения выполнен.' : 'Обучение завершилось без успеха — смотрите блокеры.', result.training?.status !== 'completed');
    } catch (error) {
      if (root) clear(root).append(el('div', undefined, 'callout warn'));
      if (root) root.lastChild.append(el('span', `Обучение не запущено: ${error.message}`));
      notify(error.message, true);
    } finally {
      button.disabled = false;
    }
  });

  async function loadIntegrations() {
    const root = $('integrations-agents');
    if (!root) return;
    try {
      const data = await api('/integrations/agents');
      const agents = data.agents || [];
      const connected = agents.filter(agent => agent.enabled).length;
      setMetric('agents', agents.length ? `${connected}/${agents.length}` : '—', agents.length ? 'Codex · Claude Code' : 'данные недоступны');
      const counter = $('agents-count');
      if (counter) counter.textContent = agents.length ? `${connected} подключено` : 'нет данных';
      clear(root);
      if (!agents.length) {
        root.append(emptyState('CLI-агенты не обнаружены', 'Установите Codex CLI или Claude Code, затем нажмите «Синхронизировать из OpenCode» или «Обновить список».'));
        return;
      }
      for (const agent of agents) {
        const info = AGENT_INFO[agent.id] || {title: agent.id, role: 'Внешний агент.'};
        const card = el('div', undefined, 'kv-group');
        const head = el('div', undefined, 'card-top');
        const title = el('div');
        title.append(el('h3', info.title), el('div', agent.id, 'model-id'));
        const statusText = agent.enabled ? 'Подключён' : ((agent.configured || agent.command) ? 'Найден, отключён' : 'Не найден');
        const statusVariant = agent.enabled ? 'badge-ok' : ((agent.configured || agent.command) ? 'badge-warn' : 'badge-muted');
        head.append(title, badge(statusText, statusVariant, true));
        card.append(head, el('p', info.role, 'hint'));
        const list = el('dl', undefined, 'kv-list');
        const rows = [
          ['Таймаут', `${Math.round(agent.timeout_seconds || 0)} с`],
          ['Запись', agent.write_enabled ? 'Разрешена' : 'Только чтение'],
          ['Команда', Array.isArray(agent.command) ? agent.command.join(' ') : (agent.command || agent.resolved_executable || '—'), true],
        ];
        rows.forEach(([label, value, mono]) => {
          const row = el('div', undefined, 'kv-row');
          row.append(el('dt', label), el('dd', humanValue(value), mono ? 'mono' : undefined));
          list.append(row);
        });
        card.append(list);
        const actions = el('div', undefined, 'chip-row');
        const toggle = el('button', agent.enabled ? 'Отключить' : 'Подключить', agent.enabled ? 'secondary small-button' : 'small-button');
        toggle.type = 'button';
        toggle.addEventListener('click', async () => {
          toggle.disabled = true;
          try {
            if (agent.enabled) {
              await api(`/integrations/executors/${encodeURIComponent(agent.id)}`, {method: 'PATCH', body: JSON.stringify({enabled: false})});
              notify(`Агент ${info.title} отключён.`);
            } else {
              await api(`/integrations/agents/${encodeURIComponent(agent.id)}/connect`, {method: 'POST'});
              await api(`/integrations/executors/${encodeURIComponent(agent.id)}`, {method: 'PATCH', body: JSON.stringify({enabled: true})});
              notify(`Агент ${info.title} подключён.`);
            }
            await loadIntegrations();
          } catch (error) {
            notify(`Не удалось изменить подключение: ${error.message}`, true);
            toggle.disabled = false;
          }
        });
        actions.append(toggle);
        card.append(actions);
        root.append(card);
      }
    } catch (error) {
      clear(root).append(el('p', `Не удалось загрузить внешних агентов: ${error.message}`, 'error'));
    }
  }

  async function loadOpenCodeStatus() {
    const root = $('opencode-status');
    if (!root) return;
    try {
      const data = await api('/integrations/opencode');
      clear(root);
      const labels = {
        ready: 'Готов',
        quota_exhausted: 'Лимит исчерпан',
        degraded: 'Ограниченно доступен',
        not_found: 'Не найден',
      };
      const quota = data.quota || {};
      const healthy = data.status === 'ready';
      const badgeNode = $('opencode-badge');
      if (badgeNode) {
        badgeNode.textContent = labels[data.status] || data.status || 'Не найден';
        badgeNode.className = `badge ${healthy ? 'badge-ok' : (data.status === 'quota_exhausted' ? 'badge-warn' : 'badge-muted')}`;
      }
      const agents = data.agents || [];
      const models = data.models || [];
      const quotaText = quota.exhausted
        ? `${quota.message || 'бесплатный лимит исчерпан'}${quota.retry_after_seconds ? ` · повтор через ${quota.retry_after_seconds} с` : ''}`
        : 'доступен';
      root.append(kvGroup('Состояние OpenCode', [
        ['Статус', labels[data.status] || data.status || 'не найден'],
        ['CLI OpenCode', data.cli || 'не найден', true],
        ['Каталог моделей', data.catalog_source === 'opencode_cli' ? 'OpenCode CLI' : (data.catalog_source || 'OpenCode CLI'), true],
        ['Модели OpenCode', models.length ? models.map(model => model.display_name || model.model_id).join(', ') : 'не обнаружены'],
        ['Лимит бесплатных моделей', quotaText],
        ['Предпочитаемая модель', data.preferred_model || '—', true],
        ['Последняя ошибка', data.last_error || '—', true],
        ['Агенты', agents.length ? agents.map(agent => `${agent.display_name || agent.id}${agent.version ? ` ${agent.version}` : ''}`).join(', ') : 'не обнаружены'],
      ]));
    } catch (error) {
      clear(root).append(el('p', `Не удалось прочитать статус OpenCode: ${error.message}`, 'error'));
    }
  }

  $('reset-opencode-quota-btn')?.addEventListener('click', async event => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      await api('/integrations/opencode/reset-quota', {method: 'POST'});
      notify('Кэш лимита OpenCode сброшен: следующая попытка выполнится сразу.');
      await loadOpenCodeStatus();
    } catch (error) {
      notify(error.message, true);
    } finally {
      button.disabled = false;
    }
  });

  $('sync-opencode-btn')?.addEventListener('click', async event => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const result = await api('/integrations/opencode/sync', {method: 'POST'});
      notify(`Синхронизировано агентов: ${result.synced.length}.`);
      await loadIntegrations();
    } catch (error) {
      notify(error.message, true);
    } finally {
      button.disabled = false;
    }
  });
  $('refresh-agents-btn')?.addEventListener('click', () => { loadIntegrations(); loadOpenCodeStatus(); });

  async function loadSystemSettings() {
    const root = $('settings');
    const raw = $('settings-raw');
    if (!root) return;
    const names = ['system', 'security', 'memory', 'connectors'];
    const results = await Promise.allSettled(names.map(name => api(`/settings/${name}`)));
    const payload = {};
    clear(root);
    names.forEach((name, index) => {
      const result = results[index];
      if (result.status !== 'fulfilled') return;
      const settings = result.value.settings || {};
      payload[name] = settings;
      const rows = [];
      for (const [key, value] of Object.entries(settings)) {
        if (key === 'telegram' && value && typeof value === 'object') {
          rows.push(['Telegram включён', value.enabled]);
          rows.push(['Токен Telegram задан', value.token_configured]);
        } else {
          rows.push([FIELD_LABELS[key] || key, value]);
        }
      }
      if (!rows.length) rows.push(['Значения', '—']);
      root.append(kvGroup(SYSTEM_LABELS[name] || name, rows));
    });
    if (raw) raw.textContent = json(payload);
    const failed = results.filter(result => result.status === 'rejected').length;
    if (failed) notify(`Не удалось прочитать ${failed} набор(а) системных настроек.`, true);
  }

  $('create-backup')?.addEventListener('click', async event => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const backup = await api('/settings/backup', {method: 'POST'});
      notify(`Создана копия ${backup.backup_id}.`);
      await loadBackups();
    } catch (error) {
      notify(error.message, true);
    } finally {
      button.disabled = false;
    }
  });
  $('refresh-backups')?.addEventListener('click', loadBackups);

  async function load() {
    await Promise.allSettled([
      loadBackups(),
      loadModels(),
      loadTraining(),
      loadReplication(),
      loadIntegrations(),
      loadOpenCodeStatus(),
      loadSystemSettings(),
    ]);
  }

  loadApiAuthInfo();
  loadLocalConfig();
  window.addEventListener('synapse-refresh', load);
  load();
})();
