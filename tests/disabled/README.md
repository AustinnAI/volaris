# Disabled Tests

Tests in this directory are temporarily disabled because their features are not yet implemented or dependencies are missing.

## Files

- **test_workers_tasks.py** - Phase 4 worker tasks (not implemented yet)
  - Module `app.workers.tasks` doesn't exist
  - Re-enable when Phase 4 is complete

- **test_market_insights.py** - Polygon client integration (optional provider)
  - Requires `polygon_client` which is not configured in current setup
  - Re-enable when Polygon.io is added as a provider

- **test_providers.py** - Databento provider tests (optional)
  - Module `app.services.databento` doesn't exist
  - Re-enable when Databento is added as a provider

- **test_market_refresh.py** - Market refresh endpoint tests
  - Requires proper auth mocking setup for VOLARIS_API_TOKEN
  - Re-enable after fixing auth dependency injection in tests

## Re-enabling

Move tests back to `tests/` when their corresponding features are implemented.
