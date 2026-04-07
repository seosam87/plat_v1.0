"""Shared conftest for smoke_seed fixture tests (Phase 15.1).

Empty — tests use `@pytest.mark.asyncio(scope="session")` to share the same
event loop as the session-scoped smoke_seed fixture.
"""
