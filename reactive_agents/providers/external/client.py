"""
MCP Client with reliability features.

This module provides a robust MCP client with:
- Health checks and connection monitoring
- Circuit breaker pattern for failed servers
- Automatic reconnection with exponential backoff
- Tool-to-server mapping cache for O(1) lookups
- Timeout handling for all operations
"""

from typing import List, Optional, Any, Dict
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from enum import Enum
import os
import uuid
import asyncio
import time

from pydantic import AnyUrl
from mcp import ClientSession, StdioServerParameters, Tool
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult

from reactive_agents.config.mcp_config import (
    load_server_config,
    MCPConfig,
    MCPServerConfig,
    DockerConfig,
)
from reactive_agents.config.logging import LogLevel, formatter
from reactive_agents.utils.logging import Logger


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class ServerHealth:
    """Tracks health status of an MCP server."""
    server_name: str
    is_connected: bool = False
    consecutive_failures: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    last_health_check: Optional[float] = None
    circuit_state: CircuitState = CircuitState.CLOSED
    total_calls: int = 0
    failed_calls: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_calls == 0:
            return 1.0
        return (self.total_calls - self.failed_calls) / self.total_calls

    def record_success(self) -> None:
        """Record a successful operation."""
        self.consecutive_failures = 0
        self.last_success_time = time.time()
        self.total_calls += 1
        if self.circuit_state == CircuitState.HALF_OPEN:
            self.circuit_state = CircuitState.CLOSED

    def record_failure(self, threshold: int) -> None:
        """Record a failed operation."""
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        self.total_calls += 1
        self.failed_calls += 1
        if self.consecutive_failures >= threshold:
            self.circuit_state = CircuitState.OPEN

    def should_attempt(self, reset_seconds: float) -> bool:
        """Check if we should attempt an operation (circuit breaker logic)."""
        if self.circuit_state == CircuitState.CLOSED:
            return True
        if self.circuit_state == CircuitState.OPEN:
            # Check if enough time has passed to try again
            if self.last_failure_time:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= reset_seconds:
                    self.circuit_state = CircuitState.HALF_OPEN
                    return True
            return False
        # HALF_OPEN - allow one attempt
        return True


