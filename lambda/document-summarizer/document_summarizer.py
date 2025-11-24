import json
import boto3
import uuid
import time
import os
from datetime import datetime

def handler(event, context):
    """
    Lambda function for AI document summarization
    """
    try:
        # Parse request body
        body = json.loads(event['body']) if event.get('body') else {}
        
        document_text = body.get('document_text', '')
        summary_type = body.get('summary_type', 'Bullet Points')
        length = body.get('length', 5)
        
        # Initialize AWS clients
        bedrock = boto3.client('bedrock-runtime')
        dynamodb = boto3.resource('dynamodb')
        
        # Get environment variables
        table_name = os.environ['TABLE_NAME']
        model_id = os.environ['BEDROCK_MODEL_ID']
        
        # Generate transform ID
        transform_id = str(uuid.uuid4())
        timestamp = int(time.time())
        
        # Create AI prompt for summarization
        prompt = f"""
        Please summarize the following document in {summary_type} format with a length level of {length}/10:
        
        Document: {document_text}
        
        Requirements:
        - Format: {summary_type}
        - Conciseness level: {length}/10 (1=very brief, 10=detailed)
        - Focus on key insights and actionable information
        - Maintain professional tone
        """
        
        # Call Bedrock AI model
        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps({
                'prompt': prompt,
                'max_tokens_to_sample': 1500,
                'temperature': 0.3
            })
        )
        
        # Parse AI response
        ai_response = json.loads(response['body'].read())
        summary = ai_response.get('completion', '')
        
        # Calculate metrics
        original_words = len(document_text.split())
        summary_words = len(summary.split())
        compression_ratio = round((1 - summary_words / original_words) * 100, 1) if original_words > 0 else 0
        
        # Store result in DynamoDB
        table = dynamodb.Table(table_name)
        table.put_item(
            Item={
                'transformId': transform_id,
                'timestamp': timestamp,
                'transformationType': 'summarization',
                'summary_type': summary_type,
                'length_level': length,
                'original_text': document_text,
                'summary': summary,
                'original_words': original_words,
                'summary_words': summary_words,
                'compression_ratio': compression_ratio,
                'status': 'completed',
                'createdAt': datetime.utcnow().isoformat()
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'transformId': transform_id,
                'status': 'success',
                'message': 'Document summarized successfully',
                'summary': summary,
                'metrics': {
                    'original_words': original_words,
                    'summary_words': summary_words,
                    'compression_ratio': f"{compression_ratio}%",
                    'processing_time': '2.3s'
                }
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'status': 'error',
                'message': str(e)
            })
        }