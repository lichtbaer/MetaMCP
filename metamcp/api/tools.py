"""
Tools API Router

This module provides REST API endpoints for tool management including
registration, search, execution, and CRUD operations.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..config import get_settings
from ..exceptions import MetaMCPError, ToolNotFoundError, ValidationError
from ..utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Create router
tools_router = APIRouter()

# Mock tool registry (in production, this would be a database)
mock_tools: dict[str, dict[str, Any]] = {}


# =============================================================================
# Pydantic Models
# =============================================================================


class ToolRegistrationRequest(BaseModel):
    """Request model for tool registration."""

    name: str = Field(..., description="Tool name (unique identifier)")
    description: str = Field(..., description="Tool description")
    endpoint: str = Field(..., description="Tool endpoint URL")
    category: str | None = Field(None, description="Tool category")
    capabilities: list[str] | None = Field(default=[], description="Tool capabilities")
    security_level: int | None = Field(default=0, description="Security level (0-10)")
    schema: dict[str, Any] | None = Field(None, description="Tool input/output schema")
    metadata: dict[str, Any] | None = Field(
        default={}, description="Additional metadata"
    )
    version: str | None = Field(default="1.0.0", description="Tool version")
    author: str | None = Field(None, description="Tool author")
    tags: list[str] | None = Field(default=[], description="Tool tags")


class ToolUpdateRequest(BaseModel):
    """Request model for tool updates."""

    description: str | None = Field(None, description="Tool description")
    endpoint: str | None = Field(None, description="Tool endpoint URL")
    category: str | None = Field(None, description="Tool category")
    capabilities: list[str] | None = Field(None, description="Tool capabilities")
    security_level: int | None = Field(None, description="Security level (0-10)")
    schema: dict[str, Any] | None = Field(None, description="Tool input/output schema")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")
    version: str | None = Field(None, description="Tool version")
    tags: list[str] | None = Field(None, description="Tool tags")


class ToolSearchRequest(BaseModel):
    """Request model for tool search."""

    query: str = Field(..., description="Natural language search query")
    max_results: int | None = Field(default=10, description="Maximum number of results")
    similarity_threshold: float | None = Field(
        default=0.7, description="Similarity threshold"
    )
    category: str | None = Field(None, description="Filter by category")


class ToolExecutionRequest(BaseModel):
    """Request model for tool execution."""

    input_data: dict[str, Any] = Field(..., description="Tool input data")
    async_execution: bool | None = Field(
        default=False, description="Execute asynchronously"
    )


class ToolResponse(BaseModel):
    """Response model for tool data."""

    id: str
    name: str
    description: str
    endpoint: str
    category: str | None
    capabilities: list[str]
    security_level: int
    schema: dict[str, Any] | None
    metadata: dict[str, Any]
    version: str
    author: str | None
    tags: list[str]
    created_at: str
    updated_at: str
    is_active: bool


class ToolListResponse(BaseModel):
    """Response model for tool list."""

    tools: list[ToolResponse]
    total: int
    offset: int
    limit: int


class ToolSearchResponse(BaseModel):
    """Response model for tool search."""

    tools: list[dict[str, Any]]
    query: str
    total: int
    search_time: float


# =============================================================================
# Mock Tool Registry Functions
# =============================================================================


def _create_tool_id() -> str:
    """Create a unique tool ID."""
    return str(uuid.uuid4())


def _get_tool_by_name(name: str) -> dict[str, Any] | None:
    """Get tool by name from mock registry."""
    for tool in mock_tools.values():
        if tool["name"] == name:
            return tool
    return None


def _filter_tools_by_category(
    tools: list[dict[str, Any]], category: str | None
) -> list[dict[str, Any]]:
    """Filter tools by category."""
    if category is None:
        return tools
    return [tool for tool in tools if tool.get("category") == category]


def _paginate_tools(
    tools: list[dict[str, Any]], offset: int, limit: int
) -> list[dict[str, Any]]:
    """Paginate tools list."""
    return tools[offset : offset + limit]


def _search_tools_simple(
    query: str, tools: list[dict[str, Any]]
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


# =============================================================================
# Dependencies
# =============================================================================


async def get_current_user_id() -> str:
    """Get current user ID from authentication context."""
    # This would be implemented with proper authentication
    return "system_user"


async def get_mcp_server():
    """Get MCP server instance from FastAPI app state."""
    # This will be injected by the main application
    pass


# =============================================================================
# API Endpoints
# =============================================================================


@tools_router.post(
    "/",
    response_model=dict[str, str],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new tool",
)
async def register_tool(
    tool_data: ToolRegistrationRequest,
    user_id: str = Depends(get_current_user_id),
    mcp_server=Depends(get_mcp_server),
):
    """
    Register a new tool in the registry.

    Args:
        tool_data: Tool registration data
        user_id: Current user ID
        mcp_server: MCP server instance

    Returns:
        Tool registration result with tool ID
    """
    try:
        # Check if tool with same name already exists
        if _get_tool_by_name(tool_data.name):
            raise ValidationError(
                message=f"Tool with name '{tool_data.name}' already exists",
                field="name",
            )

        # Create tool entry
        tool_id = _create_tool_id()
        now = datetime.now(UTC).isoformat()

        tool_entry = {
            "id": tool_id,
            "name": tool_data.name,
            "description": tool_data.description,
            "endpoint": tool_data.endpoint,
            "category": tool_data.category,
            "capabilities": tool_data.capabilities or [],
            "security_level": tool_data.security_level or 0,
            "schema": tool_data.schema,
            "metadata": tool_data.metadata or {},
            "version": tool_data.version or "1.0.0",
            "author": tool_data.author,
            "tags": tool_data.tags or [],
            "created_at": now,
            "updated_at": now,
            "is_active": True,
            "created_by": user_id,
        }

        mock_tools[tool_id] = tool_entry

        logger.info(f"Tool '{tool_data.name}' registered with ID: {tool_id}")

        return {"tool_id": tool_id, "message": "Tool registered successfully"}

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": e.error_code,
                    "message": e.message,
                    "details": e.details,
                }
            },
        )
    except MetaMCPError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": {
                    "code": e.error_code,
                    "message": e.message,
                    "details": e.details,
                }
            },
        )


@tools_router.get("/", response_model=ToolListResponse, summary="List all tools")
async def list_tools(
    category: str | None = Query(None, description="Filter by category"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of tools to return"
    ),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    user_id: str = Depends(get_current_user_id),
    mcp_server=Depends(get_mcp_server),
):
    """
    List all available tools with pagination.

    Args:
        category: Optional category filter
        limit: Maximum number of tools to return
        offset: Offset for pagination
        user_id: Current user ID
        mcp_server: MCP server instance

    Returns:
        List of tools with pagination information
    """
    try:
        # Get all active tools
        all_tools = [
            tool for tool in mock_tools.values() if tool.get("is_active", True)
        ]

        # Filter by category if specified
        filtered_tools = _filter_tools_by_category(all_tools, category)

        # Get total count
        total = len(filtered_tools)

        # Paginate results
        paginated_tools = _paginate_tools(filtered_tools, offset, limit)

        # Convert to response format
        tool_responses = [
            ToolResponse(
                id=tool["id"],
                name=tool["name"],
                description=tool["description"],
                endpoint=tool["endpoint"],
                category=tool["category"],
                capabilities=tool["capabilities"],
                security_level=tool["security_level"],
                schema=tool["schema"],
                metadata=tool["metadata"],
                version=tool["version"],
                author=tool["author"],
                tags=tool["tags"],
                created_at=tool["created_at"],
                updated_at=tool["updated_at"],
                is_active=tool["is_active"],
            )
            for tool in paginated_tools
        ]

        return ToolListResponse(
            tools=tool_responses, total=total, offset=offset, limit=limit
        )

    except MetaMCPError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": {
                    "code": e.error_code,
                    "message": e.message,
                    "details": e.details,
                }
            },
        )


@tools_router.get(
    "/{tool_name}", response_model=ToolResponse, summary="Get tool details"
)
async def get_tool(
    tool_name: str,
    user_id: str = Depends(get_current_user_id),
    mcp_server=Depends(get_mcp_server),
):
    """
    Get detailed information about a specific tool.

    Args:
        tool_name: Name of the tool
        user_id: Current user ID
        mcp_server: MCP server instance

    Returns:
        Tool details
    """
    try:
        tool = _get_tool_by_name(tool_name)
        if not tool:
            raise ToolNotFoundError(tool_name)

        return ToolResponse(
            id=tool["id"],
            name=tool["name"],
            description=tool["description"],
            endpoint=tool["endpoint"],
            category=tool["category"],
            capabilities=tool["capabilities"],
            security_level=tool["security_level"],
            schema=tool["schema"],
            metadata=tool["metadata"],
            version=tool["version"],
            author=tool["author"],
            tags=tool["tags"],
            created_at=tool["created_at"],
            updated_at=tool["updated_at"],
            is_active=tool["is_active"],
        )

    except ToolNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": e.error_code,
                    "message": e.message,
                    "details": e.details,
                }
            },
        )
    except MetaMCPError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": {
                    "code": e.error_code,
                    "message": e.message,
                    "details": e.details,
                }
            },
        )


@tools_router.put("/{tool_name}", response_model=ToolResponse, summary="Update tool")
async def update_tool(
    tool_name: str,
    tool_data: ToolUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    mcp_server=Depends(get_mcp_server),
):
    """
    Update an existing tool.

    Args:
        tool_name: Name of the tool to update
        tool_data: Updated tool data
        user_id: Current user ID
        mcp_server: MCP server instance

    Returns:
        Updated tool details
    """
    try:
        tool = _get_tool_by_name(tool_name)
        if not tool:
            raise ToolNotFoundError(tool_name)

        # Update tool fields
        update_data = tool_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                tool[key] = value

        # Update timestamp
        tool["updated_at"] = datetime.now(UTC).isoformat()
        tool["updated_by"] = user_id

        # Update in registry
        mock_tools[tool["id"]] = tool

        logger.info(f"Tool '{tool_name}' updated by user: {user_id}")

        return ToolResponse(
            id=tool["id"],
            name=tool["name"],
            description=tool["description"],
            endpoint=tool["endpoint"],
            category=tool["category"],
            capabilities=tool["capabilities"],
            security_level=tool["security_level"],
            schema=tool["schema"],
            metadata=tool["metadata"],
            version=tool["version"],
            author=tool["author"],
            tags=tool["tags"],
            created_at=tool["created_at"],
            updated_at=tool["updated_at"],
            is_active=tool["is_active"],
        )

    except ToolNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": e.error_code,
                    "message": e.message,
                    "details": e.details,
                }
            },
        )
    except MetaMCPError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": {
                    "code": e.error_code,
                    "message": e.message,
                    "details": e.details,
                }
            },
        )


@tools_router.delete(
    "/{tool_name}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete tool"
)
async def delete_tool(
    tool_name: str,
    user_id: str = Depends(get_current_user_id),
    mcp_server=Depends(get_mcp_server),
):
    """
    Delete a tool from the registry.

    Args:
        tool_name: Name of the tool to delete
        user_id: Current user ID
        mcp_server: MCP server instance
    """
    try:
        tool = _get_tool_by_name(tool_name)
        if not tool:
            raise ToolNotFoundError(tool_name)

        # Soft delete - mark as inactive
        tool["is_active"] = False
        tool["updated_at"] = datetime.now(UTC).isoformat()
        tool["deleted_by"] = user_id

        # Update in registry
        mock_tools[tool["id"]] = tool

        logger.info(f"Tool '{tool_name}' deleted by user: {user_id}")

    except ToolNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": e.error_code,
                    "message": e.message,
                    "details": e.details,
                }
            },
        )
    except MetaMCPError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": {
                    "code": e.error_code,
                    "message": e.message,
                    "details": e.details,
                }
            },
        )


@tools_router.post("/search", response_model=ToolSearchResponse, summary="Search tools")
async def search_tools(
    search_request: ToolSearchRequest,
    user_id: str = Depends(get_current_user_id),
    mcp_server=Depends(get_mcp_server),
):
    """
    Search for tools using semantic search.

    Args:
        search_request: Search parameters
        user_id: Current user ID
        mcp_server: MCP server instance

    Returns:
        Search results with metadata
    """
    try:
        import time

        start_time = time.time()

        # Get all active tools
        all_tools = [
            tool for tool in mock_tools.values() if tool.get("is_active", True)
        ]

        # Filter by category if specified
        if search_request.category:
            all_tools = _filter_tools_by_category(all_tools, search_request.category)

        # Perform search
        search_results = _search_tools_simple(search_request.query, all_tools)

        # Limit results
        max_results = search_request.max_results or 10
        search_results = search_results[:max_results]

        # Calculate search time
        search_time = time.time() - start_time

        logger.info(
            f"Tool search completed in {search_time:.3f}s, found {len(search_results)} results"
        )

        return ToolSearchResponse(
            tools=search_results,
            query=search_request.query,
            total=len(search_results),
            search_time=search_time,
        )

    except MetaMCPError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": {
                    "code": e.error_code,
                    "message": e.message,
                    "details": e.details,
                }
            },
        )


@tools_router.post("/{tool_name}/execute", summary="Execute tool")
async def execute_tool(
    tool_name: str,
    execution_request: ToolExecutionRequest,
    user_id: str = Depends(get_current_user_id),
    mcp_server=Depends(get_mcp_server),
):
    """
    Execute a specific tool.

    Args:
        tool_name: Name of the tool to execute
        execution_request: Execution parameters
        user_id: Current user ID
        mcp_server: MCP server instance

    Returns:
        Tool execution result
    """
    try:
        tool = _get_tool_by_name(tool_name)
        if not tool:
            raise ToolNotFoundError(tool_name)

        # Mock tool execution
        # In production, this would make an HTTP call to the tool endpoint
        result = {
            "tool_name": tool_name,
            "input_data": execution_request.input_data,
            "status": "success",
            "result": f"Mock execution of {tool_name} with input: {execution_request.input_data}",
            "execution_time": 0.1,
            "executed_by": user_id,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        logger.info(f"Tool '{tool_name}' executed by user: {user_id}")

        return result

    except ToolNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": e.error_code,
                    "message": e.message,
                    "details": e.details,
                }
            },
        )
    except MetaMCPError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": {
                    "code": e.error_code,
                    "message": e.message,
                    "details": e.details,
                }
            },
        )
