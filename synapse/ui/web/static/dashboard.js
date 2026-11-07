(() => {
  'use strict';
  const {api, element: el, icon, clear, notify, json, date, openConnection} = window.synapse;
  const $ = id => document.getElementById(id);
  const steps = [
    ['perceive', 'Восприятие'], ['recall', 'Память'], ['plan', 'Планирование'],
    ['security', 'Безопасность'], ['act', 'Действие'], ['observe', 'Наблюдение'],
    ['evaluate', 'Оценка'], ['learn', 'Обучение'],
  ];
  const statusNames = {
    queued: 'В очереди', running: 'Выполняется', completed: 'Завершено',
    failed: 'Ошибка', approval_required: 'Нужно подтверждение',
  };
  const state = {
    sessionId: null, session: null, sessions: [], tasks: [], events: [],
    selectedTaskId: null, filter: '', lastEventId: 0, filePath: null,
    folder: '', pollTimer: null, refreshTimer: null, submitting: false,
  };
  const storedSession = sessionStorage.getItem('synapse-session');
  if (storedSession) state.sessionId = storedSession;

  function taskById(id) { return state.tasks.find(task => task.id === id); }
  function isActive(task) { return task && ['queued', 'running'].includes(task.status); }
  function scrollConversation() {
    requestAnimationFrame(() => { $('conversation-scroll').scrollTop = $('conversation-scroll').scrollHeight; });
  }
  function statusPill(status) { return el('span', statusNames[status] || status, `status-pill ${status}`); }

  function renderSessions() {
    const root = clear($('sessions'));
    const sessions = state.sessions.filter(item => item.title.toLowerCase().includes(state.filter.toLowerCase()));
    $('session-count').textContent = state.sessions.length;
    if (!sessions.length) {
      root.append(el('p', state.filter ? 'Ничего не найдено.' : 'Создайте первую задачу.', 'muted sidebar-empty'));
      return;
    }
    for (const session of sessions) {
      const button = el('button', undefined, `session-item${session.id === state.sessionId ? ' active' : ''}`);
      button.type = 'button';
      button.title = session.title;
      button.append(icon('chat'));
      const copy = el('span', undefined, 'session-item-copy');
      copy.append(el('span', session.title, 'session-item-title'), el('span', `${session.task_count} запусков · ${date(session.updated_at)}`, 'session-item-meta'));
      button.append(copy);
      if (session.last_status === 'running' || session.last_status === 'queued') button.append(el('span', undefined, 'spinner'));
      else if (session.last_status === 'failed') { const dot = el('span', undefined, 'status-dot offline'); dot.title = 'Последняя задача завершилась с ошибкой'; button.append(dot); }
      button.addEventListener('click', () => selectSession(session.id));
      root.append(button);
    }
  }

  function miniTimeline(task) {
    const details = el('div', undefined, 'task-progress');
    const toggle = el('button', undefined, 'task-progress-toggle');
    toggle.type = 'button';
    if (isActive(task)) toggle.append(el('span', undefined, 'spinner'));
    else toggle.append(icon(task.status === 'completed' ? 'check' : 'panels'));
    toggle.append(el('span', statusNames[task.status] || task.status), el('span', undefined, 'spacer'));
    if (task.duration_ms !== null && task.duration_ms !== undefined) toggle.append(el('span', `${(task.duration_ms / 1000).toFixed(1)} с`));
    toggle.append(icon('chevron'));
    const list = el('div', undefined, 'mini-steps');
    list.hidden = true;
    toggle.addEventListener('click', () => { list.hidden = !list.hidden; });
    for (const [key, label] of steps) {
      const event = state.events.filter(item => item.task_id === task.id && item.event === key).at(-1);
      list.append(el('span', label, `mini-step ${event?.data?.status || ''}`));
    }
    toggle.addEventListener('dblclick', () => selectTask(task.id));
    details.append(toggle, list);
    return details;
  }

  function messageView(message) {
    const task = message.task_id ? taskById(message.task_id) : null;
    if (message.role === 'user') {
      const row = el('article', undefined, 'message user-message');
      row.append(el('div', `Вы · ${date(message.created_at)}`, 'message-label'));
      const bubble = el('div', message.content, 'user-bubble');
      if (task?.payload?.path) {
        const file = el('div', undefined, 'file-context');
        file.append(icon('file'), el('span', task.payload.path));
        row.append(file);
      }
      row.append(bubble);
      return row;
    }
    const row = el('article', undefined, 'message agent-message');
    const avatar = el('div', undefined, 'agent-avatar'); avatar.append(icon('shield'));
    const body = el('div');
    body.append(el('div', 'Synapse', 'agent-name'));
    if (task?.status === 'running' || task?.status === 'queued') {
      body.append(el('div', task.status === 'queued' ? 'Задача добавлена в очередь…' : 'Выполняю когнитивный цикл…', 'agent-content'), miniTimeline(task));
    } else {
      body.append(el('div', message.content || 'Нет ответа.', `agent-content${task?.status === 'failed' ? ' error' : ''}`));
      if (task) body.append(miniTimeline(task));
    }
    if (task) {
      const actions = el('div', undefined, 'task-actions');
      const inspect = el('button', 'Детали', 'small-button'); inspect.type = 'button';
      inspect.addEventListener('click', () => selectTask(task.id));
      const copy = el('button', 'Копировать', 'small-button'); copy.type = 'button';
      copy.addEventListener('click', () => copyText(message.content));
      actions.append(inspect, copy);
      if (!isActive(task)) {
        const retry = el('button', 'Повторить', 'small-button'); retry.type = 'button';
        retry.addEventListener('click', () => retryTask(task.id));
        actions.append(retry);
      }
      body.append(actions);
    }
    row.append(avatar, body);
    return row;
  }

  function renderMessages() {
    $('welcome').hidden = state.session?.task_count > 0 || state.tasks.length > 0;
    const root = clear($('messages'));
    const messages = state.session?.messages || [];
    for (const message of messages) root.append(messageView(message));
    for (const task of state.tasks.filter(isActive)) {
      if (!messages.some(message => message.task_id === task.id && message.role === 'user')) {
        root.append(messageView({role: 'user', content: task.task, task_id: task.id}));
      }
      if (!messages.some(message => message.task_id === task.id && message.role === 'assistant')) {
        root.append(messageView({role: 'assistant', content: '', task_id: task.id}));
      }
    }
    scrollConversation();
  }

  function renderTimeline(task) {
    if (!task) return;
    const root = clear($('timeline'));
    for (const [key, label] of steps) {
      const event = state.events.filter(item => item.task_id === task.id && item.event === key).at(-1);
      const status = event?.data?.status || '';
      const item = el('li', undefined, `timeline-step ${status}`);
      const marker = el('span', undefined, 'step-marker');
      if (status === 'completed') marker.append(icon('check'));
      const copy = el('div');
      let note = '';
      if (event?.data?.steps !== undefined) note = `${event.data.steps} шагов · риск ${event.data.risk_level}`;
      if (event?.data?.completed !== undefined) note = `${event.data.completed} из ${event.data.total} действий`;
      if (event?.data?.requires_approval) note = 'Требуется решение пользователя';
      if (event?.data?.score !== undefined && event.data.score !== null) note = `Оценка: ${event.data.score}`;
      copy.append(el('span', label));
      if (note) copy.append(el('small', note, 'step-note'));
      item.append(marker, copy); root.append(item);
    }
  }

  function renderPlan(task) {
    const plan = task?.result?.plan;
    $('plan-section').hidden = !plan;
    if (!plan) return;
    const root = clear($('plan-details'));
    for (const step of plan.steps || []) {
      const card = el('div', undefined, 'plan-card');
      card.append(el('strong', step.action || step.skill), el('small', `${step.skill} · ${json(step.params || {})}`));
      root.append(card);
    }
    const caps = el('div', undefined, 'capability-tags');
    for (const capability of plan.required_capabilities || []) caps.append(el('span', capability, 'capability-tag'));
    root.append(caps);
  }

  function renderInspector() {
    const task = taskById(state.selectedTaskId) || state.tasks.at(-1);
    $('run-empty').hidden = !!task;
    $('run-details').hidden = !task;
    if (!task) return;
    state.selectedTaskId = task.id;
    $('run-status').textContent = statusNames[task.status] || task.status;
    $('run-status').className = `status-pill ${task.status}`;
    $('run-duration').textContent = task.duration_ms !== null && task.duration_ms !== undefined ? `${(task.duration_ms / 1000).toFixed(2)} с` : '';
    $('run-task').textContent = task.task;
    $('run-id').textContent = task.id;
    $('run-result').textContent = task.error || (task.result ? json(task.result) : 'Выполнение ещё не завершено.');
    $('retry-task').disabled = isActive(task);

    const routerEvent = state.events.filter(item => item.task_id === task.id && item.event === 'router').at(-1);
    const routerCard = $('router-decision');
    if (routerCard) {
      if (routerEvent?.data) {
        routerCard.hidden = false;
        const d = routerEvent.data;
        $('router-model').textContent = d.model || 'auto';
        $('router-domain').textContent = d.detected_domain || 'general';
        $('router-cost').textContent = d.cost_tier || '$';
        $('router-reason').textContent = d.reason || '';
      } else {
        routerCard.hidden = true;
      }
    }

    renderTimeline(task); renderPlan(task);
  }

  function renderSessionDetails() {
    const session = state.session;
    $('stat-total').textContent = state.tasks.length;
    $('stat-completed').textContent = state.tasks.filter(task => task.status === 'completed').length;
    $('stat-failed').textContent = state.tasks.filter(task => task.status === 'failed').length;
    $('session-id').textContent = session?.id || '—';
    $('session-created').textContent = date(session?.created_at);
    $('export-session').disabled = !session;
    $('archive-session').disabled = !session || state.tasks.some(isActive);
  }

  function approvalView(item) {
    const card = el('article', undefined, 'approval-card');
    card.append(el('span', `Уровень риска ${item.risk_level} из 5`, 'risk-label'), el('h3', item.action));
    card.append(el('p', 'Проверьте действие и параметры перед выполнением. Подтверждение одноразовое.'));
    if (Object.keys(item.details || {}).length) card.append(el('pre', json(item.details), 'result-viewer'));
    const actions = el('div', undefined, 'approval-actions');
    const approve = el('button', 'Подтвердить', 'approve-button'); approve.type = 'button';
    const reject = el('button', 'Отклонить', 'secondary'); reject.type = 'button';
    approve.addEventListener('click', async () => {
      if (!window.confirm(`Подтвердить действие «${item.action}»?`)) return;
      approve.disabled = reject.disabled = true;
      try {
        const result = await api(`/approvals/${encodeURIComponent(item.id)}/approve`, {method: 'POST'});
        notify('Подтверждение применено. Действие выполнено.');
        if (result.execution_task_id) state.selectedTaskId = result.execution_task_id;
        await loadSession(); showTab('run');
      } catch (error) { notify(error.message, true); approve.disabled = reject.disabled = false; }
    });
    reject.addEventListener('click', async () => {
      approve.disabled = reject.disabled = true;
      try { await api(`/approvals/${encodeURIComponent(item.id)}/reject`, {method: 'POST'}); notify('Действие отклонено.'); await loadSession(); }
      catch (error) { notify(error.message, true); approve.disabled = reject.disabled = false; }
    });
    actions.append(approve, reject); card.append(actions);
    return card;
  }

  async function loadApprovals() {
    const root = clear($('approvals'));
    try {
      const data = await api('/approvals/pending');
      const items = data.approvals.filter(item => state.tasks.some(task => task.id === item.task_id));
      $('approval-count').textContent = items.length;
      $('approval-count').hidden = !items.length;
      if (!items.length) root.append(el('p', 'В этой сессии нет ожидающих подтверждений.', 'muted panel-description'));
      else for (const item of items) root.append(approvalView(item));
    } catch (error) { root.append(el('p', error.message, 'error')); }
  }

  function mergeTasks(tasks) {
    for (const task of tasks) {
      const index = state.tasks.findIndex(item => item.id === task.id);
      if (index === -1) state.tasks.push(task); else state.tasks[index] = task;
    }
  }

  async function pollEvents() {
    if (!state.sessionId || document.hidden) return;
    try {
      const data = await api(`/sessions/${encodeURIComponent(state.sessionId)}/events?after=${state.lastEventId}`);
      if (!data.events.length) return;
      const hasUpdate = data.events.some(event => event.event === 'task' || event.event === 'approval');
      for (const event of data.events) {
        if (!state.events.some(item => item.id === event.id)) state.events.push(event);
        state.lastEventId = Math.max(state.lastEventId, event.id);
      }
      renderTimeline(taskById(state.selectedTaskId) || state.tasks.at(-1));
      renderMessages();
      if (hasUpdate) {
        const session = await api(`/sessions/${encodeURIComponent(state.sessionId)}`);
        state.session = {...state.session, ...session}; mergeTasks(session.tasks);
        renderMessages(); renderInspector(); renderSessionDetails(); await loadApprovals(); await loadSessions();
      }
    } catch (error) {
      if (error.status === 401) stopPolling();
    }
  }

  function startPolling() {
    stopPolling();
    const tick = async () => {
      await pollEvents();
      if (state.pollTimer !== null) state.pollTimer = setTimeout(tick, 900);
    };
    state.pollTimer = setTimeout(tick, 0);
  }
  function stopPolling() { clearTimeout(state.pollTimer); state.pollTimer = null; }

  async function loadSession() {
    if (!state.sessionId) { renderAll(); return; }
    try {
      const session = await api(`/sessions/${encodeURIComponent(state.sessionId)}`);
      const [events, approvals] = await Promise.all([
        api(`/sessions/${encodeURIComponent(state.sessionId)}/events`), api('/approvals/pending'),
      ]);
      state.session = session; state.tasks = session.tasks;
      state.events = events.events; state.lastEventId = events.events.at(-1)?.id || 0;
      if (state.selectedTaskId && !taskById(state.selectedTaskId)) state.selectedTaskId = null;
      $('session-title').textContent = session.title;
      $('rename-session').hidden = false;
      sessionStorage.setItem('synapse-session', state.sessionId);
      document.title = `${session.title} — Synapse`;
      setConnection(true);
      renderAll();
      renderApprovals(approvals.approvals.filter(item => state.tasks.some(task => task.id === item.task_id)));
    } catch (error) {
      if (error.status === 404) { await createSession(); return; }
      setConnection(false); notify(error.message, true);
    }
  }

  function renderApprovals(items) {
    const root = clear($('approvals'));
    $('approval-count').textContent = items.length; $('approval-count').hidden = !items.length;
    if (!items.length) root.append(el('p', 'В этой сессии нет ожидающих подтверждений.', 'muted panel-description'));
    else for (const item of items) root.append(approvalView(item));
  }

  function renderAll() { renderSessions(); renderMessages(); renderInspector(); renderSessionDetails(); }

  async function loadSessions() {
    try {
      const data = await api('/sessions');
      state.sessions = data.sessions; setConnection(true); renderSessions();
      if (!state.sessionId && state.sessions.length) await selectSession(state.sessions[0].id, false);
      else if (state.sessionId && !state.sessions.some(item => item.id === state.sessionId)) await createSession();
    } catch (error) { setConnection(false); if (error.status !== 401) notify(error.message, true); }
  }

  async function selectSession(id, refreshList = true) {
    state.sessionId = id; state.session = null; state.tasks = []; state.events = [];
    state.selectedTaskId = null; state.lastEventId = 0;
    clear($('messages')); $('welcome').hidden = true;
    closeSidebar();
    await loadSession();
    if (refreshList) renderSessions();
  }

  async function createSession() {
    try {
      const session = await api('/sessions', {method: 'POST', body: JSON.stringify({title: 'Новая задача'})});
      state.sessionId = session.id; state.session = {...session, messages: []}; state.tasks = [];
      state.events = []; state.lastEventId = 0; state.selectedTaskId = null; state.filePath = null;
      $('session-title').textContent = session.title; $('rename-session').hidden = false;
      $('task').value = ''; $('payload').value = ''; renderFileContext();
      closeSidebar(); await loadSessions(); renderAll(); $('task').focus();
    } catch (error) { notify(error.message, true); }
  }

  function selectTask(id) {
    state.selectedTaskId = id; showTab('run'); renderInspector();
    if (window.innerWidth <= 1190) $('inspector').classList.add('open');
  }

  function showTab(name) {
    for (const button of document.querySelectorAll('[data-tab]')) {
      const active = button.dataset.tab === name;
      button.classList.toggle('active', active); button.setAttribute('aria-selected', String(active));
    }
    for (const panel of document.querySelectorAll('.inspector-content')) panel.hidden = panel.id !== `inspector-${name}`;
  }

  function renderFileContext() {
    $('file-context').hidden = !state.filePath;
    $('file-context-name').textContent = state.filePath || '';
  }

  async function loadFiles(path = '') {
    const browser = clear($('file-browser'));
    browser.append(el('p', 'Загрузка файлов…', 'muted'));
    try {
      const data = await api(`/workspace/files?path=${encodeURIComponent(path)}`);
      state.folder = data.path; $('file-path').textContent = `workspace/${data.path}`;
      clear(browser);
      if (path) {
        const up = el('button', '..', 'file-row'); up.type = 'button'; up.prepend(icon('folder'));
        up.addEventListener('click', () => loadFiles(path.split('/').slice(0, -1).join('/'))); browser.append(up);
      }
      for (const directory of data.directories) {
        const row = el('button', directory.name, 'file-row'); row.type = 'button'; row.prepend(icon('folder'));
        row.addEventListener('click', () => loadFiles(directory.path)); browser.append(row);
      }
      for (const file of data.files) {
        const row = el('button', file.name, 'file-row'); row.type = 'button'; row.prepend(icon('file'));
        row.addEventListener('click', () => {
          state.filePath = file.path;
          if (!$('task').value.trim() || $('task').value.trim() === 'Read a file') $('task').value = 'Read a file';
          $('payload').value = json({path: file.path}); $('advanced-payload').open = false;
          renderFileContext(); $('file-dialog').close(); $('task').focus();
        });
        browser.append(row);
      }
      if (!data.directories.length && !data.files.length) browser.append(el('p', 'В этой папке нет доступных файлов.', 'muted'));
    } catch (error) { clear(browser).append(el('p', error.message, 'error')); }
  }

  async function submitTask(event) {
    event.preventDefault();
    if (state.submitting) return;
    const text = $('task').value.trim();
    if (!text) return;

    if (text.startsWith('/')) {
      state.submitting = true; $('send-task').disabled = true;
      const commandName = text.split(' ')[0];
      try {
        if (!state.sessionId) await createSession();
        state.session.messages = state.session.messages || [];
        state.session.messages.push({role: 'user', content: text, created_at: new Date().toISOString()});
        state.session.messages.push({role: 'assistant', content: `Выполняю команду ${commandName}… Это может занять несколько минут.`, created_at: new Date().toISOString(), pending_slash: true});
        $('task').value = ''; resizeComposer();
        renderMessages();
        const slashRes = await api('/platform/slash/execute', {
          method: 'POST', body: JSON.stringify({command: text})
        });
        const outStr = typeof slashRes.output === 'object' ? JSON.stringify(slashRes.output, null, 2) : String(slashRes.output);
        // Replace the pending placeholder with the actual command result.
        const pending = state.session.messages.findLast(message => message.pending_slash);
        if (pending) {
          pending.content = outStr;
          delete pending.pending_slash;
        } else {
          state.session.messages.push({role: 'assistant', content: outStr, created_at: new Date().toISOString()});
        }
        renderMessages();
        notify(`Команда ${commandName} выполнена.`);
      } catch (err) {
        const pending = state.session.messages?.findLast?.(message => message.pending_slash);
        if (pending) { pending.content = `Команда ${commandName} завершилась с ошибкой: ${err.message}`; delete pending.pending_slash; renderMessages(); }
        notify(err.message, true);
      } finally {
        state.submitting = false; $('send-task').disabled = false; $('task').focus();
      }
      return;
    }

    let payload = null;
    try {
      const raw = $('payload').value.trim();
      if (raw) {
        payload = JSON.parse(raw);
        if (!payload || Array.isArray(payload) || typeof payload !== 'object') throw new Error('Параметры должны быть JSON-объектом.');
      } else if (state.filePath) payload = {path: state.filePath};
      const selectedModel = $('model-select')?.value;
      if (selectedModel && selectedModel !== 'auto') {
        payload = payload || {};
        if (selectedModel.startsWith('agent:')) {
          payload.executor = selectedModel.slice('agent:'.length);
        } else {
          payload.model = selectedModel;
        }
        if (selectedModel.startsWith('llama') || selectedModel.startsWith('codellama')) {
          payload.local_only = true;
        }
      }
    } catch (error) { notify(error instanceof SyntaxError ? 'Проверьте синтаксис JSON.' : error.message, true); return; }
    state.submitting = true; $('send-task').disabled = true;
    try {
      if (!state.sessionId) await createSession();
      const task = await api(`/sessions/${encodeURIComponent(state.sessionId)}/tasks`, {
        method: 'POST', body: JSON.stringify({task: text, payload, session_id: state.sessionId}),
      });
      if (state.session.title === 'Новая задача') {
        state.session = await api(`/sessions/${encodeURIComponent(state.sessionId)}`, {method: 'PATCH', body: JSON.stringify({title: text.slice(0, 80)})});
        $('session-title').textContent = state.session.title;
      }
      state.session.messages = state.session.messages || [];
      state.session.messages.push({role: 'user', content: text, task_id: task.id, created_at: task.created_at});
      state.session.task_count = (state.session.task_count || 0) + 1;
      state.tasks.push(task); state.selectedTaskId = task.id;
      $('task').value = ''; $('payload').value = ''; state.filePath = null; resizeComposer(); renderFileContext();
      renderAll(); showTab('run'); await loadSessions(); startPolling();
    } catch (error) { notify(error.message, true); }
    finally { state.submitting = false; $('send-task').disabled = false; $('task').focus(); }
  }

  async function retryTask(id) {
    try {
      const task = await api(`/tasks/${encodeURIComponent(id)}/retry`, {method: 'POST'});
      mergeTasks([task]); state.selectedTaskId = task.id;
      await loadSession(); showTab('run'); startPolling(); notify('Задача добавлена в очередь.');
    } catch (error) { notify(error.message, true); }
  }

  async function copyText(text) {
    try { await navigator.clipboard.writeText(text || ''); notify('Скопировано.'); }
    catch { notify('Браузер не разрешил доступ к буферу обмена.', true); }
  }

  async function loadAgentAvailability() {
    const group = $('agent-options-group');
    if (!group) return;
    try {
      const data = await api('/integrations/agents');
      for (const option of group.querySelectorAll('option')) {
        const agentId = option.value.slice('agent:'.length);
        const agent = (data.agents || []).find(item => item.id === agentId);
        if (!agent) continue;
        option.disabled = !agent.enabled && !agent.configured;
        if (!agent.enabled) option.textContent = option.textContent.replace(/\s*(отключён|включён)$/, '') + (agent.configured ? ' · отключён' : ' · не найден');
        else option.textContent = option.textContent.replace(/\s*· (отключён|не найден)$/, '');
      }
    } catch (error) { /* inventory is optional; leave options as-is */ }
  }

  function exportSession() {
    if (!state.session) return;
    const content = json({...state.session, tasks: state.tasks, events: state.events});
    const url = URL.createObjectURL(new Blob([content], {type: 'application/json;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url;
    link.download = `synapse-${state.session.id}.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    notify('Экспорт подготовлен.');
  }

  function resizeComposer() {
    const input = $('task'); input.style.height = 'auto'; input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
  }
  function closeSidebar() { $('sidebar').classList.remove('open'); }
  function setConnection(online) {
    $('connection-dot').classList.toggle('offline', !online);
    $('connection-label').textContent = online ? 'Система готова' : 'Нет соединения';
  }

  $('task-form').addEventListener('submit', submitTask);
  $('task').addEventListener('input', resizeComposer);
  $('task').addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); $('task-form').requestSubmit(); }
  });
  $('new-session').addEventListener('click', createSession);
  $('session-search').addEventListener('input', event => { state.filter = event.target.value; renderSessions(); });
  $('open-sidebar').addEventListener('click', () => $('sidebar').classList.add('open'));
  $('close-sidebar').addEventListener('click', closeSidebar);
  $('sidebar-scrim').addEventListener('click', closeSidebar);
  $('toggle-inspector').addEventListener('click', () => {
    const open = $('inspector').classList.toggle('open');
    $('toggle-inspector').setAttribute('aria-expanded', String(open));
    if (window.innerWidth > 1190) {
      document.querySelector('.app-shell').style.gridTemplateColumns = open ? '' : '256px minmax(0, 1fr) 0';
      $('inspector').hidden = !open;
    }
  });
  $('close-inspector').addEventListener('click', () => {
    $('inspector').classList.remove('open');
    if (window.innerWidth > 1190) { $('inspector').hidden = true; document.querySelector('.app-shell').style.gridTemplateColumns = '256px minmax(0, 1fr) 0'; }
    $('toggle-inspector').setAttribute('aria-expanded', 'false');
  });
  for (const button of document.querySelectorAll('[data-tab]')) button.addEventListener('click', () => showTab(button.dataset.tab));
  for (const button of document.querySelectorAll('[data-prompt]')) button.addEventListener('click', () => {
    $('task').value = button.dataset.prompt;
    if (button.dataset.prompt === 'Read a file') openFilePicker(); else $('task').focus();
    resizeComposer();
  });
  function openFilePicker() {
    if (!$('file-dialog').open) $('file-dialog').showModal();
    loadFiles();
  }

  $('choose-file').addEventListener('click', openFilePicker);
  $('file-dialog').addEventListener('close', () => { state.folder = ''; });
  $('clear-file').addEventListener('click', () => { state.filePath = null; $('payload').value = ''; renderFileContext(); });
  $('copy-result').addEventListener('click', () => copyText($('run-result').textContent));
  $('retry-task').addEventListener('click', () => { if (state.selectedTaskId) retryTask(state.selectedTaskId); });
  $('export-session').addEventListener('click', exportSession);
  $('rename-session').addEventListener('click', async () => {
    const title = window.prompt('Название сессии', state.session?.title || '');
    if (!title?.trim()) return;
    try { state.session = await api(`/sessions/${state.sessionId}`, {method: 'PATCH', body: JSON.stringify({title: title.trim()})}); $('session-title').textContent = state.session.title; await loadSessions(); }
    catch (error) { notify(error.message, true); }
  });
  $('archive-session').addEventListener('click', async () => {
    if (!state.session || !window.confirm('Архивировать эту сессию? Выполненные действия не отменяются.')) return;
    try { await api(`/sessions/${state.sessionId}`, {method: 'DELETE'}); sessionStorage.removeItem('synapse-session'); state.sessionId = null; await createSession(); }
    catch (error) { notify(error.message, true); }
  });
  $('connection-dot').parentElement.style.cursor = 'pointer';
  $('connection-dot').parentElement.title = 'Настроить API-ключ';
  $('connection-dot').parentElement.addEventListener('click', openConnection);
  $('mode-button').addEventListener('click', () => notify('Текущий режим: локальный автономный runtime. Навыки и разрешения выбирает планировщик.'));
  document.addEventListener('keydown', event => {
    if (event.ctrlKey && event.key.toLowerCase() === 'k') { event.preventDefault(); createSession(); }
    if (event.key === 'Escape') { closeSidebar(); $('inspector').classList.remove('open'); }
  });
  window.addEventListener('synapse-refresh', async () => { await loadSessions(); await loadSession(); startPolling(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) pollEvents(); });

  // Platform Tools Handlers (Security Audit, Memory Vault, Hallmark Benchmarks)
  $('run-security-scan-btn')?.addEventListener('click', async () => {
    const btn = $('run-security-scan-btn');
    btn.disabled = true; btn.textContent = 'Сканирование...';
    try {
      const rep = await api('/platform/security/audit', {method: 'POST', body: JSON.stringify({target_dir: '.'})});
      $('security-report-card').hidden = false;
      $('sec-grade').textContent = rep.grade;
      $('sec-grade').style.color = rep.grade === 'A+' || rep.grade === 'A' ? '#4ade80' : (rep.grade === 'B' ? '#facc15' : '#f87171');
      $('sec-score').textContent = `${rep.score}/100`;
      $('sec-files').textContent = rep.scanned_files_count;
      $('sec-total').textContent = rep.total_findings;
      const list = clear($('security-findings-list'));
      if (!rep.findings.length) {
        list.append(el('p', 'Уязвимостей и секретов не обнаружено. Кодовая база безопасна!', 'muted'));
      } else {
        for (const f of rep.findings) {
          const item = el('div', undefined, 'finding-item');
          const header = el('div', undefined, 'finding-header');
          header.append(el('strong', f.title), el('span', f.severity, `severity-pill ${f.severity}`));
          item.append(header, el('div', `${f.file_path}${f.line_number ? ':' + f.line_number : ''}`, 'muted'));
          if (f.snippet) item.append(el('pre', f.snippet, 'finding-snippet'));
          if (f.recommendation) item.append(el('div', `Рекомендация: ${f.recommendation}`, 'finding-recom'));
          list.append(item);
        }
      }
      notify(`Аудит завершен. Оценка: ${rep.grade} (${rep.score}/100)`);
    } catch (err) {
      notify(err.message, true);
    } finally {
      btn.disabled = false; btn.innerHTML = '<svg><use href="#i-shield"/></svg> Запустить аудит безопасности';
    }
  });

  async function loadMemories(q = '') {
    const list = clear($('memory-entries-list'));
    try {
      const url = q ? `/platform/memory/entries?q=${encodeURIComponent(q)}` : '/platform/memory/entries';
      const data = await api(url);
      if (!data.entries.length) {
        list.append(el('p', 'Записей в памяти не найдено.', 'muted'));
        return;
      }
      for (const m of data.entries) {
        const item = el('div', undefined, 'memory-item');
        const header = el('div', undefined, 'memory-header');
        header.append(el('strong', m.title), el('span', m.memory_type, 'memory-type-badge'));
        item.append(header, el('p', m.content));
        if (m.tags && m.tags.length) {
          const tagRow = el('div', undefined, 'tag-row');
          for (const t of m.tags) tagRow.append(el('span', `#${t}`, 'tag-badge'));
          item.append(tagRow);
        }
        list.append(item);
      }
    } catch (err) {
      list.append(el('p', err.message, 'error'));
    }
  }

  $('memory-search-btn')?.addEventListener('click', () => {
    loadMemories($('memory-search-input').value.trim());
  });
  $('memory-search-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); loadMemories($('memory-search-input').value.trim()); }
  });
  $('save-memory-btn')?.addEventListener('click', async () => {
    const title = $('new-mem-title').value.trim();
    const content = $('new-mem-content').value.trim();
    const type = $('new-mem-type').value;
    if (!title || !content) { notify('Заполните заголовок и содержимое.', true); return; }
    try {
      await api('/platform/memory/entries', {
        method: 'POST', body: JSON.stringify({title, content, memory_type: type})
      });
      $('new-mem-title').value = ''; $('new-mem-content').value = '';
      notify('Правило сохранено в долговременную память.');
      loadMemories();
    } catch (err) {
      notify(err.message, true);
    }
  });

  $('run-benchmarks-btn')?.addEventListener('click', async () => {
    const btn = $('run-benchmarks-btn');
    btn.disabled = true; btn.textContent = 'Тестирование...';
    try {
      const rep = await api('/platform/benchmarks/run', {method: 'POST', body: JSON.stringify({suite_id: 'core_eval_v1'})});
      $('benchmark-results-container').hidden = false;
      $('bench-grade').textContent = rep.grade;
      $('bench-grade').style.color = rep.grade === 'A+' || rep.grade === 'A' ? '#4ade80' : '#facc15';
      $('bench-pass-rate').textContent = `${rep.pass_rate}%`;
      $('bench-passed').textContent = rep.passed_tasks;
      $('bench-total').textContent = rep.total_tasks;
      const list = clear($('benchmark-tasks-list'));
      for (const t of rep.results) {
        const item = el('div', undefined, 'task-summary-item');
        const header = el('div', undefined, 'task-summary-header');
        header.append(el('strong', t.task_id), el('span', t.passed ? 'PASSED' : 'FAILED', `severity-pill ${t.passed ? 'LOW' : 'CRITICAL'}`));
        item.append(header, el('div', `Категория: ${t.category} · Баллы: ${t.score} · Латентность: ${t.latency_ms}мс`, 'muted'));
        list.append(item);
      }
      notify(`Бенчмарк завершен: ${rep.pass_rate}% пройдено (Грейд: ${rep.grade})`);
    } catch (err) {
      notify(err.message, true);
    } finally {
      btn.disabled = false; btn.innerHTML = '<svg><use href="#i-refresh"/></svg> Запустить Hallmark бенчмарк';
    }
  });

  // Self-Evolution & Trajectory Export Handlers
  async function loadTrajectories() {
    try {
      const data = await api('/platform/trajectories?limit=50');
      const trajs = data.trajectories || [];
      const successful = trajs.filter(t => t.success);
      $('evo-count').textContent = trajs.length;
      $('evo-total-trajs').textContent = trajs.length;
      $('evo-sft-ready').textContent = successful.length;

      const list = clear($('trajectories-list'));
      if (!trajs.length) {
        list.append(el('p', 'Траекторий пока нет. Запустите задачи для накопления опыта.', 'muted'));
        return;
      }
      for (const t of trajs.slice(0, 10)) {
        const item = el('div', undefined, 'memory-item');
        const header = el('div', undefined, 'memory-header');
        header.append(
          el('strong', t.objective || t.trajectory_id),
          el('span', t.success ? 'Успешно' : 'Ошибка', `severity-pill ${t.success ? 'LOW' : 'CRITICAL'}`)
        );
        item.append(header, el('p', `Модель: ${t.model} · Шагов: ${t.total_steps} · Время: ${t.duration_ms}мс`));
        list.append(item);
      }
    } catch (err) {
      console.error('Failed to load trajectories:', err);
    }
  }

  function downloadJsonlBlob(dataList, filename) {
    const content = dataList.map(item => JSON.stringify(item)).join('\n');
    const blob = new Blob([content], {type: 'application/x-jsonlines;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  $('export-sft-btn')?.addEventListener('click', async () => {
    try {
      const res = await api('/platform/trajectories/export/sft?format=chatml');
      if (!res.samples || !res.samples.length) {
        notify('Нет успешных траекторий для экспорта SFT.', true);
        return;
      }
      downloadJsonlBlob(res.samples, 'synapse_frontier_sft.jsonl');
      notify(`Экспортировано ${res.count} обучающих примеров SFT`);
    } catch (err) {
      notify(err.message, true);
    }
  });

  $('export-dpo-btn')?.addEventListener('click', async () => {
    try {
      const res = await api('/platform/trajectories/export/dpo');
      if (!res.pairs || !res.pairs.length) {
        notify('Нет траекторий для формирования DPO пар.', true);
        return;
      }
      downloadJsonlBlob(res.pairs, 'synapse_frontier_dpo.jsonl');
      notify(`Экспортировано ${res.count} контрастивных DPO пар`);
    } catch (err) {
      notify(err.message, true);
    }
  });

  $('analyze-patterns-btn')?.addEventListener('click', async () => {
    try {
      const data = await api('/platform/learning/patterns');
      $('evolution-insights-card').hidden = false;
      $('evo-insights-title').textContent = 'Результаты анализа паттернов:';
      $('evo-insights-body').textContent = JSON.stringify(data, null, 2);
      notify('Паттерны успешно проанализированы.');
    } catch (err) {
      notify(err.message, true);
    }
  });

  $('optimize-agent-btn')?.addEventListener('click', async () => {
    const agent = $('evo-agent-select').value;
    try {
      const res = await api('/platform/learning/optimize-prompts', {
        method: 'POST',
        body: JSON.stringify({agent_name: agent}),
      });
      $('evolution-insights-card').hidden = false;
      $('evo-insights-title').textContent = `Оптимизация инструкций агента: ${agent}`;
      $('evo-insights-body').textContent = res.suggestion;
      notify(`Инструкции агента '${agent}' оптимизированы.`);
    } catch (err) {
      notify(err.message, true);
    }
  });

  // Computer Use / Browser Controller Handlers
  $('browser-action-select')?.addEventListener('change', (e) => {
    const act = e.target.value;
    const isElem = act === 'click' || act === 'fill';
    $('browser-selector-input').style.display = isElem ? '' : 'none';
    $('browser-value-input').style.display = act === 'fill' ? '' : 'none';
  });

  $('execute-browser-btn')?.addEventListener('click', async () => {
    const btn = $('execute-browser-btn');
    btn.disabled = true; btn.textContent = 'Выполнение...';
    const action = $('browser-action-select').value;
    const url = $('browser-url-input').value.trim() || undefined;
    const selector = $('browser-selector-input').value.trim() || undefined;
    const value = $('browser-value-input').value.trim() || undefined;

    try {
      const res = await api('/platform/browser/execute', {
        method: 'POST',
        body: JSON.stringify({action, url, selector, value}),
      });
      $('browser-viewport').hidden = false;
      $('browser-status-line').textContent = `Статус: ${res.status} (${res.action})`;
      $('browser-url-display').textContent = res.url || '';

      if (res.screenshot) {
        $('browser-screenshot-img').src = res.screenshot;
        $('browser-screenshot-img').style.display = 'block';
        $('browser-content-display').style.display = 'none';
      } else if (res.content) {
        $('browser-content-display').textContent = res.content;
        $('browser-content-display').style.display = 'block';
        $('browser-screenshot-img').style.display = 'none';
      } else {
        $('browser-content-display').textContent = JSON.stringify(res, null, 2);
        $('browser-content-display').style.display = 'block';
        $('browser-screenshot-img').style.display = 'none';
      }
      notify(`Действие '${action}' завершено со статусом: ${res.status}`);
    } catch (err) {
      notify(err.message, true);
    } finally {
      btn.disabled = false; btn.textContent = 'Выполнить действие браузера';
    }
  });

  // OmniRouter Interactive Explorer
  async function loadRouterCatalog() {
    const list = $('router-catalog-list');
    if (!list) return;
    clear(list).append(el('p', 'Загрузка каталога моделей…', 'muted'));
    try {
      const data = await api('/router/catalog');
      clear(list);
      for (const m of (data.catalog || [])) {
        const item = el('div', '', 'memory-item');
        const header = el('div', '', 'memory-header');
        header.style.display = 'flex'; header.style.justifyContent = 'space-between'; header.style.alignItems = 'center';

        const titleSpan = el('strong', m.display_name || m.id);
        const metaSpan = el('span', `${m.provider.toUpperCase()} · ${m.tier.toUpperCase()} · ${m.cost_tier}`, 'domain-badge');
        header.append(titleSpan, metaSpan);

        const desc = el('p', `Контекст: ${(m.context_window / 1000).toFixed(0)}k токенов · Вывод: ${(m.max_output / 1000).toFixed(0)}k · Сильные стороны: ${(m.strengths || []).join(', ')}`, 'memory-body');
        desc.style.fontSize = '11px'; desc.style.margin = '4px 0';

        item.append(header, desc);
        list.append(item);
      }
    } catch (e) {
      clear(list).append(el('p', e.message, 'error'));
    }
  }

  $('refresh-router-catalog')?.addEventListener('click', () => loadRouterCatalog());

  $('router-test-btn')?.addEventListener('click', async () => {
    const task = $('router-test-task')?.value.trim();
    if (!task) { notify('Введите описание задачи для анализа маршрута.', true); return; }
    const btn = $('router-test-btn'); btn.disabled = true;
    try {
      const requirements = {};
      if ($('router-test-local')?.checked) requirements.local_only = true;
      if ($('router-test-fast')?.checked) requirements.latency = 'fast';

      const res = await api('/router/route', {
        method: 'POST',
        body: JSON.stringify({task, requirements}),
      });
      const d = res.decision;
      $('router-test-result').hidden = false;
      $('rt-model').textContent = d.model;
      $('rt-domain').textContent = d.detected_domain;
      $('rt-cost').textContent = d.cost_tier;
      $('rt-conf').textContent = `${Math.round(d.confidence * 100)}%`;
      $('rt-reason').textContent = d.reason;
      $('rt-fallback').textContent = (d.fallback_chain || []).map(f => `${f.provider}/${f.model}`).join(' → ') || 'нет';
      $('rt-output-box').hidden = true;
      notify(`Маршрут определен: ${d.model} (${d.detected_domain})`);
    } catch (err) {
      notify(err.message, true);
    } finally {
      btn.disabled = false;
    }
  });

  $('router-exec-btn')?.addEventListener('click', async () => {
    const task = $('router-test-task')?.value.trim();
    if (!task) { notify('Введите описание задачи для выполнения через роутер.', true); return; }
    const btn = $('router-exec-btn'); btn.disabled = true; btn.textContent = 'Запуск...';
    try {
      const requirements = {};
      if ($('router-test-local')?.checked) requirements.local_only = true;
      if ($('router-test-fast')?.checked) requirements.latency = 'fast';

      const res = await api('/router/execute', {
        method: 'POST',
        body: JSON.stringify({task, requirements}),
      });
      $('router-test-result').hidden = false;
      const d = res.route_decision || {};
      $('rt-model').textContent = res.model_used || d.model || 'auto';
      $('rt-domain').textContent = d.detected_domain || 'general';
      $('rt-cost').textContent = d.cost_tier || '$$';
      $('rt-conf').textContent = `${Math.round((d.confidence ?? 0.9) * 100)}%`;
      $('rt-reason').textContent = d.reason || 'Автоматическое выполнение через OmniRouter';
      $('rt-fallback').textContent = (d.fallback_chain || []).map(f => `${f.provider}/${f.model}`).join(' → ') || 'нет';

      $('rt-output-box').hidden = false;
      $('rt-output').textContent = res.content ?? '[Пустой ответ]';
      $('rt-meta').textContent = `Провайдер: ${res.provider_used} · Модель: ${res.model_used} · Время: ${res.duration_seconds}с (Всего: ${res.total_duration_seconds}с)`;
      notify(`Выполнение через OmniRouter завершено (${res.model_used})`);
    } catch (err) {
      notify(err.message, true);
    } finally {
      btn.disabled = false; btn.textContent = 'Запуск';
    }
  });

  // Composable Skills Catalog Explorer
  async function loadSkillsCatalog() {
    const list = $('skills-catalog-list');
    if (!list) return;
    clear(list).append(el('p', 'Загрузка каталога навыков…', 'muted'));
    try {
      const data = await api('/platform/skills/catalog');
      clear(list);
      for (const skill of (data.skills || [])) {
        const item = el('div', '', 'memory-item');
        const header = el('div', '', 'memory-header');
        header.style.display = 'flex'; header.style.justifyContent = 'space-between'; header.style.alignItems = 'center';

        const titleSpan = el('strong', skill.name);
        const riskBadge = el('span', `Риск: ${skill.risk_level}`, 'model-badge');
        header.append(titleSpan, riskBadge);

        const desc = el('p', skill.description, 'memory-body');
        desc.style.fontSize = '11px'; desc.style.margin = '4px 0';

        const foot = el('div');
        foot.style.display = 'flex'; foot.style.justifyContent = 'space-between'; foot.style.alignItems = 'center'; foot.style.marginTop = '4px';
        const caps = el('span', `Требует: ${(skill.required_capabilities || []).join(', ') || 'нет'}`, 'tab-count');
        caps.style.fontSize = '10px';

        const runBtn = el('button', 'Запустить', 'secondary small-button');
        runBtn.type = 'button';
        runBtn.addEventListener('click', async () => {
          runBtn.disabled = true; runBtn.textContent = 'Выполнение...';
          try {
            const params = JSON.parse($('skill-exec-params')?.value || '{}');
            if (!params || Array.isArray(params) || typeof params !== 'object') {
              throw new Error('Параметры навыка должны быть JSON-объектом.');
            }
            const res = await api(`/platform/skills/${encodeURIComponent(skill.id)}/execute`, {
              method: 'POST', body: JSON.stringify(params),
            });
            $('skill-exec-card').hidden = false;
            $('skill-exec-title').textContent = `Результат навыка: ${skill.name}`;
            $('skill-exec-result').textContent = JSON.stringify(res.result || res, null, 2);
            notify(`Навык '${skill.name}' успешно выполнен.`);
          } catch (e) {
            notify(e.message, true);
          } finally {
            runBtn.disabled = false; runBtn.textContent = 'Запустить';
          }
        });

        foot.append(caps, runBtn);
        item.append(header, desc, foot);
        list.append(item);
      }
    } catch (e) {
      clear(list).append(el('p', e.message, 'error'));
    }
  }

  $('refresh-skills-btn')?.addEventListener('click', () => loadSkillsCatalog());

  document.querySelectorAll('[data-tab]').forEach(b => {
    if (b.dataset.tab === 'memory') b.addEventListener('click', () => loadMemories());
    if (b.dataset.tab === 'evolution') b.addEventListener('click', () => loadTrajectories());
    if (b.dataset.tab === 'router') b.addEventListener('click', () => loadRouterCatalog());
    if (b.dataset.tab === 'skills') b.addEventListener('click', () => loadSkillsCatalog());
    if (b.dataset.tab === 'computer') b.addEventListener('click', async () => {
      try {
        const st = await api('/platform/browser/status');
        $('browser-status-line').textContent = `Разрешено доменов: ${st.allowed_domains.length} · Выполнено: ${st.statistics.actions_executed}`;
      } catch (e) { /* ignore */ }
    });
  });

  (async function init() {
    await api('/workspace').then(info => { $('workspace-label').textContent = info.root; $('workspace-label').title = info.root; }).catch(error => { if (error.status !== 401) notify(error.message, true); });
    loadAgentAvailability();
    await loadSessions(); await loadSession(); startPolling();
  })();
})();
