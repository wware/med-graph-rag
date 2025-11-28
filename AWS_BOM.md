# AWS Components Bill of Materials (BOM)
## Medical Knowledge Graph POC

## Core Services

### 1. Amazon OpenSearch Service
**Purpose**: Vector search + metadata storage for paper chunks

**Configuration**:
- Instance Type: `t3.medium.search` (development) → `r6g.large.search` (production)
- Number of Instances: 2 (for HA)
- Storage: 100 GB EBS (gp3) per instance
- Enable: k-NN plugin for vector search
- VPC: Deploy in private subnet

**Estimated Cost**: ~$150-200/month (dev), ~$400-500/month (prod)

**IAM Requirements**:
- IAM role for Lambda/ECS to access OpenSearch
- Fine-grained access control enabled

### 2. AWS Bedrock
**Purpose**: 
- Titan Embeddings V2 for generating embeddings
- Claude 3.5 Sonnet for query generation from natural language

**Configuration**:
- Model Access: Enable Titan Embeddings V2, Claude 3.5 Sonnet
- No infrastructure to provision (serverless)

**Estimated Cost**:
- Titan Embeddings: ~$0.0001 per 1K tokens (~$1-5 per 10K papers)
- Claude API: ~$3 per million input tokens, $15 per million output tokens

**IAM Requirements**:
- IAM policy to invoke Bedrock models

### 3. Amazon S3
**Purpose**: Storage for raw papers, processed data, artifacts

**Buckets**:
```
medical-kg-papers/
  ├── raw/             # Downloaded JATS XML files
  ├── processed/       # Parsed/extracted data
  └── artifacts/       # Logs, temp files, exports

medical-kg-code/
  ├── docker-images/   # Docker build contexts
  └── deployment/      # CDK artifacts, configs
```

**Configuration**:
- Versioning: Enabled on papers bucket
- Lifecycle: Move to Glacier after 90 days
- Encryption: SSE-S3 (or SSE-KMS for compliance)

**Estimated Cost**: ~$5-20/month (depends on corpus size)

### 4. Amazon Neptune (Graph Database)
**Purpose**: Knowledge graph storage (diseases, genes, drugs, relationships)

**Configuration**:
- Instance Type: `db.t3.medium` (dev) → `db.r6g.large` (prod)
- Storage: Auto-scaling from 10 GB
- Engine: Neptune 1.3+ (supports both Gremlin and SPARQL)
- Backup: Automated daily backups, 7-day retention

**Estimated Cost**: ~$200-300/month (dev), ~$600-800/month (prod)

**IAM Requirements**:
- IAM database authentication
- VPC security groups

### 5. AWS Lambda
**Purpose**: Serverless processing functions

**Functions**:
1. **Paper Ingestion Trigger** (S3 → Lambda)
   - Triggered when new XML uploaded to S3
   - Parses JATS XML
   - Runtime: Python 3.12
   - Memory: 2048 MB
   - Timeout: 15 minutes (max)
   
2. **Embedding Generator**
   - Generates embeddings via Bedrock
   - Runtime: Python 3.12
   - Memory: 1024 MB
   - Timeout: 5 minutes
   
3. **Entity Extractor**
   - Extracts medical entities
   - Runtime: Python 3.12
   - Memory: 2048 MB
   - Timeout: 10 minutes

**Estimated Cost**: ~$5-20/month (pay per invocation)

**IAM Requirements**:
- Lambda execution role with access to S3, OpenSearch, Bedrock, Neptune

### 6. Amazon ECS (Elastic Container Service)
**Purpose**: Long-running ingestion pipeline, API server

**Configuration**:
- Launch Type: Fargate (serverless containers)
- Tasks:
  1. **Bulk Ingestion Pipeline**: Processes batches of papers
  2. **Query API Server**: FastAPI service for queries
  
**Task Definitions**:
```
ingestion-pipeline:
  - CPU: 2 vCPU
  - Memory: 4 GB
  - Image: medical-kg-ingestion:latest

query-api:
  - CPU: 1 vCPU
  - Memory: 2 GB
  - Image: medical-kg-api:latest
  - Port: 8000
```

