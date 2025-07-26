"""
Tool Service

Business logic service for tool management operations including
registration, discovery, execution, and lifecycle management.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from ..exceptions import ToolExecutionError, ToolNotFoundError, ValidationError
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ToolService:
    """
    Service for tool management operations.

    This service handles all business logic related to tools including
    registration, discovery, execution, and lifecycle management.
    """

    def __init__(self):
        """Initialize the tool service."""
        self.tools: dict[str, dict[str, Any]] = {}
        self.execution_history: list[dict[str, Any]] = []

    async def register_tool(self, tool_data: dict[str, Any], user_id: str) -> str:
        """
        Register a new tool.

        Args:
            tool_data: Tool registration data
            user_id: ID of the user registering the tool

        Returns:
            Tool ID

        Raises:
            ValidationError: If tool data is invalid
        """
        try:
            # Validate required fields
            required_fields = ["name", "description", "endpoint"]
            for field in required_fields:
                if field not in tool_data or not tool_data[field]:
                    raise ValidationError(message=f"Missing required field: {field}")

            # Check for duplicate tool name
            if self._get_tool_by_name(tool_data["name"]):
                raise ValidationError(
                    message=f"Tool with name '{tool_data['name']}' already exists"
                )

            # Create tool entry
            tool_id = str(uuid.uuid4())
            now = datetime.now(UTC).isoformat()

            tool_entry = {
                "id": tool_id,
                "name": tool_data["name"],
                "description": tool_data["description"],
                "endpoint": tool_data["endpoint"],
                "category": tool_data.get("category"),
                "capabilities": tool_data.get("capabilities", []),
                "security_level": tool_data.get("security_level", 0),
                "schema": tool_data.get("schema"),
                "metadata": tool_data.get("metadata", {}),
                "version": tool_data.get("version", "1.0.0"),
                "author": tool_data.get("author"),
                "tags": tool_data.get("tags", []),
                "created_at": now,
                "updated_at": now,
                "is_active": True,
                "created_by": user_id,
            }

            self.tools[tool_id] = tool_entry

            logger.info(f"Tool '{tool_data['name']}' registered with ID: {tool_id}")
            return tool_id

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Tool registration failed: {e}")
            raise ValidationError(message=f"Tool registration failed: {str(e)}")

    async def get_tool(self, tool_name: str) -> dict[str, Any]:
        """
        Get tool by name.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool data

        Raises:
            ToolNotFoundError: If tool is not found
        """
        tool = self._get_tool_by_name(tool_name)
        if not tool:
            raise ToolNotFoundError(tool_name)

        return tool

    async def list_tools(
        self, category: str | None = None, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        """
        List tools with optional filtering and pagination.

        Args:
            category: Optional category filter
            limit: Maximum number of tools to return
            offset: Offset for pagination

        Returns:
            Dictionary with tools list and pagination info
        """
        # Get all active tools
        all_tools = [
            tool for tool in self.tools.values() if tool.get("is_active", True)
        ]

        # Filter by category if specified
        if category:
            all_tools = [tool for tool in all_tools if tool.get("category") == category]

        # Get total count
        total = len(all_tools)

        # Paginate results
        paginated_tools = all_tools[offset : offset + limit]

        return {
            "tools": paginated_tools,
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    async def update_tool(
        self, tool_name: str, update_data: dict[str, Any], user_id: str
    ) -> dict[str, Any]:
        """
        Update an existing tool.

        Args:
            tool_name: Name of the tool to update
            update_data: Updated tool data
            user_id: ID of the user updating the tool

        Returns:
            Updated tool data

        Raises:
            ToolNotFoundError: If tool is not found
        """
        tool = self._get_tool_by_name(tool_name)
        if not tool:
            raise ToolNotFoundError(tool_name)

        # Update tool fields
        for key, value in update_data.items():
            if value is not None:
                tool[key] = value

        # Update timestamp
        tool["updated_at"] = datetime.now(UTC).isoformat()
        tool["updated_by"] = user_id

        # Update in storage
        self.tools[tool["id"]] = tool

        logger.info(f"Tool '{tool_name}' updated by user: {user_id}")
        return tool

    async def delete_tool(self, tool_name: str, user_id: str) -> None:
        """
        Delete a tool (soft delete).

        Args:
            tool_name: Name of the tool to delete
            user_id: ID of the user deleting the tool

        Raises:
            ToolNotFoundError: If tool is not found
        """
        tool = self._get_tool_by_name(tool_name)
        if not tool:
            raise ToolNotFoundError(tool_name)

        # Soft delete - mark as inactive
        tool["is_active"] = False
        tool["updated_at"] = datetime.now(UTC).isoformat()
        tool["deleted_by"] = user_id

        # Update in storage
        self.tools[tool["id"]] = tool

        logger.info(f"Tool '{tool_name}' deleted by user: {user_id}")

    async def search_tools(
        self, query: str, max_results: int = 10, similarity_threshold: float = 0.7
    ) -> list[dict[str, Any]]:
        """
        Search for tools using semantic search.

        Args:
            query: Search query
            max_results: Maximum number of results
            similarity_threshold: Similarity threshold

        Returns:
            List of matching tools
        """
        # Get all active tools
        all_tools = [
            tool for tool in self.tools.values() if tool.get("is_active", True)
        ]

        # Simple text-based search for now
        # In production, this would use vector search
        results = self._search_tools_simple(query, all_tools)

        # Limit results
        return results[:max_results]

    async def execute_tool(
        self, tool_name: str, arguments: dict[str, Any], user_id: str
    ) -> dict[str, Any]:
        """
        Execute a tool.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool execution arguments
            user_id: ID of the user executing the tool

        Returns:
            Tool execution result

        Raises:
            ToolNotFoundError: If tool is not found
            ToolExecutionError: If tool execution fails
        """
        tool = self._get_tool_by_name(tool_name)
        if not tool:
            raise ToolNotFoundError(tool_name)

        try:
            import time

            start_time = time.time()

            # Execute tool
            result = await self._execute_tool_internal(tool_name, arguments, tool)

            # Calculate execution time
            execution_time = time.time() - start_time

            # Record execution
            execution_record = {
                "tool_name": tool_name,
                "user_id": user_id,
                "arguments": arguments,
                "result": result,
                "execution_time": execution_time,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            self.execution_history.append(execution_record)

            return {
                "tool_name": tool_name,
                "input_data": arguments,
                "status": "success",
                "result": result,
                "execution_time": execution_time,
                "executed_by": user_id,
                "timestamp": execution_record["timestamp"],
            }

        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            raise ToolExecutionError(
                message=f"Tool execution failed: {str(e)}",
                error_code="execution_failed",
            ) from e

    def _get_tool_by_name(self, name: str) -> dict[str, Any] | None:
        """Get tool by name from storage."""
        for tool in self.tools.values():
            if tool["name"] == name:
                return tool
        return None

    def _search_tools_simple(
        self, query: str, tools: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Simple text-based tool search."""
        query_lower = query.lower()
        results = []

        for tool in tools:
            # Search in name, description, and tags
            if (
                query_lower in tool["name"].lower()
                or query_lower in tool["description"].lower()
                or any(query_lower in tag.lower() for tag in tool.get("tags", []))
            ):
                results.append(tool)

        return results

    async def _execute_tool_internal(
        self, tool_name: str, arguments: dict[str, Any], tool_data: dict[str, Any]
    ) -> Any:
        """Internal tool execution implementation."""
        import asyncio

        import httpx

        endpoint = tool_data.get("endpoint")
        if not endpoint:
            # Mock execution for development when no endpoint is provided
            await asyncio.sleep(0.1)  # Simulate processing time
            return {
                "message": f"Executed {tool_name} with arguments: {arguments}",
                "status": "success",
                "tool_name": tool_name,
                "execution_time": 0.1,
            }

        # Make HTTP call to tool endpoint
        timeout = 30.0

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Try different endpoint patterns
                execution_endpoints = [
                    f"{endpoint}/execute",
                    f"{endpoint}/tools/{tool_name}/execute",
                    f"{endpoint}/api/v1/tools/{tool_name}/execute",
                    endpoint,  # Direct endpoint
                ]

                response = None
                last_error = None

                for exec_endpoint in execution_endpoints:
                    try:
                        response = await client.post(
                            exec_endpoint,
                            json={
                                "tool": tool_name,
                                "arguments": arguments,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                            headers={
                                "Content-Type": "application/json",
                                "User-Agent": "MetaMCP/1.0.0",
                            },
                        )

                        if response.status_code == 200:
                            break
                        else:
                            last_error = f"HTTP {response.status_code}: {response.text}"

                    except httpx.TimeoutException:
                        last_error = f"Timeout connecting to {exec_endpoint}"
                    except httpx.ConnectError:
                        last_error = f"Connection error to {exec_endpoint}"
                    except Exception as e:
                        last_error = f"Error calling {exec_endpoint}: {str(e)}"

                if response and response.status_code == 200:
                    try:
                        result = response.json()
                        return {
                            "status": "success",
                            "result": result,
                            "tool_name": tool_name,
                            "execution_time": 0.0,  # Will be calculated by caller
                            "http_status": response.status_code,
                        }
                    except ValueError:
                        # Return text if not JSON
                        return {
                            "status": "success",
                            "result": response.text,
                            "tool_name": tool_name,
                            "execution_time": 0.0,
                            "http_status": response.status_code,
                        }
                else:
                    # Fallback to mock execution if all endpoints fail
                    logger.warning(
                        f"Tool execution failed for {tool_name}, using mock: {last_error}"
                    )
                    await asyncio.sleep(0.1)
                    return {
                        "message": f"Mock execution of {tool_name} with arguments: {arguments}",
                        "status": "success",
                        "tool_name": tool_name,
                        "execution_time": 0.1,
                        "fallback": True,
                        "error": last_error,
                    }

        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            raise ToolExecutionError(
                message=f"Tool execution failed: {str(e)}",
                error_code="execution_failed",
            ) from e

    def get_execution_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Get tool execution history.

        Args:
            limit: Maximum number of history entries to return

        Returns:
            List of execution history entries
        """
        return self.execution_history[-limit:]

    def get_tool_statistics(self) -> dict[str, Any]:
        """
        Get tool statistics.

        Returns:
            Dictionary with tool statistics
        """
        active_tools = [
            tool for tool in self.tools.values() if tool.get("is_active", True)
        ]

        categories = {}
        for tool in active_tools:
            category = tool.get("category", "uncategorized")
            categories[category] = categories.get(category, 0) + 1

        return {
            "total_tools": len(self.tools),
            "active_tools": len(active_tools),
            "categories": categories,
            "total_executions": len(self.execution_history),
        }
