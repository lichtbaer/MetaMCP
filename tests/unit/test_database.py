"""
Unit tests for database connection pooling.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from metamcp.utils.database import DatabaseManager, get_database_manager


class TestDatabaseManager:
    @pytest.fixture
    def db_manager(self):
        return DatabaseManager()

    @pytest.mark.asyncio
    async def test_initialize_without_url(self, db_manager):
        """Test initialization without URL."""
        # Mock settings to return None for database_url
        with patch("metamcp.utils.database.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_settings.database_url = None
            mock_get_settings.return_value = mock_settings

            # Set the settings on the db_manager
            db_manager._settings = mock_settings

            await db_manager.initialize()
            # Should not raise an exception, just log a warning
            assert db_manager._pool is None

    @pytest.mark.asyncio
    async def test_initialize_with_url(self, db_manager):
        """Test initialization with URL."""
        with (
            patch("metamcp.utils.database.get_settings") as mock_get_settings,
            patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool,
        ):

            mock_settings = Mock()
            mock_settings.database_url = "postgresql://test"
            mock_get_settings.return_value = mock_settings

            # Set the settings on the db_manager
            db_manager._settings = mock_settings

            mock_pool = Mock()
            mock_connection = Mock()
            mock_connection.fetchval = AsyncMock(return_value=1)

            # Create proper async context manager for pool.acquire
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_connection
            mock_context.__aexit__.return_value = None
            mock_pool.acquire.return_value = mock_context
            mock_create_pool.return_value = mock_pool

            await db_manager.initialize()

            mock_create_pool.assert_called_once()
            assert db_manager._pool == mock_pool

    @pytest.mark.asyncio
    async def test_close(self, db_manager):
        """Test closing the database pool."""
        mock_pool = AsyncMock()
        db_manager._pool = mock_pool

        await db_manager.close()

        mock_pool.close.assert_called_once()
        assert db_manager._pool is None

    @pytest.mark.asyncio
    async def test_health_check_uninitialized(self, db_manager):
        """Test health check when pool is not initialized."""
        result = await db_manager.health_check()
        assert result["status"] == "unhealthy"
        assert "Pool not initialized" in result["error"]

    @pytest.mark.asyncio
    async def test_health_check_success(self, db_manager):
        """Test successful health check."""
        mock_pool = Mock()
        mock_connection = Mock()
        mock_connection.fetchval = AsyncMock(return_value=1)

        # Mock pool methods
        mock_pool.get_size.return_value = 10
        mock_pool.get_min_size.return_value = 5
        mock_pool.get_max_size.return_value = 20
        mock_pool.get_idle_size.return_value = 8

        # Create proper async context manager for pool.acquire
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_connection
        mock_context.__aexit__.return_value = None
        mock_pool.acquire.return_value = mock_context

        db_manager._pool = mock_pool

        result = await db_manager.health_check()
        assert result["status"] == "healthy"
        assert "response_time" in result
        assert result["test_query_result"] == 1
        assert "pool_stats" in result

    @pytest.mark.asyncio
    async def test_get_pool_stats(self, db_manager):
        """Test getting pool statistics."""
        mock_pool = Mock()
        mock_pool.get_size.return_value = 10
        mock_pool.get_min_size.return_value = 5
        mock_pool.get_max_size.return_value = 20
        mock_pool.get_idle_size.return_value = 8

        db_manager._pool = mock_pool

        stats = await db_manager.get_pool_stats()
        assert stats["size"] == 10
        assert stats["min_size"] == 5
        assert stats["max_size"] == 20
        assert stats["idle_size"] == 8
        assert stats["busy_connections"] == 2

    @pytest.mark.asyncio
    async def test_execute_query(self, db_manager):
        """Test executing a query."""
        mock_connection = Mock()
        mock_connection.execute = AsyncMock()

        mock_pool = Mock()
        # Create proper async context manager for pool.acquire
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_connection
        mock_context.__aexit__.return_value = None
        mock_pool.acquire.return_value = mock_context
        db_manager._pool = mock_pool

        await db_manager.execute("INSERT INTO test VALUES ($1)", "value")
        mock_connection.execute.assert_called_once_with(
            "INSERT INTO test VALUES ($1)", "value"
        )

    @pytest.mark.asyncio
    async def test_fetch_query(self, db_manager):
        """Test fetching multiple rows."""
        mock_connection = Mock()
        mock_connection.fetch = AsyncMock(return_value=[{"id": 1}, {"id": 2}])

        mock_pool = Mock()
        # Create proper async context manager for pool.acquire
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_connection
        mock_context.__aexit__.return_value = None
        mock_pool.acquire.return_value = mock_context
        db_manager._pool = mock_pool

        result = await db_manager.fetch("SELECT * FROM test")
        assert result == [{"id": 1}, {"id": 2}]
        mock_connection.fetch.assert_called_once_with("SELECT * FROM test")

    @pytest.mark.asyncio
    async def test_fetchval_query(self, db_manager):
        """Test fetching a single value."""
        mock_connection = Mock()
        mock_connection.fetchval = AsyncMock(return_value=42)

        mock_pool = Mock()
        # Create proper async context manager for pool.acquire
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_connection
        mock_context.__aexit__.return_value = None
        mock_pool.acquire.return_value = mock_context
        db_manager._pool = mock_pool

        result = await db_manager.fetchval("SELECT COUNT(*) FROM test")
        assert result == 42
        mock_connection.fetchval.assert_called_once_with("SELECT COUNT(*) FROM test")


def test_get_database_manager_singleton():
    """Test that get_database_manager returns singleton."""
    manager1 = get_database_manager()
    manager2 = get_database_manager()
    assert manager1 is manager2