**Estimated Cost**: ~$50-100/month (based on runtime)

### 7. Amazon ECR (Elastic Container Registry)
**Purpose**: Store Docker images

**Repositories**:
- `medical-kg-ingestion`
- `medical-kg-api`
- `medical-kg-query-generator`

**Configuration**:
- Image scanning: Enabled
- Lifecycle policy: Keep last 10 images

**Estimated Cost**: ~$1-5/month (storage + data transfer)

### 8. Application Load Balancer (ALB)
**Purpose**: Load balance API requests to ECS tasks

**Configuration**:
- Type: Application Load Balancer
- Scheme: Internal (for POC) or Internet-facing (for demo)
- Target: ECS service (query-api)
- Health checks: /health endpoint

**Estimated Cost**: ~$20-25/month

### 9. Amazon CloudWatch
**Purpose**: Logs, metrics, monitoring, alarms

**Configuration**:
- Log Groups:
  - `/aws/lambda/paper-ingestion`
  - `/aws/lambda/embedding-generator`
  - `/aws/ecs/ingestion-pipeline`
  - `/aws/ecs/query-api`
- Retention: 7 days (dev), 30 days (prod)
- Alarms:
  - OpenSearch disk space > 80%
  - Lambda errors > 10/hour
  - Neptune CPU > 80%

**Estimated Cost**: ~$10-20/month

### 10. AWS Secrets Manager
**Purpose**: Store sensitive configuration

**Secrets**:
- OpenSearch admin credentials
- Neptune connection strings
- API keys (if needed)
- GitHub tokens for Actions

**Estimated Cost**: ~$1-2/month ($0.40 per secret)

### 11. Amazon VPC
**Purpose**: Network isolation and security

**Configuration**:
```
VPC: 10.0.0.0/16
  ├── Public Subnets: 10.0.1.0/24, 10.0.2.0/24
  │   └── NAT Gateways, ALB
  └── Private Subnets: 10.0.10.0/24, 10.0.11.0/24
      └── OpenSearch, Neptune, ECS Tasks, Lambda
```

**Components**:
- 2 Availability Zones
- NAT Gateway in each AZ (for Lambda/ECS internet access)
- VPC Endpoints for S3, Bedrock (reduce costs)
- Security Groups for each service

**Estimated Cost**: ~$60-100/month (mostly NAT Gateways)

### 12. AWS Systems Manager (Parameter Store)
**Purpose**: Store non-sensitive configuration

**Parameters**:
- OpenSearch endpoint
- Neptune endpoint
- S3 bucket names
- Model IDs
- Feature flags

**Estimated Cost**: Free (standard parameters)

## Optional Services (Future Enhancement)

### 13. Amazon Comprehend Medical
**Purpose**: Medical entity extraction (alternative to SciSpacy)

**Configuration**:
- On-demand API calls
- No infrastructure needed

**Estimated Cost**: $0.01 per 100 characters (~$10-20 per 10K papers)

### 14. Amazon SageMaker
**Purpose**: Host custom medical NER models if needed

**Configuration**:
- Instance Type: ml.m5.xlarge
- Only if custom models needed

**Estimated Cost**: ~$200+/month (if used)

### 15. Amazon EventBridge
**Purpose**: Orchestrate complex workflows, scheduled tasks

**Use Cases**:
- Schedule periodic paper fetching
- Trigger reindexing workflows
- Coordinate multi-step processing

**Estimated Cost**: <$1/month

### 16. AWS Step Functions
**Purpose**: Orchestrate complex ingestion workflows

**Use Cases**:
- Multi-step paper processing
- Error handling and retries
- State management

**Estimated Cost**: $25 per million state transitions (~$1-5/month for POC)

## Development Tools

### 17. AWS Cloud9 (Optional)
**Purpose**: Cloud-based IDE for development

**Configuration**:
- Instance Type: t3.small
- Stop after 30 minutes idle

**Estimated Cost**: ~$20-30/month (if used)

