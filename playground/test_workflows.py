"""
Workflow Tests - Test multi-agent orchestration.

Tests the WorkflowOrchestrator, WorkflowBuilder, and agent chains.
"""

import asyncio
from typing import Optional

from reactive_agents import ReactiveAgentBuilder, Provider
from reactive_agents.app.workflows.orchestrator import WorkflowOrchestrator
from .tools import get_weather, analyze_sentiment


async def test_simple_workflow(model: str = "cogito:14b") -> bool:
    """Test a simple two-agent workflow."""
    print("\n--- Simple Workflow Test ---")

    try:
        # Create agents
        researcher = await (
            ReactiveAgentBuilder()
            .with_name("Researcher")
            .with_model(Provider.OLLAMA, model)
            .with_role("Research Specialist")
            .with_instructions("Research topics and provide findings.")
            .with_custom_tools([get_weather])
            .with_max_iterations(3)
            .with_log_level("warning")
            .build()
        )

        summarizer = await (
            ReactiveAgentBuilder()
            .with_name("Summarizer")
            .with_model(Provider.OLLAMA, model)
            .with_role("Content Summarizer")
            .with_instructions("Create clear summaries.")
            .with_max_iterations(2)
            .with_log_level("warning")
            .build()
        )

        # Create orchestrator
        orchestrator = WorkflowOrchestrator()
        orchestrator.register_agent(researcher)
        orchestrator.register_agent(summarizer)

        # Build workflow
        workflow = (
            orchestrator.create_workflow("SimpleWorkflow", "Research and summarize")
            .add_agent_node(
                agent_name="Researcher",
                task_template="Research: ${topic}",
                node_id="research",
                context_mapping={"result": "research.output"},
            )
            .add_agent_node(
                agent_name="Summarizer",
                task_template="Summarize this: ${research.output}",
                node_id="summarize",
                depends_on=["research"],
            )
            .set_exit_nodes(["summarize"])
            .set_global_context({"topic": "weather in Tokyo"})
            .build()
        )

        # Execute
        print("Executing workflow...")
        result = await orchestrator.execute_workflow(workflow)

        print(f"Success: {result.success}")
        print(f"Status: {result.status}")
        print(f"Time: {result.execution_time:.2f}s")
        print(f"Nodes: {result.completed_nodes}/{result.total_nodes}")

        await researcher.close()
        await summarizer.close()

        return result.success

    except Exception as e:
        print(f"Error: {e}")
        return False


async def test_parallel_workflow(model: str = "cogito:14b") -> bool:
    """Test workflow with parallel agent execution."""
    print("\n--- Parallel Workflow Test ---")

    try:
        # Create agents
        weather_agent = await (
            ReactiveAgentBuilder()
            .with_name("WeatherAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Weather Specialist")
            .with_instructions("Get weather information.")
            .with_custom_tools([get_weather])
            .with_max_iterations(3)
            .with_log_level("warning")
            .build()
        )

        sentiment_agent = await (
            ReactiveAgentBuilder()
            .with_name("SentimentAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Sentiment Analyst")
            .with_instructions("Analyze sentiment of text.")
            .with_custom_tools([analyze_sentiment])
            .with_max_iterations(3)
            .with_log_level("warning")
            .build()
        )

        combiner = await (
            ReactiveAgentBuilder()
            .with_name("Combiner")
            .with_model(Provider.OLLAMA, model)
            .with_role("Result Combiner")
            .with_instructions("Combine multiple results into a coherent summary.")
            .with_max_iterations(2)
            .with_log_level("warning")
            .build()
        )

        # Create orchestrator
        orchestrator = WorkflowOrchestrator()
        orchestrator.register_agent(weather_agent)
        orchestrator.register_agent(sentiment_agent)
        orchestrator.register_agent(combiner)

        # Build workflow with parallel nodes
        workflow = (
            orchestrator.create_workflow(
                "ParallelWorkflow", "Parallel tasks then combine"
            )
            .add_agent_node(
                agent_name="WeatherAgent",
                task_template="Get weather for ${location}",
                node_id="weather",
                context_mapping={"result": "weather.output"},
            )
            .add_agent_node(
                agent_name="SentimentAgent",
                task_template="Analyze sentiment: ${text}",
                node_id="sentiment",
                context_mapping={"result": "sentiment.output"},
            )
            .add_agent_node(
                agent_name="Combiner",
                task_template="Combine: Weather=${weather.output}, Sentiment=${sentiment.output}",
                node_id="combine",
                depends_on=["weather", "sentiment"],
            )
            .set_exit_nodes(["combine"])
            .set_global_context(
                {"location": "New York", "text": "The weather is great today!"}
            )
            .build()
        )

        # Execute
        print("Executing parallel workflow...")
        result = await orchestrator.execute_workflow(workflow)

        print(f"Success: {result.success}")
        print(f"Time: {result.execution_time:.2f}s")
        print(f"Nodes: {result.completed_nodes}/{result.total_nodes}")

        await weather_agent.close()
        await sentiment_agent.close()
        await combiner.close()

        return result.success

    except Exception as e:
        print(f"Error: {e}")
        return False


async def test_conditional_workflow(model: str = "cogito:14b") -> bool:
    """Test workflow with condition nodes."""
    print("\n--- Conditional Workflow Test ---")

    try:
        # Create agent
        agent = await (
            ReactiveAgentBuilder()
            .with_name("ConditionalAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Assistant")
            .with_instructions("Follow instructions.")
            .with_max_iterations(2)
            .with_log_level("warning")
            .build()
        )

        # Create orchestrator
        orchestrator = WorkflowOrchestrator()
        orchestrator.register_agent(agent)

        # Build workflow with condition
        workflow = (
            orchestrator.create_workflow("ConditionalWorkflow", "Condition-based flow")
            .add_condition_node(
                condition="context.get('value', 0) > 5",
                node_id="check_value",
            )
            .add_agent_node(
                agent_name="ConditionalAgent",
                task_template="Value ${value} is greater than 5",
                node_id="high_value",
                depends_on=["check_value"],
            )
            .set_exit_nodes(["high_value"])
            .set_global_context({"value": 10})
            .build()
        )

        # Execute
        print("Executing conditional workflow...")
        result = await orchestrator.execute_workflow(workflow)

        print(f"Success: {result.success}")
        print(f"Condition result: {result.node_results.get('check_value', {})}")

        await agent.close()

        return result.success

    except Exception as e:
        print(f"Error: {e}")
        return False


async def run(test_name: Optional[str] = None, model: str = "cogito:14b") -> dict:
    """
    Run workflow tests.

    Args:
        test_name: Specific test (simple, parallel, conditional) or None for all.
        model: Model to use.

    Returns:
        Dict with test results.
    """
    print("=" * 60)
    print("WORKFLOW TESTS")
    print("=" * 60)

    results = {}

    tests = {
        "simple": test_simple_workflow,
        "parallel": test_parallel_workflow,
        "conditional": test_conditional_workflow,
    }

    if test_name and test_name in tests:
        results[test_name] = await tests[test_name](model)
    else:
        for name, test_fn in tests.items():
            results[name] = await test_fn(model)

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")

    return results


if __name__ == "__main__":
    asyncio.run(run())
