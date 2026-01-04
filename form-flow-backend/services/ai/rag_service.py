"""
RAG Service - Vector Database for Form Context

Provides semantic search and context management using ChromaDB:
- Form field embeddings for understanding ambiguous labels
- User response history for auto-suggestions
- Domain-specific knowledge base

Features:
- Persistent vector storage
- Semantic similarity search
- User preference learning
- Form field pattern matching
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import hashlib
import json

logger = logging.getLogger(__name__)

# ChromaDB (optional)
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None

# Sentence Transformers (optional)
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    SentenceTransformer = None


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class SimilarField:
    """A field similar to the query."""
    field_name: str
    label: str
    similarity: float
    example_value: Optional[str] = None
    field_type: Optional[str] = None


@dataclass
class UserPreference:
    """Stored user preference for a field type."""
    field_pattern: str  # e.g., "email", "name", "address"
    value: str
    use_count: int = 1
    last_used: Optional[str] = None


# =============================================================================
# RAG Service
# =============================================================================

class RagService:
    """
    RAG (Retrieval-Augmented Generation) service for form filling.
    
    Uses ChromaDB for vector storage and sentence-transformers for embeddings.
    """
    
    COLLECTION_FIELDS = "form_fields"
    COLLECTION_RESPONSES = "user_responses"
    COLLECTION_KNOWLEDGE = "knowledge_base"
    
    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        """
        Initialize RAG service.
        
        Args:
            persist_directory: Directory to persist ChromaDB data
            embedding_model: Sentence transformer model for embeddings
        """
        if not CHROMADB_AVAILABLE:
            logger.warning("ChromaDB not available. RAG features disabled.")
            self.client = None
            self.embedder = None
            return
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )
        
        # Initialize embedder
        if EMBEDDINGS_AVAILABLE:
            try:
                self.embedder = SentenceTransformer(embedding_model)
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {e}")
                self.embedder = None
        else:
            self.embedder = None
        
        # Get or create collections
        self._init_collections()
    
    def _init_collections(self):
        """Initialize ChromaDB collections."""
        if not self.client:
            return
        
        self.fields_collection = self.client.get_or_create_collection(
            name=self.COLLECTION_FIELDS,
            metadata={"description": "Form field patterns and labels"},
        )
        
        self.responses_collection = self.client.get_or_create_collection(
            name=self.COLLECTION_RESPONSES,
            metadata={"description": "User responses for suggestions"},
        )
        
        self.knowledge_collection = self.client.get_or_create_collection(
            name=self.COLLECTION_KNOWLEDGE,
            metadata={"description": "Domain knowledge base"},
        )
    
    def _generate_id(self, *parts: str) -> str:
        """Generate a deterministic ID from parts."""
        content = "|".join(str(p) for p in parts)
        return hashlib.md5(content.encode()).hexdigest()
    
    def _embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts."""
        if not self.embedder:
            return None
        return self.embedder.encode(texts).tolist()
    
    # =========================================================================
    # Form Field Operations
    # =========================================================================
    
    def embed_form_schema(
        self,
        schema: List[Dict[str, Any]],
        form_id: str = "default",
    ) -> int:
        """
        Store form field patterns in vector database.
        
        Args:
            schema: List of field dictionaries
            form_id: Unique identifier for the form
            
        Returns:
            Number of fields embedded
        """
        if not self.client:
            return 0
        
        ids = []
        documents = []
        metadatas = []
        
        for field in schema:
            field_name = field.get("name", "")
            label = field.get("label", field.get("display_name", ""))
            field_type = field.get("type", "text")
            purpose = field.get("purpose", "")
            
            # Create searchable document
            doc = f"{label} {field_name} {purpose} {field_type}"
            doc_id = self._generate_id(form_id, field_name)
            
            ids.append(doc_id)
            documents.append(doc)
            metadatas.append({
                "form_id": form_id,
                "field_name": field_name,
                "label": label,
                "type": field_type,
                "purpose": purpose or "",
            })
        
        if not documents:
            return 0
        
        # Add to collection
        try:
            embeddings = self._embed(documents)
            self.fields_collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings,
            )
            return len(documents)
        except Exception as e:
            logger.error(f"Error embedding form schema: {e}")
            return 0
    
    def find_similar_fields(
        self,
        query: str,
        n_results: int = 5,
        form_id: Optional[str] = None,
    ) -> List[SimilarField]:
        """
        Find fields similar to the query.
        
        Args:
            query: Search query (field label or description)
            n_results: Maximum results to return
            form_id: Optional filter by form
            
        Returns:
            List of similar fields with scores
        """
        if not self.client:
            return []
        
        try:
            where_filter = {"form_id": form_id} if form_id else None
            
            results = self.fields_collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter,
            )
            
            similar = []
            for i, doc_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i]
                distance = results["distances"][0][i] if results.get("distances") else 0
                
                similar.append(SimilarField(
                    field_name=metadata.get("field_name", ""),
                    label=metadata.get("label", ""),
                    similarity=1 - distance,  # Convert distance to similarity
                    field_type=metadata.get("type"),
                ))
            
            return similar
            
        except Exception as e:
            logger.error(f"Error finding similar fields: {e}")
            return []
    
    # =========================================================================
    # User Response Operations
    # =========================================================================
    
    def store_user_response(
        self,
        user_id: str,
        field_pattern: str,
        value: str,
        field_metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Store a user's response for future suggestions.
        
        Args:
            user_id: User identifier
            field_pattern: Type of field (email, name, address, etc.)
            value: The value entered by user
            field_metadata: Additional field information
        """
        if not self.client or not value.strip():
            return
        
        doc_id = self._generate_id(user_id, field_pattern, value)
        doc = f"{field_pattern}: {value}"
        
        metadata = {
            "user_id": user_id,
            "field_pattern": field_pattern,
            "value": value,
            **(field_metadata or {}),
        }
        
        try:
            embeddings = self._embed([doc])
            self.responses_collection.upsert(
                ids=[doc_id],
                documents=[doc],
                metadatas=[metadata],
                embeddings=embeddings,
            )
        except Exception as e:
            logger.error(f"Error storing user response: {e}")
    
    def get_suggested_values(
        self,
        user_id: str,
        field_pattern: str,
        n_results: int = 3,
        partial_value: Optional[str] = None,
    ) -> List[str]:
        """
        Get suggested values for a field based on user history.
        
        Args:
            user_id: User identifier
            field_pattern: Type of field
            n_results: Maximum suggestions
            partial_value: Optional partial value to filter suggestions (for autocomplete)
            
        Returns:
            List of suggested values
        """
        if not self.client:
            return []
        
        try:
            results = self.responses_collection.query(
                query_texts=[field_pattern],
                n_results=n_results * 3 if partial_value else n_results,  # Get more to filter
                where={"user_id": user_id},
            )
            
            values = []
            for metadata in results.get("metadatas", [[]])[0]:
                value = metadata.get("value", "")
                if value and value not in values:
                    # Filter by partial_value if provided
                    if partial_value:
                        # Case-insensitive prefix match
                        if value.lower().startswith(partial_value.lower()):
                            values.append(value)
                    else:
                        values.append(value)
            
            # Limit to n_results
            return values[:n_results]
            
        except Exception as e:
            logger.error(f"Error getting suggestions: {e}")
            return []
    
    # =========================================================================
    # Knowledge Base Operations
    # =========================================================================
    
    def add_knowledge(
        self,
        category: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Add domain knowledge to the knowledge base.
        
        Args:
            category: Knowledge category (format, validation, etc.)
            content: Knowledge content
            metadata: Additional metadata
        """
        if not self.client:
            return
        
        doc_id = self._generate_id(category, content[:100])
        
        try:
            embeddings = self._embed([content])
            self.knowledge_collection.upsert(
                ids=[doc_id],
                documents=[content],
                metadatas=[{
                    "category": category,
                    **(metadata or {}),
                }],
                embeddings=embeddings,
            )
        except Exception as e:
            logger.error(f"Error adding knowledge: {e}")
    
    def search_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        n_results: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base.
        
        Args:
            query: Search query
            category: Optional category filter
            n_results: Maximum results
            
        Returns:
            List of matching knowledge entries
        """
        if not self.client:
            return []
        
        try:
            where_filter = {"category": category} if category else None
            
            results = self.knowledge_collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter,
            )
            
            entries = []
            for i, doc in enumerate(results.get("documents", [[]])[0]):
                metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                entries.append({
                    "content": doc,
                    "category": metadata.get("category", ""),
                    **metadata,
                })
            
            return entries
            
        except Exception as e:
            logger.error(f"Error searching knowledge: {e}")
            return []
    
    def seed_knowledge_base(self):
        """Seed knowledge base with common form patterns."""
        if not self.client:
            return
        
        # Format patterns
        formats = {
            "email": "Email addresses should be in format user@domain.com",
            "phone": "US phone numbers: (XXX) XXX-XXXX or XXX-XXX-XXXX",
            "ssn": "Social Security Number format: XXX-XX-XXXX",
            "date": "Common date formats: MM/DD/YYYY, YYYY-MM-DD, DD-MMM-YYYY",
            "address": "Full address: Street, City, State ZIP",
            "zip": "US ZIP codes: 5 digits (XXXXX) or ZIP+4 (XXXXX-XXXX)",
        }
        
        for category, content in formats.items():
            self.add_knowledge(f"format_{category}", content)
        
        # Validation hints
        validations = {
            "required": "Required fields must not be left blank",
            "maxlength": "Text exceeding max length will be abbreviated",
            "pattern": "Field value must match the specified pattern",
        }
        
        for category, content in validations.items():
            self.add_knowledge(f"validation_{category}", content)
    
    # =========================================================================
    # Utility
    # =========================================================================
    
    def clear_user_data(self, user_id: str) -> int:
        """
        Clear all stored data for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Number of entries deleted
        """
        if not self.client:
            return 0
        
        try:
            # Get all user entries
            results = self.responses_collection.get(
                where={"user_id": user_id},
            )
            
            ids = results.get("ids", [])
            if ids:
                self.responses_collection.delete(ids=ids)
            
            return len(ids)
            
        except Exception as e:
            logger.error(f"Error clearing user data: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the RAG database."""
        if not self.client:
            return {"available": False}
        
        try:
            return {
                "available": True,
                "fields_count": self.fields_collection.count(),
                "responses_count": self.responses_collection.count(),
                "knowledge_count": self.knowledge_collection.count(),
            }
        except Exception as e:
            return {"available": False, "error": str(e)}


# =============================================================================
# Singleton
# =============================================================================

_rag_instance: Optional[RagService] = None


def get_rag_service(
    persist_directory: str = "./chroma_db",
) -> RagService:
    """Get or create the RAG service singleton."""
    global _rag_instance
    
    if _rag_instance is None:
        _rag_instance = RagService(persist_directory=persist_directory)
    
    return _rag_instance
