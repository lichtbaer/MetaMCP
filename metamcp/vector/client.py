"""
Vector Search Client

This module provides vector search functionality using Weaviate.
It handles embeddings storage, search, and similarity calculations.
"""

from typing import Any

import weaviate

from ..config import get_settings
from ..exceptions import VectorSearchError
from ..utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class VectorSearchClient:
    """
    Vector Search Client using Weaviate.

    This class provides vector search functionality for semantic
    tool discovery and similarity matching.
    """

    def __init__(self, url: str, api_key: str | None = None, timeout: int = 30):
        """
        Initialize Vector Search Client.

        Args:
            url: Weaviate server URL
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
        """
        self.url = url
        self.api_key = api_key
        self.timeout = timeout

        # Weaviate client
        self.client: weaviate.WeaviateClient | None = None

        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the vector search client."""
        if self._initialized:
            return

        try:
            logger.info("Initializing Vector Search Client...")

            # Create Weaviate client using v4 API
            import weaviate
            from weaviate.classes.init import Auth

            if self.api_key:
                # Parse URL to extract host and port
                from urllib.parse import urlparse

                parsed_url = urlparse(self.url)
                host = parsed_url.hostname
                port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
                secure = parsed_url.scheme == "https"

                self.client = weaviate.connect_to_custom(
                    http_host=host,
                    http_port=port,
                    http_secure=secure,
                    grpc_host=host,
                    grpc_port=port,
                    grpc_secure=secure,
                    auth_credentials=Auth.api_key(self.api_key),
                )
            else:
                # For local development without authentication
                from urllib.parse import urlparse

                parsed_url = urlparse(self.url)
                host = parsed_url.hostname
                port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
                secure = parsed_url.scheme == "https"

                self.client = weaviate.connect_to_custom(
                    http_host=host,
                    http_port=port,
                    http_secure=secure,
                    grpc_host=host,
                    grpc_port=port,
                    grpc_secure=secure,
                )

            # Test connection
            await self._test_connection()

            # Initialize collections
            await self._initialize_collections()

            self._initialized = True
            logger.info("Vector Search Client initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Vector Search Client: {e}")
            raise VectorSearchError(
                message=f"Failed to initialize vector search client: {str(e)}",
                error_code="vector_init_failed",
            ) from e

    async def _test_connection(self) -> None:
        """Test connection to Weaviate."""
        try:
            # Simple health check using v4 API
            self.client.get_meta()
            logger.info("Weaviate connection test successful")
        except Exception as e:
            logger.error(f"Weaviate connection test failed: {e}")
            raise VectorSearchError(
                message=f"Weaviate connection failed: {str(e)}",
                error_code="connection_failed",
            ) from e

    async def _initialize_collections(self) -> None:
        """Initialize required collections."""
        try:
            # Create tools collection if it doesn't exist
            try:
                self.client.collections.get("tools")
                logger.info("Tools collection already exists")
            except Exception:
                # Collection doesn't exist, create it
                from weaviate.classes.config import Configure, DataType, Property

                self.client.collections.create(
                    name="tools",
                    vectorizer_config=Configure.Vectorizer.none(),
                    properties=[
                        Property(name="name", data_type=DataType.TEXT),
                        Property(name="description", data_type=DataType.TEXT),
                        Property(name="categories", data_type=DataType.TEXT_ARRAY),
                        Property(name="endpoint", data_type=DataType.TEXT),
                        Property(name="security_level", data_type=DataType.TEXT),
                        Property(name="registered_at", data_type=DataType.DATE),
                        Property(name="status", data_type=DataType.TEXT),
                    ],
                )
                logger.info("Created tools collection")

        except Exception as e:
            logger.error(f"Failed to initialize collections: {e}")
            raise VectorSearchError(
                message=f"Failed to initialize collections: {str(e)}",
                error_code="collection_init_failed",
            ) from e

    async def store_embedding(
        self, collection: str, id: str, embedding: list[float], metadata: dict[str, Any]
    ) -> None:
        """
        Store an embedding with metadata.

        Args:
            collection: Collection name
            id: Unique identifier
            embedding: Vector embedding
            metadata: Associated metadata
        """
        try:
            if not self.client:
                raise VectorSearchError(
                    message="Vector client not initialized",
                    error_code="client_not_initialized",
                )

            # Prepare data object
            data_object = {
                "name": metadata.get("name", ""),
                "description": metadata.get("description", ""),
                "categories": metadata.get("categories", []),
                "endpoint": metadata.get("endpoint", ""),
                "security_level": metadata.get("security_level", "low"),
                "registered_at": metadata.get("registered_at", ""),
                "status": metadata.get("status", "active"),
            }

            # Store in Weaviate
            self.client.collections.get(collection).data.insert(
                data_object=data_object, uuid=id, vector=embedding
            )

            logger.info(f"Stored embedding for {id} in collection {collection}")

        except Exception as e:
            logger.error(f"Failed to store embedding: {e}")
            raise VectorSearchError(
                message=f"Failed to store embedding: {str(e)}",
                error_code="store_failed",
            ) from e

    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """
        Search for similar embeddings.

        Args:
            collection: Collection name
            query_embedding: Query vector
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score

        Returns:
            List of search results with metadata
        """
        try:
            if not self.client:
                raise VectorSearchError(
                    message="Vector client not initialized",
                    error_code="client_not_initialized",
                )

            # Perform vector search
            response = self.client.collections.get(collection).query.near_vector(
                near_vector=query_embedding,
                limit=limit,
                return_properties=[
                    "name",
                    "description",
                    "categories",
                    "endpoint",
                    "security_level",
                    "status",
                ],
            )

            # Process results
            results = []
            for obj in response.objects:
                if obj.score >= similarity_threshold:
                    results.append(
                        {
                            "id": obj.uuid,
                            "score": obj.score,
                            "metadata": {
                                "name": obj.properties.get("name", ""),
                                "description": obj.properties.get("description", ""),
                                "categories": obj.properties.get("categories", []),
                                "endpoint": obj.properties.get("endpoint", ""),
                                "security_level": obj.properties.get(
                                    "security_level", "low"
                                ),
                                "status": obj.properties.get("status", "active"),
                            },
                        }
                    )

            logger.info(f"Found {len(results)} results for vector search")
            return results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise VectorSearchError(
                message=f"Vector search failed: {str(e)}", error_code="search_failed"
            ) from e

    async def delete_embedding(self, collection: str, id: str) -> None:
        """
        Delete an embedding by ID.

        Args:
            collection: Collection name
            id: Unique identifier
        """
        try:
            if not self.client:
                raise VectorSearchError(
                    message="Vector client not initialized",
                    error_code="client_not_initialized",
                )

            self.client.collections.get(collection).data.delete_by_id(id)
            logger.info(f"Deleted embedding {id} from collection {collection}")

        except Exception as e:
            logger.error(f"Failed to delete embedding: {e}")
            raise VectorSearchError(
                message=f"Failed to delete embedding: {str(e)}",
                error_code="delete_failed",
            ) from e

    async def shutdown(self) -> None:
        """Shutdown the vector search client."""
        if not self._initialized:
            return

        logger.info("Shutting down Vector Search Client...")

        if self.client:
            try:
                self.client.close()
            except Exception as e:
                logger.error(f"Error closing Weaviate client: {e}")

        self._initialized = False
        logger.info("Vector Search Client shutdown complete")

    @property
    def is_initialized(self) -> bool:
        """Check if client is initialized."""
        return self._initialized
