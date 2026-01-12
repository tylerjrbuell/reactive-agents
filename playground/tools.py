"""
Shared tools for playground tests.

These simulated tools are used across various test scenarios.
"""

from reactive_agents.core.tools.decorators import tool


@tool()
async def web_search(query: str, num_results: int = 5) -> str:
    """
    Search the web (simulated).

    Args:
        query: The search query string.
        num_results: Number of results to return.

    Returns:
        Simulated search results.
    """
    return f"Search results for '{query}': [Simulated {num_results} results]"


@tool()
async def get_weather(location: str) -> str:
    """
    Get weather for a location (simulated).

    Args:
        location: City name (New York, London, Tokyo, Sydney supported).

    Returns:
        Weather information string.
    """
    weather_data = {
        "New York": {"temp": "72°F", "condition": "Sunny", "humidity": 65},
        "London": {"temp": "18°C", "condition": "Rainy", "humidity": 80},
        "Tokyo": {"temp": "25°C", "condition": "Cloudy", "humidity": 70},
        "Sydney": {"temp": "22°C", "condition": "Partly Cloudy", "humidity": 75},
    }

    if location in weather_data:
        data = weather_data[location]
        return f"Weather in {location}: {data['temp']}, {data['condition']} (Humidity: {data['humidity']}%)"
    return f"Weather data for {location} not available. Try: New York, London, Tokyo, Sydney"


@tool()
async def get_crypto_price(coin: str) -> str:
    """
    Get cryptocurrency price (simulated).

    Args:
        coin: Cryptocurrency name (bitcoin, ethereum, solana, cardano supported).

    Returns:
        Price information string.
    """
    prices = {
        "bitcoin": "$45,234.21",
        "ethereum": "$2,890.65",
        "solana": "$98.42",
        "cardano": "$1.21",
    }

    coin_lower = coin.lower()
    if coin_lower in prices:
        return f"Current price of {coin.title()}: {prices[coin_lower]}"
    return f"Price for {coin} not available. Try: Bitcoin, Ethereum, Solana, Cardano"


@tool()
async def calculate(expression: str) -> str:
    """
    Evaluate a mathematical expression safely.

    Args:
        expression: Math expression (e.g., "2 + 2", "10 * 5").

    Returns:
        Calculation result or error message.
    """
    try:
        allowed = set("0123456789+-*/.() ")
        if not all(c in allowed for c in expression):
            return f"Error: Invalid characters in expression"
        result = eval(expression)
        return f"Result: {result}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool()
async def analyze_sentiment(text: str) -> str:
    """
    Analyze text sentiment (simulated).

    Args:
        text: Text to analyze.

    Returns:
        Sentiment analysis result.
    """
    positive_words = ["good", "great", "excellent", "happy", "love", "best", "amazing"]
    negative_words = ["bad", "terrible", "hate", "worst", "awful", "poor"]

    text_lower = text.lower()
    pos_count = sum(1 for w in positive_words if w in text_lower)
    neg_count = sum(1 for w in negative_words if w in text_lower)

    if pos_count > neg_count:
        sentiment = "positive"
    elif neg_count > pos_count:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    return f"Sentiment: {sentiment} (positive indicators: {pos_count}, negative: {neg_count})"


@tool()
async def fetch_data(data_type: str) -> str:
    """
    Fetch mock data of a specified type.

    Args:
        data_type: Type of data (weather, stock, news).

    Returns:
        Mock data as string.
    """
    mock_data = {
        "weather": "Temperature: 72°F, Condition: Sunny, Humidity: 45%",
        "stock": "TECH: $150.25 (+2.5%)",
        "news": "Headline: AI Advances Continue - Source: Tech Daily",
    }
    return mock_data.get(data_type, f"Unknown data type: {data_type}")
