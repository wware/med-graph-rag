# Test Suite

This directory contains the test suite for the Medical Knowledge Graph project. It is designed to be run with `pytest`.

## Structure (Recommended)

*   `unit/`: Tests that run in isolation, mocking external dependencies (AWS, OpenSearch). Fast and reliable.
*   `integration/`: Tests that verify interactions between components or with local services (e.g., Dockerized OpenSearch).
*   `e2e/`: End-to-end tests that might run against a deployed dev environment.
*   `conftest.py`: Shared fixtures for pytest (e.g., mock clients, sample data loaders).

## Running Tests

To run all tests:
```bash
pytest
```

To run a specific category:
```bash
pytest tests/unit
```

To run with coverage report:
```bash
pytest --cov=src tests/
```

## Proposed Pytest Cases (General)

*   **Configuration**: Test loading of environment variables and configuration files.
*   **Fixtures**:
    *   Create fixtures for sample JATS XML data.
    *   Create fixtures for mock OpenSearch clients and Bedrock clients.
    *   Create fixtures for temporary directories (using `tmp_path`).
