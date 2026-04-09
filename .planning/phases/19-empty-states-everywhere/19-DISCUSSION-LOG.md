# Phase 19: Empty States Everywhere - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-09
**Phase:** 19-empty-states-everywhere
**Areas discussed:** Macro visual design, How-to content depth, CTA strategy, Page inventory scope

---

## Macro visual design

| Option | Description | Selected |
|--------|-------------|----------|
| Bordered card | White card with border + rounded corners, matching existing Metrika pattern | ✓ |
| Centered illustration | Full-width centered layout with larger icon, more dramatic | |
| Minimal inline | Subtle gray box with text + link, closest to current ad-hoc pattern | |

**User's choice:** Bordered card
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Emoji | Simple emoji icons, already used in health widget | |
| Without icons | Text only — minimalism | ✓ |
| SVG icons | Custom SVG — more professional but requires icon set | |

**User's choice:** Without icons

| Option | Description | Selected |
|--------|-------------|----------|
| Tailwind | Tailwind classes — consistent with most project templates | ✓ |
| Inline styles | Like macros/health.html — independent from Tailwind | |

**User's choice:** Tailwind

---

## How-to content depth

| Option | Description | Selected |
|--------|-------------|----------|
| Prerequisites + steps | Detailed: what to configure first, 2-3 steps + result description | |
| Brief hint | 1-2 sentences without step-by-step | |
| Claude's discretion | Claude decides depth per page based on feature complexity | ✓ |

**User's choice:** Claude's discretion

---

## CTA strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Primary + secondary | One action button + optional text link | ✓ |
| Primary only | Single action button without additional links | |

**User's choice:** Primary + secondary

| Option | Description | Selected |
|--------|-------------|----------|
| Blue button | bg-blue-600 text-white — matches existing project buttons | ✓ |
| Text link | Simple blue link without button — less intrusive | |
| Claude's discretion | Claude decides based on existing button patterns | |

**User's choice:** Blue button

---

## Page inventory scope

| Option | Description | Selected |
|--------|-------------|----------|
| Defer Tools | Empty states for tools after Phase 25 when pages exist | |
| Do now | Create empty states for all tools pages now | ✓ |

**User's choice:** Do now (all tools pages included)

| Option | Description | Selected |
|--------|-------------|----------|
| Migrate existing | Replace all existing ad-hoc empty states with macro calls | ✓ |
| New only | Keep existing as-is, apply macro only to pages without empty state | |

**User's choice:** Migrate existing

---

## Claude's Discretion

- How-to content depth per page
- Specific "Как использовать" text for each page
- Prerequisite selection per feature
- Page grouping across plans

## Deferred Ideas

None — discussion stayed within phase scope.
