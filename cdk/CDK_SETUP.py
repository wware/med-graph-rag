# CDK Configuration Files

## cdk.json

```json
{
  "app": "python3 app.py",
  "watch": {
    "include": [
      "**"
    ],
    "exclude": [
      "README.md",
      "cdk*.json",
      "requirements*.txt",
      "source.bat",
      "**/__init__.py",
      "**/__pycache__",
      "**/*.pyc"
    ]
  },
  "context": {
    "@aws-cdk/aws-lambda:recognizeLayerVersion": true,
    "@aws-cdk/core:checkSecretUsage": true,
    "@aws-cdk/core:target-partitions": [
      "aws",
      "aws-cn"
    ],
    "@aws-cdk-containers/ecs-service-extensions:enableDefaultLogDriver": true,
    "@aws-cdk/aws-ec2:uniqueImdsv2TemplateName": true,
    "@aws-cdk/aws-ecs:arnFormatIncludesClusterName": true,
    "@aws-cdk/aws-iam:minimizePolicies": true,
    "@aws-cdk/core:validateSnapshotRemovalPolicy": true,
    "@aws-cdk/aws-codepipeline:crossAccountKeyAliasStackSafeResourceName": true,
    "@aws-cdk/aws-s3:createDefaultLoggingPolicy": true,
    "@aws-cdk/aws-sns-subscriptions:restrictSqsDescryption": true,
    "@aws-cdk/aws-apigateway:disableCloudWatchRole": true,
    "@aws-cdk/core:enablePartitionLiterals": true,
    "@aws-cdk/aws-events:eventsTargetQueueSameAccount": true,
    "@aws-cdk/aws-iam:standardizedServicePrincipals": true,
    "@aws-cdk/aws-ecs:disableExplicitDeploymentControllerForCircuitBreaker": true,
    "@aws-cdk/aws-iam:importedRoleStackSafeDefaultPolicyName": true,
    "@aws-cdk/aws-s3:serverAccessLogsUseBucketPolicy": true,
    "@aws-cdk/aws-route53-patters:useCertificate": true,
    "@aws-cdk/customresources:installLatestAwsSdkDefault": false,
    "@aws-cdk/aws-rds:databaseProxyUniqueResourceName": true,
    "@aws-cdk/aws-codedeploy:removeAlarmsFromDeploymentGroup": true,
    "@aws-cdk/aws-apigateway:authorizerChangeDeploymentLogicalId": true,
    "@aws-cdk/aws-ec2:launchTemplateDefaultUserData": true,
    "@aws-cdk/aws-secretsmanager:useAttachedSecretResourcePolicyForSecretTargetAttachments": true,
    "@aws-cdk/aws-redshift:columnId": true,
    "@aws-cdk/aws-stepfunctions-tasks:enableEmrServicePolicyV2": true,
    "@aws-cdk/aws-ec2:restrictDefaultSecurityGroup": true,
    "@aws-cdk/aws-apigateway:requestValidatorUniqueId": true,
    "@aws-cdk/aws-kms:aliasNameRef": true,
    "@aws-cdk/aws-autoscaling:generateLaunchTemplateInsteadOfLaunchConfig": true,
    "@aws-cdk/core:includePrefixInUniqueNameGeneration": true,
    "@aws-cdk/aws-efs:denyAnonymousAccess": true,
    "@aws-cdk/aws-opensearchservice:enableOpensearchMultiAzWithStandby": true,
    "@aws-cdk/aws-lambda-nodejs:useLatestRuntimeVersion": true,
    "@aws-cdk/aws-efs:mountTargetOrderInsensitiveLogicalId": true,
    "@aws-cdk/aws-rds:auroraClusterChangeScopeOfInstanceParameterGroupWithEachParameters": true,
    "@aws-cdk/aws-appsync:useArnForSourceApiAssociationIdentifier": true,
    "@aws-cdk/aws-rds:preventRenderingDeprecatedCredentials": true,
    "@aws-cdk/aws-codepipeline-actions:useNewDefaultBranchForCodeCommitSource": true,
    "@aws-cdk/aws-cloudwatch-actions:changeLambdaPermissionLogicalIdForLambdaAction": true,
    "@aws-cdk/aws-codepipeline:crossAccountKeysDefaultValueToFalse": true,
    "@aws-cdk/aws-codepipeline:defaultPipelineTypeToV2": true,
    "@aws-cdk/aws-kms:reduceCrossAccountRegionPolicyScope": true,
    "@aws-cdk/aws-eks:nodegroupNameAttribute": true,
    "@aws-cdk/aws-ec2:ebsDefaultGp3Volume": true,
    "@aws-cdk/aws-ecs:removeDefaultDeploymentAlarm": true,
    "@aws-cdk/custom-resources:logApiResponseDataPropertyTrueDefault": false,
    "@aws-cdk/aws-s3:keepNotificationInImportedBucket": false
  }
}
```

