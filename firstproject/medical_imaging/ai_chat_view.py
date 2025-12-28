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
# Can be overridden via environment variable OPENAI_MODEL
OPENAI_MODEL = config('OPENAI_MODEL', default='gpt-4-turbo-preview')


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication without CSRF enforcement.
    Used for AI chat endpoints that are already protected by session authentication.
    """
    def enforce_csrf(self, request):
        return  # Skip CSRF check


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
    api_key = config('OPENAI_API_KEY', default=None)
    if not api_key or api_key == 'your-openai-api-key-here':
        raise ValueError('OpenAI API key not configured')
    return OpenAI(api_key=api_key)


def parse_chat_request(request):
    """
    Parse and validate chat request body.

    Args:
        request: Django request object

    Returns:
        tuple: (user_message, history) if valid
        JsonResponse: Error response if invalid
    """
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        history = data.get('history', [])

        if not user_message:
            return None, JsonResponse(
                {'error': 'Message is required'},
                status=400
            )

        return (user_message, history), None

    except json.JSONDecodeError:
        return None, JsonResponse(
            {'error': 'Invalid JSON in request body'},
            status=400
        )


def build_messages(user_message, history):
    """
    Build OpenAI messages array from user message and history.

    Args:
        user_message: Current user message
        history: Previous conversation messages

    Returns:
        list: Messages array for OpenAI API
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    if history:
        messages.extend(history)

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

    # Generator function for streaming
    def generate():
        max_iterations = 10
        current_iteration = 0

        while current_iteration < max_iterations:
            current_iteration += 1

            # Stream completion from OpenAI
            stream = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                tools=TOOLS,
                stream=True,
            )

            # Variables to collect tool calls
            tool_calls = []
            current_tool_call = None
            assistant_message = {"role": "assistant", "content": ""}
            finish_reason = None

            # Process the stream
            for chunk in stream:
                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason

                # Handle content (text response)
                if delta.content:
                    assistant_message["content"] += delta.content
                    # Send content chunk to client
                    yield f"data: {json.dumps({'type': 'content', 'content': delta.content})}\n\n"

                # Handle tool calls
                if delta.tool_calls:
                    for tool_call_delta in delta.tool_calls:
                        if tool_call_delta.index is not None:
                            # Ensure we have a tool_call object at this index
                            while len(tool_calls) <= tool_call_delta.index:
                                tool_calls.append({
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""}
                                })

                            current_tool_call = tool_calls[tool_call_delta.index]

                            if tool_call_delta.id:
                                current_tool_call["id"] = tool_call_delta.id

                            if tool_call_delta.function:
                                if tool_call_delta.function.name:
                                    current_tool_call["function"]["name"] = tool_call_delta.function.name
                                if tool_call_delta.function.arguments:
                                    current_tool_call["function"]["arguments"] += tool_call_delta.function.arguments

            # If we have content, send it
            if assistant_message["content"]:
                messages.append(assistant_message)

                # If finish_reason is 'stop', we're done
                if finish_reason == "stop":
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return

            # If we have tool calls, execute them
            if tool_calls and finish_reason == "tool_calls":
                # Add assistant message with tool calls
                assistant_tool_message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_calls
                }
                messages.append(assistant_tool_message)

                # Execute each tool call
                for tool_call in tool_calls:
                    function_name = tool_call["function"]["name"]
                    function_args = json.loads(tool_call["function"]["arguments"])

                    # Send tool call info to client
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': function_name, 'args': function_args})}\n\n"

                    # Execute the tool
                    try:
                        handler = TOOL_HANDLERS.get(function_name)
                        if handler:
                            tool_output = handler(function_args)
                        else:
                            tool_output = {"error": f"Unknown tool: {function_name}"}
                    except Exception as e:
                        tool_output = {"error": f"Tool execution error: {str(e)}"}

                    # Send tool output to client
                    yield f"data: {json.dumps({'type': 'tool_output', 'name': function_name, 'output': tool_output})}\n\n"

                    # Add tool response to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(tool_output)
                    })

                # Continue loop to get next response
                continue

            # If we got here with stop, we're done
            if finish_reason == "stop":
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

        # Max iterations reached
        yield f"data: {json.dumps({'type': 'error', 'message': 'Max iterations reached'})}\n\n"

    # Return streaming response
    try:
        response = StreamingHttpResponse(
            generate(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
    except Exception as e:
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

    # Circuit breaker
    max_iterations = 10
    current_iteration = 0

    try:
        while current_iteration < max_iterations:
            current_iteration += 1

            # Get completion from OpenAI
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                tools=TOOLS,
            )

            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            # Add assistant message to history
            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": message.tool_calls if hasattr(message, 'tool_calls') else None
            })

            # If no tool calls, return the response
            if finish_reason == "stop":
                return JsonResponse({
                    'message': message.content,
                    'history': messages[1:],  # Exclude system prompt
                    'usage': {
                        'prompt_tokens': response.usage.prompt_tokens,
                        'completion_tokens': response.usage.completion_tokens,
                        'total_tokens': response.usage.total_tokens,
                    }
                })

            # Execute tool calls
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    # Execute the tool
                    try:
                        handler = TOOL_HANDLERS.get(function_name)
                        if handler:
                            tool_output = handler(function_args)
                        else:
                            tool_output = {"error": f"Unknown tool: {function_name}"}
                    except Exception as e:
                        tool_output = {"error": f"Tool execution error: {str(e)}"}

                    # Add tool response to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_output)
                    })

        # Max iterations reached
        return JsonResponse(
            {'error': 'Max iterations reached without final response'},
            status=500
        )
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return JsonResponse(
            {'error': f'Server error: {str(e)}'},
            status=500
        )
