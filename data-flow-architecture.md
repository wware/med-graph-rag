# Medical Knowledge Graph - Data Flow Architecture

## MCP Server Architecture (Post-Pivot)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER INTERACTIONS                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐         ┌───────────────────────────────┐        │
│  │  Doctor's Laptop │         │   Claude Desktop              │        │
│  │                  │────────▶│   (or other AI assistant)     │        │
│  │  User types      │         │                               │        │
│  │  question        │         │   Decides to use MCP tools    │        │
│  └──────────────────┘         └───────────────┬───────────────┘        │
│                                                │                         │
│                                                │ stdio transport         │
│                                                │                         │
│                                 ┌──────────────▼──────────────┐         │
│                                 │   MCP Server (Local)        │         │
│                                 │   - pubmed_graph_search     │         │
│                                 │   - diagnostic_chain_trace  │         │
│                                 │   - evidence_contradiction  │         │
│                                 └──────────────┬──────────────┘         │
│                                                │                         │
└────────────────────────────────────────────────┼─────────────────────────┘
                                                 │
                                                 │ HTTPS/AWS SDK
                                                 │
┌────────────────────────────────────────────────┼─────────────────────────┐
│                         AWS BACKEND SERVICES                             │
├────────────────────────────────────────────────┼─────────────────────────┤
│                                                │                          │
│                                 ┌──────────────▼──────────────┐          │
│                                 │   MCP Server Client          │          │
│                                 │   (Queries AWS backend)      │          │
│                                 └──┬─────────────────┬─────────┘          │
│                                    │                 │                    │
│                  ┌─────────────────▼─────┐   ┌──────▼────────────┐      │
│                  │   AWS Bedrock         │   │   AWS Bedrock     │      │
│                  │   Claude 3.5          │   │   Titan Embed V2  │      │
│                  │   (Query reasoning)   │   │   (Query embed)   │      │
│                  └─────────┬─────────────┘   └──────┬────────────┘      │
│                            │                         │                    │
│          ┌─────────────────▼─────────────────────────▼─────────┐        │
│          │          Amazon OpenSearch Service                  │        │
│          │          - Vector KNN search                        │        │
│          │          - Hybrid query (vector + keyword)          │        │
│          │          - Entity metadata + relationships          │        │
│          │          - Aggregations and filtering               │        │
│          └─────────────────────┬───────────────────────────────┘        │
│                                │                                         │
│                                │ Results                                 │
│                                │                                         │
│                 ┌──────────────▼──────────────┐                         │
│                 │  Results Synthesis          │                         │
│                 │  & Evidence Formatting      │                         │
│                 └──────────────┬──────────────┘                         │
│                                │                                         │
└────────────────────────────────┼─────────────────────────────────────────┘
                                 │
                                 │ Return JSON response
                                 │
                  ┌──────────────▼──────────────┐
                  │   MCP Server (Local)        │
                  │   Formats for AI assistant  │
                  └──────────────┬──────────────┘
                                 │
                                 │ stdio transport
                                 │
                  ┌──────────────▼──────────────┐
                  │   Claude Desktop            │
                  │   Presents results to user  │
                  └─────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
                           INGESTION PIPELINE
═══════════════════════════════════════════════════════════════════════════

┌──────────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCE LAYER                                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌────────────────┐         ┌────────────────┐      ┌─────────────────┐│
│  │  PubMed Central│         │  Manual Upload │      │  Bulk Download  ││
│  │  API (E-utils) │         │  (scripts)     │      │  (FTP Archive)  ││
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
                                 │
                      ┌──────────▼──────────┐
                      │   Write to          │
                      │   OpenSearch        │
                      │   - Chunks          │
                      │   - Embeddings      │
                      │   - Metadata        │
                      │   - Entities        │
                      │   - Relationships   │
                      └─────────────────────┘


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


Step 2: XML Parsing (Lambda)
─────────────────────────────
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

Result: Relationship data stored in OpenSearch
    {
        subject: "BRCA1",
        predicate: "INCREASES_RISK",
        object: "Breast Cancer",
        confidence: 0.85,
        source: "PMC123456",
        section: "results",
        paragraph: 3
    }


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


Step 6: Write to OpenSearch
────────────────────────────
Input:  Processed paper data
Output: Indexed data

┌─────────────────────────────────────────┐
│      Write to OpenSearch                │
├─────────────────────────────────────────┤
│                                         │
│ For each chunk:                         │
│   - embedding vector (1024-dim)         │
│   - chunk_text (full paragraph)         │
│   - section (results/methods/etc)       │
│   - entities found ([{id, type, ...}])  │
│   - paper_id (PMC123456)                │
│   - metadata (authors, date, journal)   │
│                                         │
│ For each relationship:                  │
│   - subject_entity                      │
│   - predicate (TREATS, etc)             │
│   - object_entity                       │
│   - confidence score                    │
│   - provenance (PMC, section, para)     │
│                                         │
│ Index names:                            │
│   - medical-papers-chunks               │
│   - medical-papers-relationships        │
│                                         │
└─────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
                      QUERY FLOW VIA MCP SERVER
═══════════════════════════════════════════════════════════════════════════

User Query: "What drugs treat BRCA1-mutated breast cancer?"

