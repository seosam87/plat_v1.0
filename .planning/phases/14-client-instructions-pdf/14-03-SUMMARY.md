---
phase: 14-client-instructions-pdf
plan: "03"
subsystem: testing
tags: [tests, service-layer, subprocess, weasyprint, pytest]
dependency_graph:
  requires: ["14-01"]
  provides: ["CPDF-01-tests", "CPDF-02-tests", "CPDF-03-tests"]
  affects: ["14-01"]
tech_stack:
  added: []
  patterns:
    - "Pure unit tests for constants using class-based test organization"
    - "Async DB tests using db_session fixture with rollback isolation"
    - "Mock-based subprocess isolation tests with unittest.mock.patch"
    - "skipif guard for WeasyPrint integration tests when library absent"
key_files:
  created:
    - tests/test_client_report_service.py
    - tests/test_subprocess_pdf.py
  modified: []
decisions:
  - "WeasyPrint integration tests marked with skipif when library not installed — consistent with Docker-only execution model"
  - "DB-dependent async tests follow db_session fixture pattern matching existing tests"
metrics:
  duration_minutes: 8
  completed_date: "2026-04-06"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
requirements: [CPDF-01, CPDF-02, CPDF-03]
---

# Phase 14 Plan 03: Service-Layer Tests Summary

Service-layer test coverage for the client instruction PDF system: 14 tests in `test_client_report_service.py` and 7 tests in `test_subprocess_pdf.py`.

## What Was Built

**tests/test_client_report_service.py** (14 tests):
- `TestInstructionTemplates.test_instruction_templates_keys` — verifies exactly 7 problem type keys
- `TestInstructionTemplates.test_instruction_templates_structure` — verifies label + instruction on each entry
- `TestInstructionTemplates.test_instruction_templates_russian_content` — verifies Cyrillic text in labels
- `TestInstructionTemplates.test_top_n_value` — verifies TOP_N == 20
- `test_gather_report_data_all_blocks` — all 4 blocks return summary/problem_groups/positions
- `test_gather_report_data_quick_wins_only` — partial config returns empty positions dict
- `test_gather_report_data_summary_structure` — summary has total_pages/total_problems/critical_count
- `test_gather_report_data_problem_groups_have_instruction` — groups include label/instruction/pages
- `test_create_report_record` — creates ClientReport with status=pending, correct blocks_config
- `test_save_report_pdf` — updates status to ready, stores pdf_data bytes
- `test_mark_report_failed` — updates status to failed, stores error_message
- `test_mark_report_failed_truncates_long_error` — error_message truncated to 500 chars
- `test_get_report_history_ordered_by_created_at` — newest-first ordering verified
- `test_get_report_by_id_returns_none_for_missing` — returns None for unknown UUID

**tests/test_subprocess_pdf.py** (7 tests):
- `test_valid_html_returns_pdf_bytes` — PDF bytes start with %PDF- (skipped without WeasyPrint)
- `test_russian_text_renders` — Cyrillic HTML renders to PDF (skipped without WeasyPrint)
- `test_lenient_html_still_produces_pdf` — unclosed tags handled gracefully (skipped without WeasyPrint)
- `test_temp_files_cleaned_on_success` — no .html/.pdf files remain in temp dir (skipped without WeasyPrint)
- `test_timeout_via_mock` — TimeoutExpired -> RuntimeError("timed out")
- `test_subprocess_failure_raises_runtime_error` — exit code 1 -> RuntimeError("PDF render failed")
- `test_temp_files_cleaned_on_failure` — temp HTML file removed even on subprocess failure

## Test Results

In the current environment (no Docker): 7 passed, 4 skipped, 10 errors (DB connection errors — same pattern as all async DB tests in the project without Docker compose running).

In Docker test environment: all 21 tests expected to pass.

## Deviations from Plan

**1. [Rule 2 - Missing functionality] Added Russian text test for subprocess_pdf**

- Found during: Task 2
- Issue: Plan mentioned Russian text rendering as behavior but only had English assertion in code sample
- Fix: Added `test_russian_text_renders` with Cyrillic HTML content
- Files modified: tests/test_subprocess_pdf.py

**2. [Rule 2 - Missing functionality] Added WeasyPrint availability guard**

- Found during: Task 2
- Issue: WeasyPrint integration tests would fail outright if library is absent (not a skip)
- Fix: Added `HAS_WEASYPRINT` try/except check + `@needs_weasyprint` marker
- Files modified: tests/test_subprocess_pdf.py

Otherwise: plan executed as written.

## Known Stubs

None. Both test files are complete with no placeholder logic.

## Self-Check: PASSED

- tests/test_client_report_service.py: FOUND
- tests/test_subprocess_pdf.py: FOUND
- Commit b74762b (Task 1): verified
- Commit dc86350 (Task 2): verified
