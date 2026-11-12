(() => {
  'use strict';
  const {api, element: el, clear, notify} = window.synapse;

  const DOMAIN_LABELS = {
    general: 'Общая задача',
    code: 'Код и рефакторинг',
    coding: 'Код и рефакторинг',
    reasoning: 'Сложные рассуждения',
    computer_use: 'Браузер и UI',
    browser: 'Браузер и UI',
    local_privacy: 'Приватные данные',
    privacy: 'Приватные данные',
    creative: 'Тексты и контент',
    math: 'Математика',
    data: 'Анализ данных',
    vision: 'Изображения',
    security: 'Безопасность',
  };
  const COST_LABELS = {FREE: 'Бесплатно', '$': 'Низкая стоимость', '$$': 'Средняя стоимость', '$$$': 'Высокая стоимость'};
  const TIER_LABELS = {local: 'Локальная', frontier: 'Frontier', standard: 'Standard', fast: 'Быстрая'};
  const PROVIDER_LABELS = {
    anthropic: 'Anthropic', openai: 'OpenAI', ollama: 'Ollama',
    local_transformers: 'Локальные веса', google: 'Google', openrouter: 'OpenRouter',
  };
  const STRENGTH_LABELS = {
    complex_reasoning: 'сложные рассуждения', system_architecture: 'архитектура систем',
    security_audit: 'аудит безопасности', deep_refactoring: 'глубокий рефакторинг',
    coding: 'код', agentic_workflows: 'агентные сценарии', computer_use: 'управление браузером',
    tool_use: 'инструменты', data_analysis: 'анализ данных', low_latency: 'низкая задержка',
    fast_triage: 'быстрая сортировка', classification: 'классификация', summarization: 'суммаризация',
    creative_writing: 'тексты', extended_synthesis: 'синтез материалов', documentation: 'документация',
    math: 'математика', competitive_coding: 'олимпиадный код', formal_logic: 'формальная логика',
    scientific_reasoning: 'научные рассуждения', general_intelligence: 'общие задачи',
    multimodal: 'мультимодальность', fast_reasoning: 'быстрые рассуждения', tools: 'инструменты',
    fast_response: 'быстрый ответ', cost_efficiency: 'экономия', triage: 'сортировка запросов',
    light_chat: 'лёгкий чат', local_privacy: 'приватность', offline: 'офлайн',
    general_tasks: 'общие задачи', zero_cost: 'бесплатно', local_coding: 'локальный код',
    offline_scripts: 'офлайн-скрипты', refactoring: 'рефакторинг', minimal_ram: 'мало памяти',
    offline_lightweight: 'лёгкий офлайн', agent_executor: 'исполнитель агента',
    code_reasoning: 'рассуждения о коде', fast_logic: 'быстрая логика',
  };
  const CAPABILITY_LABELS = {
    tool_calling: 'Инструменты', computer_use: 'Браузер', vision: 'Изображения',
    reasoning: 'Рассуждения', streaming: 'Стриминг',
  };

  const state = {providers: [], catalog: [], defaultModel: null, health: null, filter: 'all'};
  const BASE_HEALTH_PROVIDERS = new Set(['anthropic', 'openai', 'ollama']);

  function isConfigured(item) {
    return Boolean(item?.available || item?.key_configured || item?.credential_configured);
  }

  function isReady(id, item) {
    if (id === 'ollama') return Boolean(item?.available && (item?.installed_models || []).length);
    return isConfigured(item);
  }

  function healthEntries() {
    const providers = state.health?.providers || {};
    const knownProfiles = new Set((state.providers || []).map(profile => profile.id));
    return Object.entries(providers).filter(([id]) => BASE_HEALTH_PROVIDERS.has(id) || knownProfiles.has(id));
  }

  function healthLabel(id, item) {
    if (PROVIDER_LABELS[id]) return PROVIDER_LABELS[id];
    const profile = (state.providers || []).find(candidate => candidate.id === id);
    return profile?.name || item?.display_name || id;
  }

  function label(map, value, fallback) {
    if (value === undefined || value === null || value === '') return fallback || '—';
    return map[value] || String(value).replace(/_/g, ' ');
  }

  function makeBadge(text, variant, withDot) {
    const badge = el('span', undefined, `badge${variant ? ` ${variant}` : ''}`);
    if (withDot) badge.append(el('span', undefined, 'dot'));
    badge.append(document.createTextNode(text));
    return badge;
  }

  function formatContext(value) {
    if (!value) return 'контекст не указан';
    if (value >= 1000000) return `контекст ${(value / 1000000).toFixed(value % 1000000 ? 1 : 0)}M токенов`;
    if (value >= 1000) return `контекст ${Math.round(value / 1000)}k токенов`;
    return `контекст ${value} токенов`;
  }

  function modelName(id) {
    const found = state.catalog.find(model => model.id === id);
    return found ? found.display_name : id;
  }

  function plural(count, one, few, many) {
    const value = Math.abs(Number(count)) % 100;
    const last = value % 10;
    if (value > 10 && value < 20) return many;
    if (last === 1) return one;
    if (last >= 2 && last <= 4) return few;
    return many;
  }

  function friendlyError(message) {
    const text = String(message || '').trim();
    if (/ConnectError|Connection refused|ECONNREFUSED|Failed to connect|Network is unreachable/i.test(text)) {
      return 'сервер не отвечает по указанному адресу. Проверьте, запущен ли провайдер (для Ollama — приложение Ollama) и верен ли базовый URL';
    }
    if (/timed? ?out|Timeout/i.test(text)) {
      return 'превышено время ожидания. Проверьте сеть, VPN или адрес API';
    }
    if (/401|403|Unauthorized|Forbidden|authentication|invalid.*key/i.test(text)) {
      return 'провайдер отклонил ключ (401/403). Проверьте, что секрет существует и действителен';
    }
    if (/404|not found/i.test(text)) {
      return 'адрес API не найден (404). Проверьте базовый URL и протокол';
    }
    return text || 'неизвестная ошибка';
  }

  function humanReason(reason) {
    const text = String(reason || '').trim();
    const patterns = [
      [/^Explicitly requested model '(.+)'\.$/, 'Явно запрошена модель «$1».'],
      [/^Task requires local offline execution or strict data privacy\.$/, 'Задача требует локального выполнения или строгой приватности данных.'],
      [/^Preference '(.+)' tier: routed to '(.+)'\.$/, 'Приоритет «$1»: выбрана модель «$2».'],
      [/^Task involves GUI\/browser interactions.*$/, 'Задача связана с браузером: у Claude 5 Sonnet есть встроенные возможности управления интерфейсом.'],
      [/^Task involves deep (.+) analysis: Routed to frontier Claude 5 Opus\.$/, 'Задача требует глубокого анализа ($1): выбрана frontier-модель Claude 5 Opus.'],
      [/^Task requires formal logic \/ mathematical derivation.*$/, 'Задача требует формальной логики или математического вывода: выбрана OpenAI o1.'],
      [/^Task requires software engineering \/ code generation.*$/, 'Задача про разработку и генерацию кода: выбрана Claude 5 Sonnet, которая сильна в кодинге.'],
      [/^Lightweight query requiring ultra-low latency.*$/, 'Лёгкий запрос с требованием минимальной задержки: выбрана Claude 5 Haiku.'],
      [/^Standard task routing to primary balanced model '(.+)'\.$/, 'Стандартная задача: выбрана основная сбалансированная модель «$1».'],
      [/^No provider satisfies.*$/s, 'Ни один провайдер не подошёл под ограничения задачи или все недоступны.'],
    ];
    for (const [pattern, template] of patterns) {
      if (pattern.test(text)) return text.replace(pattern, template);
    }
    return text || 'Роутер не объяснил решение.';
  }

  function renderMetrics() {
    const providers = state.providers || [];
    const catalog = state.catalog || [];
    const entries = healthEntries();
    const ready = entries.filter(([id, item]) => isReady(id, item)).length;
    const enabled = providers.filter(item => item.enabled !== false).length;

    const set = (name, value) => {
      const node = document.querySelector(`[data-metric="${name}"]`);
      if (node) node.textContent = value;
    };
    set('providers', providers.length);
    set('providers-note', providers.length ? `${enabled} включено · приоритет 1 — первый` : 'пока не добавлены');
    set('models', catalog.length || '—');
    const sources = new Set(catalog.map(model => model.provider)).size;
    set('models-note', catalog.length ? `${catalog.filter(model => model.is_local).length} локальных · ${sources} ${plural(sources, 'источник', 'источника', 'источников')}` : 'каталог загружается');
    set('ready', entries.length ? `${ready} из ${entries.length}` : '—');
    set('ready-note', entries.length ? entries.map(([id, item]) => healthLabel(id, item)).join(' · ') : 'нет данных роутера');
    const defaultId = state.health?.default_model || state.defaultModel;
    set('default', defaultId ? modelName(defaultId) : '—');
    set('default-note', defaultId && modelName(defaultId) !== defaultId ? defaultId : 'выбор OmniRouter');
  }

  function renderHealth() {
    const root = document.getElementById('provider-health');
    const counter = document.getElementById('health-count');
    if (!root) return;
    const entries = healthEntries();
    const ready = entries.filter(([id, item]) => isReady(id, item)).length;
    if (counter) counter.textContent = entries.length ? `${ready} из ${entries.length} готовы` : 'нет данных';
    clear(root);
    if (!entries.length) {
      const empty = el('div', undefined, 'empty-state');
      empty.append(el('strong', 'Нет данных о доступности'), el('span', 'Роутер не вернул статус провайдеров. Проверьте, что сервис запущен и /router/health отвечает.'));
      root.append(empty);
      return;
    }
    for (const [id, item] of entries) {
      const isOllama = id === 'ollama';
      const isBase = BASE_HEALTH_PROVIDERS.has(id);
      const models = item.installed_models || [];
      let statusText;
      let variant;
      if (isOllama) {
        statusText = item.available ? 'Запущена' : 'Не запущена';
        variant = item.available ? 'badge-ok' : 'badge-warn';
      } else if (item.enabled === false) {
        statusText = 'Отключён';
        variant = 'badge-muted';
      } else if (item.available) {
        statusText = 'Доступен';
        variant = 'badge-ok';
      } else if (item.auth_type === 'none') {
        statusText = 'Нет связи';
        variant = 'badge-warn';
      } else if (isConfigured(item)) {
        statusText = 'Нет связи';
        variant = 'badge-warn';
      } else {
        statusText = 'Ключ не задан';
        variant = 'badge-muted';
      }
      const card = el('article', undefined, 'provider-card');
      const top = el('div', undefined, 'card-top');
      const title = el('div');
      title.append(el('h3', healthLabel(id, item)), el('div', isBase ? (item.tier ? `класс ${label(TIER_LABELS, item.tier)}` : id) : 'профиль провайдера', 'model-id'));
      top.append(title, makeBadge(statusText, variant, true));
      card.append(top);
      const meta = el('div', undefined, 'card-meta');
      if (isOllama) {
        meta.append(makeBadge(`Моделей: ${models.length}`, models.length ? 'badge-ok' : 'badge'));
        if (item.endpoint) meta.append(makeBadge(item.endpoint, 'badge'));
        if (models.length) meta.append(makeBadge(models.slice(0, 3).join(', '), 'badge'));
      } else {
        meta.append(makeBadge(isBase && item.tier ? label(TIER_LABELS, item.tier) : 'настроенный профиль', 'badge'));
      }
      card.append(meta);
      let note;
      if (isOllama) {
        note = !item.available
          ? 'Ollama не отвечает. Запустите приложение Ollama и скачайте модель, чтобы работать офлайн.'
          : models.length
            ? 'Ollama отвечает, локальные модели готовы к работе без интернета.'
            : 'Ollama отвечает, но моделей пока нет. Скачайте модель через Ollama, чтобы работать офлайн.';
      } else if (item.enabled === false) {
        note = 'Профиль отключён и не участвует в маршрутизации. Включите его в разделе «Профили провайдеров» ниже.';
      } else if (item.auth_type === 'none') {
        note = item.available
          ? 'Профиль работает без ключа и отвечает на запросы.'
          : 'Профиль работает без ключа, но сервер по указанному адресу не отвечает. Проверьте, что он запущен, и верен ли базовый URL.';
      } else if (isConfigured(item)) {
        note = 'Ключ найден. Проверьте соединение в профиле провайдера — оно может зависеть от квоты и сети.';
      } else if (isBase) {
        note = `Ключ ${id.toUpperCase()}_API_KEY не найден в окружении. Добавьте его и перезапустите Synapse.`;
      } else {
        note = 'У профиля не задан ключ. Откройте «Профили провайдеров» ниже и укажите секрет или выберите авторизацию без ключа.';
      }
      card.append(el('p', note, 'hint'));
      root.append(card);
    }
  }

  function catalogFilter(model) {
    if (state.filter === 'all') return true;
    if (state.filter === 'local') return Boolean(model.is_local);
    return model.tier === state.filter;
  }

  function renderCatalog() {
    const root = document.getElementById('router-catalog');
    if (!root) return;
    const catalog = state.catalog || [];
    const visible = catalog.filter(catalogFilter);
    const counter = document.getElementById('catalog-count');
    if (counter) counter.textContent = catalog.length ? `${visible.length} из ${catalog.length}` : 'пусто';
    clear(root);
    if (!catalog.length) {
      const empty = el('div', undefined, 'empty-state');
      empty.append(el('strong', 'Каталог пуст'), el('span', 'OmniRouter не получил ни одной модели. Проверьте конфигурацию runtime.'));
      root.append(empty);
      return;
    }
    if (!visible.length) {
      const empty = el('div', undefined, 'empty-state');
      empty.append(el('strong', 'В этой категории нет моделей'), el('span', 'Выберите другой фильтр или добавьте провайдера с моделями этого типа.'));
      root.append(empty);
      return;
    }
    for (const model of visible) {
      const card = el('article', undefined, 'model-card');
      const top = el('div', undefined, 'card-top');
      const title = el('div');
      title.append(
        el('h3', model.display_name || model.id),
        el('div', `${model.id} · ${label(PROVIDER_LABELS, model.provider)}`, 'model-id'),
      );
      const tierVariant = model.is_local ? 'badge-local' : (model.tier === 'frontier' ? 'badge-accent' : 'badge-info');
      top.append(title, makeBadge(label(TIER_LABELS, model.tier, 'Модель'), tierVariant));
      card.append(top);

      const meta = el('div', undefined, 'model-meta');
      meta.append(makeBadge(label(COST_LABELS, model.cost_tier, 'стоимость неизвестна'), model.cost_tier === 'FREE' ? 'badge-ok' : 'badge-warn'));
      if (model.capabilities?.computer_use) meta.append(makeBadge('Браузер', 'badge'));
      if (model.capabilities?.tool_calling) meta.append(makeBadge('Инструменты', 'badge'));
      if (model.capabilities?.vision) meta.append(makeBadge('Изображения', 'badge'));
      card.append(meta);

      const strengths = (model.strengths || []).slice(0, 5).map(item => label(STRENGTH_LABELS, item));
      card.append(el('p', strengths.length ? `Сильные стороны: ${strengths.join(', ')}.` : 'Описание возможностей не задано.', 'model-strengths'));

      const foot = el('div', undefined, 'card-foot');
      foot.append(el('span', formatContext(model.context_window), 'model-context'));
      if (model.max_output) foot.append(el('span', `вывод до ${(model.max_output / 1024).toFixed(0)}k`, 'model-context'));
      card.append(foot);
      root.append(card);
    }
  }

  function renderProviders() {
    const root = document.getElementById('providers');
    if (!root) return;
    const providers = [...(state.providers || [])].sort((a, b) => (a.priority || 99) - (b.priority || 99));
    const counter = document.getElementById('providers-count');
    if (counter) counter.textContent = providers.length ? `${providers.length} профил${providers.length === 1 ? 'ь' : providers.length < 5 ? 'я' : 'ей'}` : 'нет профилей';
    clear(root);
    if (!providers.length) {
      const empty = el('div', undefined, 'empty-state');
      empty.append(
        el('strong', 'Провайдеры ещё не подключены'),
        el('span', 'Synapse работает и без внешних ключей: задачи выполняются детерминированным runtime, а локальные модели доступны через Ollama. Чтобы добавить внешнюю модель, заполните форму выше.'),
      );
      const link = el('a', 'Перейти к добавлению провайдера');
      link.href = '#add-provider';
      empty.append(el('br'), link);
      root.append(empty);
      return;
    }
    for (const provider of providers) {
      const card = el('article', undefined, 'provider-card');
      const top = el('div', undefined, 'card-top');
      const title = el('div');
      title.append(
        el('h3', provider.name || provider.id),
        el('div', `${provider.api_mode || 'openai_compatible'} · ${provider.auth_type || 'api_key'}`, 'model-id'),
      );
      const enabled = provider.enabled !== false;
      top.append(title, makeBadge(enabled ? 'Включён' : 'Выключен', enabled ? 'badge-ok' : 'badge-bad', true));
      card.append(top);

      const models = [...new Set([provider.default_model, ...(provider.fallback_models || []), ...(provider.models || [])].filter(Boolean))];
      const modelRow = el('div', undefined, 'provider-models');
      if (models.length) {
        for (const model of models) modelRow.append(el('span', model, 'capability-tag'));
      } else {
        modelRow.append(el('span', 'Модели не указаны — будут загружены из API провайдера', 'hint'));
      }
      card.append(modelRow);

      const meta = el('div', undefined, 'card-meta');
      const credential = provider.credential_ref;
      meta.append(makeBadge(credential ? 'Секрет привязан' : (provider.auth_type === 'none' ? 'Без авторизации' : 'Секрет не задан'), credential || provider.auth_type === 'none' ? 'badge-info' : 'badge-warn'));
      if (provider.base_url) meta.append(makeBadge(provider.base_url, 'badge'));
      card.append(meta);

      const priorityRow = el('div', undefined, 'chip-row');
      priorityRow.append(el('span', 'Приоритет', 'hint'));
      const select = el('select', undefined, 'priority-select');
      select.setAttribute('aria-label', `Приоритет провайдера ${provider.id}`);
      for (let value = 1; value <= 10; value += 1) {
        const option = el('option', String(value));
        option.value = String(value);
        if (Number(provider.priority) === value) option.selected = true;
        select.append(option);
      }
      select.addEventListener('change', async () => {
        select.disabled = true;
        try {
          await api(`/providers/${encodeURIComponent(provider.id)}/priority`, {method: 'PATCH', body: JSON.stringify({priority: Number(select.value)})});
          notify(`Приоритет «${provider.name || provider.id}»: ${select.value}.`);
          provider.priority = Number(select.value);
          renderProviders();
        } catch (error) {
          notify(`Не удалось изменить приоритет: ${friendlyError(error.message)}.`, true);
          select.value = String(provider.priority || 3);
        } finally {
          select.disabled = false;
        }
      });
      priorityRow.append(select);
      card.append(priorityRow);

      const result = el('p', undefined, 'inline-result');
      result.hidden = true;
      card.append(result);

      const actions = el('div', undefined, 'provider-actions');
      const test = el('button', 'Проверить соединение', 'small-button');
      test.type = 'button';
      test.addEventListener('click', async () => {
        const initial = test.textContent;
        test.disabled = true;
        test.textContent = 'Проверяю…';
        result.hidden = false;
        result.className = 'inline-result';
        result.textContent = 'Отправляю реальный запрос к API провайдера…';
        try {
          const response = await api(`/providers/${encodeURIComponent(provider.id)}/test`, {method: 'POST'});
          if (response.success) {
            const latency = response.latency_ms !== undefined && response.latency_ms !== null ? ` · ${Math.round(response.latency_ms)} мс` : '';
            const model = response.model ? ` · модель ${response.model}` : '';
            result.className = 'inline-result ok';
            result.textContent = `Соединение работает${latency}${model}.`;
            notify(`Соединение с «${provider.name || provider.id}» работает.`);
          } else {
            result.className = 'inline-result bad';
            result.textContent = `Не удалось подключиться: ${friendlyError(response.error)}.`;
            notify(`Проверка «${provider.name || provider.id}» не пройдена.`, true);
          }
        } catch (error) {
          result.className = 'inline-result bad';
          result.textContent = `Ошибка проверки: ${friendlyError(error.message)}.`;
          notify(friendlyError(error.message), true);
        } finally {
          test.disabled = false;
          test.textContent = initial;
        }
        loadHealth();
      });

      const modelsButton = el('button', 'Показать модели', 'small-button');
      modelsButton.type = 'button';
      modelsButton.addEventListener('click', async () => {
        modelsButton.disabled = true;
        result.hidden = false;
        result.className = 'inline-result';
        result.textContent = 'Запрашиваю список моделей у провайдера…';
        try {
          const response = await api(`/providers/${encodeURIComponent(provider.id)}/models`);
          const list = response.models || [];
          if (!list.length) {
            result.className = 'inline-result';
            result.textContent = 'Провайдер не вернул ни одной модели. Проверьте ключ и базовый URL.';
          } else {
            result.className = 'inline-result ok';
            result.textContent = `Доступно моделей: ${list.length}. ${list.slice(0, 8).map(item => item.id || item.model_id || item).join(', ')}${list.length > 8 ? '…' : ''}`;
          }
        } catch (error) {
          result.className = 'inline-result bad';
          result.textContent = `Не удалось получить модели: ${friendlyError(error.message)}.`;
        } finally {
          modelsButton.disabled = false;
        }
      });

      const remove = el('button', 'Удалить', 'small-button danger');
      remove.type = 'button';
      remove.addEventListener('click', async () => {
        if (!window.confirm(`Удалить профиль «${provider.name || provider.id}»? Это не удалит ключ из хранилища.`)) return;
        remove.disabled = true;
        try {
          await api(`/providers/${encodeURIComponent(provider.id)}`, {method: 'DELETE'});
          notify('Профиль удалён.');
          await load();
          await loadHealth();
        } catch (error) {
          notify(friendlyError(error.message), true);
          remove.disabled = false;
        }
      });
      actions.append(test, modelsButton, remove);
      card.append(actions);

      const details = el('details', undefined, 'tech-details');
      details.append(el('summary', 'Технические детали профиля'));
      const pre = el('pre');
      pre.textContent = JSON.stringify(provider, null, 2);
      details.append(pre);
      card.append(details);
      root.append(card);
    }
  }

  async function loadCatalog() {
    const root = document.getElementById('router-catalog');
    try {
      const data = await api('/router/catalog');
      state.catalog = data.catalog || [];
      state.defaultModel = data.default_model || state.defaultModel;
      renderCatalog();
      renderMetrics();
    } catch (error) {
      if (root) {
        clear(root).append(el('p', `Не удалось загрузить каталог роутера: ${error.message}`, 'error'));
      }
    }
  }

  async function loadHealth() {
    try {
      state.health = await api('/router/health');
    } catch (_) {
      state.health = null;
    }
    renderMetrics();
    renderHealth();
  }

  async function load() {
    const root = document.getElementById('providers');
    try {
      const data = await api('/providers');
      state.providers = data.providers || [];
      renderProviders();
      renderMetrics();
      renderHealth();
    } catch (error) {
      if (root) clear(root).append(el('p', `Не удалось загрузить профили провайдеров: ${error.message}`, 'error'));
    }
  }

  async function testRouteSandbox(event) {
    if (event) event.preventDefault();
    const taskInput = document.getElementById('sandbox-task');
    const taskText = taskInput?.value.trim();
    if (!taskText) {
      notify('Опишите задачу, чтобы роутер мог выбрать модель.', true);
      taskInput?.focus();
      return;
    }
    const button = document.getElementById('test-route-btn');
    const initial = button?.textContent;
    if (button) { button.disabled = true; button.textContent = 'Подбираю…'; }
    try {
      const data = await api('/router/route', {method: 'POST', body: JSON.stringify({task: taskText})});
      const decision = data.decision || {};
      const card = document.getElementById('sandbox-result');
      if (card) {
        card.hidden = false;
        const modelNode = document.getElementById('sandbox-model');
        if (modelNode) modelNode.textContent = `${decision.model || '—'}${decision.provider ? ` · ${label(PROVIDER_LABELS, decision.provider)}` : ''}`;
        const domainNode = document.getElementById('sandbox-domain');
        if (domainNode) domainNode.textContent = label(DOMAIN_LABELS, decision.detected_domain, 'Домен не определён');
        const costNode = document.getElementById('sandbox-cost');
        if (costNode) costNode.textContent = label(COST_LABELS, decision.cost_tier, 'Стоимость неизвестна');
        const availability = document.getElementById('sandbox-availability');
        if (availability) {
          availability.textContent = decision.provider_available ? 'Провайдер готов' : 'Ключ не задан · локальный режим';
          availability.className = `badge ${decision.provider_available ? 'badge-ok' : 'badge-warn'}`;
        }
        const reason = document.getElementById('sandbox-reason');
        if (reason) reason.textContent = humanReason(decision.reason);
        const fallbacks = document.getElementById('sandbox-fallbacks');
        if (fallbacks) {
          const chain = (decision.fallback_chain || []).map(item => `${item.model} (${label(PROVIDER_LABELS, item.provider)})`);
          fallbacks.textContent = chain.length ? chain.join(' → ') : 'запасных моделей нет — запрос пойдёт только в выбранную модель.';
        }
      }
      notify(`OmniRouter выбрал: ${decision.model || 'модель не определена'}`);
    } catch (error) {
      notify(`Ошибка маршрутизации: ${friendlyError(error.message)}.`, true);
    } finally {
      if (button) { button.disabled = false; button.textContent = initial; }
    }
  }

  const form = document.getElementById('provider-form');
  if (form) {
    const authMode = document.getElementById('provider-auth-mode');
    const secretField = document.getElementById('provider-secret-field');
    const keyField = document.getElementById('provider-key-field');
    const status = document.getElementById('provider-form-status');
    const modeSelect = document.getElementById('provider-mode');
    const baseUrl = document.getElementById('provider-base-url');
    const baseHint = document.getElementById('provider-base-hint');
    const baseDefaults = {
      openai_chat: 'https://api.openai.com/v1',
      openai_responses: 'https://api.openai.com/v1',
      anthropic_messages: 'https://api.anthropic.com/v1',
      ollama: 'http://localhost:11434',
      gemini_native: 'https://generativelanguage.googleapis.com/v1beta',
      azure_openai: 'https://<resource>.openai.azure.com',
      bedrock: 'https://bedrock-runtime.<region>.amazonaws.com',
      vertex_ai: 'https://<region>-aiplatform.googleapis.com',
      openai_compatible: 'https://openrouter.ai/api/v1',
      custom_http: 'https://…',
    };
    const secretDefaults = {
      openai_chat: 'secret://env/OPENAI_API_KEY',
      openai_responses: 'secret://env/OPENAI_API_KEY',
      anthropic_messages: 'secret://env/ANTHROPIC_API_KEY',
      gemini_native: 'secret://env/GEMINI_API_KEY',
      azure_openai: 'secret://env/AZURE_OPENAI_API_KEY',
      openai_compatible: 'secret://env/OPENAI_API_KEY',
      ollama: 'secret://env/OLLAMA_API_KEY',
    };

    const syncAuth = () => {
      const mode = authMode?.value || 'secret_ref';
      if (secretField) secretField.hidden = mode !== 'secret_ref';
      if (keyField) keyField.hidden = mode !== 'api_key';
      if (status) { status.textContent = ''; status.className = 'form-status'; }
    };
    const syncBase = () => {
      const mode = modeSelect?.value || 'openai_compatible';
      if (baseHint) baseHint.textContent = baseDefaults[mode] ? `Пусто — будет использован ${baseDefaults[mode]}.` : 'Укажите адрес API вручную.';
      if (baseUrl) baseUrl.placeholder = baseDefaults[mode] || 'https://…';
      const secretInput = document.getElementById('provider-credential-ref');
      if (secretInput && secretDefaults[mode] && /^\s*$|^secret:\/\/env\/OPENAI_API_KEY$/.test(secretInput.value)) {
        secretInput.value = secretDefaults[mode];
      }
    };
    authMode?.addEventListener('change', syncAuth);
    modeSelect?.addEventListener('change', syncBase);
    syncAuth();
    syncBase();

    form.addEventListener('submit', async event => {
      event.preventDefault();
      const setStatus = (message, kind) => {
        if (!status) return;
        status.textContent = message;
        status.className = `form-status${kind ? ` ${kind}` : ''}`;
      };
      const name = document.getElementById('provider-name')?.value.trim() || '';
      if (!/^[a-zA-Z0-9_-]+$/.test(name)) {
        setStatus('Имя должно содержать только латиницу, цифры, дефис или подчёркивание.', 'bad');
        document.getElementById('provider-name')?.focus();
        return;
      }
      const mode = authMode?.value || 'secret_ref';
      const body = {
        name,
        api_mode: modeSelect?.value || 'openai_compatible',
        models: (document.getElementById('provider-models')?.value || '').split(',').map(item => item.trim()).filter(Boolean),
        priority: Math.min(10, Math.max(1, Number(document.getElementById('provider-priority')?.value) || 3)),
        base_url: baseUrl?.value.trim() || undefined,
      };
      if (mode === 'secret_ref') {
        const ref = document.getElementById('provider-credential-ref')?.value.trim();
        if (!ref) { setStatus('Укажите ссылку на секрет, например secret://env/OPENAI_API_KEY.', 'bad'); return; }
        body.credential_ref = ref;
        body.auth_type = 'api_key';
      } else if (mode === 'api_key') {
        const key = document.getElementById('provider-key')?.value.trim();
        if (!key) { setStatus('Вставьте API-ключ или выберите ссылку на секрет.', 'bad'); return; }
        body.api_key = key;
        body.auth_type = 'api_key';
      } else {
        body.auth_type = 'none';
      }
      const submit = document.getElementById('provider-submit');
      if (submit) submit.disabled = true;
      setStatus('Сохраняю профиль…');
      try {
        await api('/providers', {method: 'POST', body: JSON.stringify(body)});
        setStatus(`Провайдер «${name}» добавлен. Проверьте соединение в списке ниже.`, 'ok');
        notify('Профиль провайдера сохранён.');
        const keyInput = document.getElementById('provider-key');
        if (keyInput) keyInput.value = '';
        await load();
        await loadHealth();
      } catch (error) {
        const message = String(error.message || '');
        if (error.status === 503 || /credential storage|secret key|хранилищ/i.test(message)) {
          setStatus('Шифрованное хранилище не настроено. Выберите «Ссылка на секрет», задайте переменную окружения и перезапустите Synapse — либо настройте SYNAPSE_SECRET_KEY.', 'bad');
        } else {
          setStatus(`Не удалось сохранить профиль: ${friendlyError(message)}.`, 'bad');
        }
        notify('Профиль не сохранён.', true);
      } finally {
        if (submit) submit.disabled = false;
      }
    });
  }

  document.getElementById('sandbox-form')?.addEventListener('submit', testRouteSandbox);
  document.querySelectorAll('[data-task]').forEach(button => {
    button.addEventListener('click', () => {
      const input = document.getElementById('sandbox-task');
      if (input) input.value = button.dataset.task || '';
      testRouteSandbox();
    });
  });
  document.querySelectorAll('#catalog-filters .chip').forEach(button => {
    button.addEventListener('click', () => {
      state.filter = button.dataset.filter || 'all';
      document.querySelectorAll('#catalog-filters .chip').forEach(item => {
        const active = item === button;
        item.classList.toggle('active', active);
        item.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      renderCatalog();
    });
  });

  async function init() {
    await Promise.allSettled([load(), loadCatalog()]);
    await loadHealth();
  }

  window.addEventListener('synapse-refresh', () => {
    init();
  });
  init();
})();