class MCPClient:
    """
    Robust MCP Client with reliability features.

    Features:
    - Health checks for connected servers
    - Circuit breaker pattern to prevent cascade failures
    - Automatic reconnection with exponential backoff
    - O(1) tool-to-server mapping
    - Configurable timeouts for all operations
    """

    def __init__(
        self,
        config_file: str = "config/mcp.json",
        server_filter: Optional[List[str]] = None,
        server_config: Optional[MCPConfig] = None,
        log_level: Optional[str] = None,
    ):
        # Initialize session and client objects
        self.sessions: Dict[str, ClientSession] = {}
        self.tools: List[Tool] = []
        self.tool_signatures: List[Dict[str, Any]] = []
        self.server_tools: Dict[str, List[Tool]] = {}
        self.exit_stack = AsyncExitStack()
        self.server_params: Optional[StdioServerParameters] = None
        self._closed = False
        self.server_filter = server_filter
        self.instance_id = str(uuid.uuid4())[:8]
        self.config: Optional[MCPConfig] = None
        self.config_file = config_file
        self.server_config = server_config
        self.logger = Logger("MCPClient", "mcp", log_level or LogLevel.INFO.value)
        self.logger.formatter = formatter

        # Reliability tracking
        self._server_health: Dict[str, ServerHealth] = {}
        self._tool_to_server: Dict[str, str] = {}  # O(1) tool lookup cache
        self._health_check_task: Optional[asyncio.Task] = None
        self._reconnect_lock = asyncio.Lock()

    def _prepare_docker_args(
        self, server_name: str, server_config: MCPServerConfig
    ) -> List[str]:
        """Prepare Docker arguments with any custom configuration"""
        args = list(server_config.args)  # Convert to list to allow modification
        if server_config.command == "docker":
            # Modify container name for better identification
            if "--name" in args:
                name_index = args.index("--name") + 1
                if name_index < len(args):
                    args[name_index] = (
                        f"{server_config.args[name_index]}-{self.instance_id}"
                    )
            else:
                args.insert(args.index("run") + 1, "--name")
                args.insert(args.index("run") + 2, f"{server_name}-{self.instance_id}")

            if server_config.docker:
                # Add network if specified
                if server_config.docker.network:
                    args.extend(["--network", server_config.docker.network])

                # Add any extra mount points
                for mount in server_config.docker.extra_mounts:
                    args.extend(["--mount", mount])

                # Add any extra environment variables
                for key, value in server_config.docker.extra_env.items():
                    args.extend(["-e", f"{key}={value}"])
        return args

    def _prepare_environment(self, server_config: MCPServerConfig) -> Dict[str, str]:
        """Prepare environment variables for the server"""
        env = {**os.environ}  # Start with current environment

        # Add server-specific environment variables
        env.update(server_config.env)

        # Add Docker-specific environment variables if applicable
        if server_config.docker and server_config.docker.extra_env:
            env.update(server_config.docker.extra_env)

        return env

    async def _connect_single_server(
        self, server_name: str, server_config: MCPServerConfig
    ) -> bool:
        """Connect to a single MCP server with timeout handling."""
        try:
            # Prepare command arguments
            args = (
                self._prepare_docker_args(server_name, server_config)
                if server_config.command == "docker"
                else server_config.args
            )

            # Prepare environment
            env = self._prepare_environment(server_config)

            # Create server parameters
            server_params = StdioServerParameters(
                command=server_config.command,
                args=args,
                env=env,
                cwd=server_config.working_dir,
            )

            # Connect with timeout
            async with asyncio.timeout(server_config.timeout_seconds):
                stdio_transport = await self.exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                stdio, write = stdio_transport
                session = await self.exit_stack.enter_async_context(
                    ClientSession(stdio, write)
                )

                # Initialize and store session
                await session.initialize()
                self.sessions[server_name] = session
                tools_list = (await session.list_tools()).tools
                self.server_tools[server_name] = tools_list

                # Update tool-to-server cache
                for tool in tools_list:
                    self._tool_to_server[tool.name] = server_name

                # Update health tracking
                if server_name not in self._server_health:
                    self._server_health[server_name] = ServerHealth(server_name=server_name)
                self._server_health[server_name].is_connected = True
                self._server_health[server_name].record_success()

                self.logger.info(
                    f"Successfully connected to {server_name} with {len(tools_list)} tools"
                )
                return True

        except asyncio.TimeoutError:
            self.logger.error(
                f"Timeout connecting to server {server_name} "
                f"(limit: {server_config.timeout_seconds}s)"
            )
            self._handle_server_failure(server_name, server_config)
            return False
        except Exception as e:
            self.logger.error(f"Failed to connect to server {server_name}: {str(e)}")
            import traceback
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            self._handle_server_failure(server_name, server_config)
            return False

    def _handle_server_failure(
        self, server_name: str, server_config: MCPServerConfig
    ) -> None:
        """Handle a server connection/operation failure."""
        # Clean up any partial connections
        if server_name in self.sessions:
            del self.sessions[server_name]
        if server_name in self.server_tools:
            # Remove tools from cache
            for tool in self.server_tools[server_name]:
                self._tool_to_server.pop(tool.name, None)
            del self.server_tools[server_name]

        # Update health tracking
        if server_name not in self._server_health:
            self._server_health[server_name] = ServerHealth(server_name=server_name)
        self._server_health[server_name].is_connected = False
        self._server_health[server_name].record_failure(
            server_config.circuit_breaker_threshold
        )

    async def connect_to_servers(self) -> None:
        """Connect to configured MCP servers with reliability handling."""
        if self.server_config:
            # Use provided server configuration
            servers_dict = {}
            for server_name, server_config in self.server_config.mcpServers.items():
                docker_config = None
                if "docker" in server_config.command and server_config.docker:
                    docker_config = DockerConfig(
                        network=server_config.docker.network,
                        extra_mounts=server_config.docker.extra_mounts,
                        extra_env=server_config.docker.extra_env,
                    )

                servers_dict[server_name] = MCPServerConfig(
                    command=server_config.command,
                    args=server_config.args,
                    env=server_config.env,
                    working_dir=server_config.working_dir,
                    docker=docker_config,
                    enabled=server_config.enabled,
                )
            self.config = MCPConfig(mcpServers=servers_dict)
        else:
            # Load from config file
            self.config = load_server_config()

        for server_name, server_config in self.config.mcpServers.items():
            # Skip if server is disabled or already closed
            if self._closed or not server_config.enabled:
                self.logger.warning(f"Skipping disabled server {server_name}...")
                continue

            # Skip if server is not in filter
            if self.server_filter and server_name not in self.server_filter:
                self.logger.info(f"Filtering out server {server_name}...")
                continue

            # Skip if already connected
            if server_name in self.sessions:
                self.logger.info(f"Already connected to server {server_name}...")
                continue

            await self._connect_single_server(server_name, server_config)

    async def reconnect_server(self, server_name: str) -> bool:
        """Attempt to reconnect to a specific server with exponential backoff."""
        async with self._reconnect_lock:
            if self._closed:
                return False

            if not self.config or server_name not in self.config.mcpServers:
                self.logger.error(f"No configuration found for server {server_name}")
                return False

            server_config = self.config.mcpServers[server_name]
            health = self._server_health.get(server_name)

            if health and not health.should_attempt(server_config.circuit_breaker_reset_seconds):
                self.logger.warning(
                    f"Circuit breaker OPEN for {server_name}, skipping reconnect"
                )
                return False

            # Exponential backoff
            retry_count = 0
            max_retries = server_config.max_retries
            base_delay = server_config.retry_delay_seconds

            while retry_count <= max_retries and not self._closed:
                if retry_count > 0:
                    delay = base_delay * (2 ** (retry_count - 1))
                    self.logger.info(
                        f"Reconnect attempt {retry_count}/{max_retries} for {server_name} "
                        f"after {delay:.1f}s delay"
                    )
                    await asyncio.sleep(delay)

                success = await self._connect_single_server(server_name, server_config)
                if success:
                    self.logger.info(f"Successfully reconnected to {server_name}")
                    return True

                retry_count += 1

            self.logger.error(
                f"Failed to reconnect to {server_name} after {max_retries} attempts"
            )
            return False

    async def check_health(self, server_name: str) -> bool:
        """Check health of a specific server by listing tools."""
        if server_name not in self.sessions:
            return False

        try:
            session = self.sessions[server_name]
            async with asyncio.timeout(5.0):  # Quick health check timeout
                await session.list_tools()

            if server_name in self._server_health:
                self._server_health[server_name].last_health_check = time.time()
                self._server_health[server_name].record_success()

            return True

        except Exception as e:
            self.logger.warning(f"Health check failed for {server_name}: {e}")
            if self.config and server_name in self.config.mcpServers:
                self._handle_server_failure(
                    server_name, self.config.mcpServers[server_name]
                )
            return False

    async def check_all_health(self) -> Dict[str, bool]:
        """Check health of all connected servers."""
        results = {}
        for server_name in list(self.sessions.keys()):
            results[server_name] = await self.check_health(server_name)
        return results

    def get_server_health(self, server_name: str) -> Optional[ServerHealth]:
        """Get health status for a specific server."""
        return self._server_health.get(server_name)

    def get_all_health(self) -> Dict[str, ServerHealth]:
        """Get health status for all known servers."""
        return self._server_health.copy()

    async def initialize(self) -> "MCPClient":
        """Initialize the client and connect to servers."""
        await self.connect_to_servers()
        await self.get_tools()
        return self

    async def get_tools(self) -> List[Tool]:
        """Get all available tools from connected servers."""
        self.logger.info(
            f"get_tools() called. Closed: {self._closed}, Sessions: {len(self.sessions)}"
        )
        if not self._closed:
            self.tools = []
            self.tool_signatures = []

            for server_name, session in self.sessions.items():
                try:
                    tools = (await session.list_tools()).tools
                    self.tools.extend(tools)

                    # Update tool-to-server cache
                    for tool in tools:
                        self._tool_to_server[tool.name] = server_name

                    # Create tool signatures
                    for tool in tools:
                        self.tool_signatures.append(
                            {
                                "type": "function",
                                "function": {
                                    "name": tool.name,
                                    "description": tool.description,
                                    "parameters": tool.inputSchema,
                                },
                            }
                        )
                except Exception as e:
                    self.logger.error(
                        f"Error getting tools from server {server_name}: {str(e)}"
                    )
                    if self.config and server_name in self.config.mcpServers:
                        self._handle_server_failure(
                            server_name, self.config.mcpServers[server_name]
                        )

        return self.tools

    async def call_tool(
        self, tool_name: str, params: dict, retry: bool = True
    ) -> CallToolResult:
        """Call a tool on the appropriate server with reliability handling."""
        if self._closed:
            raise RuntimeError("Client is closed")

        # O(1) lookup using cache
        server_name = self._tool_to_server.get(tool_name)

        if not server_name:
            # Fallback to linear search (in case cache is stale)
            server_name = next(
                (
                    server
                    for server, tools in self.server_tools.items()
                    if tool_name in [tool.name for tool in tools]
                ),
                None,
            )
            if server_name:
                self._tool_to_server[tool_name] = server_name

        if not server_name:
            raise ValueError(f"Tool {tool_name} not found in any connected server")

        # Check circuit breaker
        health = self._server_health.get(server_name)
        server_config = self.config.mcpServers.get(server_name) if self.config else None

        if health and server_config:
            if not health.should_attempt(server_config.circuit_breaker_reset_seconds):
                raise RuntimeError(
                    f"Circuit breaker OPEN for server {server_name} - "
                    f"server has failed {health.consecutive_failures} consecutive times"
                )

        try:
            timeout = server_config.timeout_seconds if server_config else 30.0
            async with asyncio.timeout(timeout):
                result = await self.sessions[server_name].call_tool(
                    name=tool_name, arguments=params
                )

            # Record success
            if health:
                health.record_success()

            return result

        except asyncio.TimeoutError:
            self.logger.error(
                f"Timeout calling tool {tool_name} on server {server_name}"
            )
            if health and server_config:
                health.record_failure(server_config.circuit_breaker_threshold)

            # Attempt reconnect and retry if enabled
            if retry and server_config and server_config.max_retries > 0:
                self.logger.info(f"Attempting to reconnect to {server_name}...")
                if await self.reconnect_server(server_name):
                    return await self.call_tool(tool_name, params, retry=False)

            raise

        except Exception as e:
            self.logger.error(f"Error calling tool {tool_name}: {str(e)}")
            if health and server_config:
                health.record_failure(server_config.circuit_breaker_threshold)

            # Check if this is a connection error that warrants reconnection
            if retry and self._is_connection_error(e) and server_config:
                self.logger.info(f"Connection error, attempting to reconnect to {server_name}...")
                if await self.reconnect_server(server_name):
                    return await self.call_tool(tool_name, params, retry=False)

            raise

    def _is_connection_error(self, error: Exception) -> bool:
        """Determine if an error is a connection-related error worth retrying."""
        error_types = (
            ConnectionError,
            ConnectionResetError,
            BrokenPipeError,
            OSError,
        )
        error_messages = (
            "connection",
            "broken pipe",
            "reset by peer",
            "closed",
            "eof",
        )
        if isinstance(error, error_types):
            return True
        error_str = str(error).lower()
        return any(msg in error_str for msg in error_messages)

    def get_session(self, server_name: str) -> ClientSession:
        """Get a specific server session."""
        if self._closed:
            raise RuntimeError("Client is closed")
        if server_name not in self.sessions:
            raise KeyError(f"No session found for server {server_name}")
        return self.sessions[server_name]

    async def get_resource(self, server: str, uri: AnyUrl) -> Any:
        """Get a resource from a specific server."""
        if self._closed:
            raise RuntimeError("Client is closed")
        if server not in self.sessions:
            raise KeyError(f"No session found for server {server}")
        return await self.sessions[server].read_resource(uri)

    async def close(self) -> None:
        """Clean up all resources."""
        if not self._closed:
            self._closed = True

            # Cancel health check task if running
            if self._health_check_task and not self._health_check_task.done():
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass

            # Stop Docker containers first
            if self.config:
                for server_name, server_config in self.config.mcpServers.items():
                    if server_config.command == "docker":
                        container_name = None
                        if "--name" in server_config.args:
                            name_index = server_config.args.index("--name") + 1
                            if name_index < len(server_config.args):
                                container_name = f"{server_config.args[name_index]}-{self.instance_id}"
                        else:
                            container_name = f"{server_name}-{self.instance_id}"
                        if container_name:
                            try:
                                import subprocess
                                subprocess.run(
                                    ["docker", "rm", "-f", container_name],
                                    timeout=5,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL,
                                )
                            except Exception as e:
                                self.logger.warning(
                                    f"Error cleaning up Docker container {container_name}: {e}"
                                )

            # Clear sessions and server tools
            self.sessions.clear()
            self.server_tools.clear()
            self._tool_to_server.clear()

            # Close the exit stack
            try:
                await self.exit_stack.aclose()
            except asyncio.TimeoutError:
                self.logger.warning("MCPClient cleanup timed out after 5 seconds")
            except Exception as e:
                self.logger.warning(f"Error during MCPClient cleanup: {e}")
            finally:
                self.exit_stack = AsyncExitStack()

    async def __aenter__(self) -> "MCPClient":
        """Async context manager support."""
        return await self.initialize()

    def __await__(self):
        """Make MCPClient awaitable."""
        return self.initialize().__await__()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Ensure cleanup on context exit."""
        await self.close()
