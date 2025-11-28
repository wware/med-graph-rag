#!/usr/bin/env python3
"""
Simple test script to verify OpenSearch connection
"""
import os
import sys

# Set environment variables for local docker-compose
os.environ['OPENSEARCH_HOST'] = 'localhost'
os.environ['OPENSEARCH_PORT'] = '9200'

from src.ingestion.pipeline import OpenSearchIndexer

def test_connection():
    """Test connection to local OpenSearch"""
    print("Testing connection to local OpenSearch...")
    print(f"Host: {os.getenv('OPENSEARCH_HOST')}")
    print(f"Port: {os.getenv('OPENSEARCH_PORT')}")
    print()

    try:
        # Initialize indexer
        indexer = OpenSearchIndexer(
            index_name='medical-papers',
            create_index=True  # Will create index if it doesn't exist
        )

        # Test cluster health
        health = indexer.client.cluster.health()
        print(f"✓ Cluster health: {health['status']}")
        print(f"✓ Number of nodes: {health['number_of_nodes']}")
        print(f"✓ Number of data nodes: {health['number_of_data_nodes']}")
        print()

        # List indices
        indices = indexer.client.cat.indices(format='json')
        print("Available indices:")
        for idx in indices:
            print(f"  - {idx['index']} ({idx['docs.count']} docs, {idx['store.size']})")
        print()

        print("✓ Successfully connected to OpenSearch!")
        return True

    except Exception as e:
        print(f"✗ Error connecting to OpenSearch: {e}")
        print()
        print("Make sure docker-compose is running:")
        print("  docker-compose up -d")
        return False

if __name__ == '__main__':
    success = test_connection()
    sys.exit(0 if success else 1)
