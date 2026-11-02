(() => {
  'use strict';
  const {api, element: el, clear, notify} = window.synapse;

  async function loadCatalog() {
    const root = document.getElementById('router-catalog');
    if (!root) return;
    try {
      const data = await api('/router/catalog');
      clear(root);
      const catalog = data.catalog || [];
      if (!catalog.length) {
        root.append(el('p', 'Каталог моделей пуст.', 'muted'));
        return;
      }
      for (const m of catalog) {
        const row = el('div', undefined, 'row');
        const info = el('div');
        const badges = `${m.provider.toUpperCase()} · ${m.tier} · ${m.cost_tier} · Context: ${(m.context_window / 1024).toFixed(0)}k`;
        info.append(
          el('strong', `${m.display_name} (${m.id})`),
          el('div', `${badges} · Сильные стороны: ${(m.strengths || []).join(', ')}`, 'muted')
        );
        const caps = el('div', undefined, 'capability-tags');
        if (m.capabilities?.computer_use) caps.append(el('span', 'computer_use', 'capability-tag'));
        if (m.capabilities?.tool_calling) caps.append(el('span', 'tools', 'capability-tag'));
        if (m.capabilities?.reasoning) caps.append(el('span', 'reasoning', 'capability-tag'));
        if (m.is_local) caps.append(el('span', 'offline', 'capability-tag'));
        row.append(info, caps);
        root.append(row);
      }
    } catch (error) {
      clear(root).append(el('p', `Не удалось загрузить каталог роутера: ${error.message}`, 'error'));
    }
  }

  async function testRouteSandbox(event) {
    if (event) event.preventDefault();
    const taskInput = document.getElementById('sandbox-task');
    const taskText = taskInput?.value.trim();
    if (!taskText) return;
    const btn = document.getElementById('test-route-btn');
    if (btn) btn.disabled = true;
    try {
      const data = await api('/router/route', {
        method: 'POST',
        body: JSON.stringify({task: taskText}),
      });
      const d = data.decision;
      const resCard = document.getElementById('sandbox-result');
      if (resCard) {
        resCard.hidden = false;
        document.getElementById('sandbox-model').textContent = `${d.model} (${d.provider})`;
        document.getElementById('sandbox-domain').textContent = `Домен: ${d.detected_domain}`;
        document.getElementById('sandbox-cost').textContent = `Стоимость: ${d.cost_tier}`;
        const avail = document.getElementById('sandbox-availability');
        avail.textContent = d.provider_available ? 'Провайдер активен' : 'Локальный режим / без ключа';
        avail.className = `status-pill ${d.provider_available ? 'completed' : 'running'}`;
        document.getElementById('sandbox-reason').textContent = d.reason;
        const fallbacks = (d.fallback_chain || []).map(f => `${f.model} (${f.provider})`).join(' → ') || 'нет';
        document.getElementById('sandbox-fallbacks').textContent = fallbacks;
      }
      notify(`Роутер выбрал: ${d.model}`);
    } catch (error) {
      notify(`Ошибка маршрутизации: ${error.message}`, true);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function load() {
    const root = document.getElementById('providers');
    try {
      const data = await api('/providers'); clear(root);
      if (!data.providers.length) { root.append(el('p', 'Профили не настроены.', 'muted')); return; }
      for (const item of data.providers) {
        const row = el('div', undefined, 'row'); const info = el('div');
        info.append(el('strong', item.name || item.id), el('div', `Модели: ${(item.models || []).join(', ') || 'не заданы'} · ${item.credential_ref || 'без credential_ref'}`, 'muted'));
        const test = el('button', 'Проверить соединение', 'secondary');
        test.addEventListener('click', async () => { test.disabled = true; try { const result = await api(`/providers/${encodeURIComponent(item.id)}/test`, {method: 'POST'}); notify(jsonMessage(result), !result.success); } catch (error) { notify(error.message, true); } finally { test.disabled = false; } });
        const remove = el('button', 'Удалить', 'danger');
        remove.addEventListener('click', async () => { if (!window.confirm(`Удалить профиль ${item.id}?`)) return; try { await api(`/providers/${encodeURIComponent(item.id)}`, {method: 'DELETE'}); notify('Профиль удалён.'); await load(); } catch (error) { notify(error.message, true); } });
        const controls = el('div'); controls.append(test, remove); row.append(info, controls); root.append(row);
      }
    } catch (error) { clear(root).append(el('p', error.message, 'error')); }
  }

  function jsonMessage(value) { return value.success ? 'Соединение успешно.' : `Проверка не пройдена: ${value.error || JSON.stringify(value)}`; }

  document.getElementById('sandbox-form')?.addEventListener('submit', testRouteSandbox);

  document.getElementById('provider-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    try {
      await api('/providers', {method: 'POST', body: JSON.stringify({name: document.getElementById('provider-name').value, api_key: document.getElementById('provider-key').value || undefined, models: document.getElementById('provider-models').value.split(',').map(x => x.trim()).filter(Boolean), priority: Number(document.getElementById('provider-priority').value)})});
      notify('Профиль сохранён. Для использования задайте переменную окружения и перезапустите Synapse.'); await load();
    } catch (error) { notify(error.message, true); }
  });

  window.addEventListener('synapse-refresh', () => { load(); loadCatalog(); });
  load();
  loadCatalog();
})();
