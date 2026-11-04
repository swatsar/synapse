(() => {
  'use strict';
  const {api, element: el, clear, notify, json} = window.synapse;
  async function loadBackups() {
    const root = document.getElementById('backups');
    try {
      const data = await api('/settings/backups'); clear(root);
      if (!data.backups.length) { root.append(el('p', 'Резервных копий нет.', 'muted')); return; }
      const table = el('table'); const body = el('tbody');
      for (const backup of data.backups) {
        const row = el('tr');
        for (const value of [backup.backup_id, backup.created_at, `${backup.size_bytes} байт`]) row.append(el('td', value));
        body.append(row);
      }
      table.append(body); root.append(table);
    } catch (error) { clear(root).append(el('p', error.message, 'error')); }
  }
  async function loadModels() {
    const root = document.getElementById('models');
    if (!root) return;
    try {
      const data = await api('/runtime-config/models'); clear(root);
      if (!data.models.length) { root.append(el('p', 'Manifest’ов моделей нет.', 'muted')); return; }
      for (const model of data.models) {
        const row = el('div', `${model.model_id} — ${model.status}`);
        const button = el('button', 'Скачать'); button.type = 'button'; button.className = 'secondary small-button';
        button.addEventListener('click', async () => {
          button.disabled = true;
          try { await api(`/runtime-config/models/${encodeURIComponent(model.model_id)}/download`, {method: 'POST'}); notify('Модель скачана или уже доступна.'); await loadModels(); }
          catch (error) { notify(error.message, true); button.disabled = false; }
        });
        row.append(' ', button); root.append(row);
      }
    } catch (error) { clear(root).append(el('p', error.message, 'error')); }
  }

  async function loadTraining() {
    const root = document.getElementById('training-status');
    if (!root) return;
    try {
      const data = await api('/training/snapshots');
      root.textContent = json({snapshots: data.snapshots});
    } catch (error) { root.textContent = error.message; }
  }

  document.getElementById('create-snapshot')?.addEventListener('click', async event => {
    event.currentTarget.disabled = true;
    try { const result = await api('/training/snapshots', {method: 'POST', body: JSON.stringify({seed: 0})}); notify(`Snapshot ${result.snapshot.snapshot_id} создан.`); await loadTraining(); }
    catch (error) { notify(error.message, true); }
    finally { event.currentTarget.disabled = false; }
  });

  async function selectedTrainingInputs() {
    const models = await api('/runtime-config/models');
    const downloaded = models.models.find(model => model.status === 'downloaded');
    const snapshots = await api('/training/snapshots');
    const snapshot = snapshots.snapshots[0];
    if (!downloaded || !snapshot) throw new Error('Нужны скачанная модель и verified dataset snapshot.');
    return {model_id: downloaded.model_id, snapshot_id: snapshot.snapshot_id};
  }

  document.getElementById('training-preflight')?.addEventListener('click', async event => {
    event.currentTarget.disabled = true;
    try { const input = await selectedTrainingInputs(); const result = await api('/training/preflight', {method: 'POST', body: JSON.stringify({...input, require_gpu: true})}); document.getElementById('training-status').textContent = json(result); }
    catch (error) { notify(error.message, true); }
    finally { event.currentTarget.disabled = false; }
  });

  document.getElementById('run-training')?.addEventListener('click', async event => {
    event.currentTarget.disabled = true;
    try { const input = await selectedTrainingInputs(); const result = await api('/training/run', {method: 'POST', body: JSON.stringify({...input, steps: 1, require_gpu: true})}); document.getElementById('training-status').textContent = json(result); }
    catch (error) { notify(error.message, true); }
    finally { event.currentTarget.disabled = false; }
  });

  document.getElementById('model-declare-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    try {
      await api('/runtime-config/models', {method: 'POST', body: JSON.stringify({
        model_id: document.getElementById('model-id').value,
        source: document.getElementById('model-id').value,
        revision: document.getElementById('model-revision').value,
      })});
      notify('Manifest модели сохранён.'); await loadModels();
    } catch (error) { notify(error.message, true); }
  });

  async function load() {
    try {
      const [system, security, memory, connectors] = await Promise.all(['system', 'security', 'memory', 'connectors'].map(name => api(`/settings/${name}`)));
      document.getElementById('settings').textContent = json({system: system.settings, security: security.settings, memory: memory.settings, connectors: connectors.settings});
      await loadBackups();
      await loadModels();
      await loadTraining();
    } catch (error) { notify(error.message, true); }
  }
  document.getElementById('create-backup').addEventListener('click', async event => {
    event.currentTarget.disabled = true;
    try { const backup = await api('/settings/backup', {method: 'POST'}); notify(`Создана копия ${backup.backup_id}.`); await loadBackups(); }
    catch (error) { notify(error.message, true); }
    finally { event.currentTarget.disabled = false; }
  });

  // Local Fine-Tuning & OmniRouter Preferences
  const CFG_KEY = 'synapse-fine-tuning-cfg';
  async function loadLocalConfig() {
    try {
      const remote = await api('/runtime-config');
      const saved = remote.values || {};
      if (saved.model_tier) document.getElementById('cfg-pref-tier').value = saved.model_tier;
      if (saved.latency_budget_ms) document.getElementById('cfg-latency-budget').value = saved.latency_budget_ms;
      if (saved.success_threshold) document.getElementById('cfg-success-threshold').value = saved.success_threshold;
      if (saved.failure_trigger) document.getElementById('cfg-failure-trigger').value = saved.failure_trigger;
      if (saved.export_format) document.getElementById('cfg-export-format').value = saved.export_format;
      if (saved.sliding_window_days) document.getElementById('cfg-sliding-window').value = saved.sliding_window_days;
    } catch (error) { notify(`Не удалось загрузить server config: ${error.message}`, true); }
  }

  document.getElementById('save-local-cfg-btn')?.addEventListener('click', async event => {
    event.currentTarget.disabled = true;
    const config = {
      model_tier: document.getElementById('cfg-pref-tier')?.value,
      latency_budget_ms: Number(document.getElementById('cfg-latency-budget')?.value),
      success_threshold: Number(document.getElementById('cfg-success-threshold')?.value),
      failure_trigger: Number(document.getElementById('cfg-failure-trigger')?.value),
      export_format: document.getElementById('cfg-export-format')?.value,
      sliding_window_days: Number(document.getElementById('cfg-sliding-window')?.value),
    };
    try {
      const saved = await api('/runtime-config', {method: 'PUT', body: JSON.stringify(config)});
      notify(`Server config сохранён, revision ${saved.revision}.`);
    } catch (error) { notify(error.message, true); }
    finally { event.currentTarget.disabled = false; }
  });

  loadLocalConfig();
  window.addEventListener('synapse-refresh', load); load();
})();
