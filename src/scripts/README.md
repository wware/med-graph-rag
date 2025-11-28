# Utility Scripts

This directory contains standalone scripts for data acquisition, testing, and maintenance of the Medical Knowledge Graph.

## Contents

*   `download_papers.py`: Fetches papers from PubMed Central (PMC) using the NCBI E-utilities API. Supports searching and bulk downloading.
*   `test_queries.py`: A CLI tool for running test queries (semantic, keyword, hybrid) against the indexed data. Useful for validating search quality.

## Proposed Pytest Cases

### `download_papers.py`
*   **NCBI API Interaction**:
    *   Mock `requests.get` to simulate NCBI API responses (ESearch, ESummary, EFetch).
    *   Test `search_papers`: Verify query construction and ID extraction.
    *   Test `get_paper_metadata`: Verify parsing of JSON summaries into `PaperMetadata` objects.
    *   Test `download_paper_xml`: Verify file writing and error handling (e.g., network timeout, invalid XML).
*   **Rate Limiting**:
    *   Verify that the fetcher respects the specified rate limit (mock `time.sleep`).

### `test_queries.py`
*   **CLI Arguments**:
    *   Test argument parsing (valid/invalid flags).
*   **Query Execution**:
    *   Mock `MedicalPapersClient`.
    *   Verify that the script calls the correct client methods based on arguments (e.g., `--search-type semantic`).
    *   Test interactive mode input loop (mock `input`).
