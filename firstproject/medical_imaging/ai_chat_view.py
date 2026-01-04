"""
AI Chat API View with OpenAI integration and streaming support.
"""
import json
import os
import logging
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from decouple import config
from openai import OpenAI
from rest_framework.decorators import api_view, throttle_classes, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from .throttling import AIQueryRateThrottle
from .ai_tools import TOOLS, TOOL_HANDLERS

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

# OpenAI model to use for chat completions
# Can be overridden via environment variable OPENAI_MODEL in .env file
# Default is 'gpt-5-nano' - change to 'gpt-4', 'gpt-4-turbo', etc. as needed
OPENAI_MODEL = config('OPENAI_MODEL', default='gpt-5-nano')


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication without CSRF enforcement.

    Used for AI chat endpoints that are already protected by session authentication.
    CSRF checks can interfere with API endpoints that use session cookies.

    Note: Only use this for endpoints that have other security measures in place
    (like rate limiting and authentication).
    """
    def enforce_csrf(self, request):
        # Override parent method to skip CSRF validation
        return  # Do nothing - no CSRF check


# System prompt for the AI assistant
SYSTEM_PROMPT = """You are a helpful medical imaging database assistant.
You have access to tools to query patients, hospitals, imaging studies, and statistics.

When answering questions:
1. Use the appropriate tools to get accurate data from the database
2. If a tool call fails, analyze the error and retry with adjusted parameters
3. Present information clearly and concisely
4. For numeric questions (like "how many"), always call the appropriate tool to get exact counts
5. When listing items, respect the limit parameter (default 10) and mention if there are more results

Available tools:
- get_patients: Query patients by gender, hospital, etc.
- get_hospitals: Query hospitals by name
- get_studies: Query imaging studies by patient, modality, status, date
- get_statistics: Get aggregate counts and breakdowns