### 18. AWS CodeBuild
**Purpose**: Build Docker images in CI/CD pipeline

**Configuration**:
- Build compute: 4 GB, 2 vCPU
- Triggered by GitHub Actions or CodePipeline

**Estimated Cost**: $0.005 per build minute (~$5-10/month)

## Total Estimated Monthly Costs

### Development/POC Environment
- OpenSearch: $150
- Neptune: $200
- S3: $10
- Lambda: $10
- ECS/Fargate: $30
- ECR: $2
- ALB: $20
- VPC/NAT: $60
- CloudWatch: $10
- Secrets Manager: $2
- Bedrock: $5-20 (usage-based)
- **Total: ~$500-550/month**

### Production Environment
- OpenSearch: $400
- Neptune: $600
- S3: $20
- Lambda: $20
- ECS/Fargate: $100
- ECR: $5
- ALB: $25
- VPC/NAT: $100
- CloudWatch: $20
- Secrets Manager: $5
- Bedrock: $20-100 (usage-based)
- **Total: ~$1,315-1,500/month**

## Cost Optimization Tips

1. **Use VPC Endpoints**: Save on NAT Gateway costs for S3/Bedrock
2. **Reserved Instances**: For OpenSearch/Neptune (40% savings)
3. **Fargate Spot**: For non-critical batch jobs (70% savings)
4. **S3 Intelligent Tiering**: Automatic cost optimization
5. **Lambda SnapStart**: Reduce cold starts and costs
6. **Stop dev resources**: Automate shutdown outside business hours
7. **Use AWS Free Tier**: 12 months free for many services

## IAM Roles Summary

### 1. Lambda Execution Role
```
Permissions:
- S3: GetObject, PutObject
- OpenSearch: ESHttpPost, ESHttpPut
- Bedrock: InvokeModel
- Neptune: connect
- CloudWatch: CreateLogGroup, PutLogEvents
- Secrets Manager: GetSecretValue
```

### 2. ECS Task Role
```
Permissions:
- Same as Lambda + ECR pull
```

### 3. GitHub Actions Role (OIDC)
```
Permissions:
- ECR: Push images
- ECS: UpdateService, RegisterTaskDefinition
- S3: Deploy CDK artifacts
- CloudFormation: Create/Update stacks
```

### 4. Developer Role
```
Permissions:
- Full access to all POC resources
- CDK deploy permissions
- CloudFormation management
```

## Networking Details

### Security Groups

**OpenSearch SG**:
- Inbound: 443 from Lambda SG, ECS SG
- Outbound: All

**Neptune SG**:
- Inbound: 8182 (Gremlin) from Lambda SG, ECS SG
- Outbound: All

**ECS Task SG**:
- Inbound: 8000 from ALB SG
- Outbound: All

**ALB SG**:
- Inbound: 443 from 0.0.0.0/0 (or restricted IPs)
- Outbound: All to ECS Task SG

### VPC Endpoints (Cost Savings)

**Gateway Endpoints** (Free):
- S3
- DynamoDB (if used)

**Interface Endpoints** ($7.50/month each):
- Bedrock (recommended)
- Secrets Manager (recommended)
- ECR (recommended for ECS)

## Tags for Resource Management

All resources should be tagged:
```
Project: medical-knowledge-graph
Environment: dev|prod
ManagedBy: cdk
Owner: your-email@example.com
CostCenter: research
```

## Backup and Disaster Recovery

1. **OpenSearch**: Automated snapshots to S3 daily
2. **Neptune**: Automated backups, 7-day retention
3. **S3**: Versioning enabled
4. **Infrastructure**: CDK templates in Git

**RTO**: 4 hours (time to restore)
**RPO**: 24 hours (acceptable data loss)

## Next Steps

1. Set up AWS account structure
2. Deploy network infrastructure (VPC) via CDK
3. Deploy OpenSearch cluster
4. Deploy Neptune cluster
5. Set up ECR repositories
6. Build and push Docker images
7. Deploy Lambda functions
8. Deploy ECS services
9. Set up monitoring and alarms
10. Configure CI/CD pipeline
