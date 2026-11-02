(() => {
  'use strict';
  const {api, element: el, clear, notify} = window.synapse;
  async function load() {
    const root = document.getElementById('agents');
    try {
      const data = await api('/agents'); clear(root);
      if (!data.agents.length) { root.append(el('p', 'Компоненты не зарегистрированы.', 'muted')); return; }
      const table = el('table'); const head = el('thead'); const hr = el('tr');
      for (const name of ['Компонент', 'Тип', 'Состояние', 'ID']) hr.append(el('th', name));
      head.append(hr); table.append(head); const body = el('tbody');
      for (const agent of data.agents) {
        const row = el('tr');
        for (const value of [agent.name, agent.type, agent.status, agent.id]) row.append(el('td', value));
        body.append(row);
      }
      table.append(body); root.append(table);
    } catch (error) { clear(root).append(el('p', error.message, 'error')); notify('Ошибка загрузки компонентов.', true); }
  }
  window.addEventListener('synapse-refresh', load); load();
})();
