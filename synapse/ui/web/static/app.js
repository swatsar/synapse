(() => {
  'use strict';
  const keyInput = document.getElementById('api-key');
  const keyForm = document.getElementById('api-key-form');
  const keyDialog = document.getElementById('key-dialog');
  if (keyInput) keyInput.value = sessionStorage.getItem('synapse-api-key') || '';
  if (keyForm) keyForm.addEventListener('submit', event => {
    event.preventDefault();
    if (keyInput.value) sessionStorage.setItem('synapse-api-key', keyInput.value);
    else sessionStorage.removeItem('synapse-api-key');
    if (keyDialog) keyDialog.close();
    window.dispatchEvent(new Event('synapse-refresh'));
  });
  const cancelKey = document.getElementById('cancel-key');
  if (cancelKey) cancelKey.addEventListener('click', () => keyDialog.close());
  let noticeTimer;

  window.synapse = {
    async api(path, options = {}) {
      const headers = new Headers(options.headers || {});
      const key = sessionStorage.getItem('synapse-api-key');
      if (key) headers.set('X-API-Key', key);
      if (options.body !== undefined) headers.set('Content-Type', 'application/json');
      let response;
      try {
        response = await fetch(`/api/v1${path}`, {...options, headers});
      } catch {
        throw new Error('Сервер недоступен. Проверьте, запущен ли Synapse.');
      }
      let data = null;
      try { data = response.status === 204 ? null : await response.json(); }
      catch { if (response.ok) throw new Error('Сервер вернул некорректный JSON.'); }
      if (!response.ok) {
        const detail = data && (data.detail || data.message || data.error);
        const text = Array.isArray(detail) ? detail.map(item => item.msg).join('; ') : detail;
        const error = new Error(typeof text === 'string' ? text : `Ошибка запроса (HTTP ${response.status})`);
        error.status = response.status;
        if (response.status === 401 && keyDialog && !keyDialog.open) keyDialog.showModal();
        throw error;
      }
      return data;
    },
    element(tag, text, className) {
      const node = document.createElement(tag);
      if (text !== undefined) node.textContent = String(text ?? '');
      if (className) node.className = className;
      return node;
    },
    icon(name, className) {
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      if (className) svg.setAttribute('class', className);
      svg.setAttribute('aria-hidden', 'true');
      const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
      use.setAttribute('href', `#i-${name}`);
      svg.append(use);
      return svg;
    },
    clear(node) { node.replaceChildren(); return node; },
    notify(message, error = false) {
      const node = document.getElementById('notice');
      if (!node) return;
      clearTimeout(noticeTimer);
      node.textContent = message;
      node.className = `toast ${error ? 'error' : 'success'}`;
      node.hidden = false;
      noticeTimer = setTimeout(() => { node.hidden = true; }, error ? 8000 : 4000);
    },
    json(value) { return JSON.stringify(value, null, 2); },
    date(value) {
      if (!value) return '—';
      const parsed = new Date(value);
      return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString('ru-RU', {dateStyle: 'short', timeStyle: 'short'});
    },
    openConnection() {
      if (keyDialog) { keyInput.value = sessionStorage.getItem('synapse-api-key') || ''; keyDialog.showModal(); }
      else if (keyInput) { keyInput.focus(); keyInput.scrollIntoView({behavior: 'smooth', block: 'center'}); }
    },
  };
})();
