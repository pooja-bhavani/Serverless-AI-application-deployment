from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_iam as iam,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    Duration,
    CfnOutput,
    RemovalPolicy
)
from constructs import Construct

class ContentTransformerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # S3 Bucket for content storage
        content_bucket = s3.Bucket(
            self, "ContentBucket",
            bucket_name=f"content-transformer-bucket-{self.account}",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            cors=[s3.CorsRule(
                allowed_methods=[s3.HttpMethods.GET, s3.HttpMethods.POST, s3.HttpMethods.PUT],
                allowed_origins=["*"],
                allowed_headers=["*"]
            )]
        )

        # DynamoDB table for transformation results
        transform_table = dynamodb.Table(
            self, "TransformTable",
            table_name="content-transformation-results",
            partition_key=dynamodb.Attribute(
                name="transformId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.NUMBER
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        # IAM Role for Lambda with Bedrock access
        lambda_role = iam.Role(
            self, "ContentTransformerLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "BedrockAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:ListFoundationModels",
                                "bedrock:GetFoundationModel"
                            ],
                            resources=["*"]
                        )
                    ]
                ),
                "S3Access": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:DeleteObject"
                            ],
                            resources=[f"{content_bucket.bucket_arn}/*"]
                        )
                    ]
                )
            }
        )

        # Grant DynamoDB permissions
        transform_table.grant_read_write_data(lambda_role)

        # Lambda Layer for dependencies
        dependencies_layer = _lambda.LayerVersion(
            self, "ContentTransformerDependenciesLayer",
            code=_lambda.Code.from_asset("lambda_layer"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_9],
            description="Content Transformer dependencies"
        )

        # Lambda Functions
        summarizer_lambda = _lambda.Function(
            self, "DocumentSummarizerFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="document_summarizer.handler",
            code=_lambda.Code.from_asset("lambda/document-summarizer"),
            role=lambda_role,
            timeout=Duration.seconds(120),
            memory_size=1024,
            environment={
                "BUCKET_NAME": content_bucket.bucket_name,
                "TABLE_NAME": transform_table.table_name,
                "BEDROCK_MODEL_ID": "anthropic.claude-v2"
            },
            layers=[dependencies_layer]
        )

        translator_lambda = _lambda.Function(
            self, "LanguageTranslatorFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="language_translator.handler",
            code=_lambda.Code.from_asset("lambda/language-translator"),
            role=lambda_role,
            timeout=Duration.seconds(120),
            memory_size=1024,
            environment={
                "TABLE_NAME": transform_table.table_name,
                "BEDROCK_MODEL_ID": "anthropic.claude-v2"
            },
            layers=[dependencies_layer]
        )

        converter_lambda = _lambda.Function(
            self, "FormatConverterFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="format_converter.handler",
            code=_lambda.Code.from_asset("lambda/format-converter"),
            role=lambda_role,
            timeout=Duration.seconds(180),
            memory_size=2048,
            environment={
                "BUCKET_NAME": content_bucket.bucket_name,
                "TABLE_NAME": transform_table.table_name,
                "BEDROCK_MODEL_ID": "anthropic.claude-v2"
            },
            layers=[dependencies_layer]
        )

        rewriter_lambda = _lambda.Function(
            self, "StyleRewriterFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="style_rewriter.handler",
            code=_lambda.Code.from_asset("lambda/style-rewriter"),
            role=lambda_role,
            timeout=Duration.seconds(120),
            memory_size=1024,
            environment={
                "TABLE_NAME": transform_table.table_name,
                "BEDROCK_MODEL_ID": "anthropic.claude-v2"
            },
            layers=[dependencies_layer]
        )

        repurposer_lambda = _lambda.Function(
            self, "ContentRepurposerFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="content_repurposer.handler",
            code=_lambda.Code.from_asset("lambda/content-repurposer"),
            role=lambda_role,
            timeout=Duration.seconds(180),
            memory_size=1536,
            environment={
                "TABLE_NAME": transform_table.table_name,
                "BEDROCK_MODEL_ID": "anthropic.claude-v2"
            },
            layers=[dependencies_layer]
        )

        # API Gateway
        api = apigw.RestApi(
            self, "ContentTransformerAPI",
            rest_api_name="Content Transformer AI API",
            description="AI-powered content transformation services",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key"]
            )
        )

        # API Resources and Methods
        # Document Summarizer endpoint
        summarize_resource = api.root.add_resource("summarize")
        summarize_resource.add_method(
            "POST",
            apigw.LambdaIntegration(summarizer_lambda),
            method_responses=[
                apigw.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                        "method.response.header.Access-Control-Allow-Headers": True
                    }
                )
            ]
        )

        # Language Translator endpoint
        translate_resource = api.root.add_resource("translate")
        translate_resource.add_method(
            "POST",
            apigw.LambdaIntegration(translator_lambda),
            method_responses=[
                apigw.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                        "method.response.header.Access-Control-Allow-Headers": True
                    }
                )
            ]
        )

        # Format Converter endpoint
        convert_resource = api.root.add_resource("convert")
        convert_resource.add_method(
            "POST",
            apigw.LambdaIntegration(converter_lambda),
            method_responses=[
                apigw.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                        "method.response.header.Access-Control-Allow-Headers": True
                    }
                )
            ]
        )

        # Style Rewriter endpoint
        rewrite_resource = api.root.add_resource("rewrite")
        rewrite_resource.add_method(
            "POST",
            apigw.LambdaIntegration(rewriter_lambda),
            method_responses=[
                apigw.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                        "method.response.header.Access-Control-Allow-Headers": True
                    }
                )
            ]
        )

        # Content Repurposer endpoint
        repurpose_resource = api.root.add_resource("repurpose")
        repurpose_resource.add_method(
            "POST",
            apigw.LambdaIntegration(repurposer_lambda),
            method_responses=[
                apigw.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                        "method.response.header.Access-Control-Allow-Headers": True
                    }
                )
            ]
        )

        # Health check endpoint
        health_resource = api.root.add_resource("health")
        health_resource.add_method(
            "GET",
            apigw.MockIntegration(
                integration_responses=[
                    apigw.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": '{"status": "healthy", "service": "Content Transformer AI API"}'
                        }
                    )
                ],
                request_templates={
                    "application/json": '{"statusCode": 200}'
                }
            ),
            method_responses=[
                apigw.MethodResponse(status_code="200")
            ]
        )

        # Outputs
        CfnOutput(
            self, "APIEndpoint",
            value=api.url,
            description="Content Transformer AI API Gateway endpoint"
        )

        CfnOutput(
            self, "BucketName",
            value=content_bucket.bucket_name,
            description="S3 bucket for content storage"
        )

        CfnOutput(
            self, "TableName",
            value=transform_table.table_name,
            description="DynamoDB table for transformation results"
        )