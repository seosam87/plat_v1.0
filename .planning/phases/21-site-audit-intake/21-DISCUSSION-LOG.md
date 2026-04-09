# Phase 21: Site Audit Intake - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-09
**Phase:** 21-site-audit-intake
**Areas discussed:** Form structure & sections, Verification checklist, Save & resume UX, Intake completion flow

---

## Form Structure & Sections

### Layout style

| Option | Description | Selected |
|--------|-------------|----------|
| Accordion sections | Collapsible sections on single page, save on collapse | |
| Wizard steps | Step-by-step flow with Next/Back buttons | |
| Tabbed sections | Horizontal tabs like CRM detail page | checkmark |

**User's choice:** Tabbed sections
**Notes:** Consistent with CRM detail page pattern from Phase 20.

### Number of sections

| Option | Description | Selected |
|--------|-------------|----------|
| 5 sections | Access, Goals, Analytics, Tech SEO, Checklist | checkmark |
| 4 sections | Access, Goals, Tech (merged analytics+SEO), Checklist | |
| 3 sections | Access+Tech, Goals, Checklist | |

**User's choice:** 5 sections

### Access tab fields

| Option | Description | Selected |
|--------|-------------|----------|
| Minimum: show current | Read-only WP status + link to settings | checkmark |
| Extended | WP status + hosting, DNS, notes | |
| Full set | Extended + FTP/SSH, CDN, domain registrar | |

**User's choice:** Minimum -- only show existing data

### Goals & Competitors tab

| Option | Description | Selected |
|--------|-------------|----------|
| Standard | Goal textarea, regions, competitor URLs (up to 10), notes | checkmark |
| Minimal | Goal textarea, competitors as free text | |
| Extended | Standard + business type dropdown, SEO priorities checkboxes | |

**User's choice:** Standard

---

## Verification Checklist

### Update mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Static snapshot | From DB on page load, "Refresh" button | checkmark |
| Real-time | Auto-check on tab open, Celery tasks | |

**User's choice:** Static snapshot with refresh button

### Status states

| Option | Description | Selected |
|--------|-------------|----------|
| 3 states | Connected / Not configured / Not checked | checkmark |
| 2 states | OK / Not OK | |

**User's choice:** 3 states

---

## Save & Resume UX

### Save mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit save button per tab | "Save section" button, HTMX POST, toast | checkmark |
| Auto-save on tab switch | Saves current tab when switching | |

**User's choice:** Explicit save button

### Progress indicator

| Option | Description | Selected |
|--------|-------------|----------|
| Tab checkmarks | Checkmark icon on saved tabs | checkmark |
| Progress bar + checkmarks | Overall bar + tab checkmarks | |

**User's choice:** Tab checkmarks only

---

## Intake Completion Flow

### Completion trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Always available with warning | Button active, warns if sections incomplete | checkmark |
| Only after all sections | Button disabled until all saved | |
| Explicit user action | Always active, no warnings | |

**User's choice:** Always available with warning

### Badge location

| Option | Description | Selected |
|--------|-------------|----------|
| Site list + site detail | Badge in both places | checkmark |
| Site detail only | Badge only on site page | |

**User's choice:** Both site list and site detail

---

## Claude's Discretion

- JSON schema for intake section data
- Error handling for verification checklist items
- Exact badge styling and placement

## Deferred Ideas

- INTAKE-06: Auto-generate baseline crawl on completion
- INTAKE-07: Intake answers pre-populate proposal templates
