/*
 * tour.js — Shepherd.js-based interactive tour player (Phase 19.2)
 *
 * Loaded from base.html only for admin users. Consumes the /api/tours/ API
 * shipped in Plan 03 and plays tour-only scenario YAML files as guided
 * onboarding tours over the live application.
 *
 * Op handling (D-02):
 *   - say            → Shepherd step with text + "Далее" button
 *   - highlight      → Shepherd step attached to resolved target
 *   - wait_for_click → Shepherd step with advanceOn click
 *   - open           → persist resume state, window.location.assign
 *   - click / fill / wait_for / expect_*  → console.warn and skip
 */
(function () {
  'use strict';

  const RESUME_KEY = 'gsd_tour_resume_v1';

  /**
   * Resolve a scenario locator string (mirrors tests/fixtures/scenario_runner/locators.py)
   * to a CSS selector usable by Shepherd's attachTo/advanceOn.
   *
   * Returns null for prefixes that can't be mapped to a pure CSS selector
   * (text=, label=) — the caller then renders a centered modal step.
   */
  function resolveSelector(target) {
    if (!target || typeof target !== 'string') return null;

    if (target.startsWith('css=')) {
      return target.slice(4);
    }
    if (target.startsWith('testid=')) {
      return '[data-testid="' + target.slice(7) + '"]';
    }
    if (target.startsWith('role=')) {
      const m = target.match(/^role=(\w+)(?:\[name=["'](.+?)["']\])?$/);
      if (!m) {
        console.warn('[tour] unparseable role= locator', target);
        return null;
      }
      const roleName = m[1];
      const accName = m[2];
      if (!accName) {
        return '[role="' + roleName + '"]';
      }
      return '[role="' + roleName + '"][aria-label="' + accName + '"], button[aria-label="' + accName + '"]';
    }
    if (target.startsWith('text=')) {
      console.warn('[tour] text= locator not supported in tour mode; use css= or role=', target);
      return null;
    }
    if (target.startsWith('label=')) {
      console.warn('[tour] label= locator not supported in tour mode; use css= or role=', target);
      return null;
    }
    // Raw CSS fallback
    return target;
  }

  /**
   * Build a Shepherd tour from a parsed scenario JSON object. Optionally
   * resumes from startAtIndex (used by the sessionStorage resume handler).
   */
  function buildTour(scenario, startAtIndex) {
    const tour = new Shepherd.Tour({
      useModalOverlay: true,
      defaultStepOptions: {
        scrollTo: { behavior: 'smooth', block: 'center' },
        cancelIcon: { enabled: true },
        classes: 'shepherd-theme-arrows',
      },
    });

    const skipBefore = startAtIndex || 0;
    let lastSayText = (scenario.tour && scenario.tour.intro) || '';

    scenario.steps.forEach(function (step, i) {
      if (i < skipBefore) return;

      const op = step.op;

      if (op === 'say') {
        lastSayText = step.text;
        tour.addStep({
          id: 's' + i,
          text: step.text,
          buttons: [{ text: 'Далее', action: tour.next }],
        });
        return;
      }

      if (op === 'highlight') {
        const sel = resolveSelector(step.target);
        tour.addStep({
          id: 's' + i,
          text: lastSayText,
          attachTo: sel ? { element: sel, on: 'bottom' } : undefined,
          buttons: [{ text: 'Далее', action: tour.next }],
        });
        return;
      }

      if (op === 'wait_for_click') {
        const sel = resolveSelector(step.target);
        tour.addStep({
          id: 's' + i,
          text: lastSayText,
          attachTo: sel ? { element: sel, on: 'bottom' } : undefined,
          advanceOn: sel ? { selector: sel, event: 'click' } : undefined,
        });
        return;
      }

      if (op === 'open') {
        const url = step.url;
        tour.addStep({
          id: 's' + i,
          text: lastSayText || 'Переходим на следующую страницу...',
          buttons: [
            {
              text: 'Продолжить',
              action: function () {
                sessionStorage.setItem(
                  RESUME_KEY,
                  JSON.stringify({ name: scenario.name, index: i + 1 })
                );
                window.location.assign(url);
              },
            },
          ],
        });
        return;
      }

      // click / fill / wait_for / expect_text / expect_status — test-only
      console.warn('[tour] skipping test-only op:', op);
    });

    tour.on('complete', function () {
      sessionStorage.removeItem(RESUME_KEY);
    });
    tour.on('cancel', function () {
      sessionStorage.removeItem(RESUME_KEY);
    });

    return tour;
  }

  /**
   * Fetch a single tour by name and start it. Optionally resume from index.
   */
  async function startTour(name, startAtIndex) {
    try {
      const res = await fetch('/api/tours/' + encodeURIComponent(name));
      if (!res.ok) {
        console.error('[tour] failed to load tour', name, res.status);
        return;
      }
      const scenario = await res.json();
      const tour = buildTour(scenario, startAtIndex || 0);
      tour.start();
    } catch (err) {
      console.error('[tour] startTour error', err);
    }
  }

  /**
   * Render a floating "Show tour" button in the bottom-right corner.
   * z-index 100 sits above sidebar (40) and log panel (50) but below
   * toast-container (999) — the intended ordering.
   */
  function renderShowTourButton(tours) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.setAttribute('data-tour-launcher', '1');
    btn.style.cssText =
      'position:fixed;bottom:1.5rem;right:1.5rem;z-index:100;background:#4f46e5;color:#fff;border:none;border-radius:9999px;padding:.75rem 1.25rem;box-shadow:0 4px 12px rgba(0,0,0,.15);cursor:pointer;font-size:.9rem;';
    btn.textContent = '🎓 Показать тур';
    btn.addEventListener('click', function () {
      if (tours.length === 1) {
        startTour(tours[0].name);
        return;
      }
      const listing = tours
        .map(function (t, i) {
          return i + 1 + '. ' + (t.title || t.name);
        })
        .join('\n');
      const raw = window.prompt('Выберите тур:\n' + listing, '1');
      if (!raw) return;
      const idx = parseInt(raw, 10) - 1;
      if (isNaN(idx) || idx < 0 || idx >= tours.length) return;
      startTour(tours[idx].name);
    });
    document.body.appendChild(btn);
  }

  /**
   * Bootstrap: either resume a tour interrupted by navigation, or ask the
   * API which tours apply to the current page and render the launcher.
   */
  async function bootstrap() {
    // 1. Resume path — survives full-page navigation from an `open` op.
    const resumeRaw = sessionStorage.getItem(RESUME_KEY);
    if (resumeRaw) {
      try {
        const parsed = JSON.parse(resumeRaw);
        if (parsed && parsed.name) {
          await startTour(parsed.name, parsed.index || 0);
          return;
        }
      } catch (err) {
        console.warn('[tour] invalid resume state, clearing', err);
        sessionStorage.removeItem(RESUME_KEY);
      }
    }

    // 2. Normal path — show launcher button if any tours match this page.
    try {
      const res = await fetch('/api/tours/?page=' + encodeURIComponent(location.pathname));
      if (!res.ok) return; // belt-and-braces; non-admins are server-gated
      const tours = await res.json();
      if (!Array.isArray(tours) || tours.length === 0) return;
      renderShowTourButton(tours);
    } catch (err) {
      console.warn('[tour] bootstrap fetch failed', err);
    }
  }

  // Handle the defer-after-ready case: defer means this script evaluates
  // after DOMContentLoaded in most cases, but be defensive.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap);
  } else {
    bootstrap();
  }
})();