## requirements.txt (for CDK)

```
aws-cdk-lib>=2.120.0
constructs>=10.0.0
```

## .gitignore

```
# CDK
.cdk.staging/
cdk.out/
cdk.context.json

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
ENV/
env/
.venv

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Secrets
.env
*.pem
*.key

# Local data
data/
papers/
*.zip
```

## CDK Setup Instructions

### 1. Install CDK

```bash
# Install Node.js (required for CDK CLI)
# Download from https://nodejs.org/

# Install AWS CDK CLI
npm install -g aws-cdk

# Verify installation
cdk --version
```

### 2. Set Up Python Environment

```bash
cd cdk/

# Create virtual environment
python -m venv .venv

# Activate
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure AWS Credentials

```bash
# Configure AWS CLI (if not already done)
aws configure

# Verify credentials
aws sts get-caller-identity
```

### 4. Bootstrap CDK (First Time Only)

```bash
# Bootstrap your AWS account for CDK
cdk bootstrap aws://ACCOUNT-NUMBER/REGION

# Example:
cdk bootstrap aws://123456789012/us-east-1
```

### 5. Review Stack

```bash
# See what will be created
cdk diff

# Synthesize CloudFormation template
cdk synth
```

### 6. Deploy Stack

```bash
# Deploy the stack
cdk deploy

# Or with auto-approval (no prompts)
cdk deploy --require-approval never

# Deploy to specific account/region
cdk deploy --profile my-aws-profile
```

### 7. View Outputs

After deployment completes:

```bash
# Stack outputs are displayed, or retrieve them:
aws cloudformation describe-stacks \
    --stack-name MedicalKgBudgetStack \
    --query 'Stacks[0].Outputs'
```

### 8. Destroy Stack (When Done)

```bash
# WARNING: This deletes all resources
cdk destroy

# With auto-approval
cdk destroy --force
```

## Useful CDK Commands

```bash
# List all stacks
cdk list

# Show differences between deployed and local
cdk diff

# Synthesize CloudFormation template
cdk synth

# Deploy with hotswap for faster development iterations
cdk deploy --hotswap

# Watch mode - auto-deploy on changes
cdk watch

# Show CloudFormation template
cdk synth > template.yaml
```

## Cost Estimation

Before deploying, estimate costs:

```bash
# Use AWS Cost Calculator or review the BOM
# Expected monthly cost: ~$50

# Main costs:
# - OpenSearch t3.small.search: ~$30/month
# - VPC Endpoints: ~$15/month
# - S3: ~$1/month
# - CloudWatch: ~$2/month
# - Secrets Manager: ~$1/month
# - Lambda: Free tier (likely $0-2/month)
```

## Monitoring Costs

```bash
# Set up billing alarm (recommended!)
aws cloudwatch put-metric-alarm \
    --alarm-name medical-kg-budget-exceeded \
    --alarm-description "Alert when monthly costs exceed $60" \
    --metric-name EstimatedCharges \
    --namespace AWS/Billing \
    --statistic Maximum \
    --period 21600 \
    --evaluation-periods 1 \
    --threshold 60 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=Currency,Value=USD
```

## Troubleshooting

### OpenSearch Domain Creation Fails

```bash
# Check service quotas
aws service-quotas get-service-quota \
    --service-code opensearch \
    --quota-code L-11 A58E4F

# Request quota increase if needed
```

### VPC Endpoint Issues

```bash
# Verify VPC endpoints are created
aws ec2 describe-vpc-endpoints

# Check security groups
aws ec2 describe-security-groups
```

### Lambda Can't Access OpenSearch

```bash
# Check Lambda is in correct VPC/subnets
aws lambda get-function-configuration \
    --function-name medical-kg-ingestion

# Check security group rules
aws ec2 describe-security-group-rules
```

## Next Steps After Deployment

1. Upload test papers to S3:
   ```bash
   aws s3 cp papers/raw/PMC123456.xml \
       s3://YOUR-BUCKET-NAME/raw/
   ```

2. Check Lambda logs:
   ```bash
   aws logs tail /aws/lambda/YOUR-FUNCTION-NAME --follow
   ```

3. Query OpenSearch:
   ```bash
   # Get endpoint from CDK outputs
   curl -X GET "https://YOUR-OPENSEARCH-ENDPOINT/_cat/indices?v" \
       -u admin:YOUR-PASSWORD
   ```

4. Monitor costs:
   ```bash
   aws ce get-cost-and-usage \
       --time-period Start=2024-01-01,End=2024-01-31 \
       --granularity MONTHLY \
       --metrics BlendedCost
   ```
