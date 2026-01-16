"""
Tool decorator for converting Python functions into LLM-callable tools.

This module provides the @tool decorator which adds metadata to functions
that allows them to be used as tools in LLM function calling.
"""

import inspect
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, get_type_hints, get_origin, get_args

try:
    import docstring_parser
    HAS_DOCSTRING_PARSER = True
except ImportError:
    HAS_DOCSTRING_PARSER = False


def _python_type_to_json_schema_type(python_type) -> str:
    """Convert Python type to JSON schema type string.

    Args:
        python_type: A Python type annotation

    Returns:
        The corresponding JSON schema type string
    """
    if python_type is None:
        return "string"  # Default fallback

    # Handle basic types
    if python_type in (str, type(None)):
        return "string"
    elif python_type is int:
        return "integer"
    elif python_type is float:
        return "number"
    elif python_type is bool:
        return "boolean"
    elif python_type in (list, tuple):
        return "array"
    elif python_type is dict:
        return "object"

    # Handle typing generics
    origin = get_origin(python_type)
    if origin is not None:
        if origin in (list, tuple):
            return "array"
        elif origin is dict:
            return "object"

    # Handle string representations
    if isinstance(python_type, str):
        python_type_lower = python_type.lower()
        if python_type_lower in ("str", "string"):
            return "string"
        elif python_type_lower in ("int", "integer"):
            return "integer"
        elif python_type_lower in ("float", "number"):
            return "number"
        elif python_type_lower in ("bool", "boolean"):
            return "boolean"
        elif python_type_lower in ("list", "array"):
            return "array"
        elif python_type_lower in ("dict", "object"):
            return "object"

    # Default fallback
    return "string"


def _build_parameters_schema(func: Callable) -> Dict[str, Any]:
    """Build JSON schema for function parameters.

    Extracts parameter information from:
    1. Type hints
    2. Docstring (if docstring_parser is available)
    3. Default values

    Args:
        func: The function to analyze

    Returns:
        A JSON schema dict describing the function's parameters
    """
    # Parse docstring if available
    func_doc = None
    if HAS_DOCSTRING_PARSER and func.__doc__:
        try:
            func_doc = docstring_parser.parse(func.__doc__)
        except Exception:
            pass

    # Get function signature
    func_signature = inspect.signature(func)

    # Get type hints
    try:
        type_hints = get_type_hints(func)
    except (NameError, AttributeError, TypeError):
        type_hints = {}

    # Build parameter properties
    properties = {}
    required = []

    for param_name, param in func_signature.parameters.items():
        # Skip *args and **kwargs
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue

        # Get type from type hints first
        param_type = type_hints.get(param_name)
        json_type = _python_type_to_json_schema_type(param_type)

        # Get description from docstring if available
        param_description = param_name
        if func_doc and func_doc.params:
            for doc_param in func_doc.params:
                if doc_param.arg_name == param_name:
                    if doc_param.description:
                        param_description = doc_param.description
                    # Also try to get type from docstring if type hints failed
                    if json_type == "string" and doc_param.type_name:
                        json_type = _python_type_to_json_schema_type(doc_param.type_name)
                    break

        properties[param_name] = {
            "type": json_type,
            "description": param_description,
        }

        # Add to required if no default value
        if param.default is param.empty:
            required.append(param_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def _get_function_description(func: Callable, description: Optional[str] = None) -> str:
    """Extract description from function or use provided one.

    Args:
        func: The function to get description from
        description: Optional override description

    Returns:
        The function description string
    """
    if description:
        return description

    if HAS_DOCSTRING_PARSER and func.__doc__:
        try:
            func_doc = docstring_parser.parse(func.__doc__)
            if func_doc.description:
                return func_doc.description
            elif func_doc.short_description:
                return func_doc.short_description
        except Exception:
            pass

    # Fallback to raw docstring or generic message
    if func.__doc__:
        # Use first line of docstring
        first_line = func.__doc__.strip().split('\n')[0]
        return first_line

    return f"Execute {func.__name__}"


def tool(
    description: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    category: str = "general",
    requires_confirmation: bool = False,
    cacheable: bool = False,
    cache_ttl: int = 300,
):
    """
    A decorator to convert a Python function into a tool with LLM-callable metadata.

    The decorated function will have a `tool_definition` attribute containing
    an OpenAI-compatible function schema that can be used for LLM function calling.

    Args:
        description: Optional. Description of the function's purpose.
                    If not provided, extracted from the function's docstring.
        parameters: Optional. JSON schema for function parameters.
                   If not provided, inferred from the function's signature and type hints.
        category: Tool category for organization (default: "general")
        requires_confirmation: Whether the tool requires user confirmation (default: False)
        cacheable: Whether results can be cached (default: False)
        cache_ttl: Cache time-to-live in seconds (default: 300)

    Returns:
        A decorator that adds tool metadata to the function.

    Example:
        @tool(description="Search the web for information")
        async def web_search(query: str, limit: int = 10) -> str:
            '''
            Search the web.

            Args:
                query: The search query
                limit: Maximum results to return
            '''
            return f"Results for {query}"

        # The function now has tool_definition attribute:
        # web_search.tool_definition = {
        #     "type": "function",
        #     "function": {
        #         "name": "web_search",
        #         "description": "Search the web for information",
        #         "parameters": {
        #             "type": "object",
        #             "properties": {
        #                 "query": {"type": "string", "description": "The search query"},
        #                 "limit": {"type": "integer", "description": "Maximum results to return"}
        #             },
        #             "required": ["query"]
        #         }
        #     }
        # }
    """

    def decorator(func: Callable) -> Callable:
        # Preserve async nature of function
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
        else:
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

        # Build parameters schema
        inferred_parameters = _build_parameters_schema(func)

        # Get description
        final_description = _get_function_description(func, description)

        # Attach the tool metadata as an attribute
        wrapper.tool_definition = {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": final_description,
                "parameters": parameters or inferred_parameters,
            },
        }

        # Attach additional metadata for the new Tool class
        wrapper.tool_metadata = {
            "category": category,
            "requires_confirmation": requires_confirmation,
            "cacheable": cacheable,
            "cache_ttl": cache_ttl,
        }

        return wrapper

    return decorator


def create_tool_from_function(
    func: Callable,
    description: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    **kwargs
) -> "Tool":
    """Create a Tool instance directly from a function.

    This is a convenience function that combines the @tool decorator
    with Tool instantiation.

    Args:
        func: The function to convert to a tool
        description: Optional description override
        parameters: Optional parameters schema override
        **kwargs: Additional Tool configuration (category, requires_confirmation, etc.)

    Returns:
        A configured Tool instance

    Example:
        async def my_search(query: str) -> str:
            return f"Results for {query}"

        tool = create_tool_from_function(
            my_search,
            description="Search for things",
            category="search"
        )
    """
    from reactive_agents.core.tools.base import Tool

    # Apply the decorator to get tool_definition
    decorated = tool(description=description, parameters=parameters, **kwargs)(func)

    # Create and return Tool instance
    return Tool(function=decorated)
