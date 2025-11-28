# Medical Knowledge Graph - Data Flow Architecture

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER INTERACTIONS                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐         ┌──────────────┐        ┌──────────────┐    │
│  │   Doctor's   │         │   Research   │        │  Web/Mobile  │    │
│  │   Laptop     │────────▶│  Interface   │◀───────│     App      │    │
│  │  (Client)    │         │  (FastAPI)   │        │              │    │
│  └──────────────┘         └──────┬───────┘        └──────────────┘    │
│                                   │                                     │
└───────────────────────────────────┼─────────────────────────────────────┘
                                    │
                    ┌───────────────┴────────────────┐
                    │   Application Load Balancer    │
                    │         (Port 443)             │
                    └───────────────┬────────────────┘
                                    │
┌───────────────────────────────────┼─────────────────────────────────────┐
│                         QUERY PROCESSING LAYER                           │
├───────────────────────────────────┼─────────────────────────────────────┤
│                                   │                                      │
│                    ┌──────────────▼──────────────┐                     │
│                    │   ECS Fargate Service       │                     │
│                    │   (Query API Container)     │                     │
│                    │   - FastAPI App             │                     │
│                    │   - Query Generator         │                     │
│                    │   - Result Aggregator       │                     │
│                    └──┬─────────────────┬────────┘                     │
│                       │                 │                               │
│                       │                 │                               │
│         ┌─────────────▼─────┐   ┌──────▼────────────┐                 │
│         │   AWS Bedrock     │   │   AWS Bedrock     │                 │
│         │   Claude 3.5      │   │   Titan Embed V2  │                 │
│         │   (NL→Query)      │   │   (Query Embed)   │                 │
│         └─────────┬─────────┘   └──────┬────────────┘                 │
│                   │                     │                               │
└───────────────────┼─────────────────────┼───────────────────────────────┘
                    │                     │
        ┌───────────▼─────────────────────▼───────────┐
        │         QUERY EXECUTION LAYER                │
        ├──────────────────────────────────────────────┤
        │                                              │
        │  ┌──────────────────┐  ┌─────────────────┐ │
        │  │   OpenSearch     │  │   Neptune       │ │
        │  │   - Vector KNN   │  │   - Gremlin/    │ │
        │  │   - Hybrid       │  │     SPARQL      │ │
        │  │   - Aggregations │  │   - Graph Trav. │ │
        │  └────────┬─────────┘  └────────┬────────┘ │
        │           │                     │          │
        └───────────┼─────────────────────┼──────────┘
                    │                     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Results Synthesis  │
                    │  & Formatting       │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Return to User    │
                    └─────────────────────┘


═══════════════════════════════════════════════════════════════════════════
                           INGESTION PIPELINE
═══════════════════════════════════════════════════════════════════════════

┌──────────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCE LAYER                                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌────────────────┐         ┌────────────────┐      ┌─────────────────┐│
│  │  PubMed Central│         │  Manual Upload │      │  Bulk Download  ││
│  │  API (E-utils) │         │  (Web UI)      │      │  (FTP Archive)  ││
│  └────────┬───────┘         └────────┬───────┘      └────────┬────────┘│
│           │                          │                       │          │
│           └──────────────────────────┼───────────────────────┘          │
│                                      │                                   │
└──────────────────────────────────────┼───────────────────────────────────┘
                                       │
                                       │ JATS XML Files
                                       │
                        ┌──────────────▼──────────────┐
                        │      S3 Bucket              │
                        │   medical-kg-papers/raw/    │
                        └──────────────┬──────────────┘
                                       │
                                       │ S3 Event Notification
                                       │
┌──────────────────────────────────────┼───────────────────────────────────┐
│                      PROCESSING LAYER                                     │
├──────────────────────────────────────┼───────────────────────────────────┤
│                                      │                                    │
│              ┌───────────────────────▼────────────────────┐              │
│              │  Lambda: Paper Ingestion Trigger           │              │
│              │  - Validates XML                           │              │
│              │  - Triggers ECS task for processing        │              │
│              └───────────────────┬────────────────────────┘              │
│                                  │                                        │
│                                  │ Start ECS Task                         │
│                                  │                                        │
│              ┌───────────────────▼────────────────────────┐              │
│              │  ECS Fargate Task: Ingestion Pipeline      │              │
│              │  ┌──────────────────────────────────────┐  │              │
│              │  │ 1. JATS Parser                       │  │              │
│              │  │    - Extract structure               │  │              │
│              │  │    - Parse metadata                  │  │              │
│              │  │    - Create chunks                   │  │              │
│              │  └──────────────┬───────────────────────┘  │              │
│              │                 │                           │              │
│              │  ┌──────────────▼───────────────────────┐  │              │
│              │  │ 2. Entity Extractor                  │  │              │
│              │  │    - Medical NER                     │  │              │
│              │  │    - Entity linking (UMLS)           │  │              │
│              │  │    - Normalize to canonical IDs      │  │              │
│              │  └──────────────┬───────────────────────┘  │              │
│              │                 │                           │              │
│              │  ┌──────────────▼───────────────────────┐  │              │
│              │  │ 3. Relationship Extractor            │  │              │
│              │  │    - Pattern matching                │  │              │
│              │  │    - Co-occurrence analysis          │  │              │
│              │  │    - Confidence scoring              │  │              │
│              │  └──────────────┬───────────────────────┘  │              │
│              │                 │                           │              │
│              │  ┌──────────────▼───────────────────────┐  │              │
│              │  │ 4. Embedding Generator               │  │              │
│              │  │    - Call Bedrock Titan              │  │              │
│              │  │    - Generate chunk embeddings       │  │              │
│              │  │    - Batch processing                │  │              │
│              │  └──────────────┬───────────────────────┘  │              │
│              │                 │                           │              │
│              └─────────────────┼───────────────────────────┘              │
│                                │                                          │
└────────────────────────────────┼──────────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
         ┌──────────▼──────────┐   ┌─────────▼──────────┐
         │   Write to          │   │  Write to          │
         │   OpenSearch        │   │  Neptune           │
         │   - Chunks          │   │  - Entities (nodes)│
         │   - Embeddings      │   │  - Relationships   │
         │   - Metadata        │   │  - Provenance      │
         └─────────────────────┘   └────────────────────┘


