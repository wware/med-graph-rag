"""
Embedding and Indexing Pipeline for Medical Research Papers

Takes parsed JATS papers, generates embeddings using AWS Bedrock Titan Embeddings V2,
and indexes them to Amazon OpenSearch Service for hybrid vector + keyword search.
"""

import boto3
import json
from typing import List, Dict, Any, Optional
from dataclasses import asdict
import time
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from jats_parser import ParsedPaper, Chunk


class EmbeddingGenerator:
    """Generate embeddings using AWS Bedrock Titan Embeddings V2"""
    
    def __init__(self, region_name: str = 'us-east-1'):
        """Initialize Bedrock client"""
        self.bedrock = boto3.client(
            service_name='bedrock-runtime',
            region_name=region_name
        )
        self.model_id = 'amazon.titan-embed-text-v2:0'
        
    def embed_text(self, text: str, input_type: str = 'search_document') -> List[float]:
        """
        Generate embedding for a single text string
        
        Args:
            text: Text to embed (max ~8000 tokens)
            input_type: 'search_document' for indexing, 'search_query' for queries
            
        Returns:
            List of floats representing the embedding vector (1024 dimensions)
        """
        # Truncate if too long (Titan v2 max is ~8000 tokens, roughly 30k chars)
        if len(text) > 30000:
            text = text[:30000]
        
        request_body = {
            "inputText": text,
            "dimensions": 1024,
            "normalize": True
        }
        
        try:
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                contentType='application/json',
                accept='application/json',
                body=json.dumps(request_body)
            )
            
            response_body = json.loads(response['body'].read())
            return response_body['embedding']
            
        except Exception as e:
            print(f"Error generating embedding: {e}")
            raise
    
    def embed_batch(self, texts: List[str], input_type: str = 'search_document',
                   batch_size: int = 10, delay: float = 0.1) -> List[List[float]]:
        """
        Generate embeddings for multiple texts with rate limiting
        
        Args:
            texts: List of texts to embed
            input_type: 'search_document' for indexing, 'search_query' for queries
            batch_size: Process this many at once before delay
            delay: Seconds to wait between batches
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            for text in batch:
                embedding = self.embed_text(text, input_type)
                embeddings.append(embedding)
            
            # Rate limiting
            if i + batch_size < len(texts):
                time.sleep(delay)
            
            if (i + batch_size) % 100 == 0:
                print(f"Processed {i + batch_size}/{len(texts)} embeddings")
        
        return embeddings


class OpenSearchIndexer:
    """Index documents with embeddings to Amazon OpenSearch"""
    
    def __init__(self, 
                 host: str,
                 region: str = 'us-east-1',
                 index_name: str = 'medical-papers',
                 create_index: bool = True):
        """
        Initialize OpenSearch client
        
        Args:
            host: OpenSearch domain endpoint (without https://)
            region: AWS region
            index_name: Name of the index to use
            create_index: Whether to create index if it doesn't exist
        """
        # Set up AWS authentication
        credentials = boto3.Session().get_credentials()
        auth = AWSV4SignerAuth(credentials, region, 'es')
        
        self.client = OpenSearch(
            hosts=[{'host': host, 'port': 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=60
        )
        
        self.index_name = index_name
        
        if create_index:
            self._create_index_if_not_exists()
    
    def _create_index_if_not_exists(self):
        """Create the index with appropriate mappings if it doesn't exist"""
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
        """
        Index a single document
        
        Args:
            doc_id: Unique document ID
            document: Document to index (must include 'embedding' field)
            
        Returns:
            True if successful
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
        """
        Bulk index multiple documents
        
        Args:
            documents: List of dicts with 'id' and 'document' keys
            chunk_size: Number of docs to index at once
            
        Returns:
            Dict with 'success' and 'failed' counts
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
        """
        Perform hybrid search combining vector similarity and keyword matching
        
        Args:
            query_text: Text query for keyword search
            query_embedding: Vector for k-NN search
            filters: Additional filters (e.g., {"section": "results"})
            k: Number of results to return
            vector_weight: Weight for vector search (0-1), keyword gets (1 - vector_weight)
            
        Returns:
            List of search results with scores
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
    """Complete pipeline for embedding and indexing parsed papers"""
    
    def __init__(self, 
                 opensearch_host: str,
                 aws_region: str = 'us-east-1',
                 index_name: str = 'medical-papers'):
        """Initialize the pipeline"""
        self.embedder = EmbeddingGenerator(region_name=aws_region)
        self.indexer = OpenSearchIndexer(
            host=opensearch_host,
            region=aws_region,
            index_name=index_name
        )
    
    def process_paper(self, paper: ParsedPaper) -> Dict[str, int]:
        """
        Process a single paper: generate embeddings and index all chunks
        
        Args:
            paper: ParsedPaper object from JATS parser
            
        Returns:
            Dict with success/failure counts
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
        """
        Process multiple papers
        
        Args:
            papers: List of ParsedPaper objects
            
        Returns:
            Dict with total success/failure counts
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


def example_usage():
    """Example of how to use the pipeline"""
    from jats_parser import JATSParser
    
    # Configuration
    OPENSEARCH_HOST = "your-domain.us-east-1.es.amazonaws.com"
    AWS_REGION = "us-east-1"
    
    # Initialize pipeline
    pipeline = PaperIndexingPipeline(
        opensearch_host=OPENSEARCH_HOST,
        aws_region=AWS_REGION
    )
    
    # Parse and process a paper
    parser = JATSParser('path/to/paper.xml')
    paper = parser.parse()
    
    result = pipeline.process_paper(paper)
    print(f"Indexed {result['success']} chunks, {result['failed']} failed")
    
    # Example: Search the index
    query = "BRCA1 mutations and breast cancer risk"
    query_embedding = pipeline.embedder.embed_text(query, input_type='search_query')
    
    results = pipeline.indexer.search_hybrid(
        query_text=query,
        query_embedding=query_embedding,
        filters={"section": "results"},
        k=5
    )
    
    print(f"\nSearch results for: {query}")
    for i, result in enumerate(results):
        print(f"\n{i+1}. Score: {result['score']:.3f}")
        print(f"   Paper: {result['source']['title']}")
        print(f"   Section: {result['source']['section']}")
        print(f"   Text: {result['source']['chunk_text'][:200]}...")


if __name__ == '__main__':
    example_usage()
