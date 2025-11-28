"""
Test Queries Script

This file contains tests for querying the medical knowledge graph.
It can be run using pytest:

    pytest src/scripts/test_queries.py

To run with output display:

    pytest -s src/scripts/test_queries.py
"""

import json
import sys
from pathlib import Path
import pytest

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.client.medical_papers_client import MedicalPapersClient


def interactive_mode(client: MedicalPapersClient) -> None:
    """Interactive query testing mode.

    Args:
        client (MedicalPapersClient): The initialized client.
    """
    print("=== Medical Knowledge Graph - Interactive Query Mode ===")
    print("Enter your queries below. Type 'quit' or 'exit' to exit.")
    print("Commands:")
    print("  semantic <query>  - Semantic search using embeddings")
    print("  keyword <query>   - Keyword search")
    print("  hybrid <query>    - Hybrid search (semantic + keyword)")
    print("  quit/exit         - Exit interactive mode")
    print()

    while True:
        try:
            query_input = input("Query> ").strip()

            if not query_input:
                continue

            if query_input.lower() in ['quit', 'exit']:
                print("Goodbye!")
                break

            # Parse command
            parts = query_input.split(maxsplit=1)
            if len(parts) < 2:
                print("Please specify a search type and query")
                continue

            search_type, query = parts

            # Execute search
            if search_type == 'semantic':
                results = client.search(query, k=10, search_type='vector')
                print(f"\n=== Semantic Search Results for: '{query}' ===")
            elif search_type == 'keyword':
                results = client.search(query, k=10, search_type='keyword')
                print(f"\n=== Keyword Search Results for: '{query}' ===")
            elif search_type == 'hybrid':
                results = client.search(query, k=10, search_type='hybrid')
                print(f"\n=== Hybrid Search Results for: '{query}' ===")
            else:
                print(f"Unknown search type: {search_type}")
                continue

            # Display results
            if not results:
                print("No results found.")
            else:
                for i, result in enumerate(results, 1):
                    print(f"\n{i}. {result.title} (Score: {result.score:.3f})")
                    print(f"   PMC ID: {result.pmc_id}")
                    print(f"   Section: {result.section}")
                    print(f"   {result.chunk_text[:200]}...")

            print()

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


def run_query(client: MedicalPapersClient, query: str, search_type: str = 'hybrid', k: int = 10) -> None:
    """Run a single query and display results.

    Args:
        client (MedicalPapersClient): The initialized client.
        query (str): The search query.
        search_type (str): The type of search ('semantic', 'keyword', 'hybrid'). Defaults to 'hybrid'.
        k (int): Number of results to return. Defaults to 10.
    """
    print(f"Running {search_type} search for: '{query}'")

    if search_type == 'semantic':
        results = client.search(query, k=k, search_type='vector')
    elif search_type == 'keyword':
        results = client.search(query, k=k, search_type='keyword')
    elif search_type == 'hybrid':
        results = client.search(query, k=k, search_type='hybrid')
    else:
        print(f"Unknown search type: {search_type}")
        return

    print(f"\nFound {len(results)} results:\n")

    for i, result in enumerate(results, 1):
        # Result is a SearchResult object, not a dict
        print(f"{i}. {result.title} (Score: {result.score:.3f})")
        print(f"   PMC ID: {result.pmc_id}")
        print(f"   Section: {result.section}")
        print(f"   {result.chunk_text[:200]}...")
        print()


def print_curl_command(client: MedicalPapersClient, body: dict) -> None:
    """Helper to print equivalent curl command."""
    try:
        # Try to get host/port from client connection
        # This depends on the internals of opensearch-py
        connection = client.client.transport.hosts[0]
        host = connection.get('host', 'localhost')
        port = connection.get('port', 9200)
        scheme = 'https' if client.client.transport.use_ssl else 'http'
    except Exception:
        host = 'localhost'
        port = 9200
        scheme = 'http'

    url = f"{scheme}://{host}:{port}/{client.index_name}/_search"

    print("\n--- Equivalent CURL command ---")
    print(f"curl -X POST {url} \\")
    print("  -H 'Content-Type: application/json' \\")
    print(f"  -d '{json.dumps(body, indent=2)}'")
    print("-------------------------------\n")


def test_queries():
    """Test that queries can be executed against the OpenSearch instance."""
    try:
        client = MedicalPapersClient()
    except Exception as e:
        pytest.skip(f"Could not connect to OpenSearch: {e}")

    # Test a simple keyword search
    print("\nTesting keyword search...")
    query = "cancer"
    k = 1

    # Generate and print curl command
    try:
        body = client._build_keyword_query(query, k)
        print_curl_command(client, body)
    except Exception as e:
        print(f"Could not generate curl command: {e}")

    results = client.search(query, k=k, search_type='keyword')
    assert isinstance(results, list)

    # Test a hybrid search
    print("\nTesting hybrid search...")
    query = "treatment"

    try:
        # For hybrid, we need an embedding.
        # If we can't generate one (no Bedrock), we might skip the curl print or use a dummy one.
        if client.bedrock:
            embedding = client._generate_query_embedding(query)
            body = client._build_hybrid_query(query, embedding, k, 0.5)
            # Truncate embedding for display to avoid spamming console
            # We'll just print it as is, user can handle the output size
            print_curl_command(client, body)
        else:
            print("(Skipping hybrid curl command generation - Bedrock not configured)")

        results = client.search(query, k=k, search_type='hybrid')
        assert isinstance(results, list)
    except RuntimeError as e:
        # This might happen if Bedrock is not configured
        print(f"Skipping hybrid search test: {e}")
