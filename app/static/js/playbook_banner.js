/* Phase 999.8 Playbook Banner (D-16/D-17).
 *
 * Reads sessionStorage.active_playbook_step on DOMContentLoaded, fetches
 * fresh step data from /api/playbook-step-active, renders the sticky
 * indigo banner, and wires its two CTA buttons. Skips /m/* mobile routes
 * entirely. Silently clears stale state on 404 or on status === 'done'.
 */
(function () {
  'use strict';

  var SS_KEY = 'active_playbook_step';

  function hide() {
    var el = document.getElementById('playbook-banner');
    if (el) {
      el.hidden = true;
      el.style.display = 'none';
    }
    document.body.classList.remove('has-playbook-banner');
  }

  function show(title, meta) {
    var el = document.getElementById('playbook-banner');
    if (!el) return;
    var titleEl = document.getElementById('playbook-banner-title');
    var metaEl = document.getElementById('playbook-banner-meta');
    if (titleEl) titleEl.textContent = title;
    if (metaEl) metaEl.textContent = meta;
    el.hidden = false;
    el.style.display = 'flex';
    document.body.classList.add('has-playbook-banner');
  }

  function wireButtons(data) {
    var complete = document.getElementById('playbook-banner-complete');
    var back = document.getElementById('playbook-banner-back');

    if (complete) {
      complete.onclick = function () {
        fetch('/api/project-playbook-steps/' + encodeURIComponent(data.step_id) + '/complete', {
          method: 'POST',
          headers: {'Accept': 'application/json'},
        })
          .then(function (r) {
            if (!r.ok) {
              alert('Не удалось отметить выполненным. Попробуйте ещё раз.');
              return null;
            }
            return r.json().catch(function () { return {}; });
          })
          .then(function (body) {
            if (body === null) return;
            sessionStorage.removeItem(SS_KEY);
            var projectId = (body && body.project_id) || data.project_id;
            if (projectId) {
              window.location.href = '/ui/projects/' + projectId + '/kanban#playbook';
            } else {
              hide();
            }
          })
          .catch(function () {
            alert('Ошибка сети. Попробуйте ещё раз.');
          });
      };
    }

    if (back) {
      back.onclick = function () {
        sessionStorage.removeItem(SS_KEY);
        if (data.project_id) {
          window.location.href = '/ui/projects/' + data.project_id + '/kanban#playbook';
        } else {
          hide();
        }
      };
    }
  }

  function init() {
    // Skip on mobile routes entirely — /m/* has its own base template.
    if (window.location.pathname.indexOf('/m/') === 0) {
      hide();
      return;
    }

    // Skip on playbook admin/config pages — banner is for target flow screens,
    // not the screens where the admin configures blocks/templates/experts.
    if (window.location.pathname.indexOf('/ui/playbooks') === 0) {
      hide();
      return;
    }

    var state;
    try {
      var raw = sessionStorage.getItem(SS_KEY);
      if (!raw) {
        hide();
        return;
      }
      state = JSON.parse(raw);
    } catch (e) {
      console.warn('playbook_banner: bad sessionStorage', e);
      try { sessionStorage.removeItem(SS_KEY); } catch (_) {}
      hide();
      return;
    }

    if (!state || !state.step_id) {
      hide();
      return;
    }

    fetch('/api/playbook-step-active?step_id=' + encodeURIComponent(state.step_id), {
      headers: {'Accept': 'application/json'},
    })
      .then(function (resp) {
        if (resp.status === 404) {
          // Step gone — silently clear so the banner never resurrects.
          sessionStorage.removeItem(SS_KEY);
          hide();
          return null;
        }
        if (!resp.ok) {
          hide();
          return null;
        }
        return resp.json();
      })
      .then(function (data) {
        if (!data) return;
        if (data.status === 'done') {
          sessionStorage.removeItem(SS_KEY);
          hide();
          return;
        }
        var title = 'Шаг ' + data.position + '/' + data.total + ' · ' + data.title;
        var meta = 'Playbook: ' + data.playbook_name;
        show(title, meta);
        wireButtons(data);
      })
      .catch(function (e) {
        console.warn('playbook_banner: fetch failed', e);
        hide();
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
