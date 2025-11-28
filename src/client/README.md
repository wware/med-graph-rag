# Medical Papers Client

This directory contains the client library for interacting with the Medical Knowledge Graph. It abstracts the complexity of OpenSearch queries and AWS Bedrock interactions, providing a clean Python interface for users and applications.

## Contents

*   `medical_papers_client.py`: The main client class `MedicalPapersClient`. Handles connection to OpenSearch, executes semantic/keyword/hybrid searches, and manages results.

## Proposed Pytest Cases

### Unit Tests
*   **`MedicalPapersClient` Initialization**:
    *   Test initialization with different configurations (local vs. AWS, custom hosts).
    *   Verify environment variable fallbacks.
*   **Search Methods (`semantic_search`, `keyword_search`, `hybrid_search`)**:
    *   Mock the `opensearchpy` client to return controlled responses.
    *   Verify that the correct OpenSearch DSL queries are constructed (check JSON structure).
    *   Test result parsing: Ensure OpenSearch hits are correctly converted to `SearchResult` Pydantic models.
    *   Test handling of empty results.
*   **`get_paper`**:
    *   Test retrieving a specific paper by ID.
    *   Test error handling when a paper is not found.
*   **`export_results_to_csv`**:
    *   Verify that results are correctly written to a CSV file (using `tmp_path` fixture).

### Integration Tests
*   **Local OpenSearch**:
    *   Spin up a local OpenSearch container (via `docker-compose`).
    *   Index some sample data.
    *   Run actual search queries via the client and assert on the returned results.
    *   Verify connection handling and timeouts.
