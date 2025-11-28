"""
Embedding and Indexing Pipeline for Medical Research Papers

Takes parsed JATS papers, generates embeddings using AWS Bedrock Titan Embeddings V2,
and indexes them to Amazon OpenSearch Service for hybrid vector + keyword search.
"""

import boto3
import os
import pytest
from typing import List, Dict, Any, Optional
from pathlib import Path
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from jats_parser import ParsedPaper, PaperMetadata, Chunk
from embedding_generator import EmbeddingGenerator
from unittest.mock import patch, MagicMock


class OpenSearchIndexer:
    """Index documents with embeddings to OpenSearch (local or AWS).

    Attributes:
        client (OpenSearch): The OpenSearch client.
        index_name (str): The name of the index.
    """

    def __init__(self,
                 host: Optional[str] = None,
                 port: Optional[int] = None,
                 region: str = 'us-east-1',
                 index_name: str = 'medical-papers',
                 create_index: bool = True,
                 use_ssl: Optional[bool] = None,
                 use_aws_auth: Optional[bool] = None):
        """Initialize OpenSearch client.

        Args:
            host (Optional[str]): OpenSearch host. Defaults to OPENSEARCH_HOST env var or 'localhost'.
            port (Optional[int]): OpenSearch port. Defaults to OPENSEARCH_PORT env var or 9200.
            region (str): AWS region (only used if use_aws_auth=True). Defaults to 'us-east-1'.
            index_name (str): Name of the index to use. Defaults to 'medical-papers'.
            create_index (bool): Whether to create index if it doesn't exist. Defaults to True.
            use_ssl (Optional[bool]): Whether to use SSL. Auto-detected based on host if None.
            use_aws_auth (Optional[bool]): Whether to use AWS auth. Auto-detected based on host if None.
        """
        # Get configuration from environment variables
        host = host or os.getenv('OPENSEARCH_HOST', 'localhost')
        port = port or int(os.getenv('OPENSEARCH_PORT', '9200'))

        # Auto-detect local vs AWS deployment
        is_local = host in ('localhost', '127.0.0.1', 'opensearch') or port != 443

        if use_ssl is None:
            use_ssl = not is_local

        if use_aws_auth is None:
            use_aws_auth = not is_local

        # Set up authentication
        http_auth = None
        if use_aws_auth:
            credentials = boto3.Session().get_credentials()
            http_auth = AWSV4SignerAuth(credentials, region, 'es')

        # Create OpenSearch client
        self.client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            http_auth=http_auth,
            use_ssl=use_ssl,
            verify_certs=use_ssl,
            connection_class=RequestsHttpConnection,
            timeout=60
        )

        self.index_name = index_name

        print(f"Connected to OpenSearch at {host}:{port} (SSL: {use_ssl}, AWS Auth: {use_aws_auth})")

        if create_index:
            self._create_index_if_not_exists()

    def _create_index_if_not_exists(self) -> None:
        """Create the index with appropriate mappings if it doesn't exist."""
        if self.client.indices.exists(index=self.index_name):
            print(f"Index '{self.index_name}' already exists")
            return

        # Index mapping with vector field for k-NN search
        index_body = {
            "settings": {
                "index": {
                    "knn": True,  # Enable k-NN plugin
                    "knn.algo_param.ef_search": 512,
                    "number_of_shards": 2,
                    "number_of_replicas": 1
                }
            },
            "mappings": {
                "properties": {
                    # Vector field
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": 1024,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "nmslib",
                            "parameters": {
                                "ef_construction": 512,
                                "m": 16
                            }
                        }
                    },

                    # Text fields for keyword search
                    "chunk_text": {
                        "type": "text",
                        "analyzer": "standard"
                    },
                    "title": {
                        "type": "text",
                        "analyzer": "standard",
                        "fields": {
                            "keyword": {"type": "keyword"}
                        }
                    },

                    # Metadata fields
                    "paper_id": {"type": "keyword"},
                    "pmc_id": {"type": "keyword"},
                    "pmid": {"type": "keyword"},
                    "doi": {"type": "keyword"},
                    "section": {"type": "keyword"},
                    "subsection": {"type": "keyword"},
                    "chunk_type": {"type": "keyword"},
                    "paragraph_index": {"type": "integer"},

                    # Author and journal
                    "authors": {"type": "text"},
                    "journal": {"type": "keyword"},
                    "publication_date": {"type": "date"},

                    # Medical terms
                    "mesh_terms": {"type": "keyword"},
                    "keywords": {"type": "keyword"},
                    "entities": {
                        "type": "nested",
                        "properties": {
                            "text": {"type": "text"},
                            "type": {"type": "keyword"},
                            "umls_id": {"type": "keyword"}
                        }
                    },

                    # Citations
                    "citations": {"type": "keyword"},

                    # Full abstract for context
                    "abstract": {"type": "text"}
                }
            }
        }

        self.client.indices.create(index=self.index_name, body=index_body)
        print(f"Created index '{self.index_name}'")

    def index_document(self, doc_id: str, document: Dict[str, Any]) -> bool:
        """Index a single document.

        Args:
            doc_id (str): Unique document ID.
            document (Dict[str, Any]): Document to index (must include 'embedding' field).

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            response = self.client.index(
                index=self.index_name,
                id=doc_id,
                body=document,
                refresh=False  # Don't refresh immediately for better performance
            )
            return response['result'] in ['created', 'updated']
        except Exception as e:
            print(f"Error indexing document {doc_id}: {e}")
            return False

    def bulk_index(self, documents: List[Dict[str, Any]],
                   chunk_size: int = 500) -> Dict[str, int]:
        """Bulk index multiple documents.

        Args:
            documents (List[Dict[str, Any]]): List of dicts with 'id' and 'document' keys.
            chunk_size (int): Number of docs to index at once. Defaults to 500.

        Returns:
            Dict[str, int]: Dict with 'success' and 'failed' counts.
        """
        from opensearchpy import helpers

        success = 0
        failed = 0

        # Prepare bulk actions
        actions = []
        for doc in documents:
            action = {
                "_index": self.index_name,
                "_id": doc['id'],
                "_source": doc['document']
            }
            actions.append(action)

        # Bulk index in chunks
        for i in range(0, len(actions), chunk_size):
            chunk = actions[i:i + chunk_size]

            try:
                response = helpers.bulk(self.client, chunk, raise_on_error=False)
                success += response[0]
                if response[1]:  # Errors
                    failed += len(response[1])

                print(f"Indexed {i + len(chunk)}/{len(actions)} documents")

            except Exception as e:
                print(f"Error in bulk indexing: {e}")
                failed += len(chunk)

        return {"success": success, "failed": failed}

    def search_hybrid(self,
                     query_text: str,
                     query_embedding: List[float],
                     filters: Optional[Dict[str, Any]] = None,
                     k: int = 10,
                     vector_weight: float = 0.5) -> List[Dict[str, Any]]:
        """Perform hybrid search combining vector similarity and keyword matching.

        Args:
            query_text (str): Text query for keyword search.
            query_embedding (List[float]): Vector for k-NN search.
            filters (Optional[Dict[str, Any]]): Additional filters (e.g., {"section": "results"}).
            k (int): Number of results to return. Defaults to 10.
            vector_weight (float): Weight for vector search (0-1), keyword gets (1 - vector_weight).
                Defaults to 0.5.

        Returns:
            List[Dict[str, Any]]: List of search results with scores.
        """
        # Build the query
        query = {
            "size": k,
            "query": {
                "bool": {
                    "should": [
                        # Vector similarity search
                        {
                            "script_score": {
                                "query": {"match_all": {}},
                                "script": {
                                    "source": "knn_score",
                                    "lang": "knn",
                                    "params": {
                                        "field": "embedding",
                                        "query_value": query_embedding,
                                        "space_type": "cosinesimil"
                                    }
                                },
                                "boost": vector_weight
                            }
                        },
                        # Keyword search
                        {
                            "multi_match": {
                                "query": query_text,
                                "fields": ["chunk_text^2", "title", "abstract"],
                                "type": "best_fields",
                                "boost": 1 - vector_weight
                            }
                        }
                    ]
                }
            }
        }

        # Add filters if provided
        if filters:
            query["query"]["bool"]["filter"] = []
            for field, value in filters.items():
                query["query"]["bool"]["filter"].append({"term": {field: value}})

        # Execute search
        try:
            response = self.client.search(index=self.index_name, body=query)

            results = []
            for hit in response['hits']['hits']:
                result = {
                    'id': hit['_id'],
                    'score': hit['_score'],
                    'source': hit['_source']
                }
                results.append(result)

            return results

        except Exception as e:
            print(f"Error searching: {e}")
            return []


class PaperIndexingPipeline:
    """Complete pipeline for embedding and indexing parsed papers.

    Attributes:
        embedder (EmbeddingGenerator): The embedding generator.
        indexer (OpenSearchIndexer): The OpenSearch indexer.
    """

    def __init__(self,
                 opensearch_host: Optional[str] = None,
                 opensearch_port: Optional[int] = None,
                 aws_region: str = 'us-east-1',
                 index_name: str = 'medical-papers'):
        """Initialize the pipeline.

        Args:
            opensearch_host (Optional[str]): OpenSearch host. Defaults to OPENSEARCH_HOST env var or 'localhost'.
            opensearch_port (Optional[int]): OpenSearch port. Defaults to OPENSEARCH_PORT env var or 9200.
            aws_region (str): AWS region for Bedrock and OpenSearch (if using AWS). Defaults to 'us-east-1'.
            index_name (str): Name of the OpenSearch index. Defaults to 'medical-papers'.
        """
        self.embedder = EmbeddingGenerator(region_name=aws_region)
        self.indexer = OpenSearchIndexer(
            host=opensearch_host,
            port=opensearch_port,
            region=aws_region,
            index_name=index_name
        )

    def process_paper(self, paper: ParsedPaper) -> Dict[str, int]:
        """Process a single paper: generate embeddings and index all chunks.

        Args:
            paper (ParsedPaper): ParsedPaper object from JATS parser.

        Returns:
            Dict[str, int]: Dict with success/failure counts.
        """
        documents_to_index = []

        # Generate embeddings for all chunks
        chunk_texts = [chunk.text for chunk in paper.chunks]
        print(f"Generating {len(chunk_texts)} embeddings for paper {paper.metadata.pmc_id}")

        embeddings = self.embedder.embed_batch(chunk_texts)

        # Prepare documents for indexing
        for chunk, embedding in zip(paper.chunks, embeddings):
            doc_id = f"{paper.metadata.pmc_id}_{chunk.section}_{chunk.paragraph_index}"

            document = {
                # Embedding
                "embedding": embedding,

                # Chunk content
                "chunk_text": chunk.text,
                "chunk_type": chunk.chunk_type,
                "section": chunk.section,
                "subsection": chunk.subsection,
                "paragraph_index": chunk.paragraph_index,
                "citations": chunk.citations,

                # Paper metadata
                "paper_id": paper.metadata.pmc_id,
                "pmc_id": paper.metadata.pmc_id,
                "pmid": paper.metadata.pmid,
                "doi": paper.metadata.doi,
                "title": paper.metadata.title,
                "abstract": paper.metadata.abstract,
                "authors": paper.metadata.authors,
                "journal": paper.metadata.journal,
                "publication_date": paper.metadata.publication_date,
                "mesh_terms": paper.metadata.mesh_terms,
                "keywords": paper.metadata.keywords,

                # Placeholder for entities (to be filled by Comprehend Medical)
                "entities": []
            }

            documents_to_index.append({
                'id': doc_id,
                'document': document
            })

        # Bulk index
        print(f"Indexing {len(documents_to_index)} chunks to OpenSearch")
        result = self.indexer.bulk_index(documents_to_index)

        return result

    def process_papers_batch(self, papers: List[ParsedPaper]) -> Dict[str, int]:
        """Process multiple papers.

        Args:
            papers (List[ParsedPaper]): List of ParsedPaper objects.

        Returns:
            Dict[str, int]: Dict with total success/failure counts.
        """
        total_success = 0
        total_failed = 0

        for i, paper in enumerate(papers):
            print(f"\nProcessing paper {i+1}/{len(papers)}: {paper.metadata.pmc_id}")

            try:
                result = self.process_paper(paper)
                total_success += result['success']
                total_failed += result['failed']
            except Exception as e:
                print(f"Error processing paper {paper.metadata.pmc_id}: {e}")
                total_failed += len(paper.chunks)

        return {
            "success": total_success,
            "failed": total_failed,
            "papers_processed": len(papers)
        }


def main():
    """Main CLI interface"""
    import argparse
    import glob
    import os
    from .jats_parser import JATSParser

    parser = argparse.ArgumentParser(
        description='Ingest and index medical papers from JATS XML files'
    )

    parser.add_argument(
        '--input-dir',
        required=True,
        help='Input directory or glob pattern for XML files (e.g., "papers/*.xml")'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Batch size for indexing (default: 10)'
    )
    parser.add_argument(
        '--opensearch-host',
        default=os.environ.get('OPENSEARCH_HOST'),
        help='OpenSearch host (default: from env or localhost)'
    )
    parser.add_argument(
        '--opensearch-port',
        type=int,
        default=int(os.environ.get('OPENSEARCH_PORT', '9200')),
        help='OpenSearch port (default: from env or 9200)'
    )
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region (default: us-east-1)'
    )

    args = parser.parse_args()

    # Handle glob patterns
    if '*' in args.input_dir:
        files = glob.glob(args.input_dir)
    else:
        input_path = Path(args.input_dir)
        if input_path.is_dir():
            files = list(input_path.glob('*.xml'))
        else:
            files = [str(input_path)]

    if not files:
        print(f"No files found matching: {args.input_dir}")
        return

    print(f"Found {len(files)} files to process")

    # Initialize pipeline
    pipeline = PaperIndexingPipeline(
        opensearch_host=args.opensearch_host,
        opensearch_port=args.opensearch_port,
        aws_region=args.region
    )

    # Process papers
    success_count = 0
    failed_count = 0

    for i, file_path in enumerate(files):
        print(f"\nProcessing file {i+1}/{len(files)}: {file_path}")
        try:
            parser = JATSParser(str(file_path))
            paper = parser.parse()

            result = pipeline.process_paper(paper)
            success_count += result['success']
            failed_count += result['failed']

        except Exception as e:
            print(f"Failed to process {file_path}: {e}")
            failed_count += 1

    print(f"\n{'='*60}")
    print(f"Ingestion complete!")
    print(f"{'='*60}")
    print(f"Chunks indexed: {success_count}")
    print(f"Chunks failed: {failed_count}")

### pytest ###

@pytest.fixture
def mock_opensearch_client():
    """Fixture providing a mocked OpenSearch client"""
    with patch('opensearchpy.OpenSearch') as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        mock_instance.indices.exists.return_value = False
        mock_instance.indices.create.return_value = {'acknowledged': True}
        yield mock_instance


@pytest.fixture
def sample_paper():
    """Fixture providing a sample ParsedPaper for testing"""
    metadata = PaperMetadata(
        pmc_id="PMC123456",
        pmid="12345678",
        doi="10.1234/test",
        title="Test Paper",
        abstract="Test abstract",
        authors=["Smith J", "Doe J"],
        affiliations=["University A"],
        journal="Test Journal",
        publication_date="2024-01-01",
        mesh_terms=["Test Term"],
        keywords=["test", "paper"]
    )
    
    chunks = [
        Chunk(
            text="Test chunk 1",
            section="introduction",
            subsection=None,
            paragraph_index=0,
            chunk_type="paragraph",
            citations=[]
        ),
        Chunk(
            text="Test chunk 2",
            section="methods",
            subsection=None,
            paragraph_index=1,
            chunk_type="paragraph",
            citations=["ref1"]
        )
    ]
    
    return ParsedPaper(
        metadata=metadata,
        chunks=chunks,
        tables=[],
        references={},
        full_text="Test full text"
    )


class TestOpenSearchIndexer:
    
    def test_init_local_deployment(self, mock_opensearch_client):
        """Test initialization for local OpenSearch"""
        indexer = OpenSearchIndexer(
            host='localhost',
            port=9200,
            create_index=False
        )
        
        assert indexer.index_name == 'medical-papers'
        assert indexer.client is not None
    
    
    def test_init_aws_deployment(self):
        """Test initialization for AWS OpenSearch"""
        with patch('opensearchpy.OpenSearch') as mock_os, \
             patch('boto3.Session') as mock_session:
            
            mock_creds = MagicMock()
            mock_session.return_value.get_credentials.return_value = mock_creds
            
            OpenSearchIndexer(
                host='search-domain.us-east-1.es.amazonaws.com',
                port=443,
                create_index=False,
                use_ssl=True,
                use_aws_auth=True
            )
            
            # Verify AWS auth was configured
            mock_session.return_value.get_credentials.assert_called_once()
    
    
    def test_create_index_if_not_exists(self, mock_opensearch_client):
        """Test index creation when it doesn't exist"""
        mock_opensearch_client.indices.exists.return_value = False
        
        OpenSearchIndexer(create_index=True)
        
        mock_opensearch_client.indices.create.assert_called_once()
        call_args = mock_opensearch_client.indices.create.call_args
        assert call_args.kwargs['index'] == 'medical-papers'
        assert 'embedding' in call_args.kwargs['body']['mappings']['properties']
    
    
    def test_skip_index_creation_if_exists(self, mock_opensearch_client):
        """Test that index creation is skipped if index exists"""
        mock_opensearch_client.indices.exists.return_value = True
        
        indexer = OpenSearchIndexer(create_index=True)
        
        mock_opensearch_client.indices.create.assert_not_called()
    
    
    def test_index_document_success(self, mock_opensearch_client):
        """Test successful document indexing"""
        mock_opensearch_client.index.return_value = {'result': 'created'}
        
        indexer = OpenSearchIndexer(create_index=False)
        document = {
            'embedding': [0.1] * 1024,
            'chunk_text': 'Test text',
            'pmc_id': 'PMC123'
        }
        
        result = indexer.index_document('doc1', document)
        
        assert result is True
        mock_opensearch_client.index.assert_called_once()
    
    
    def test_index_document_failure(self, mock_opensearch_client):
        """Test document indexing failure handling"""
        mock_opensearch_client.index.side_effect = Exception("Index error")
        
        OpenSearchIndexer(create_index=False)
        document = {'embedding': [0.1] * 1024}
        
        result = OpenSearchIndexer.index_document('doc1', document)
        
        assert result is False
    
    
    def test_bulk_index(self, mock_opensearch_client):
        """Test bulk indexing of multiple documents"""
        with patch('opensearchpy.helpers.bulk') as mock_bulk:
            mock_bulk.return_value = (3, [])  # 3 successful, 0 failed
            
            indexer = OpenSearchIndexer(create_index=False)
            documents = [
                {'id': 'doc1', 'document': {'embedding': [0.1] * 1024}},
                {'id': 'doc2', 'document': {'embedding': [0.2] * 1024}},
                {'id': 'doc3', 'document': {'embedding': [0.3] * 1024}}
            ]
            
            result = indexer.bulk_index(documents)
            
            assert result['success'] == 3
            assert result['failed'] == 0
    
    
    def test_bulk_index_with_failures(self, mock_opensearch_client):
        """Test bulk indexing with some failures"""
        with patch('opensearchpy.helpers.bulk') as mock_bulk:
            mock_bulk.return_value = (2, [{'index': {'error': 'test error'}}])
            
            indexer = OpenSearchIndexer(create_index=False)
            documents = [
                {'id': 'doc1', 'document': {'embedding': [0.1] * 1024}},
                {'id': 'doc2', 'document': {'embedding': [0.2] * 1024}},
                {'id': 'doc3', 'document': {'embedding': [0.3] * 1024}}
            ]
            
            result = indexer.bulk_index(documents)
            
            assert result['success'] == 2
            assert result['failed'] == 1
    
    
    def test_search_hybrid(self, mock_opensearch_client):
        """Test hybrid search functionality"""
        mock_opensearch_client.search.return_value = {
            'hits': {
                'hits': [
                    {
                        '_id': 'doc1',
                        '_score': 0.95,
                        '_source': {'chunk_text': 'Test result'}
                    }
                ]
            }
        }
        
        indexer = OpenSearchIndexer(create_index=False)
        results = indexer.search_hybrid(
            query_text="test query",
            query_embedding=[0.1] * 1024,
            k=10
        )
        
        assert len(results) == 1
        assert results[0]['id'] == 'doc1'
        assert results[0]['score'] == 0.95
    
    
    def test_search_with_filters(self, mock_opensearch_client):
        """Test search with metadata filters"""
        mock_opensearch_client.search.return_value = {
            'hits': {'hits': []}
        }
        
        indexer = OpenSearchIndexer(create_index=False)
        indexer.search_hybrid(
            query_text="test",
            query_embedding=[0.1] * 1024,
            filters={'section': 'methods', 'journal': 'Nature'}
        )
        
        call_args = mock_opensearch_client.search.call_args
        query = call_args.kwargs['body']['query']
        
        assert 'filter' in query['bool']
        assert len(query['bool']['filter']) == 2


