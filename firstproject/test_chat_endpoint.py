"""
Test the chat endpoint to see actual errors
"""
import os
import django
import sys
import traceback

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import RequestFactory
from medical_imaging.ai_chat_view import chat_stream
import json

try:
    # Create a mock request
    factory = RequestFactory()
    request = factory.post(
        '/api/ai/chat/stream/',
        data=json.dumps({'message': 'How many patients are there?'}),
        content_type='application/json'
    )

    # Call the view
    print("Calling chat_stream view...")
    response = chat_stream(request)

    print(f"Response type: {type(response)}")
    print(f"Response status: {getattr(response, 'status_code', 'N/A')}")

    # Try to get streaming content
    if hasattr(response, 'streaming_content'):
        print("\nStreaming response:")
        for chunk in response.streaming_content:
            print(chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk)
    else:
        print(f"\nResponse content: {response.content}")

except Exception as e:
    print(f"\nERROR: {type(e).__name__}: {str(e)}")
    print("\nFull traceback:")
    traceback.print_exc()
