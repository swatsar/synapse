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
  async function load() {
    try {
      const [system, security, memory, connectors] = await Promise.all(['system', 'security', 'memory', 'connectors'].map(name => api(`/settings/${name}`)));
      document.getElementById('settings').textContent = json({system: system.settings, security: security.settings, memory: memory.settings, connectors: connectors.settings});
      await loadBackups();
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
  function loadLocalConfig() {
    try {
      const saved = JSON.parse(localStorage.getItem(CFG_KEY) || '{}');
      if (saved.tier) document.getElementById('cfg-pref-tier').value = saved.tier;
      if (saved.latency) document.getElementById('cfg-latency-budget').value = saved.latency;
      if (saved.threshold) document.getElementById('cfg-success-threshold').value = saved.threshold;
      if (saved.trigger) document.getElementById('cfg-failure-trigger').value = saved.trigger;
      if (saved.format) document.getElementById('cfg-export-format').value = saved.format;
      if (saved.window) document.getElementById('cfg-sliding-window').value = saved.window;
    } catch (_) { /* ignore */ }
  }

  document.getElementById('save-local-cfg-btn')?.addEventListener('click', () => {
    const config = {
      tier: document.getElementById('cfg-pref-tier')?.value,
      latency: document.getElementById('cfg-latency-budget')?.value,
      threshold: document.getElementById('cfg-success-threshold')?.value,
      trigger: document.getElementById('cfg-failure-trigger')?.value,
      format: document.getElementById('cfg-export-format')?.value,
      window: document.getElementById('cfg-sliding-window')?.value,
    };
    localStorage.setItem(CFG_KEY, JSON.stringify(config));
    notify('Локальные параметры OmniRouter и самообучения успешно сохранены.');
  });

  loadLocalConfig();
  window.addEventListener('synapse-refresh', load); load();
})();
