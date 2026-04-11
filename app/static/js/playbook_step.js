/* Phase 999.8 Plan 06 — global openPlaybookStep handler.
 * Loaded once from base.html so HTMX innerHTML swaps of the Playbook tab
 * do not re-inline a <script> tag (HTMX 2.0 inline-script regression).
 */
(function () {
  if (typeof window.openPlaybookStep === 'function') {
    return;
  }
  window.openPlaybookStep = async function (stepId, ppId, projectId, title, pos, total, pbName, actionKind) {
    try {
      sessionStorage.setItem('active_playbook_step', JSON.stringify({
        step_id: stepId,
        project_playbook_id: ppId,
        project_id: projectId,
        title: title,
        position: pos,
        total: total,
        playbook_name: pbName,
        opened_at: Date.now()
      }));
    } catch (e) {
      console.warn('sessionStorage write failed', e);
    }
    try {
      await fetch('/api/project-playbook-steps/' + encodeURIComponent(stepId) + '/open-action', {
        method: 'POST',
        credentials: 'same-origin'
      });
    } catch (e) {
      console.warn('open-action failed', e);
    }
    try {
      const resp = await fetch(
        '/api/playbook-step-route?step_id=' + encodeURIComponent(stepId),
        { credentials: 'same-origin' }
      );
      if (!resp.ok) {
        alert('Не удалось открыть шаг (код ' + resp.status + ')');
        return;
      }
      const data = await resp.json();
      if (data && data.url) {
        window.location.href = data.url;
      } else {
        alert('Шаг завершается вручную');
      }
    } catch (e) {
      console.error('playbook-step-route failed', e);
      alert('Ошибка при открытии шага: ' + (e && e.message ? e.message : 'unknown'));
    }
  };
})();
