(() => {
  'use strict';
  const {api, element: el, clear, notify} = window.synapse;
  async function load() {
    const root = document.getElementById('agents');
    try {
      const data = await api('/agents'); clear(root);
      if (data.agents.length) {
        const table = el('table'); const head = el('thead'); const hr = el('tr');
        for (const name of ['Компонент', 'Тип', 'Состояние']) hr.append(el('th', name));
        head.append(hr); table.append(head); const body = el('tbody');
        for (const agent of data.agents) {
          const row = el('tr');
          for (const value of [agent.name, agent.type, agent.status]) row.append(el('td', value));
          body.append(row);
        }
        table.append(body); root.append(table);
      } else root.append(el('p', 'Компоненты не зарегистрированы.', 'muted'));
      await loadIntegrations();
    } catch (error) { clear(root).append(el('p', error.message, 'error')); notify('Ошибка загрузки компонентов.', true); }
  }
  async function loadIntegrations() {
    const root = document.getElementById('integrations');
    if (!root) return;
    try {
      const data = await api('/integrations'); clear(root);
      const rows = [
        ['MCP', data.mcp.status, data.mcp.note],
        ['Plugins', data.plugins.status, data.plugins.note],
        ['Velly', data.vally.status, data.vally.note],
        ...data.executors.map(item => [item.id, `${item.status} (${item.configured ? 'включён' : 'отключён'})`, `${item.safe_mode}; ${item.supports.join(', ')}`]),
      ];
      const table = el('table'); const head = el('thead'); const hr = el('tr');
      for (const name of ['Интеграция', 'Статус', 'Пояснение']) hr.append(el('th', name));
      head.append(hr); table.append(head); const body = el('tbody');
      rows.forEach(values => { const row = el('tr'); values.forEach(value => row.append(el('td', value))); body.append(row); });
      table.append(body); root.append(table);
    } catch (error) { clear(root).append(el('p', error.message, 'error')); }
  }
  window.addEventListener('synapse-refresh', load); load();
})();
