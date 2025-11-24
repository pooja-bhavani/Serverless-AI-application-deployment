import json
import boto3
import uuid
import time
import os
from datetime import datetime

def handler(event, context):
    """
    Lambda function for AI language translation
    """
    try:
        # Parse request body
        body = json.loads(event['body']) if event.get('body') else {}
        
        text_to_translate = body.get('text_to_translate', '')
        source_language = body.get('source_language', 'Auto-Detect')
        target_language = body.get('target_language', 'English')
        translation_style = body.get('translation_style', 'Standard')
        
        # Initialize AWS clients
        bedrock = boto3.client('bedrock-runtime')
        dynamodb = boto3.resource('dynamodb')
        
        # Get environment variables
        table_name = os.environ['TABLE_NAME']
        model_id = os.environ['BEDROCK_MODEL_ID']
        
        # Generate transform ID
        transform_id = str(uuid.uuid4())
        timestamp = int(time.time())
        
        # Create AI prompt for translation
        prompt = f"""
        Translate the following text from {source_language} to {target_language}.
        
        Translation requirements:
        - Style: {translation_style}
        - Maintain original meaning and context
        - Use natural, fluent language in the target language
        - Preserve any technical terms appropriately
        
        Text to translate: "{text_to_translate}"
        
        Provide only the translated text without any additional commentary.
        """
        
        # Call Bedrock AI model
        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps({
                'prompt': prompt,
                'max_tokens_to_sample': 1000,
                'temperature': 0.3
            })
        )
        
        # Parse AI response
        ai_response = json.loads(response['body'].read())
        translated_text = ai_response.get('completion', '').strip()
        
        # Calculate confidence score (mock for demo)
        confidence_score = 94.5
        
        # Store result in DynamoDB
        table = dynamodb.Table(table_name)
        table.put_item(
            Item={
                'transformId': transform_id,
                'timestamp': timestamp,
                'transformationType': 'translation',
                'source_language': source_language,
                'target_language': target_language,
                'translation_style': translation_style,
                'original_text': text_to_translate,
                'translated_text': translated_text,
                'confidence_score': confidence_score,
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
                'message': 'Translation completed successfully',
                'original_text': text_to_translate,
                'translated_text': translated_text,
                'source_language': source_language,
                'target_language': target_language,
                'confidence_score': confidence_score
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