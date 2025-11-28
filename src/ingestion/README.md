# Ingestion Pipeline

This directory contains the core logic for processing medical papers, generating embeddings, and indexing them into the knowledge graph.

## Contents

*   `jats_parser.py`: Parses JATS XML files (standard format for PMC papers) into structured objects (`ParsedPaper`, `Chunk`, `TableData`).
*   `embedding_generator.py`: Handles interactions with AWS Bedrock (Titan Embeddings v2) to generate vector embeddings for text chunks. Includes rate limiting.
*   `pipeline.py`: Orchestrates the flow: Parse XML -> Generate Embeddings -> Index to OpenSearch.

## Proposed Pytest Cases

### `jats_parser.py`
*   **XML Parsing**:
    *   Provide sample JATS XML strings/files.
    *   Verify extraction of metadata (Title, Authors, PMID, DOI).
    *   Verify section splitting and paragraph extraction.
    *   Test extraction of tables and citations.
*   **Edge Cases**:
    *   Test with malformed XML.
    *   Test with missing optional fields (e.g., no abstract, no keywords).

### `embedding_generator.py`
*   **Bedrock Interaction**:
    *   Mock `boto3` client.
    *   Verify that `embed_text` calls the Bedrock API with the correct model ID and parameters.
    *   Test `embed_batch` to ensure it handles lists of text correctly.
*   **Rate Limiting**:
    *   Verify that the delay logic functions (mock `time.sleep`).
    *   Test batching logic (splitting large lists into smaller batches).

### `pipeline.py`
*   **`OpenSearchIndexer`**:
    *   Mock `opensearchpy` client.
    *   Test `create_index_if_not_exists`: Verify mapping definition (vector dimensions, field types).
    *   Test `index_document` and `bulk_index`.
*   **`PaperIndexingPipeline`**:
    *   Mock `EmbeddingGenerator` and `OpenSearchIndexer`.
    *   Test `process_paper`: Verify that a `ParsedPaper` is correctly converted into document dicts with embeddings and sent to the indexer.
    *   Test error handling during processing (e.g., embedding failure).
