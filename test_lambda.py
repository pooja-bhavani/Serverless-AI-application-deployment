#!/usr/bin/env python3
"""
Test script for document summarizer Lambda function
"""
import json
import os
import sys
from unittest.mock import Mock, patch

# Add lambda directory to path
sys.path.append('/workspace/content-transformer-ai/lambda/document-summarizer')

# Set environment variables
os.environ['TABLE_NAME'] = 'content-transformer-table'
os.environ['BEDROCK_MODEL_ID'] = 'anthropic.claude-v2'

def create_mock_event():
    """Create a mock API Gateway event"""
    return {
        'body': json.dumps({
            'document_text': '''
            Artificial Intelligence (AI) is revolutionizing the way we work and live. 
            From automated customer service to predictive analytics, AI technologies 
            are being integrated into various industries. Machine learning algorithms 
            can process vast amounts of data to identify patterns and make predictions. 
            Natural language processing enables computers to understand and generate 
            human language. Computer vision allows machines to interpret visual information. 
            The future of AI holds immense potential for solving complex problems and 
            improving efficiency across multiple domains.
            ''',
            'summary_type': 'Bullet Points',
            'length': 5
        }),
        'headers': {
            'Content-Type': 'application/json'
        }
    }

def create_mock_context():
    """Create a mock Lambda context"""
    context = Mock()
    context.function_name = 'document-summarizer'
    context.function_version = '$LATEST'
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:document-summarizer'
    context.memory_limit_in_mb = 128
    context.remaining_time_in_millis = lambda: 30000
    return context

def mock_bedrock_response():
    """Mock Bedrock API response"""
    return {
        'body': Mock(read=lambda: json.dumps({
            'completion': '''
            • AI is transforming industries through automation and intelligent systems
            • Machine learning processes large datasets to identify patterns and predictions
            • Natural language processing enables human-computer communication
            • Computer vision allows machines to interpret visual data
            • AI holds significant potential for solving complex problems efficiently
            '''
        }).encode())
    }

def mock_dynamodb_table():
    """Mock DynamoDB table operations"""
    table = Mock()
    table.put_item = Mock(return_value={'ResponseMetadata': {'HTTPStatusCode': 200}})
    return table

def run_test():
    """Run the Lambda function test"""
    print("🚀 Testing Document Summarizer Lambda Function")
    print("=" * 50)
    
    # Import the handler after setting environment variables
    from document_summarizer import handler
    
    # Create mock objects
    event = create_mock_event()
    context = create_mock_context()
    
    print("📝 Input Document:")
    input_data = json.loads(event['body'])
    print(f"Text: {input_data['document_text'][:100]}...")
    print(f"Summary Type: {input_data['summary_type']}")
    print(f"Length: {input_data['length']}")
    print()
    
    # Mock AWS services
    with patch('boto3.client') as mock_bedrock_client, \
         patch('boto3.resource') as mock_dynamodb_resource:
        
        # Setup mocks
        mock_bedrock_client.return_value.invoke_model.return_value = mock_bedrock_response()
        mock_dynamodb_resource.return_value.Table.return_value = mock_dynamodb_table()
        
        try:
            # Call the Lambda handler
            response = handler(event, context)
            
            # Parse and display results
            print("✅ Lambda Function Response:")
            print(f"Status Code: {response['statusCode']}")
            
            if response['statusCode'] == 200:
                body = json.loads(response['body'])
                print(f"Transform ID: {body['transformId']}")
                print(f"Status: {body['status']}")
                print(f"Message: {body['message']}")
                print()
                print("📊 Summary:")
                print(body['summary'])
                print()
                print("📈 Metrics:")
                for key, value in body['metrics'].items():
                    print(f"  {key}: {value}")
            else:
                print("❌ Error occurred:")
                print(json.loads(response['body']))
                
        except Exception as e:
            print(f"❌ Test failed with error: {str(e)}")
            return False
    
    print("\n🎉 Test completed successfully!")
    return True

if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)