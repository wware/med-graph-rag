#!/usr/bin/env python3
"""
Cost-Optimized CDK Stack for Medical Knowledge Graph POC

Target cost: ~$50/month
- Single small OpenSearch node
- No Neptune (store graph in OpenSearch)
- VPC endpoints instead of NAT Gateway
- Lambda-based processing
- Minimal infrastructure
"""

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_opensearchservice as opensearch,
    aws_ec2 as ec2,
    aws_s3 as s3,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    aws_ssm as ssm,
    aws_logs as logs,
    RemovalPolicy,
    Duration,
    CfnOutput,
)
from constructs import Construct


class MedicalKgBudgetStack(Stack):
    """Budget-optimized stack for Medical Knowledge Graph POC"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ================================================================
        # VPC Configuration
        # ================================================================
        
        # Create VPC with minimal infrastructure
        # Using public subnets to avoid NAT Gateway costs
        self.vpc = ec2.Vpc(
            self,
            "MedicalKgVpc",
            max_azs=2,  # Use 2 AZs for some redundancy
            nat_gateways=0,  # No NAT Gateway - save $45/month
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

        # VPC Endpoints for cost savings (avoid NAT Gateway)
        # S3 Gateway endpoint (free)
        self.vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
        )

        # Bedrock Interface endpoint ($7.50/month but saves on data transfer)
        bedrock_endpoint = self.vpc.add_interface_endpoint(
            "BedrockEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.BEDROCK_RUNTIME,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
        )

        # ================================================================
        # S3 Buckets
        # ================================================================

        # Bucket for papers and data
        self.papers_bucket = s3.Bucket(
            self,
            "PapersBucket",
            bucket_name=f"medical-kg-papers-{self.account}-{self.region}",
            versioned=False,  # Save costs for POC
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,  # Keep data if stack deleted
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ArchiveOldPapers",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90),
                        )
                    ],
                )
            ],
        )

        # ================================================================
        # OpenSearch Domain (Single Small Instance)
        # ================================================================

        # Security group for OpenSearch
        opensearch_sg = ec2.SecurityGroup(
            self,
            "OpenSearchSG",
            vpc=self.vpc,
            description="Security group for OpenSearch domain",
            allow_all_outbound=True,
        )

        # Allow access from Lambda (will be added later)
        opensearch_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS from VPC",
        )

        # Create OpenSearch domain with minimal configuration
        self.opensearch_domain = opensearch.Domain(
            self,
            "OpenSearchDomain",
            domain_name="medical-kg-poc",
            version=opensearch.EngineVersion.OPENSEARCH_2_11,
            # COST OPTIMIZATION: Single small instance
            capacity=opensearch.CapacityConfig(
                data_node_instance_type="t3.small.search",  # ~$30/month
                data_nodes=1,  # Single node (no HA for POC)
            ),
            ebs=opensearch.EbsOptions(
                volume_size=10,  # 10GB for ~1000-5000 papers
                volume_type=ec2.EbsDeviceVolumeType.GP3,
            ),
            # Network configuration
            vpc=self.vpc,
            vpc_subnets=[
                ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED)
            ],
            security_groups=[opensearch_sg],
            # Remove public access
            enforce_https=True,
            node_to_node_encryption=True,
            encryption_at_rest=opensearch.EncryptionAtRestOptions(enabled=True),
            # Fine-grained access control
            fine_grained_access_control=opensearch.AdvancedSecurityOptions(
                master_user_name="admin"
            ),
            # Logging (minimal to save costs)
            logging=opensearch.LoggingOptions(
                slow_search_log_enabled=False,  # Disable to save costs
                app_log_enabled=True,
                slow_index_log_enabled=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,  # Can recreate for POC
        )

        # ================================================================
        # IAM Roles
        # ================================================================

        # Lambda execution role
        lambda_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaVPCAccessExecutionRole"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )

        # Grant OpenSearch access
        self.opensearch_domain.grant_read_write(lambda_role)

        # Grant S3 access
        self.papers_bucket.grant_read_write(lambda_role)

        # Grant Bedrock access
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v2:0",
                    f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
                ],
            )
        )

        # ================================================================
        # Lambda Functions
        # ================================================================

        # Lambda layer with dependencies
        dependencies_layer = lambda_.LayerVersion(
            self,
            "DependenciesLayer",
            code=lambda_.Code.from_asset("lambda_layer.zip"),  # You'll need to create this
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="Python dependencies for medical-kg functions",
        )

        # Paper ingestion Lambda
        ingestion_function = lambda_.Function(
            self,
            "IngestionFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="ingestion.handler",
            code=lambda_.Code.from_asset("lambda/ingestion"),  # Your code directory
            role=lambda_role,
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            security_groups=[opensearch_sg],
            timeout=Duration.minutes(15),  # Max timeout
            memory_size=2048,  # 2GB for processing
            environment={
                "OPENSEARCH_ENDPOINT": self.opensearch_domain.domain_endpoint,
                "PAPERS_BUCKET": self.papers_bucket.bucket_name,
                "AWS_REGION": self.region,
            },
            layers=[dependencies_layer],
            log_retention=logs.RetentionDays.ONE_WEEK,  # Reduce log costs
        )

        # S3 trigger for ingestion
        self.papers_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(ingestion_function),
            s3.NotificationKeyFilter(prefix="raw/", suffix=".xml"),
        )

        # ================================================================
        # Secrets Manager
        # ================================================================

        # Store OpenSearch credentials
        opensearch_secret = secretsmanager.Secret(
            self,
            "OpenSearchSecret",
            secret_name="medical-kg/opensearch",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username":"admin"}',
                generate_string_key="password",
                exclude_characters='/@"',
            ),
        )

        # Grant Lambda access to secrets
        opensearch_secret.grant_read(lambda_role)

        # ================================================================
        # SSM Parameters (for non-sensitive config)
        # ================================================================

        ssm.StringParameter(
            self,
            "OpenSearchEndpoint",
            parameter_name="/medical-kg/opensearch/endpoint",
            string_value=self.opensearch_domain.domain_endpoint,
        )

        ssm.StringParameter(
            self,
            "PapersBucket",
            parameter_name="/medical-kg/s3/papers-bucket",
            string_value=self.papers_bucket.bucket_name,
        )

        # ================================================================
        # CloudWatch Alarms (Cost Control)
        # ================================================================

        # Alarm for high OpenSearch disk usage
        self.opensearch_domain.metric_free_storage_space().create_alarm(
            self,
            "OpenSearchLowDiskSpace",
            threshold=1000,  # 1GB
            evaluation_periods=1,
            alarm_description="OpenSearch disk space below 1GB",
        )

        # ================================================================
        # Outputs
        # ================================================================

        CfnOutput(
            self,
            "OpenSearchDomainEndpoint",
            value=f"https://{self.opensearch_domain.domain_endpoint}",
            description="OpenSearch domain endpoint",
        )

        CfnOutput(
            self,
            "PapersBucketName",
            value=self.papers_bucket.bucket_name,
            description="S3 bucket for papers",
        )

        CfnOutput(
            self,
            "OpenSearchDashboardsURL",
            value=f"https://{self.opensearch_domain.domain_endpoint}/_dashboards",
            description="OpenSearch Dashboards URL",
        )

        CfnOutput(
            self,
            "IngestionFunctionName",
            value=ingestion_function.function_name,
            description="Ingestion Lambda function name",
        )

        # ================================================================
        # Tags (for cost tracking)
        # ================================================================

        cdk.Tags.of(self).add("Project", "medical-knowledge-graph")
        cdk.Tags.of(self).add("Environment", "poc")
        cdk.Tags.of(self).add("ManagedBy", "cdk")
        cdk.Tags.of(self).add("CostCenter", "research")


# ================================================================
# App Definition
# ================================================================

app = cdk.App()

MedicalKgBudgetStack(
    app,
    "MedicalKgBudgetStack",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1",
    ),
    description="Budget POC stack for Medical Knowledge Graph (~$50/month)",
)

app.synth()
