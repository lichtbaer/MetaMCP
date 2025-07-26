"""
Tests for API versioning functionality.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from metamcp.utils.api_versioning import (
    APIVersionManager,
    APIVersionMiddleware,
    VersionInfo,
    VersionMigrationHelper,
    VersionStatus,
    create_version_middleware,
    get_supported_versions,
    get_version_info,
    is_version_supported,
)


class TestVersionStatus:
    """Test VersionStatus enum."""

    def test_version_status_values(self):
        """Test version status values."""
        assert VersionStatus.CURRENT.value == "current"
        assert VersionStatus.DEPRECATED.value == "deprecated"
        assert VersionStatus.SUNSET.value == "sunset"


class TestVersionInfo:
    """Test VersionInfo class."""

    def test_version_info_creation(self):
        """Test creating version info."""
        now = datetime.utcnow()
        version_info = VersionInfo(
            version="v1",
            status=VersionStatus.CURRENT,
            release_date=now,
            new_features=["Feature 1"],
            bug_fixes=["Bug fix 1"],
            breaking_changes=[],
        )

        assert version_info.version == "v1"
        assert version_info.status == VersionStatus.CURRENT
        assert version_info.release_date == now
        assert version_info.new_features == ["Feature 1"]
        assert version_info.bug_fixes == ["Bug fix 1"]
        assert version_info.breaking_changes == []

    def test_version_info_defaults(self):
        """Test version info with defaults."""
        now = datetime.utcnow()
        version_info = VersionInfo(
            version="v1", status=VersionStatus.CURRENT, release_date=now
        )

        assert version_info.breaking_changes == []
        assert version_info.new_features == []
        assert version_info.bug_fixes == []


class TestAPIVersionManager:
    """Test APIVersionManager class."""

    @pytest.fixture
    def version_manager(self):
        """Create version manager for testing."""
        return APIVersionManager()

    def test_initialization(self, version_manager):
        """Test version manager initialization."""
        assert version_manager.current_version == "v1"
        assert version_manager.default_version == "v1"
        assert "v1" in version_manager.versions
        assert "v2" in version_manager.versions

    def test_add_version(self, version_manager):
        """Test adding a version."""
        now = datetime.utcnow()
        version_info = VersionInfo(
            version="v3", status=VersionStatus.CURRENT, release_date=now
        )

        version_manager.add_version(version_info)

        assert "v3" in version_manager.versions
        assert version_manager.versions["v3"] == version_info

    def test_is_version_supported(self, version_manager):
        """Test checking if version is supported."""
        assert version_manager.is_version_supported("v1") is True
        assert version_manager.is_version_supported("v2") is True
        assert version_manager.is_version_supported("v999") is False

    def test_is_version_deprecated(self, version_manager):
        """Test checking if version is deprecated."""
        # v1 should not be deprecated
        assert version_manager.is_version_deprecated("v1") is False

        # v2 should not be deprecated yet (deprecation_date is in the future)
        assert version_manager.is_version_deprecated("v2") is False

    def test_get_supported_versions(self, version_manager):
        """Test getting supported versions."""
        versions = version_manager.get_supported_versions()

        assert "v1" in versions
        assert "v2" in versions
        assert len(versions) == 2

    def test_get_current_version(self, version_manager):
        """Test getting current version."""
        current = version_manager.get_current_version()
        assert current == "v1"

    def test_get_latest_version(self, version_manager):
        """Test getting latest version."""
        latest = version_manager.get_latest_version()
        assert latest == "v2"  # v2 is newer than v1

    def test_check_compatibility(self, version_manager):
        """Test checking version compatibility."""
        # Same version should be compatible
        compatible, message = version_manager.check_compatibility("v1", "v1")
        assert compatible is True

        # Different versions should be compatible (no breaking changes)
        compatible, message = version_manager.check_compatibility("v1", "v2")
        assert compatible is True

    def test_get_deprecation_warning(self, version_manager):
        """Test getting deprecation warning."""
        # v1 should not have deprecation warning
        warning = version_manager.get_deprecation_warning("v1")
        assert warning is None

        # v2 should not have deprecation warning yet (not deprecated)
        warning = version_manager.get_deprecation_warning("v2")
        assert warning is None


class TestAPIVersionMiddleware:
    """Test APIVersionMiddleware class."""

    @pytest.fixture
    def version_manager(self):
        """Create version manager for testing."""
        return APIVersionManager()

    @pytest.fixture
    def middleware(self, version_manager):
        """Create middleware for testing."""
        return APIVersionMiddleware(version_manager)

    @pytest.mark.asyncio
    async def test_middleware_call_success(self, middleware):
        """Test successful middleware call."""
        request = Mock()
        request.headers = {"accept": "application/vnd.api+json; version=v1"}
        request.url.path = "/api/v1/test"

        # Create a proper response mock
        response_mock = Mock()
        response_mock.headers = {}

        call_next = AsyncMock()
        call_next.return_value = response_mock

        response = await middleware(request, call_next)

        assert response == response_mock
        assert response.headers["X-API-Version"] == "v1"
        call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_middleware_unsupported_version(self, middleware):
        """Test middleware with unsupported version."""
        request = Mock()
        request.headers = {"X-API-Version": "v999"}
        request.url.path = "/api/test"  # No version in path
        request.query_params = {}

        call_next = AsyncMock()

        # Check that the version is actually unsupported
        version = middleware._extract_version(request)
        assert version == "v999"
        assert not middleware.version_manager.is_version_supported(version)

        response = await middleware(request, call_next)

        # The response should be a JSONResponse with status_code attribute
        assert hasattr(response, "status_code")
        assert response.status_code == 400
        # Check that the response content contains version error information
        assert hasattr(response, "body")
        response_content = response.body.decode()
        assert "version_error" in response_content.lower()
        assert "v999" in response_content

    def test_extract_version_from_header(self, middleware):
        """Test extracting version from header."""
        request = Mock()
        request.headers = {"X-API-Version": "v1"}

        version = middleware._extract_version(request)
        assert version == "v1"

    def test_extract_version_from_url(self, middleware):
        """Test extracting version from URL."""
        request = Mock()
        request.headers = {}
        request.url.path = "/api/v2/test"
        request.query_params = {}

        version = middleware._extract_version(request)
        assert version == "v2"

    def test_extract_version_default(self, middleware):
        """Test extracting default version."""
        request = Mock()
        request.headers = {}
        request.url.path = "/api/test"
        request.query_params = {}

        version = middleware._extract_version(request)
        assert version == "v1"  # default version


class TestVersionMigrationHelper:
    """Test VersionMigrationHelper class."""

    @pytest.fixture
    def version_manager(self):
        """Create version manager for testing."""
        return APIVersionManager()

    @pytest.fixture
    def migration_helper(self, version_manager):
        """Create migration helper for testing."""
        return VersionMigrationHelper(version_manager)

    def test_create_migration_guide(self, migration_helper):
        """Test creating migration guide."""
        guide = migration_helper.create_migration_guide("v1", "v2")

        assert "from_version" in guide
        assert "to_version" in guide
        assert "breaking_changes" in guide
        assert "new_features" in guide
        assert guide["from_version"] == "v1"
        assert guide["to_version"] == "v2"

    def test_validate_migration(self, migration_helper):
        """Test validating migration."""
        valid, issues = migration_helper.validate_migration("v1", "v2")

        assert valid is True
        assert isinstance(issues, list)


class TestAPIVersioningFunctions:
    """Test API versioning utility functions."""

    def test_create_version_middleware(self):
        """Test creating version middleware."""
        middleware = create_version_middleware()

        assert middleware is not None
        assert hasattr(middleware, "_extract_version")

    def test_get_version_info(self):
        """Test getting version info."""
        info = get_version_info("v1")

        assert info is not None
        assert info.version == "v1"
        assert info.status == VersionStatus.CURRENT

    def test_get_version_info_nonexistent(self):
        """Test getting version info for nonexistent version."""
        info = get_version_info("v999")

        assert info is None

    def test_is_version_supported(self):
        """Test checking if version is supported."""
        assert is_version_supported("v1") is True
        assert is_version_supported("v2") is True
        assert is_version_supported("v999") is False

    def test_get_supported_versions(self):
        """Test getting supported versions."""
        versions = get_supported_versions()

        assert "v1" in versions
        assert "v2" in versions
        assert len(versions) == 2


class TestAPIVersioningIntegration:
    """Test API versioning integration scenarios."""

    def test_complete_version_lifecycle(self):
        """Test complete version lifecycle."""
        manager = APIVersionManager()

        # Add a new version
        now = datetime.utcnow()
        v3_info = VersionInfo(
            version="v3",
            status=VersionStatus.CURRENT,
            release_date=now,
            new_features=["New feature"],
            breaking_changes=["Breaking change"],
        )
        manager.add_version(v3_info)

        # Test version management
        assert manager.is_version_supported("v3") is True
        assert manager.get_latest_version() == "v3"

        # Test compatibility
        compatible, message = manager.check_compatibility("v1", "v3")
        assert compatible is True  # No breaking changes in default setup

        # Test deprecation
        v3_info.status = VersionStatus.DEPRECATED
        v3_info.deprecation_date = now + timedelta(days=30)
        assert manager.is_version_deprecated("v3") is True

    def test_middleware_integration(self):
        """Test middleware integration."""
        manager = APIVersionManager()
        middleware = APIVersionMiddleware(manager)

        # Test with valid version
        request = Mock()
        request.headers = {"accept": "application/vnd.api+json; version=v1"}
        request.url.path = "/api/v1/test"

        call_next = Mock()
        call_next.return_value = {"status": "success"}

        # This would be an async test in practice
        # For now, just test the version extraction
        version = middleware._extract_version(request)
        assert version == "v1"

    def test_migration_helper_integration(self):
        """Test migration helper integration."""
        manager = APIVersionManager()
        helper = VersionMigrationHelper(manager)

        # Test migration guide creation
        guide = helper.create_migration_guide("v1", "v2")

        assert guide["from_version"] == "v1"
        assert guide["to_version"] == "v2"
        assert "breaking_changes" in guide
        assert "new_features" in guide

        # Test migration validation
        valid, issues = helper.validate_migration("v1", "v2")
        assert valid is True