Step 1: User Interaction
────────────────────────
Doctor types question in Claude Desktop
    │
    └─▶ Claude decides to use MCP tool: pubmed_graph_search


Step 2: MCP Tool Call
─────────────────────
Claude Desktop → MCP Server (stdio)
    │
    └─▶ Calls: pubmed_graph_search({
          query: "What drugs treat BRCA1-mutated breast cancer?",
          depth: 2
        })


Step 3: Query Processing (MCP Server → AWS)
───────────────────────────────────────────
MCP Server sends query to AWS backend
    │
    ├─▶ Call Bedrock Claude 3.5 for query understanding
    │   - Extract entities: BRCA1 (gene), breast cancer (disease), drugs
    │   - Identify query type: multi-hop traversal
    │   - Generate search strategy
    │
    └─▶ Create OpenSearch query plan


Step 4: OpenSearch Execution
────────────────────────────
                        ┌──────────────────────┐
                        │  OpenSearch Queries  │
                        └──────────┬───────────┘
                                   │
                 ┌─────────────────┴─────────────────┐
                 │                                   │
     ┌───────────▼──────────┐          ┌───────────▼──────────┐
     │  Relationship Query  │          │   Vector Search      │
     ├──────────────────────┤          ├──────────────────────┤
     │                      │          │                      │
     │ Query relationships: │          │ Generate embedding:  │
     │                      │          │ embed("BRCA1...")    │
     │ subject: "BRCA1"     │          │                      │
     │ predicate: TREATS    │          │ KNN search for       │
     │ filter: confidence>0.7│         │ similar chunks       │
     │                      │          │                      │
     │ Returns:             │          │ Filter by section:   │
     │ - Drug entities      │          │ "results"            │
     │ - Confidence scores  │          │                      │
     │ - Source papers      │          │ Returns:             │
     │                      │          │ - Relevant paragraphs│
     │                      │          │ - Evidence chunks    │
     │                      │          │ - Provenance         │
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
                        │ - Relationship data  │
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
                        │       "confidence": │
                        │       "evidence": [ ]│
                        │       "sources": [ ] │
                        │     }                │
                        │   ]                  │
                        │ }                    │
                        │                      │
                        └──────────────────────┘


Step 5: Return to User
──────────────────────
Formatted JSON → MCP Server
    │
    └─▶ MCP Server returns to Claude Desktop via stdio

Claude Desktop receives structured response
    │
    └─▶ Claude formats answer for user with:
        - Drug names
        - Evidence strength
        - Source citations (PMC IDs, sections, paragraphs)
        - Contradictions flagged (if any)


═══════════════════════════════════════════════════════════════════════════
                         MCP TOOL DESCRIPTIONS
═══════════════════════════════════════════════════════════════════════════

1. pubmed_graph_search
   Purpose: Multi-hop reasoning across papers
   Input: Natural language query + max depth
   Output: Entities, relationships, evidence with provenance
   Example: "What proteins interact with BRCA1?" → Multi-hop traversal

2. diagnostic_chain_trace
   Purpose: Follow symptom → diagnosis → treatment chains
   Input: Symptoms/findings
   Output: Possible diagnoses with evidence chains
   Example: "Elevated ALP + fatigue + rash" → Diagnostic pathway

3. evidence_contradiction_check
   Purpose: Find contradictory evidence
   Input: Medical claim or question
   Output: Supporting vs contradicting evidence
   Example: "Does aspirin prevent heart attacks?" → Both sides with RCTs


═══════════════════════════════════════════════════════════════════════════
                    MONITORING & OBSERVABILITY
═══════════════════════════════════════════════════════════════════════════

All components send metrics to CloudWatch:

┌────────────────────────────────────────────────────────────────────┐
│                        CloudWatch                                   │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Logs:                           Metrics:                          │
│  ├─ Lambda execution logs        ├─ Query latency                 │
│  ├─ MCP server logs (local)      ├─ Error rates                   │
│  ├─ OpenSearch slow queries      ├─ OpenSearch disk usage         │
│  └─ Bedrock API calls            └─ Bedrock API usage              │
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
3. **Trigger** Lambda on S3 event
4. **Parse** XML to extract structure and content
5. **Extract** medical entities and relationships
6. **Generate** embeddings for text chunks
7. **Index** to OpenSearch (vectors + metadata + relationships)

### Query Pipeline (via MCP)
1. **Receive** natural language query from user (via Claude Desktop)
2. **Call** appropriate MCP tool (pubmed_graph_search, diagnostic_chain_trace, etc.)
3. **Process** query in MCP server:
   - Convert to structured query (via Bedrock Claude)
   - Generate embeddings for vector search (via Bedrock Titan)
4. **Execute** searches in OpenSearch:
   - Relationship queries (graph-like traversal)
   - Vector similarity search
5. **Aggregate** results from both query types
6. **Rank** by confidence and relevance
7. **Format** response with evidence and provenance
8. **Return** to AI assistant via stdio
9. **Present** to user with citations

### Data Stores
- **S3**: Raw papers, processed data, logs
- **OpenSearch**: Chunk embeddings, metadata, entities, relationships, full-text search
- **Secrets Manager**: Credentials, API keys (OpenSearch, AWS)
- **Parameter Store**: Configuration values
