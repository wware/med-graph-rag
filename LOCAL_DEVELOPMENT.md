# Local Development Setup

Complete guide for developing the MCP server and backend locally (no AWS deployment needed).

## Prerequisites

- Docker Desktop installed and running
- Python 3.12+ (for local development)
- AWS CLI configured (for Bedrock access - embeddings only)
- At least 8GB RAM available for Docker

## Quick Start

### 1. Start Core Services

```bash
# Start OpenSearch and OpenSearch Dashboards
docker-compose up -d

# Check that services are healthy
docker-compose ps

# View logs
docker-compose logs -f opensearch
```

This starts:
- **OpenSearch** at http://localhost:9200 (vector + keyword search)
- **OpenSearch Dashboards** at http://localhost:5601 (data exploration)
- **LocalStack** (optional) at http://localhost:4566 (mock AWS S3)

### 2. Set Up Python Environment

**Option A: Using `uv` (recommended - 10-100x faster):**

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh  # Linux/Mac
# Or: pip install uv

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # Linux/Mac
# OR: .venv\Scripts\activate  # Windows

# Install package in development mode
uv pip install -e .
```

**Option B: Using traditional pip:**

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# OR: venv\Scripts\activate  # Windows

# Install package in development mode
pip install -e .
```

### 3. Configure Environment

Create a `.env` file in the project root:

```bash
# OpenSearch (local Docker)
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200

# AWS Bedrock (for embeddings only - uses your configured AWS CLI)
AWS_PROFILE=default
AWS_REGION=us-east-1

# Optional: LocalStack for S3 testing
S3_ENDPOINT=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test

# Application settings
LOG_LEVEL=INFO
BATCH_SIZE=10
```

### 4. Download Sample Papers

```bash
# Create papers directory
mkdir -p papers/raw

# Download 100 breast cancer papers from PubMed Central
python -m src.scripts.download_papers \
    --query "breast cancer BRCA1" \
    --max-results 100 \
    --output-dir papers/raw
```

### 5. Run Ingestion Pipeline

```bash
# Process papers (parses XML, generates embeddings, indexes to OpenSearch)
python -m src.ingestion.pipeline \
    --input-dir papers/raw \
    --batch-size 10
```

This will:
1. Parse JATS XML files
2. Extract entities and text chunks
3. Generate embeddings via AWS Bedrock Titan
4. Index to local OpenSearch

### 6. Test MCP Server Locally

```bash
# Run the MCP server
python -m src.mcp_server

# The server listens on stdio
# To test with Claude Desktop, add to your config:
# File: ~/.config/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "pubmed-graph-rag": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/path/to/med-graph-rag"
    }
  }
}
```

**For production use:**
```bash
# Install as package via uvx
uvx pubmed-graph-rag

# Configure in Claude Desktop
{
  "mcpServers": {
    "pubmed-graph-rag": {
      "command": "uvx",
      "args": ["pubmed-graph-rag"]
    }
  }
}
```

## Development Workflow

### Working with OpenSearch

```bash
# Check cluster health
curl http://localhost:9200/_cluster/health?pretty

# List indices
curl http://localhost:9200/_cat/indices?v

# Search documents
curl -X POST http://localhost:9200/medical-papers/_search?pretty \
  -H 'Content-Type: application/json' \
  -d '{"query": {"match_all": {}}}'

# Use OpenSearch Dashboards UI
open http://localhost:5601
```

### Testing Queries (Direct Backend Access)

```bash
# Interactive query testing
python -m src.scripts.test_queries --interactive

# Or programmatically
python -m src.scripts.test_queries \
    --query "What drugs treat breast cancer?"
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Run specific test
pytest tests/test_jats_parser.py -v
```

### Code Quality

```bash
# Format code
black src/

# Lint code
ruff check src/

# Type checking (if mypy configured)
mypy src/
```

## Project Structure

```
med-graph-rag/
├── src/
│   ├── mcp_server.py         # MCP server (NEW - stdio transport)
│   ├── ingestion/
│   │   ├── jats_parser.py    # Parse PubMed XML
│   │   ├── embedding_generator.py
│   │   └── pipeline.py       # Ingestion orchestration
│   ├── client/
│   │   └── medical_papers_client.py  # OpenSearch client
│   └── scripts/
│       ├── download_papers.py
│       └── test_queries.py
├── papers/
│   ├── raw/                  # Downloaded JATS XML files
│   └── processed/            # Parsed data (optional)
├── tests/
├── docker-compose.yml        # Local OpenSearch
├── pyproject.toml           # Package config + MCP entry point
└── README.md
```

## Troubleshooting

### OpenSearch won't start

```bash
# Check Docker resources
docker stats

# Increase memory in Docker Desktop settings (8GB minimum)

# Check logs
docker-compose logs opensearch

# Reset volumes if corrupted
docker-compose down -v
docker-compose up -d
```

### OpenSearch out of memory

```bash
# Edit docker-compose.yml to reduce heap size:
OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m
```

### Can't connect to AWS Bedrock

```bash
# Verify AWS credentials
aws sts get-caller-identity

# Check Bedrock model access
aws bedrock list-foundation-models --region us-east-1

# Enable Titan Embeddings V2 in AWS Console if needed:
# https://console.aws.amazon.com/bedrock/ → Model access
```

### Papers not indexing

```bash
# Check OpenSearch is accepting writes
curl -X PUT http://localhost:9200/test-index

# Check index exists
curl http://localhost:9200/_cat/indices?v

# Check for errors in pipeline
python -m src.ingestion.pipeline --input-dir papers/raw --batch-size 1 --verbose
```

### MCP Server not responding

```bash
# Test server directly
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python -m src.mcp_server

# Check Claude Desktop logs
# Mac: ~/Library/Logs/Claude/mcp*.log
# Windows: %APPDATA%\Claude\logs\mcp*.log

# Verify cwd path in config is correct
```

## Resource Usage

Expected resource usage for local development:

- **OpenSearch**: ~1-2GB RAM, ~5GB disk
- **LocalStack**: ~500MB RAM (if used)
- **Ingestion pipeline**: ~500MB RAM (when running)
- **MCP server**: ~200MB RAM (when serving queries)

**Total**: ~2-3GB RAM when all services running

## Cost Comparison

| Environment | Monthly Cost | Use Case |
|-------------|--------------|----------|
| Local Development | ~$2 (Bedrock embeddings only) | Development, testing |
| AWS POC | ~$50 | Demos, small-scale validation |
| AWS Production | ~$500-1000 | 1000+ papers, high availability |

**Recommendation**: Develop and test everything locally first. Only deploy to AWS when you need:
- Persistent storage beyond laptop
- Demo access for customers
- Production scale (1000+ papers)

## Stopping Services

```bash
# Stop all Docker services
docker-compose down

# Stop and remove volumes (deletes all data)
docker-compose down -v

# Stop specific service
docker-compose stop opensearch
```

## Next Steps

1. ✅ Start services: `docker-compose up -d`
2. ✅ Install Python package: `pip install -e .`
3. ✅ Download 100 sample papers
4. ✅ Run ingestion pipeline
5. ✅ Test MCP server with Claude Desktop
6. ⏭️  When validated locally, consider AWS deployment (see AWS_BOM.md)

## Getting Help

- **OpenSearch**: https://opensearch.org/docs/latest/
- **MCP Protocol**: https://modelcontextprotocol.io/
- **AWS Bedrock**: https://docs.aws.amazon.com/bedrock/
- **Project Issues**: https://github.com/wware/med-graph-rag/issues
