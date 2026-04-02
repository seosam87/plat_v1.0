# Phase 5: Content Gap Analysis - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Find keywords where competitors rank in TOP-10 but we don't ("упущенные темы"). Support loading competitor keywords from CSV/XLSX (keys.so, Topvisor). Manual grouping of gap keywords, scoring by potential (frequency × position factor), auto-proposals for content plan with user approval before adding. Tooltip on potential score explaining the formula.

</domain>

<decisions>
## Implementation Decisions

### Data Sources
- **D-01:** Gap detection from existing SERP data (v3-04 sessions) — ключи, по которым конкурент в TOP-10 а мы нет. Плюс возможность догрузить ключи конкурента через CSV/XLSX (из keys.so, Topvisor, или ручной съём позиций).

### Grouping
- **D-02:** Ручная группировка gap-ключей в UI. Без автоматической кластеризации.

### Content Plan Integration
- **D-03:** Отдельная таблица `GapProposal` — предложения, которые пользователь одобряет перед добавлением в контент-план. Не автоматическое добавление.

### Potential Score
- **D-04:** Формула: `score = frequency × top_factor`, где top_factor = 1.0 для TOP-3, 0.7 для TOP-10, 0.3 для TOP-30, 0.1 для остальных. В UI рядом с полем потенциала — иконка "?" с tooltip описанием формулы. Со временем пользователь оценит актуальность.

### Scope
- **D-05:** Всё в одну фазу: gap detection + CSV/XLSX import + ручная группировка + proposals + potential scoring + UI.

### Claude's Discretion
- CSV/XLSX column mapping for keys.so and Topvisor formats
- GapProposal model fields
- Gap keyword group model design
- UI layout for gap analysis page

</decisions>

<canonical_refs>
## Canonical References

### SERP data (from v3-04)
- `app/models/analytics.py` — SessionSerpResult (SERP TOP-10 per keyword per session)
- `app/services/serp_analysis_service.py` — analyze_serp_results, extract_domain

### Competitors
- `app/models/competitor.py` — Competitor model
- `app/services/competitor_service.py` — compare_positions, detect_serp_competitors

### Keywords & positions
- `app/models/keyword.py` — Keyword, KeywordGroup
- `app/models/position.py` — KeywordPosition
- `app/services/keyword_service.py` — bulk_add_keywords, parsers

### Content plan
- `app/models/project.py` — ContentPlanItem (existing content plan entries)

### File import patterns
- `app/services/keyword_service.py` — existing CSV/XLSX import with openpyxl
- `app/routers/uploads.py` — existing file upload endpoints

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable
- SessionSerpResult stores TOP-10 per keyword — can derive gaps
- keyword_service.py has CSV/XLSX parsing patterns
- openpyxl already in stack for XLSX reading
- Competitor model already tracks domains per site

### New Components
- `GapKeyword` model — competitor keyword not in our set
- `GapGroup` model — manual grouping of gap keywords
- `GapProposal` model — proposals for content plan (pending/approved/rejected)
- `gap_service.py` — gap detection, scoring, import, proposals
- `app/routers/gap.py` — gap analysis router
- `app/templates/gap/index.html` — gap analysis UI

</code_context>

<deferred>
## Deferred Ideas

- Auto-clustering of gap keywords by SERP intersection
- DataForSEO domain keywords API integration
- Auto-scoring refinement based on actual ranking success rate

</deferred>

---

*Phase: v3-05-content-gap*
*Context gathered: 2026-04-02*
