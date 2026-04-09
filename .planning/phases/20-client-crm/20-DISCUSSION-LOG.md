# Phase 20: Client CRM - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-09
**Phase:** 20-client-crm
**Areas discussed:** Client card layout, Interaction log design, Client list & filtering, Site ↔ Client linking

---

## Client Card Layout

### Page organization

| Option | Description | Selected |
|--------|-------------|----------|
| Tabbed sections | Header with company info, then tabs: Sites, Contacts, Interactions, Info | ✓ |
| Single scroll page | All sections stacked vertically | |
| Two-column layout | Left: static data, Right: dynamic data | |

**User's choice:** Tabbed sections
**Notes:** Keeps the page clean as data grows, matches site detail page pattern.

### Header info

| Option | Description | Selected |
|--------|-------------|----------|
| Company name + legal name | Both trade and legal name at top | ✓ |
| Manager badge | Avatar/name chip in header | ✓ |
| Site count + quick stats | Summary counters | ✓ |
| INN/KPP + contact info | Tax IDs and primary contact | ✓ |

**User's choice:** All four options selected (multiselect)

### Tabs

| Option | Description | Selected |
|--------|-------------|----------|
| Sites | Linked sites with status | ✓ |
| Contacts | Contact persons, inline add/edit | ✓ |
| Interactions | Chronological note log | ✓ |
| Info | Full company details | ✓ |

**User's choice:** All four tabs
**Notes:** User requested questions in Russian from this point forward.

### Create/edit form

| Option | Description | Selected |
|--------|-------------|----------|
| Modal dialog | Popup modal, stays on current page | ✓ |
| Dedicated page | Full page form at /clients/new | |
| You decide | Claude picks | |

**User's choice:** Modal dialog

### Open tasks display

| Option | Description | Selected |
|--------|-------------|----------|
| Counter in header | Just a number "5 open tasks" | ✓ |
| Task list on Sites tab | Show 2-3 recent open tasks per site | |
| You decide | Claude picks | |

**User's choice:** Counter in header only

### Client deletion

| Option | Description | Selected |
|--------|-------------|----------|
| Soft delete | is_archived flag, data preserved | |
| Hard delete | CASCADE delete from DB | |
| You decide | Claude decides | ✓ |

**User's choice:** Claude's discretion

### Sidebar placement

| Option | Description | Selected |
|--------|-------------|----------|
| Top of sidebar | After Dashboard, before Sites | |
| Separate CRM section | New section with sub-items for Phases 21-23 | ✓ |
| You decide | Claude decides | |

**User's choice:** Separate CRM section

### In-card search

| Option | Description | Selected |
|--------|-------------|----------|
| No search needed | Unnecessary at scale | ✓ |
| HTMX live-search | Per-tab search | |

**User's choice:** No search needed

### Contact fields

| Option | Description | Selected |
|--------|-------------|----------|
| Just 4 fields | Name, phone, email, role | |
| Add Telegram | +Telegram username | |
| Extended set | Name, phone, email, role, Telegram, notes | ✓ |

**User's choice:** Extended set

### Contact editing

| Option | Description | Selected |
|--------|-------------|----------|
| Inline editing | Click row → editable via HTMX | ✓ |
| Modal for contact | Separate modal | |
| You decide | Claude picks | |

**User's choice:** Inline editing

---

## Interaction Log Design

### Interaction types

| Option | Description | Selected |
|--------|-------------|----------|
| Simple notes | Text + date + author only | ✓ |
| Notes + type | Add call/email/meeting/note category | |
| Notes + type + pin | Add pinning important entries | |

**User's choice:** Simple notes

### Adding entries

| Option | Description | Selected |
|--------|-------------|----------|
| Form above log | Textarea + button above the feed, HTMX | ✓ |
| Modal | Button opens modal with form | |

**User's choice:** Form above log

### Edit/delete permissions

| Option | Description | Selected |
|--------|-------------|----------|
| Own entries + admin all | User edits own, admin edits any | ✓ |
| Immutable log | Append-only, no editing | |
| You decide | Claude decides | |

**User's choice:** Own entries editable, admin can edit all

### Sort order

| Option | Description | Selected |
|--------|-------------|----------|
| Newest first | Descending by date | ✓ |
| Oldest first | Chronological | |

**User's choice:** Newest first

---

## Client List & Filtering

### Display format

| Option | Description | Selected |
|--------|-------------|----------|
| Table | Rows with columns | ✓ |
| Cards | Tile cards with metrics | |

**User's choice:** Table

### Filters

| Option | Description | Selected |
|--------|-------------|----------|
| Manager | Dropdown filter | ✓ |
| Has sites | With/without sites | |
| Text search | HTMX live-search by name/INN/email | ✓ |
| Date created | Filter by creation date | ✓ |

**User's choice:** Manager, Text search, Date created

### Pagination

| Option | Description | Selected |
|--------|-------------|----------|
| Server-side pagination | HTMX pagination, 20-50 per page | ✓ |
| All on one page | No pagination | |

**User's choice:** Server-side pagination

### Default sort

| Option | Description | Selected |
|--------|-------------|----------|
| By name A→Z | Alphabetical | ✓ |
| By last interaction | Recent activity first | |
| By creation date | Newest first | |

**User's choice:** By name A→Z

---

## Site ↔ Client Linking

### Attach mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Dropdown with search | Button → dropdown of free sites, HTMX search | ✓ |
| Modal with checkboxes | Modal with all sites, multi-select | |
| You decide | Claude picks | |

**User's choice:** Dropdown with search

### Already-attached sites

| Option | Description | Selected |
|--------|-------------|----------|
| Don't show | Only free sites in dropdown | ✓ |
| Show with label | Show all, mark attached ones | |

**User's choice:** Don't show (must detach from other client first)

### Reverse link on site page

| Option | Description | Selected |
|--------|-------------|----------|
| Client badge | Small "Client: X" badge with link | ✓ |
| No reverse link | Client only visible in CRM section | |

**User's choice:** Client badge on site page

### Bidirectional linking

| Option | Description | Selected |
|--------|-------------|----------|
| Yes | Can attach from both client card and site page | ✓ |
| No | Only from client card | |

**User's choice:** Yes, bidirectional

---

## Claude's Discretion

- Client deletion strategy (soft delete vs hard delete)
- Exact pagination page size
- HTMX partial templates structure

## Deferred Ideas

None — discussion stayed within phase scope.
