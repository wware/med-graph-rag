# Local Development Setup

## Prerequisites

- Docker Desktop installed and running
- Python 3.12+ (for local development outside containers)
- AWS CLI configured (for Bedrock access)
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
- OpenSearch at http://localhost:9200
- OpenSearch Dashboards at http://localhost:5601
- LocalStack (mock AWS) at http://localhost:4566

### 2. Set Up Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Download Sample Papers

```bash
# Create papers directory
mkdir -p papers/raw

# Download 100 breast cancer papers from PubMed Central
python -m src.scripts.download_papers \
    --query "breast cancer BRCA1" \
    --max-results 100 \
    --output-dir papers/raw
```

### 4. Run Ingestion Pipeline

```bash
# Process papers locally (uses local OpenSearch + AWS Bedrock)
python -m src.ingestion.pipeline \
    --input-dir papers/raw \
    --batch-size 10
```

This will:
1. Parse JATS XML files
2. Extract entities
3. Generate embeddings (calls AWS Bedrock Titan)
4. Index to local OpenSearch

### 5. Test Queries

```bash
# Interactive query testing
python -m src.scripts.test_queries --interactive

# Or programmatically
python -m src.scripts.test_queries \
    --query "What drugs treat breast cancer?"
```

### 6. Start API Server (Optional)

```bash
# Start the FastAPI server
docker-compose --profile api up -d

# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
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

# Use OpenSearch Dashboards
open http://localhost:5601
```

### Working with LocalStack (Mock S3)

```bash
# Create S3 bucket
aws --endpoint-url=http://localhost:4566 s3 mb s3://medical-kg-papers

# List buckets
aws --endpoint-url=http://localhost:4566 s3 ls

# Upload file
aws --endpoint-url=http://localhost:4566 s3 cp \
    papers/raw/PMC123456.xml \
    s3://medical-kg-papers/raw/
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Run specific test file
pytest tests/test_jats_parser.py -v
```

### Code Quality

```bash
# Format code
black src/

# Lint code
ruff check src/

# Type checking
mypy src/
```

## Directory Structure

```
medical-knowledge-graph/
├── docker/
│   ├── Dockerfile.ingestion
│   └── Dockerfile.api
├── src/
│   ├── ingestion/
│   │   ├── jats_parser.py
│   │   ├── embedding_generator.py
│   │   └── pipeline.py
│   ├── api/
│   │   └── main.py
│   ├── client/
│   │   └── medical_papers_client.py
│   └── scripts/
│       ├── download_papers.py
│       └── test_queries.py
├── papers/
│   ├── raw/          # Downloaded JATS XML files
│   └── processed/    # Parsed data
├── tests/
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Environment Variables

Create a `.env` file in the project root:

```bash
# AWS Credentials (for Bedrock)
AWS_PROFILE=default
AWS_REGION=us-east-1

# OpenSearch (local)
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200

# LocalStack (mock AWS services)
S3_ENDPOINT=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test

# Application
LOG_LEVEL=INFO
BATCH_SIZE=10
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
OPENSEARCH_JAVA_OPTS=-Xms256m -Xmx256m
```

### Can't connect to Bedrock

```bash
# Verify AWS credentials
aws sts get-caller-identity

# Check Bedrock model access
aws bedrock list-foundation-models --region us-east-1

# Enable models in AWS Console if needed
```

### Papers not indexing

```bash
# Check OpenSearch is accepting writes
curl -X PUT http://localhost:9200/test-index

# Check index exists
curl http://localhost:9200/_cat/indices?v

# Check for errors in logs
docker-compose logs -f
```

## Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (deletes all data)
docker-compose down -v

# Stop specific service
docker-compose stop opensearch
```

## Resource Usage

Expected resource usage for local development:

- OpenSearch: ~1GB RAM, ~5GB disk
- LocalStack: ~500MB RAM
- Ingestion service: ~500MB RAM (when running)
- API service: ~200MB RAM (when running)

Total: ~2-3GB RAM when all services running

## Next Steps

1. ✅ Start services with `docker-compose up -d`
2. ✅ Download 100 sample papers
3. ✅ Run ingestion pipeline
4. ✅ Test queries
5. ⏭️  When everything works locally, deploy to AWS

## Cost Comparison

| Environment | Monthly Cost |
|-------------|--------------|
| Local Development | $0 (just electricity + ~$2 for Bedrock) |
| AWS POC | ~$50/month |
| AWS Production | ~$1,000+/month |

**Recommendation**: Develop and test everything locally first, then deploy to AWS only when ready to demo or when you need full production features.

## Getting Help

- OpenSearch docs: https://opensearch.org/docs/latest/
- FastAPI docs: https://fastapi.tiangolo.com/
- Bedrock docs: https://docs.aws.amazon.com/bedrock/
- Project issues: [your GitHub repo]
