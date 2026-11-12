(() => {
  'use strict';
  const {api, element: el, clear, notify, json} = window.synapse;

  const COMPONENT_ROLES = {
    planner: 'Разбирает задачу на шаги и строит план. Определяет, какие инструменты и данные понадобятся для выполнения.',
    critic: 'Проверяет промежуточные и финальные результаты, находит ошибки и противоречия, инициирует переделку при необходимости.',
    developer: 'Пишет и правит код, готовит патчи и проверяет их в изолированном рабочем окружении.',
    guardian: 'Security Manager: проверяет capabilities, уровень риска и необходимость подтверждения человеком перед опасными действиями.',
  };
  const COMPONENT_LETTERS = {planner: 'P', critic: 'C', developer: 'D', guardian: 'S'};
  const EXECUTOR_INFO = {
    codex: {
      title: 'OpenAI Codex CLI',
      role: 'Внешний исполнитель для задач в кодовой базе. Запускается по явному выбору и возвращает отчёт о выполнении.',
      link: '/settings.html#external-agents',
    },
    claude_code: {
      title: 'Claude Code',
      role: 'Внешний CLI-агент Anthropic для работы с файлами проекта. По умолчанию работает в режиме чтения.',
      link: '/settings.html#external-agents',
    },
  };

  function makeBadge(text, variant, withDot) {
    const badge = el('span', undefined, `badge${variant ? ` ${variant}` : ''}`);
    if (withDot) badge.append(el('span', undefined, 'dot'));
    badge.append(document.createTextNode(text));
    return badge;
  }

  function setMetric(name, value) {
    const node = document.querySelector(`[data-metric="${name}"]`);
    if (node) node.textContent = value;
  }

  function renderComponents(payload) {
    const root = document.getElementById('agents');
    if (!root) return;
    const agents = payload?.agents || [];
    const available = agents.filter(agent => agent.status === 'embedded');
    const counter = document.getElementById('components-count');
    if (counter) counter.textContent = agents.length ? `${available.length} из ${agents.length} доступны` : 'нет данных';
    setMetric('components', agents.length ? `${available.length}/${agents.length}` : '—');
    setMetric('components-note', agents.length ? 'встроено в единый runtime' : 'данные недоступны');
    clear(root);
    if (!agents.length) {
      root.append(el('p', 'Компоненты не зарегистрированы. Проверьте, что runtime запущен.', 'muted'));
      return;
    }
    for (const agent of agents) {
      const card = el('article', undefined, 'component-card');
      const icon = el('div', COMPONENT_LETTERS[agent.id] || (agent.name || '?').slice(0, 1).toUpperCase(), 'component-icon');
      const top = el('div', undefined, 'card-top');
      const title = el('div');
      title.append(el('h3', agent.name || agent.id), el('div', agent.type && agent.type !== agent.id ? `${agent.id} · ${agent.type}` : agent.id, 'model-id'));
      top.append(title, makeBadge(agent.status === 'embedded' ? 'Встроен' : 'Недоступен', agent.status === 'embedded' ? 'badge-ok' : 'badge-bad', true));
      card.append(icon, top);
      card.append(el('p', COMPONENT_ROLES[agent.id] || 'Роль описана в runtime, но подробное описание пока не добавлено.', 'component-role'));
      const foot = el('div', undefined, 'component-foot');
      foot.append(el('span', 'Работает внутри общего runtime', 'hint'));
      card.append(foot);
      root.append(card);
    }
  }

  function renderMetrics(integrations, agentList, opencode) {
    const executors = integrations?.executors || [];
    const agentById = new Map((agentList?.agents || []).map(item => [item.id, item]));
    const enabled = executors.filter(item => agentById.get(item.id)?.enabled ?? item.configured).length;
    setMetric('executors', executors.length ? `${enabled}/${executors.length}` : '—');
    setMetric('executors-note', executors.length ? 'Codex · Claude Code' : 'данные недоступны');

    const mcp = integrations?.mcp;
    setMetric('mcp', mcp ? mcp.configured_servers || 0 : '—');
    setMetric('mcp-note', mcp?.status === 'registry_available' ? 'реестр доступен' : 'статус неизвестен');

    const plugins = integrations?.plugins;
    setMetric('plugins', plugins ? plugins.configured_plugins || 0 : '—');
    setMetric('plugins-note', plugins?.status === 'runtime_available' ? 'реестр доступен' : 'статус неизвестен');
  }

  function renderIntegrations(integrations, agentList, opencode) {
    const root = document.getElementById('integration-cards');
    const raw = document.getElementById('integrations-raw');
    if (raw) raw.textContent = json({integrations, executors: agentList?.agents, opencode: opencode});
    if (!root) return;
    clear(root);
    if (!integrations) {
      root.append(el('p', 'Не удалось загрузить инвентарь интеграций.', 'error'));
      return;
    }

    const agentById = new Map((agentList?.agents || []).map(item => [item.id, item]));

    const mcp = integrations.mcp || {};
    const mcpCard = el('article', undefined, 'integration-card');
    mcpCard.append(
      el('div', 'MCP', 'component-icon info'),
      (() => { const top = el('div', undefined, 'card-top'); top.append(el('h3', 'MCP-серверы'), makeBadge(mcp.status === 'registry_available' ? 'Реестр доступен' : 'Недоступно', mcp.status === 'registry_available' ? 'badge-ok' : 'badge-bad', true)); return top; })(),
      el('p', 'Model Context Protocol — способ подключать внешние инструменты и источники данных как безопасные сервисы.', 'component-role'),
    );
    const mcpMeta = el('div', undefined, 'card-meta');
    mcpMeta.append(makeBadge(`Серверов: ${mcp.configured_servers || 0}`, 'badge'), makeBadge((mcp.transports || []).join(' · ') || 'stdio', 'badge'));
    mcpCard.append(mcpMeta);
    root.append(mcpCard);

    const plugins = integrations.plugins || {};
    const pluginsCard = el('article', undefined, 'integration-card');
    pluginsCard.append(
      el('div', 'PL', 'component-icon info'),
      (() => { const top = el('div', undefined, 'card-top'); top.append(el('h3', 'Плагины'), makeBadge(plugins.status === 'runtime_available' ? 'Runtime доступен' : 'Недоступно', plugins.status === 'runtime_available' ? 'badge-ok' : 'badge-bad', true)); return top; })(),
      el('p', 'Расширения с manifest’ом и собственным жизненным циклом. Регистрация manifest’а ещё не означает активацию: включение проходит проверку capabilities.', 'component-role'),
    );
    const pluginMeta = el('div', undefined, 'card-meta');
    pluginMeta.append(makeBadge(`Зарегистрировано: ${plugins.configured_plugins || 0}`, 'badge'));
    pluginsCard.append(pluginMeta);
    root.append(pluginsCard);

    for (const executor of integrations.executors || []) {
      const info = EXECUTOR_INFO[executor.id] || {title: executor.id, role: 'Внешний исполнитель задач.', link: '/settings.html#external-agents'};
      const agent = agentById.get(executor.id) || {};
      const connected = agent.enabled ?? executor.configured;
      const found = executor.configured || Boolean(agent.command);
      const statusText = connected ? 'Подключён' : (found ? 'Найден, выключен' : 'Не найден');
      const statusVariant = connected ? 'badge-ok' : (found ? 'badge-warn' : 'badge-muted');
      const card = el('article', undefined, 'integration-card');
      const top = el('div', undefined, 'card-top');
      const title = el('div');
      title.append(el('h3', info.title), el('div', executor.id, 'model-id'));
      top.append(title, makeBadge(statusText, statusVariant, true));
      card.append(el('div', 'CLI', 'component-icon info'), top);
      card.append(el('p', info.role, 'component-role'));
      const meta = el('div', undefined, 'card-meta');
      meta.append(makeBadge(`Режим: ${executor.safe_mode || 'read-only'}`, 'badge'));
      if (executor.timeout_seconds) meta.append(makeBadge(`Таймаут: ${Math.round(executor.timeout_seconds)} с`, 'badge'));
      if (executor.write_enabled) meta.append(makeBadge('Запись разрешена', 'badge-warn'));
      card.append(meta);
      if (agent.command) {
        const command = el('div', Array.isArray(agent.command) ? agent.command.join(' ') : String(agent.command), 'model-id');
        command.title = command.textContent;
        card.append(command);
      }
      const foot = el('div', undefined, 'component-foot');
      const link = el('a', connected ? 'Изменить в настройках' : 'Подключить в настройках', 'link');
      link.href = info.link;
      foot.append(el('span', connected ? 'Запуск проходит approval' : 'Требуется явное подключение', 'hint'), link);
      card.append(foot);
      root.append(card);
    }

    const opencodeCard = el('article', undefined, 'integration-card');
    const opencodeLabels = {
      ready: 'Готов',
      quota_exhausted: 'Лимит исчерпан',
      degraded: 'Ограниченно доступен',
      not_found: 'Не найден',
    };
    const opencodeStatus = opencodeLabels[opencode?.status] || opencode?.status || 'Не найден';
    const opencodeVariant = opencode?.status === 'ready' ? 'badge-ok' : (opencode?.status === 'quota_exhausted' ? 'badge-warn' : 'badge-muted');
    const opencodeTop = el('div', undefined, 'card-top');
    opencodeTop.append(el('h3', 'OpenCode'), makeBadge(opencodeStatus, opencodeVariant, true));
    opencodeCard.append(el('div', 'OC', 'component-icon info'), opencodeTop);
    opencodeCard.append(el('p', 'Основной runtime внешних моделей и агентских CLI. Synapse читает только несекретную конфигурацию, а при исчерпании бесплатного лимита честно переключается на локальную модель. Каталог моделей и пути к CLI берутся напрямую из OpenCode и PATH.', 'component-role'));
    const opencodeMeta = el('div', undefined, 'card-meta');
    opencodeMeta.append(makeBadge(`Моделей: ${opencode?.model_count ?? (opencode?.models || []).length}`, 'badge'));
    const opencodeQuota = opencode?.quota || {};
    if (opencodeQuota.exhausted) {
      opencodeMeta.append(makeBadge(`Лимит: повтор через ${opencodeQuota.retry_after_seconds || 0} с`, 'badge-warn'));
    }
    const opencodeAgents = opencode?.agents || [];
    if (opencodeAgents.length) {
      for (const agent of opencodeAgents) {
        opencodeMeta.append(makeBadge(`${agent.display_name || agent.id}${agent.version ? ` ${agent.version}` : ''}`, agent.available ? 'badge-ok' : 'badge-muted'));
      }
    } else {
      opencodeMeta.append(makeBadge('Агенты не обнаружены', 'badge-muted'));
    }
    opencodeCard.append(opencodeMeta);
    if (opencode?.last_error) {
      const error = el('div', opencode.last_error, 'model-id');
      error.title = opencode.last_error;
      opencodeCard.append(error);
    }
    const opencodeFoot = el('div', undefined, 'component-foot');
    opencodeFoot.append(el('span', 'Каталог моделей: OpenCode CLI', 'hint'));
    const opencodeLink = el('a', 'Открыть настройки OpenCode', 'link');
    opencodeLink.href = '/settings.html#opencode';
    opencodeFoot.append(opencodeLink);
    opencodeCard.append(opencodeFoot);
    root.append(opencodeCard);
  }

  async function load() {
    const [components, integrations, agentList, opencode] = await Promise.allSettled([
      api('/agents'),
      api('/integrations'),
      api('/integrations/agents'),
      api('/integrations/opencode'),
    ]);
    const componentsValue = components.status === 'fulfilled' ? components.value : null;
    const integrationsValue = integrations.status === 'fulfilled' ? integrations.value : null;
    const agentsValue = agentList.status === 'fulfilled' ? agentList.value : null;
    const opencodeValue = opencode.status === 'fulfilled' ? opencode.value : null;

    if (componentsValue) {
      renderComponents(componentsValue);
    } else {
      const root = document.getElementById('agents');
      if (root) clear(root).append(el('p', `Не удалось загрузить встроенные компоненты: ${components.reason?.message || 'неизвестная ошибка'}`, 'error'));
    }
    renderMetrics(integrationsValue, agentsValue, opencodeValue);
    renderIntegrations(integrationsValue, agentsValue, opencodeValue);
    if (!integrationsValue) notify('Часть данных об интеграциях недоступна.', true);
  }

  window.addEventListener('synapse-refresh', load);
  load();
})();