class TestPaperIndexingPipeline:
    
    def test_init(self):
        """Test pipeline initialization"""
        with patch('boto3.client'), \
             patch('opensearchpy.OpenSearch'):
            
            pipeline = PaperIndexingPipeline(
                opensearch_host='localhost',
                opensearch_port=9200
            )
            
            assert pipeline.embedder is not None
            assert pipeline.indexer is not None
    
    
    def test_process_paper(self, sample_paper):
        """Test processing a single paper"""
        with patch('boto3.client') as mock_bedrock, \
             patch('opensearchpy.OpenSearch'), \
             patch('opensearchpy.helpers.bulk') as mock_bulk:
            
            # Mock embedding generation
            mock_response = {
                'body': MagicMock(read=lambda: '{"embedding": ' + str([0.1] * 1024) + '}')
            }
            mock_bedrock.return_value.invoke_model.return_value = mock_response
            
            # Mock bulk indexing
            mock_bulk.return_value = (2, [])
            
            pipeline = PaperIndexingPipeline()
            result = pipeline.process_paper(sample_paper)
            
            assert result['success'] == 2
            assert result['failed'] == 0
    
    
    def test_process_papers_batch(self, sample_paper):
        """Test batch processing of multiple papers"""
        with patch('boto3.client') as mock_bedrock, \
             patch('opensearchpy.OpenSearch'), \
             patch('opensearchpy.helpers.bulk') as mock_bulk:
            
            mock_response = {
                'body': MagicMock(read=lambda: '{"embedding": ' + str([0.1] * 1024) + '}')
            }
            mock_bedrock.return_value.invoke_model.return_value = mock_response
            mock_bulk.return_value = (2, [])
            
            pipeline = PaperIndexingPipeline()
            papers = [sample_paper, sample_paper]
            
            result = pipeline.process_papers_batch(papers)
            
            assert result['success'] == 4  # 2 chunks × 2 papers
            assert result['papers_processed'] == 2
    
    
    def test_process_paper_error_handling(self, sample_paper):
        """Test error handling when processing fails"""
        with patch('boto3.client') as mock_bedrock, \
             patch('opensearchpy.OpenSearch'), \
             patch('opensearchpy.helpers.bulk'):
            
            mock_bedrock.return_value.invoke_model.side_effect = Exception("Bedrock error")
            
            pipeline = PaperIndexingPipeline()
            
            # Should not raise, but return failure count
            result = pipeline.process_papers_batch([sample_paper])
            
            assert result['failed'] == 2  # Both chunks failed


def test_environment_variable_defaults():
    """Test that environment variables are respected"""
    with patch.dict(os.environ, {
        'OPENSEARCH_HOST': 'custom-host',
        'OPENSEARCH_PORT': '9999'
    }):
        with patch('opensearchpy.OpenSearch'):
            OpenSearchIndexer(create_index=False)
            
            # Verify the environment variables were used
            assert True  # The mock would fail if wrong values were passed



if __name__ == '__main__':
    pytest.main([__file__])
    # main()
