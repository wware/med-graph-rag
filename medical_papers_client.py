"""
Medical Papers Client

Client library for querying the medical papers knowledge base from your laptop.
Provides convenient methods for search, exploration, and analysis.
"""

import boto3
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from datetime import datetime
import pandas as pd


@dataclass
class SearchResult:
    """Structured search result"""
    score: float
    pmc_id: str
    pmid: Optional[str]
    title: str
    section: str
    chunk_text: str
    authors: List[str]
    journal: str
    publication_date: str
    citations: List[str]
    mesh_terms: List[str]
    subsection: Optional[str] = None
    doi: Optional[str] = None
    
    def __str__(self) -> str:
        """Pretty print a result"""
        return f"""
Score: {self.score:.3f}
Paper: {self.title}
Authors: {', '.join(self.authors[:3])}{'...' if len(self.authors) > 3 else ''}
Journal: {self.journal} ({self.publication_date})
Section: {self.section}{f'.{self.subsection}' if self.subsection else ''}
PMC: {self.pmc_id} | PMID: {self.pmid or 'N/A'}

Text:
{self.chunk_text[:500]}{'...' if len(self.chunk_text) > 500 else ''}
"""


class MedicalPapersClient:
    """Client for querying medical papers knowledge base"""
    
    def __init__(self,
                 opensearch_host: str,
                 aws_region: str = 'us-east-1',
                 index_name: str = 'medical-papers',
                 aws_profile: Optional[str] = None):
        """
        Initialize client
        
        Args:
            opensearch_host: OpenSearch domain endpoint (without https://)
            aws_region: AWS region
            index_name: Name of the index
            aws_profile: AWS profile name (if using multiple profiles)
        """
        # Set up AWS session
        session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
        credentials = session.get_credentials()
        auth = AWSV4SignerAuth(credentials, aws_region, 'es')
        
        # OpenSearch client
        self.client = OpenSearch(
            hosts=[{'host': opensearch_host, 'port': 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=60
        )
        
        self.index_name = index_name
        
        # Bedrock client for generating query embeddings
        self.bedrock = session.client('bedrock-runtime', region_name=aws_region)
        self.model_id = 'amazon.titan-embed-text-v2:0'
    
    def _generate_query_embedding(self, text: str) -> List[float]:
        """Generate embedding for a query"""
        request_body = {
            "inputText": text,
            "dimensions": 1024,
            "normalize": True
        }
        
        response = self.bedrock.invoke_model(
            modelId=self.model_id,
            contentType='application/json',
            accept='application/json',
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['embedding']
    
    def search(self,
               query: str,
               k: int = 10,
               search_type: str = 'hybrid',
               vector_weight: float = 0.5,
               filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        Search for papers
        
        Args:
            query: Search query (natural language)
            k: Number of results to return
            search_type: 'hybrid', 'vector', or 'keyword'
            vector_weight: Weight for vector search (0-1), only for hybrid
            filters: Additional filters (e.g., {'section': 'results', 'year': 2023})
            
        Returns:
            List of SearchResult objects
        """
        # Generate query embedding
        query_embedding = self._generate_query_embedding(query)
        
        # Build query based on search type
        if search_type == 'vector':
            search_query = self._build_vector_query(query_embedding, k)
        elif search_type == 'keyword':
            search_query = self._build_keyword_query(query, k)
        else:  # hybrid
            search_query = self._build_hybrid_query(query, query_embedding, k, vector_weight)
        
        # Add filters
        if filters:
            search_query = self._add_filters(search_query, filters)
        
        # Execute search
        response = self.client.search(index=self.index_name, body=search_query)
        
        # Parse results
        results = []
        for hit in response['hits']['hits']:
            source = hit['_source']
            result = SearchResult(
                score=hit['_score'],
                pmc_id=source.get('pmc_id', ''),
                pmid=source.get('pmid'),
                title=source.get('title', ''),
                section=source.get('section', ''),
                subsection=source.get('subsection'),
                chunk_text=source.get('chunk_text', ''),
                authors=source.get('authors', []),
                journal=source.get('journal', ''),
                publication_date=source.get('publication_date', ''),
                doi=source.get('doi'),
                citations=source.get('citations', []),
                mesh_terms=source.get('mesh_terms', [])
            )
            results.append(result)
        
        return results
    
    def _build_vector_query(self, embedding: List[float], k: int) -> Dict:
        """Build pure vector similarity query"""
        return {
            "size": k,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": embedding,
                        "k": k
                    }
                }
            }
        }
    
    def _build_keyword_query(self, query: str, k: int) -> Dict:
        """Build pure keyword query"""
        return {
            "size": k,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["chunk_text^2", "title", "abstract"],
                    "type": "best_fields"
                }
            }
        }
    
    def _build_hybrid_query(self, query: str, embedding: List[float], 
                           k: int, vector_weight: float) -> Dict:
        """Build hybrid vector + keyword query"""
        return {
            "size": k,
            "query": {
                "bool": {
                    "should": [
                        {
                            "script_score": {
                                "query": {"match_all": {}},
                                "script": {
                                    "source": "knn_score",
                                    "lang": "knn",
                                    "params": {
                                        "field": "embedding",
                                        "query_value": embedding,
                                        "space_type": "cosinesimil"
                                    }
                                },
                                "boost": vector_weight
                            }
                        },
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["chunk_text^2", "title", "abstract"],
                                "type": "best_fields",
                                "boost": 1 - vector_weight
                            }
                        }
                    ]
                }
            }
        }
    
    def _add_filters(self, query: Dict, filters: Dict[str, Any]) -> Dict:
        """Add filters to a query"""
        if "query" not in query:
            query["query"] = {"bool": {}}
        
        if "bool" not in query["query"]:
            original_query = query["query"]
            query["query"] = {"bool": {"must": [original_query]}}
        
        if "filter" not in query["query"]["bool"]:
            query["query"]["bool"]["filter"] = []
        
        for field, value in filters.items():
            if isinstance(value, list):
                query["query"]["bool"]["filter"].append({"terms": {field: value}})
            else:
                query["query"]["bool"]["filter"].append({"term": {field: value}})
        
        return query
    
    def find_papers_by_id(self, pmc_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get all chunks from specific papers
        
        Args:
            pmc_ids: List of PMC IDs
            
        Returns:
            List of all chunks from those papers
        """
        query = {
            "size": 1000,  # Adjust based on expected paper size
            "query": {
                "terms": {
                    "pmc_id": pmc_ids
                }
            },
            "sort": [
                {"pmc_id": "asc"},
                {"paragraph_index": "asc"}
            ]
        }
        
        response = self.client.search(index=self.index_name, body=query)
        return [hit['_source'] for hit in response['hits']['hits']]
    
    def get_related_papers(self, pmc_id: str, k: int = 10) -> List[SearchResult]:
        """
        Find papers similar to a given paper
        
        Args:
            pmc_id: PMC ID of the reference paper
            k: Number of similar papers to return
            
        Returns:
            List of similar papers
        """
        # Get the abstract or first few chunks of the paper
        query = {
            "size": 1,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"pmc_id": pmc_id}},
                        {"term": {"chunk_type": "abstract"}}
                    ]
                }
            }
        }
        
        response = self.client.search(index=self.index_name, body=query)
        
        if not response['hits']['hits']:
            print(f"Paper {pmc_id} not found")
            return []
        
        # Get the embedding of the abstract
        abstract_embedding = response['hits']['hits'][0]['_source']['embedding']
        
        # Find similar papers by vector similarity
        similar_query = {
            "size": k + 10,  # Get extra to filter out the same paper
            "query": {
                "knn": {
                    "embedding": {
                        "vector": abstract_embedding,
                        "k": k + 10
                    }
                }
            }
        }
        
        response = self.client.search(index=self.index_name, body=similar_query)
        
        # Parse and filter out the original paper
        results = []
        for hit in response['hits']['hits']:
            source = hit['_source']
            if source['pmc_id'] != pmc_id:
                result = SearchResult(
                    score=hit['_score'],
                    pmc_id=source['pmc_id'],
                    pmid=source.get('pmid'),
                    title=source['title'],
                    section=source['section'],
                    subsection=source.get('subsection'),
                    chunk_text=source['chunk_text'],
                    authors=source['authors'],
                    journal=source['journal'],
                    publication_date=source['publication_date'],
                    doi=source.get('doi'),
                    citations=source['citations'],
                    mesh_terms=source['mesh_terms']
                )
                results.append(result)
                
                if len(results) >= k:
                    break
        
        return results
    
    def aggregate_by_journal(self, query: str, top_n: int = 10) -> pd.DataFrame:
        """
        Search and aggregate results by journal
        
        Args:
            query: Search query
            top_n: Number of top journals to return
            
        Returns:
            DataFrame with journal counts
        """
        search_query = {
            "size": 0,  # We only want aggregations
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["chunk_text", "title", "abstract"]
                }
            },
            "aggs": {
                "journals": {
                    "terms": {
                        "field": "journal",
                        "size": top_n
                    }
                }
            }
        }
        
        response = self.client.search(index=self.index_name, body=search_query)
        
        buckets = response['aggregations']['journals']['buckets']
        
        df = pd.DataFrame([
            {'journal': b['key'], 'count': b['doc_count']}
            for b in buckets
        ])
        
        return df
    
    def aggregate_by_year(self, query: str) -> pd.DataFrame:
        """
        Search and aggregate results by publication year
        
        Args:
            query: Search query
            
        Returns:
            DataFrame with year counts
        """
        search_query = {
            "size": 0,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["chunk_text", "title", "abstract"]
                }
            },
            "aggs": {
                "years": {
                    "date_histogram": {
                        "field": "publication_date",
                        "calendar_interval": "year",
                        "format": "yyyy",
                        "order": {"_key": "desc"}
                    }
                }
            }
        }
        
        response = self.client.search(index=self.index_name, body=search_query)
        
        buckets = response['aggregations']['years']['buckets']
        
        df = pd.DataFrame([
            {'year': b['key_as_string'], 'count': b['doc_count']}
            for b in buckets
        ])
        
        return df
    
    def get_citation_context(self, pmc_id: str, cited_pmc_id: str) -> List[str]:
        """
        Find contexts where one paper cites another
        
        Args:
            pmc_id: The citing paper
            cited_pmc_id: The cited paper
            
        Returns:
            List of text chunks where the citation appears
        """
        # Note: This assumes citations array contains PMC IDs
        # Adjust based on your actual citation format
        query = {
            "size": 100,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"pmc_id": pmc_id}},
                        {"term": {"citations": cited_pmc_id}}
                    ]
                }
            }
        }
        
        response = self.client.search(index=self.index_name, body=query)
        
        contexts = []
        for hit in response['hits']['hits']:
            source = hit['_source']
            contexts.append(f"[{source['section']}] {source['chunk_text']}")
        
        return contexts
    
    def export_results_to_csv(self, results: List[SearchResult], filename: str):
        """Export search results to CSV for further analysis"""
        df = pd.DataFrame([asdict(r) for r in results])
        df.to_csv(filename, index=False)
        print(f"Exported {len(results)} results to {filename}")
    
    def get_corpus_stats(self) -> Dict[str, Any]:
        """Get statistics about the indexed corpus"""
        # Total documents
        count_query = {"query": {"match_all": {}}}
        total_docs = self.client.count(index=self.index_name, body=count_query)['count']
        
        # Unique papers
        unique_papers_query = {
            "size": 0,
            "aggs": {
                "unique_papers": {
                    "cardinality": {
                        "field": "pmc_id"
                    }
                }
            }
        }
        response = self.client.search(index=self.index_name, body=unique_papers_query)
        unique_papers = response['aggregations']['unique_papers']['value']
        
        # Date range
        date_range_query = {
            "size": 0,
            "aggs": {
                "earliest": {"min": {"field": "publication_date"}},
                "latest": {"max": {"field": "publication_date"}}
            }
        }
        response = self.client.search(index=self.index_name, body=date_range_query)
        
        return {
            "total_chunks": total_docs,
            "unique_papers": unique_papers,
            "avg_chunks_per_paper": total_docs / unique_papers if unique_papers > 0 else 0,
            "earliest_paper": response['aggregations']['earliest']['value_as_string'],
            "latest_paper": response['aggregations']['latest']['value_as_string']
        }


