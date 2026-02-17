from typing import List, Dict, Any, Optional
import pinecone
from app.config import settings
import hashlib


class PineconeService:
    def __init__(self):
        self.index_name = settings.PINECONE_INDEX_NAME
        self._init_pinecone()
    
    def _init_pinecone(self):
        """Initialize Pinecone connection."""
        pinecone.init(
            api_key=settings.PINECONE_API_KEY,
            environment=settings.PINECONE_ENVIRONMENT
        )
        
        # Create index if it doesn't exist
        if self.index_name not in pinecone.list_indexes():
            pinecone.create_index(
                name=self.index_name,
                dimension=768,  # Gemini embedding dimension
                metric="cosine"
            )
        
        self.index = pinecone.Index(self.index_name)
    
    async def store_commitment(
        self,
        user_id: str,
        commitment_id: str,
        description: str,
        amount: float,
        date: Optional[str] = None
    ) -> str:
        """Store commitment embedding in Pinecone."""
        # Generate embedding using Gemini (simplified - in production use proper embeddings)
        # For now, we'll use a text representation and rely on metadata filtering
        vector_id = f"{user_id}_{commitment_id}"
        
        # Create a rich text representation for semantic search
        text_to_embed = f"Financial commitment: {description}. Amount: {amount}. Date: {date or 'upcoming'}"
        
        # Generate embedding (simplified approach)
        embedding = await self._generate_embedding(text_to_embed)
        
        # Upsert to Pinecone
        self.index.upsert([
            {
                'id': vector_id,
                'values': embedding,
                'metadata': {
                    'user_id': user_id,
                    'commitment_id': commitment_id,
                    'description': description,
                    'amount': amount,
                    'date': str(date) if date else '',
                    'type': 'commitment'
                }
            }
        ])
        
        return vector_id
    
    async def query_relevant_commitments(
        self,
        user_id: str,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant commitments based on query."""
        
        # Generate query embedding
        query_embedding = await self._generate_embedding(query)
        
        # Query Pinecone with user filter
        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            filter={"user_id": {"$eq": user_id}},
            include_metadata=True
        )
        
        return [
            {
                'id': match.id,
                'score': match.score,
                'description': match.metadata.get('description', ''),
                'amount': float(match.metadata.get('amount', 0)),
                'date': match.metadata.get('date')
            }
            for match in results.matches
        ]
    
    async def delete_commitment(self, user_id: str, commitment_id: str):
        """Delete commitment from Pinecone."""
        vector_id = f"{user_id}_{commitment_id}"
        self.index.delete(ids=[vector_id])
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding using Gemini API.
        In production, use proper embedding model.
        """
        import google.generativeai as genai
        
        # Note: Gemini Pro doesn't have native embeddings yet
        # Using a simple hashing approach for demo, replace with proper embeddings
        import hashlib
        import numpy as np
        
        # Generate deterministic pseudo-embedding based on text hash
        # REPLACE THIS with actual embedding API call in production
        hash_obj = hashlib.sha256(text.encode())
        hash_int = int(hash_obj.hexdigest(), 16)
        
        # Generate 768-dimensional vector
        np.random.seed(hash_int % (2**32))
        embedding = np.random.randn(768).tolist()
        
        # Normalize
        norm = np.linalg.norm(embedding)
        embedding = [x / norm for x in embedding]
        
        return embedding


pinecone_service = PineconeService()