"""
Real-World Scenario Tests - Practical use cases.

These tests simulate actual production scenarios to validate
the framework's readiness for real applications.
"""

import asyncio
from typing import Optional, List, Dict, Any
import time
import json

from reactive_agents import ReactiveAgentBuilder, Provider, ReasoningStrategies
from .tools import get_weather, get_crypto_price, calculate


async def test_customer_support_agent(model: str = "cogito:14b") -> bool:
    """
    Simulate a customer support agent handling a complex inquiry:
    - Multi-turn conversation
    - Context retention
    - Tool usage for lookups
    - Professional responses
    """
    print("\n--- Customer Support Agent ---")

    try:

        def lookup_order(order_id: str) -> Dict[str, Any]:
            """Look up order details."""
            # Simulated order database
            orders = {
                "ORD-12345": {
                    "status": "shipped",
                    "tracking": "TRACK-789",
                    "items": ["Widget A", "Widget B"],
                    "total": 99.99,
                },
                "ORD-67890": {
                    "status": "processing",
                    "tracking": None,
                    "items": ["Gadget X"],
                    "total": 149.99,
                },
            }
            return orders.get(order_id, {"error": "Order not found"})

        def check_inventory(item: str) -> Dict[str, Any]:
            """Check item inventory."""
            inventory = {
                "Widget A": {"in_stock": True, "quantity": 50},
                "Widget B": {"in_stock": False, "quantity": 0},
                "Gadget X": {"in_stock": True, "quantity": 25},
            }
            return inventory.get(item, {"error": "Item not found"})

        agent = await (
            ReactiveAgentBuilder()
            .with_name("SupportAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Customer Support Specialist")
            .with_instructions(
                "You are a helpful customer support agent. Be professional, "
                "empathetic, and thorough. Use tools to look up information. "
                "Provide clear, actionable responses."
            )
            .with_reasoning_strategy(ReasoningStrategies.REFLECT_DECIDE_ACT)
            .with_custom_tools([lookup_order, check_inventory])
            .with_max_iterations(8)
            .with_log_level("info")
            .build()
        )

        # Simulated customer interaction
        inquiry = """
        I placed order ORD-12345 last week and haven't received it yet. 
        Can you check the status? Also, I wanted to add Widget B to my order 
        if possible. Is it in stock?
        """

        result = await agent.run(inquiry)

        print(f"Status: {result.status.value}")
        print(f"Iterations: {result.session.iterations}")
        print(f"Tools Used: {result.session.successful_tools}")

        # Validate response quality
        response = result.final_answer or ""
        has_order_status = "shipped" in response.lower() or "track" in response.lower()
        has_inventory_info = "stock" in response.lower()

        print(f"Mentioned Order Status: {has_order_status}")
        print(f"Checked Inventory: {has_inventory_info}")
        print(f"Success: {result.was_successful()}")

        await agent.close()
        return result.was_successful() and has_order_status

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_data_analysis_agent(model: str = "cogito:14b") -> bool:
    """
    Simulate a data analyst working with structured data:
    - Data transformation
    - Statistical calculations
    - Insight generation
    - Report creation
    """
    print("\n--- Data Analysis Agent ---")

    try:

        def get_sales_data() -> List[Dict[str, Any]]:
            """Retrieve sales data."""
            return [
                {"product": "A", "units": 100, "revenue": 1000},
                {"product": "B", "units": 150, "revenue": 2250},
                {"product": "C", "units": 75, "revenue": 1125},
            ]

        def calculate_stats(numbers: List[float]) -> Dict[str, float | str]:
            """Calculate basic statistics."""
            if not numbers:
                return {"error": "No data provided"}
            return {
                "sum": sum(numbers),
                "avg": sum(numbers) / len(numbers),
                "min": min(numbers),
                "max": max(numbers),
            }

        agent = await (
            ReactiveAgentBuilder()
            .with_name("DataAnalyst")
            .with_model(Provider.OLLAMA, model)
            .with_role("Data Analyst")
            .with_instructions(
                "Analyze data systematically. Calculate relevant metrics, "
                "identify trends, and provide actionable insights."
            )
            .with_reasoning_strategy(ReasoningStrategies.PLAN_EXECUTE_REFLECT)
            .with_custom_tools([get_sales_data, calculate_stats, calculate])
            .with_max_iterations(10)
            .with_log_level("info")
            .build()
        )

        task = """
        Analyze the sales data:
        1. Get the sales data
        2. Calculate total revenue
        3. Find which product has the highest revenue per unit
        4. Provide insights and recommendations
        """

        result = await agent.run(task)

        print(f"Status: {result.status.value}")
        print(f"Iterations: {result.session.iterations}")
        print(f"Success: {result.was_successful()}")

        # Check if analysis was performed
        response = result.final_answer or ""
        has_revenue = "revenue" in response.lower()
        has_product_analysis = (
            "product" in response.lower() or "b" in response.lower()
        )  # Product B has highest

        print(f"Mentioned Revenue: {has_revenue}")
        print(f"Product Analysis: {has_product_analysis}")

        await agent.close()
        return result.was_successful() and has_revenue

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_research_assistant(model: str = "cogito:14b") -> bool:
    """
    Simulate a research assistant synthesizing information:
    - Multiple information sources
    - Cross-referencing data
    - Synthesis and summarization
    - Citation tracking
    """
    print("\n--- Research Assistant ---")

    try:

        def search_papers(topic: str) -> List[Dict[str, str]]:
            """Search academic papers."""
            papers = {
                "ai": [
                    {
                        "title": "Deep Learning Advances",
                        "year": "2024",
                        "finding": "Neural networks show 95% accuracy",
                    },
                    {
                        "title": "Transformer Models",
                        "year": "2023",
                        "finding": "Attention mechanisms improve performance",
                    },
                ],
                "climate": [
                    {
                        "title": "Climate Change Analysis",
                        "year": "2024",
                        "finding": "Temperature increased 1.2°C",
                    },
                    {
                        "title": "Renewable Energy",
                        "year": "2023",
                        "finding": "Solar costs decreased 40%",
                    },
                ],
            }
            for key in papers:
                if key in topic.lower():
                    return papers[key]
            return []

        def get_statistics(topic: str) -> Dict[str, Any]:
            """Get statistical data."""
            stats = {
                "ai": {"market_size": "500B USD", "growth_rate": "40% YoY"},
                "climate": {"emissions": "40Gt CO2", "renewable_percent": "30%"},
            }
            for key in stats:
                if key in topic.lower():
                    return stats[key]
            return {}

        agent = await (
            ReactiveAgentBuilder()
            .with_name("ResearchAssistant")
            .with_model(Provider.OLLAMA, model)
            .with_role("Research Assistant")
            .with_instructions(
                "Conduct thorough research. Gather information from multiple sources, "
                "cross-reference findings, and synthesize insights. Cite sources."
            )
            .with_reasoning_strategy(ReasoningStrategies.PLAN_EXECUTE_REFLECT)
            .with_custom_tools([search_papers, get_statistics])
            .with_max_iterations(10)
            .with_log_level("info")
            .build()
        )

        task = """
        Research the current state of AI technology:
        1. Find recent academic papers on AI
        2. Get market statistics
        3. Synthesize findings into a comprehensive summary
        4. Include key trends and numbers
        """

        result = await agent.run(task)

        print(f"Status: {result.status.value}")
        print(f"Iterations: {result.session.iterations}")
        print(f"Tools Used: {result.session.successful_tools}")
        print(f"Success: {result.was_successful()}")

        # Validate research quality
        response = result.final_answer or ""
        has_papers = (
            "deep learning" in response.lower() or "transformer" in response.lower()
        )
        has_stats = "500" in response or "market" in response.lower()

        print(f"Cited Papers: {has_papers}")
        print(f"Included Statistics: {has_stats}")

        await agent.close()
        return result.was_successful() and (has_papers or has_stats)

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_code_reviewer(model: str = "cogito:14b") -> bool:
    """
    Simulate a code review assistant:
    - Code analysis
    - Pattern detection
    - Best practice recommendations
    - Security checks
    """
    print("\n--- Code Reviewer ---")

    try:

        def analyze_code(code: str) -> Dict[str, Any]:
            """Analyze code for issues."""
            issues = []
            suggestions = []

            if "password" in code.lower() and "=" in code:
                issues.append("Hardcoded credentials detected")
            if "eval(" in code:
                issues.append("Use of eval() is dangerous")
            if "TODO" in code:
                suggestions.append("Contains TODO items")
            if len(code.split("\n")) > 50:
                suggestions.append("Function is long, consider splitting")

            return {
                "issues": issues,
                "suggestions": suggestions,
                "complexity": len(code.split("\n")),
            }

        def check_security(code: str) -> Dict[str, List[str]]:
            """Check for security issues."""
            vulnerabilities = []
            if "input(" in code and "eval(" in code:
                vulnerabilities.append("Unsafe user input handling")
            if "password" in code.lower():
                vulnerabilities.append("Potential credential exposure")

            return {
                "vulnerabilities": vulnerabilities,
                "risk_level": "high" if vulnerabilities else "low",
            }

        agent = await (
            ReactiveAgentBuilder()
            .with_name("CodeReviewer")
            .with_model(Provider.OLLAMA, model)
            .with_role("Senior Code Reviewer")
            .with_instructions(
                "Review code thoroughly. Check for bugs, security issues, "
                "and adherence to best practices. Provide constructive feedback."
            )
            .with_reasoning_strategy(ReasoningStrategies.REFLECT_DECIDE_ACT)
            .with_custom_tools([analyze_code, check_security])
            .with_max_iterations(8)
            .with_log_level("info")
            .build()
        )

        code_sample = """
def login(username):
    password = "admin123"  # TODO: Move to config
    user_input = eval(input("Enter command: "))
    return user_input
        """

        task = f"""
        Review this code and provide feedback:
        
        ```python
        {code_sample}
        ```
        
        Check for security issues, bugs, and best practice violations.
        """

        result = await agent.run(task)

        print(f"Status: {result.status.value}")
        print(f"Iterations: {result.session.iterations}")
        print(f"Success: {result.was_successful()}")

        # Check if issues were identified
        response = result.final_answer or ""
        found_password_issue = (
            "password" in response.lower() or "credential" in response.lower()
        )
        found_eval_issue = "eval" in response.lower() or "dangerous" in response.lower()

        print(f"Identified Password Issue: {found_password_issue}")
        print(f"Identified Eval Issue: {found_eval_issue}")

        await agent.close()
        return result.was_successful() and (found_password_issue or found_eval_issue)

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_task_automation_agent(model: str = "cogito:14b") -> bool:
    """
    Simulate task automation with dependencies:
    - Multi-step workflow execution
    - Dependency management
    - Error handling in workflows
    - Status reporting
    """
    print("\n--- Task Automation Agent ---")

    try:
        task_state = {"completed": [], "failed": []}

        def execute_task(
            task_name: str, depends_on: Optional[str] = None
        ) -> Dict[str, Any]:
            """Execute a task with dependency checking."""
            if depends_on and depends_on not in task_state["completed"]:
                return {
                    "status": "blocked",
                    "message": f"Waiting for {depends_on} to complete",
                }

            # Simulate task execution
            if task_name == "failing_task":
                task_state["failed"].append(task_name)
                return {"status": "failed", "error": "Simulated failure"}

            task_state["completed"].append(task_name)
            return {"status": "success", "task": task_name}

        def get_task_status() -> Dict[str, Any]:
            """Get current task execution status."""
            return {
                "completed": task_state["completed"],
                "failed": task_state["failed"],
                "total": len(task_state["completed"]) + len(task_state["failed"]),
            }

        agent = await (
            ReactiveAgentBuilder()
            .with_name("AutomationAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Task Automation Specialist")
            .with_instructions(
                "Execute tasks systematically. Handle dependencies, "
                "track progress, and recover from failures."
            )
            .with_reasoning_strategy(ReasoningStrategies.PLAN_EXECUTE_REFLECT)
            .with_custom_tools([execute_task, get_task_status])
            .with_max_iterations(12)
            .with_log_level("info")
            .build()
        )

        task = """
        Execute this workflow:
        1. Execute task "setup" (no dependencies)
        2. Execute task "process" (depends on "setup")
        3. Execute task "cleanup" (depends on "process")
        4. Check overall status
        
        Report final status and any issues.
        """

        result = await agent.run(task)

        print(f"Status: {result.status.value}")
        print(f"Iterations: {result.session.iterations}")
        print(f"Tasks Completed: {len(task_state['completed'])}")
        print(f"Tasks Failed: {len(task_state['failed'])}")
        print(f"Success: {result.was_successful()}")

        await agent.close()
        return result.was_successful() and len(task_state["completed"]) >= 2

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def run_all_real_world_tests(model: str = "cogito:14b"):
    """Run all real-world scenario tests."""
    print("=" * 60)
    print("REAL-WORLD SCENARIO TESTS")
    print("=" * 60)

    tests = [
        ("Customer Support Agent", test_customer_support_agent),
        ("Data Analysis Agent", test_data_analysis_agent),
        ("Research Assistant", test_research_assistant),
        ("Code Reviewer", test_code_reviewer),
        ("Task Automation Agent", test_task_automation_agent),
    ]

    results = {}
    start_time = time.time()

    for name, test_func in tests:
        try:
            result = await test_func(model)
            results[name] = "PASS" if result else "FAIL"
        except Exception as e:
            print(f"\n{name} - EXCEPTION: {e}")
            results[name] = "ERROR"

    total_duration = time.time() - start_time

    print("\n" + "=" * 60)
    print("REAL-WORLD TEST RESULTS")
    print("=" * 60)

    for name, status in results.items():
        emoji = "✓" if status == "PASS" else "✗" if status == "FAIL" else "⚠"
        print(f"  {emoji} {name}: {status}")

    print(f"\nTotal Duration: {total_duration:.2f}s")

    passed = sum(1 for s in results.values() if s == "PASS")
    total = len(results)
    print(f"Success Rate: {passed}/{total} ({100*passed//total}%)")

    return results


async def run(model: str = "cogito:14b", **kwargs):
    """Entry point for runner."""
    return await run_all_real_world_tests(model)