def example_usage():
    """Example usage from your laptop"""
    
    # Initialize client
    client = MedicalPapersClient(
        opensearch_host="your-domain.us-east-1.es.amazonaws.com",
        aws_region="us-east-1",
        aws_profile="default"  # or None if using default
    )
    
    # Example 1: Basic search
    print("=" * 60)
    print("Basic Search")
    print("=" * 60)
    
    results = client.search(
        query="BRCA1 mutations and breast cancer risk",
        k=5,
        search_type='hybrid'
    )
    
    for i, result in enumerate(results, 1):
        print(f"\n--- Result {i} ---")
        print(result)
    
    # Example 2: Filtered search
    print("\n" + "=" * 60)
    print("Filtered Search - Results section only")
    print("=" * 60)
    
    results = client.search(
        query="treatment outcomes",
        k=5,
        filters={'section': 'results'}
    )
    
    for result in results:
        print(f"\n{result.title}")
        print(f"Section: {result.section}")
        print(f"Preview: {result.chunk_text[:200]}...")
    
    # Example 3: Find related papers
    print("\n" + "=" * 60)
    print("Related Papers")
    print("=" * 60)
    
    related = client.get_related_papers(
        pmc_id="123456",  # Replace with actual PMC ID
        k=5
    )
    
    print(f"Papers similar to PMC123456:")
    for paper in related:
        print(f"- {paper.title} ({paper.journal}, {paper.publication_date})")
    
    # Example 4: Aggregations
    print("\n" + "=" * 60)
    print("Top Journals for Topic")
    print("=" * 60)
    
    journal_df = client.aggregate_by_journal(
        query="immunotherapy",
        top_n=10
    )
    print(journal_df)
    
    # Example 5: Export results
    results = client.search(query="diabetes treatment", k=100)
    client.export_results_to_csv(results, "diabetes_papers.csv")
    
    # Example 6: Corpus statistics
    print("\n" + "=" * 60)
    print("Corpus Statistics")
    print("=" * 60)
    
    stats = client.get_corpus_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == '__main__':
    example_usage()