═══════════════════════════════════════════════════════════════════════════
                        DETAILED DATA FLOW
═══════════════════════════════════════════════════════════════════════════

Step 1: Paper Download
──────────────────────
Input:  Search query or paper list
Output: JATS XML files in S3

PubMed API Request
    │
    ├─▶ Fetch paper metadata (PMC IDs)
    ├─▶ Download JATS XML via E-fetch
    └─▶ Store in S3: s3://medical-kg-papers/raw/PMC{id}.xml


Step 2: XML Parsing (ECS Task)
──────────────────────────────
Input:  JATS XML from S3
Output: Structured paper object

JATS XML File
    │
    ├─▶ Extract metadata (title, authors, journal, date)
    ├─▶ Parse abstract
    ├─▶ Parse body sections (intro, methods, results, discussion)
    ├─▶ Extract tables
    ├─▶ Extract citations
    └─▶ Create chunks (paragraph-level with section context)

Result: ParsedPaper object
    {
        metadata: {...},
        chunks: [{text, section, citations}, ...],
        tables: [...],
        references: {...}
    }


Step 3: Entity Extraction
─────────────────────────
Input:  ParsedPaper chunks
Output: Entities with canonical IDs

For each chunk:
    │
    ├─▶ Run NER (SciSpacy or Comprehend Medical)
    │   Output: [(text, type, span), ...]
    │
    ├─▶ Entity Linking
    │   "breast cancer" → UMLS:C0006142
    │   "BRCA1" → HGNC:1100
    │   "Olaparib" → RxNorm:1187832
    │
    └─▶ Store entities with chunk reference

Result: Enriched chunks with entity annotations


Step 4: Relationship Extraction
───────────────────────────────
Input:  Chunks with entities
Output: Entity relationships

Patterns detected:
    │
    ├─▶ "Drug X treats Disease Y" → TREATS relationship
    ├─▶ "Gene X increases risk of Disease Y" → INCREASES_RISK
    ├─▶ "Drug X interacts with Drug Y" → INTERACTS_WITH
    │
    ├─▶ Calculate confidence score
    │   - Based on sentence structure
    │   - Hedging language detection
    │   - Statistical measures mentioned
    │
    └─▶ Store relationship with provenance

Result: Relationship triples
    (Gene:BRCA1) -[INCREASES_RISK {risk_ratio: 5.0, source: PMC123}]-> (Disease:BreastCancer)


Step 5: Embedding Generation
────────────────────────────
Input:  Text chunks
Output: Vector embeddings

Batch of chunks (max 10)
    │
    ├─▶ Call Bedrock Titan Embeddings V2
    │   Request: {inputText: chunk_text, dimensions: 1024}
    │
    ├─▶ Receive embedding vector [1024 floats]
    │
    └─▶ Attach to chunk

Result: Chunks with embeddings ready for indexing


Step 6: Dual Write to Datastores
────────────────────────────────
Input:  Processed paper data
Output: Indexed data

┌─────────────────────────┐       ┌──────────────────────────┐
│   Write to OpenSearch   │       │    Write to Neptune      │
├─────────────────────────┤       ├──────────────────────────┤
│                         │       │                          │
│ For each chunk:         │       │ For each entity:         │
│   - embedding vector    │       │   CREATE (e:Entity {...})│
│   - chunk_text          │       │                          │
│   - section/metadata    │       │ For each relationship:   │
│   - entities found      │       │   MATCH (a), (b)         │
│   - paper_id            │       │   CREATE (a)-[r:REL]->(b)│
│                         │       │                          │
│ Index name:             │       │ Graph structure:         │
│   medical-papers        │       │   Nodes + Edges          │
│                         │       │                          │
└─────────────────────────┘       └──────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
                         QUERY FLOW (Hybrid)