Always be helpful and provide context with your answers.
"""


# ============================================================================
# Helper Functions (DRY)
# ============================================================================

def get_openai_client():
    """
    Get configured OpenAI client instance.
    Centralizes API key retrieval and validation.

    Returns:
        OpenAI: Configured client instance

    Raises:
        ValueError: If API key is not configured
    """
    # Read API key from environment variable or .env file
    # config() comes from python-decouple library
    api_key = config('OPENAI_API_KEY', default=None)

    # Validate that a real API key is configured
    # Reject default placeholder values
    if not api_key or api_key == 'your-openai-api-key-here':
        raise ValueError('OpenAI API key not configured')

    # Return configured OpenAI client
    return OpenAI(api_key=api_key)


def parse_chat_request(request):
    """
    Parse and validate chat request body.

    Args:
        request: Django request object

    Returns:
        tuple: (user_message, history) if valid, or (None, error_response) if invalid
    """
    try:
        # Parse JSON from request body
        data = json.loads(request.body)

        # Extract message and conversation history
        user_message = data.get('message', '').strip()  # Remove leading/trailing whitespace
        history = data.get('history', [])  # Previous messages, defaults to empty list

        # Validate that message is not empty
        if not user_message:
            return None, JsonResponse(
                {'error': 'Message is required'},
                status=400  # Bad Request
            )

        # Return parsed data and no error
        return (user_message, history), None

    except json.JSONDecodeError:
        # Handle invalid JSON in request body
        return None, JsonResponse(
            {'error': 'Invalid JSON in request body'},
            status=400
        )


def build_messages(user_message, history):
    """
    Build OpenAI messages array from user message and history.

    OpenAI's chat API expects messages in this format:
    [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        ...
    ]

    Args:
        user_message: Current user message string
        history: Previous conversation messages (list of message dicts)

    Returns:
        list: Complete messages array for OpenAI API
    """
    # Start with system prompt - this guides the AI's behavior
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    # Add conversation history if it exists
    # This gives the AI context about previous exchanges
    if history:
        messages.extend(history)

    # Add the current user message
    messages.append({
        "role": "user",
        "content": user_message
    })

    return messages


@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
@throttle_classes([AIQueryRateThrottle])
def chat_stream(request):
    """
    AI Chat endpoint with streaming support.

    Expected request body:
    {
        "message": "How many patients are there?",
        "history": [...]  // Optional previous messages
    }
    """
    # Debug logging
    logger.info(f"Chat stream request - User: {request.user}, Authenticated: {request.user.is_authenticated}")
    logger.info(f"Session key: {request.session.session_key}")
    logger.info(f"Cookies: {request.COOKIES.keys()}")

    # Parse and validate request
    result, error_response = parse_chat_request(request)
    if error_response:
        return error_response

    user_message, history = result

    # Get OpenAI client
    try:
        client = get_openai_client()
    except ValueError as e:
        return JsonResponse(
            {'error': str(e)},
            status=500
        )

    # Build messages
    messages = build_messages(user_message, history)

    # Generator function for streaming response to client
    # This function yields data chunks as Server-Sent Events (SSE)
    def generate():
        # Prevent infinite loops - limit to 10 AI->tool->AI cycles
        max_iterations = 10
        current_iteration = 0

        # Main loop: AI generates response, calls tools, generates more, etc.
        while current_iteration < max_iterations:
            current_iteration += 1

            # Request streaming response from OpenAI
            # stream=True makes the API return chunks incrementally instead of all at once
            stream = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,  # Conversation history including system prompt
                tools=TOOLS,  # Available function tools the AI can call
                stream=True,  # Enable streaming mode
            )

            # Initialize variables to accumulate streaming chunks
            tool_calls = []  # List of tools the AI wants to call
            current_tool_call = None  # Currently being built tool call
            assistant_message = {"role": "assistant", "content": ""}  # AI's text response
            finish_reason = None  # Why the AI stopped (e.g., 'stop', 'tool_calls')

            # Process each chunk from the stream
            for chunk in stream:
                # delta contains the incremental changes in this chunk
                delta = chunk.choices[0].delta
                # finish_reason tells us why the stream ended (if it did)
                finish_reason = chunk.choices[0].finish_reason

                # Handle text content chunks
                # If the AI is writing a text response, we get it piece by piece
                if delta.content:
                    assistant_message["content"] += delta.content
                    # Send this chunk to the client immediately via Server-Sent Events
                    # Format: "data: {json}\n\n"
                    yield f"data: {json.dumps({'type': 'content', 'content': delta.content})}\n\n"

                # Handle tool call chunks
                # When the AI wants to call a function, we receive it in pieces too
                if delta.tool_calls:
                    # AI can call multiple tools at once, each has an index
                    for tool_call_delta in delta.tool_calls:
                        if tool_call_delta.index is not None:
                            # Ensure we have a placeholder for this tool call index
                            # If this is the first chunk for tool_call[2], we need to create slots [0], [1], [2]
                            while len(tool_calls) <= tool_call_delta.index:
                                tool_calls.append({
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""}
                                })

                            # Get reference to the tool call we're building
                            current_tool_call = tool_calls[tool_call_delta.index]

                            # Accumulate the tool call ID (comes in first chunk)
                            if tool_call_delta.id:
                                current_tool_call["id"] = tool_call_delta.id

                            # Accumulate function details
                            if tool_call_delta.function:
                                # Function name (comes early)
                                if tool_call_delta.function.name:
                                    current_tool_call["function"]["name"] = tool_call_delta.function.name
                                # Function arguments come as JSON string chunks - append them
                                if tool_call_delta.function.arguments:
                                    current_tool_call["function"]["arguments"] += tool_call_delta.function.arguments

            # If we have content, send it
            if assistant_message["content"]:
                messages.append(assistant_message)

                # If finish_reason is 'stop', we're done
                if finish_reason == "stop":
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return

            # If AI requested tool calls, execute them
            if tool_calls and finish_reason == "tool_calls":
                # Add the assistant's tool call request to conversation history
                # This is required for OpenAI's API - it needs to see the full conversation flow
                assistant_tool_message = {
                    "role": "assistant",
                    "content": None,  # No text content, just tool calls
                    "tool_calls": tool_calls
                }
                messages.append(assistant_tool_message)

                # Execute each tool the AI requested
                for tool_call in tool_calls:
                    function_name = tool_call["function"]["name"]
                    # Parse JSON arguments string into Python dict
                    function_args = json.loads(tool_call["function"]["arguments"])

                    # Notify client that we're calling a tool
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': function_name, 'args': function_args})}\n\n"

                    # Execute the actual tool function
                    try:
                        # Look up the handler function by name
                        handler = TOOL_HANDLERS.get(function_name)
                        if handler:
                            # Call it with the parsed arguments
                            tool_output = handler(function_args)
                        else:
                            tool_output = {"error": f"Unknown tool: {function_name}"}
                    except Exception as e:
                        # If tool execution fails, return error to AI
                        tool_output = {"error": f"Tool execution error: {str(e)}"}

                    # Send tool results to client for display
                    yield f"data: {json.dumps({'type': 'tool_output', 'name': function_name, 'output': tool_output})}\n\n"

                    # Add tool result to conversation history
                    # The AI will see this result in the next iteration and formulate a response
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],  # Match the original request
                        "content": json.dumps(tool_output)  # Tool result as JSON string
                    })

                # Continue the loop - AI will now see the tool results and generate a response
                continue

            # If we got here with stop, we're done
            if finish_reason == "stop":
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

        # Max iterations reached
        yield f"data: {json.dumps({'type': 'error', 'message': 'Max iterations reached'})}\n\n"

    # Return streaming response using Server-Sent Events (SSE)
    try:
        response = StreamingHttpResponse(
            generate(),  # Our generator function
            content_type='text/event-stream'  # SSE content type
        )
        # Prevent caching of streaming responses
        response['Cache-Control'] = 'no-cache'
        # Disable buffering in nginx (if used as reverse proxy)
        response['X-Accel-Buffering'] = 'no'
        return response
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Stream error: {str(e)}")
        return JsonResponse(
            {'error': f'Server error: {str(e)}'},
            status=500
        )


@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
@throttle_classes([AIQueryRateThrottle])
def chat(request):
    """
    Non-streaming chat endpoint for simple requests.

    Expected request body:
    {
        "message": "How many patients are there?",
        "history": [...]  // Optional previous messages
    }
    """
    # Parse and validate request
    result, error_response = parse_chat_request(request)
    if error_response:
        return error_response

    user_message, history = result

    # Get OpenAI client
    try:
        client = get_openai_client()
    except ValueError as e:
        return JsonResponse(
            {'error': str(e)},
            status=500
        )

    # Build messages
    messages = build_messages(user_message, history)

    # Circuit breaker - prevent infinite loops
    # If AI keeps calling tools repeatedly, stop after 10 iterations
    max_iterations = 10
    current_iteration = 0

    try:
        # Main loop: AI responds, calls tools, responds again, etc.
        while current_iteration < max_iterations:
            current_iteration += 1

            # Get completion from OpenAI (non-streaming)
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,  # Full conversation history
                tools=TOOLS,  # Available function tools
            )

            # Extract the AI's response
            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason  # 'stop' or 'tool_calls'

            # Add AI's message to conversation history
            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": message.tool_calls if hasattr(message, 'tool_calls') else None
            })

            # If AI finished without calling tools, return the final response
            if finish_reason == "stop":
                return JsonResponse({
                    'message': message.content,
                    'history': messages[1:],  # Exclude system prompt from returned history
                    'usage': {  # Token usage stats for billing/monitoring
                        'prompt_tokens': response.usage.prompt_tokens,  # Input tokens
                        'completion_tokens': response.usage.completion_tokens,  # Output tokens
                        'total_tokens': response.usage.total_tokens,  # Total
                    }
                })

            # Execute tool calls if AI requested them
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    # Extract function name and arguments
                    function_name = tool_call.function.name
                    # Arguments come as JSON string, parse into dict
                    function_args = json.loads(tool_call.function.arguments)

                    # Execute the requested tool
                    try:
                        # Look up the handler function
                        handler = TOOL_HANDLERS.get(function_name)
                        if handler:
                            # Call the function with validated arguments
                            tool_output = handler(function_args)
                        else:
                            # Unknown tool requested
                            tool_output = {"error": f"Unknown tool: {function_name}"}
                    except Exception as e:
                        # Tool execution failed
                        tool_output = {"error": f"Tool execution error: {str(e)}"}

                    # Add tool result to conversation history
                    # AI will see this in next iteration and can use it in response
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,  # Match to original request
                        "content": json.dumps(tool_output)  # Result as JSON string
                    })

        # If we exit the loop, max iterations was reached
        # This means AI kept calling tools without giving a final answer
        return JsonResponse(
            {'error': 'Max iterations reached without final response'},
            status=500  # Internal Server Error
        )
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return JsonResponse(
            {'error': f'Server error: {str(e)}'},
            status=500
        )
