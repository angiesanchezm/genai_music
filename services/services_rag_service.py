"""
Servicio RAG con Pinecone para knowledge base
"""
from typing import List, Dict
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI
from config.settings import settings
import structlog

logger = structlog.get_logger()

class RAGService:
    """Servicio de Retrieval-Augmented Generation"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        
        # Inicializar Pinecone
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        
        # Obtener o crear índice
        self.index_name = settings.pinecone_index_name
        self._ensure_index()
        
        self.index = self.pc.Index(self.index_name)
    
    def _ensure_index(self):
        """Asegurar que el índice existe"""
        existing_indexes = [index.name for index in self.pc.list_indexes()]
        
        if self.index_name not in existing_indexes:
            logger.info("creating_pinecone_index", index_name=self.index_name)
            self.pc.create_index(
                name=self.index_name,
                dimension=3072,  # Dimensión de embeddings de GPT-5
                metric='cosine',
                spec=ServerlessSpec(
                    cloud='aws',
                    region=settings.pinecone_environment.split('-')[0] + '-' + settings.pinecone_environment.split('-')[1]
                )
            )
    
    async def get_embedding(self, text: str) -> List[float]:
        """Generar embedding usando OpenAI GPT-5"""
        try:
            response = self.client.embeddings.create(
                model="text-embedding-3-large",  # Modelo de embeddings más reciente
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error("embedding_generation_error", error=str(e))
            raise
    
    async def query_knowledge_base(
        self, 
        query: str, 
        top_k: int = 3,
        filter_metadata: Dict = None
    ) -> List[Dict]:
        """
        Consultar knowledge base con retrieval semántico
        
        Args:
            query: Consulta del usuario
            top_k: Número de resultados a retornar
            filter_metadata: Filtros adicionales
            
        Returns:
            Lista de documentos relevantes con scores
        """
        try:
            # Generar embedding de la consulta
            query_embedding = await self.get_embedding(query)
            
            # Buscar en Pinecone
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
                filter=filter_metadata
            )
            
            # Formatear resultados
            documents = []
            for match in results.matches:
                documents.append({
                    "text": match.metadata.get("text", ""),
                    "source": match.metadata.get("source", ""),
                    "score": match.score,
                    "metadata": match.metadata
                })
            
            logger.info(
                "rag_query_completed", 
                query=query[:50], 
                results_count=len(documents)
            )
            
            return documents
            
        except Exception as e:
            logger.error("rag_query_error", error=str(e))
            return []
    
    async def upsert_documents(self, documents: List[Dict]):
        """
        Insertar o actualizar documentos en knowledge base
        
        Args:
            documents: Lista de documentos con formato:
                [{"id": "doc1", "text": "...", "metadata": {...}}]
        """
        try:
            vectors = []
            
            for doc in documents:
                embedding = await self.get_embedding(doc["text"])
                
                vectors.append({
                    "id": doc["id"],
                    "values": embedding,
                    "metadata": {
                        "text": doc["text"],
                        **doc.get("metadata", {})
                    }
                })
            
            # Upsert en batches de 100
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                self.index.upsert(vectors=batch)
            
            logger.info("documents_upserted", count=len(documents))
            
        except Exception as e:
            logger.error("upsert_error", error=str(e))
            raise
    
    async def build_context_from_results(self, results: List[Dict]) -> str:
        """Construir contexto RAG a partir de resultados"""
        if not results:
            return ""
        
        context_parts = []
        for i, doc in enumerate(results, 1):
            context_parts.append(
                f"[Fuente {i} - Score: {doc['score']:.2f}]\n{doc['text']}\n"
            )
        
        return "\n---\n".join(context_parts)