═══════════════════════════════════════════════════════════════════════════

User Query: "What drugs treat BRCA1-mutated breast cancer?"

Step 1: Query Understanding
───────────────────────────
Natural Language Query
    │
    ├─▶ Send to Bedrock Claude 3.5
    │   Prompt: Convert to graph query JSON
    │
    └─▶ Generate structured query

Result: GraphQuery JSON
    {
        "match": {
            "nodes": [
                {"var": "gene", "type": "Gene", "properties": {"symbol": "BRCA1"}},
                {"var": "disease", "type": "Disease", "properties": {"name": "Breast Cancer"}},
                {"var": "drug", "type": "Drug"}
            ],
            "relationships": [
                {"from": "gene", "to": "disease", "type": "INCREASES_RISK"},
                {"from": "drug", "to": "disease", "type": "TREATS"}
            ]
        },
        "return": ["drug.name", "treats.efficacy"]
    }


Step 2: Parallel Execution
──────────────────────────
                        ┌──────────────────────┐
                        │  Orchestration Layer │
                        └──────────┬───────────┘
                                   │
                 ┌─────────────────┴─────────────────┐
                 │                                   │
     ┌───────────▼──────────┐          ┌───────────▼──────────┐
     │   Graph Query        │          │   Vector Search      │
     │   (Neptune)          │          │   (OpenSearch)       │
     ├──────────────────────┤          ├──────────────────────┤
     │                      │          │                      │
     │ Translate to Cypher: │          │ Generate embedding:  │
     │ MATCH (g:Gene)       │          │ embed("BRCA1...")    │
     │   -[:INCREASES_RISK] │          │                      │
     │   ->(d:Disease)      │          │ KNN search for       │
     │ <-[:TREATS]-         │          │ similar chunks       │
     │   (drug:Drug)        │          │                      │
     │                      │          │ Filter by section:   │
     │ Execute traversal    │          │ "results"            │
     │                      │          │                      │
     └───────────┬──────────┘          └───────────┬──────────┘
                 │                                  │
                 └─────────────────┬────────────────┘
                                   │
                        ┌──────────▼───────────┐
                        │  Results Aggregation │
                        ├──────────────────────┤
                        │                      │
                        │ Merge results:       │
                        │ - Graph entities     │
                        │ - Supporting chunks  │
                        │ - Confidence scores  │
                        │ - Source papers      │
                        │                      │
                        │ Deduplicate          │
                        │ Rank by confidence   │
                        │                      │
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │  Format Response     │
                        ├──────────────────────┤
                        │                      │
                        │ {                    │
                        │   "drugs": [         │
                        │     {                │
                        │       "name": "...", │
                        │       "efficacy": ..│
                        │       "evidence": [ ]│
                        │     }                │
                        │   ]                  │
                        │ }                    │
                        │                      │
                        └──────────────────────┘


═══════════════════════════════════════════════════════════════════════════
                    MONITORING & OBSERVABILITY
═══════════════════════════════════════════════════════════════════════════

All components send metrics to CloudWatch:

┌────────────────────────────────────────────────────────────────────┐
│                        CloudWatch                                   │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Logs:                           Metrics:                          │
│  ├─ Lambda execution logs        ├─ Request latency               │
│  ├─ ECS task logs                ├─ Error rates                   │
│  ├─ OpenSearch slow queries      ├─ OpenSearch disk usage         │
│  └─ Neptune query logs           ├─ Neptune connections           │
│                                  └─ Bedrock API usage              │
│                                                                     │
│  Alarms:                         Dashboards:                       │
│  ├─ High error rate              ├─ Ingestion pipeline status     │
│  ├─ Disk space > 80%             ├─ Query performance             │
│  ├─ High query latency           ├─ Cost tracking                 │
│  └─ Failed ingestion tasks       └─ System health overview        │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

## Data Flow Summary

### Ingestion Pipeline
1. **Download** papers from PubMed Central (JATS XML)
2. **Store** raw files in S3
3. **Parse** XML to extract structure and content
4. **Extract** medical entities and relationships
5. **Generate** embeddings for text chunks
6. **Index** to OpenSearch (vectors + metadata)
7. **Load** entities and relationships into Neptune

### Query Pipeline
1. **Receive** natural language query from user
2. **Convert** to structured graph query (via Claude)
3. **Execute** parallel searches:
   - Graph traversal in Neptune
   - Vector similarity in OpenSearch
4. **Aggregate** results from both sources
5. **Rank** by confidence and relevance
6. **Format** response with evidence
7. **Return** to user

### Data Stores
- **S3**: Raw papers, processed data, logs
- **OpenSearch**: Chunk embeddings, metadata, full-text search
- **Neptune**: Knowledge graph (entities, relationships, provenance)
- **Secrets Manager**: Credentials, API keys
- **Parameter Store**: Configuration values
