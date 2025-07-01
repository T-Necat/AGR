import logging
import pandas as pd
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional
from openai import AsyncOpenAI, OpenAI, BadRequestError
import tiktoken
from langchain.text_splitter import RecursiveCharacterTextSplitter

from src.config import get_settings

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentEmbeddingService:
    """OpenAI API'si kullanarak vektör oluşturan ve yöneten servis"""

    def __init__(self, collection_name: str = "agents_openai"):
        settings = get_settings()
        self.persist_directory = settings.CHROMA_PERSIST_DIRECTORY
        self.embedding_model_name = settings.EMBEDDING_MODEL
        self.collection_name = collection_name

        # Asenkron OpenAI istemcisini başlat
        self.async_openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        # Bazı operasyonlar (eski batch recursive gibi) senkron kalabilir, bu yüzden senkronu da tutalım
        self.sync_openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        logger.info(f"OpenAI embedding modeli kullanılacak: {self.embedding_model_name}")

        self.client = chromadb.PersistentClient(path=self.persist_directory, settings=Settings(anonymized_telemetry=False, allow_reset=True))
        self.collection = self._get_or_create_collection()
        logger.info(f"Embedding servisi başlatıldı: {self.persist_directory}")

    def _reset_collection(self):
        """Mevcut koleksiyonu siler ve yeniden oluşturur."""
        logger.info(f"'{self.collection_name}' koleksiyonu sıfırlanıyor...")
        self.client.delete_collection(name=self.collection_name)
        self.collection = self._get_or_create_collection()
        logger.info("Koleksiyon başarıyla sıfırlandı.")

    def _get_or_create_collection(self):
        """Koleksiyonu alır veya 'cosine' metriğiyle oluşturur."""
        return self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    async def create_openai_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Verilen metin listesi için OpenAI embedding'leri asenkron olarak oluşturur."""
        if not texts:
            return []
        
        response = await self.async_openai_client.embeddings.create(
            input=texts,
            model=self.embedding_model_name
        )
        return [embedding.embedding for embedding in response.data]

    async def search_similar_agents(self,
                            query: str,
                            top_k: int,
                            score_threshold: float) -> List[Dict]:
        """Sorguya benzer agent'ları asenkron olarak arar."""
        try:
            logger.info(f"OpenAI ile asenkron arama yapılıyor: query='{query}', top_k={top_k}, score_threshold={score_threshold}")
            query_embedding = (await self.create_openai_embeddings([query]))[0]

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=None
            )
            
            similar_agents = []
            doc_lists = results.get('documents')
            meta_lists = results.get('metadatas')
            dist_lists = results.get('distances')

            if not (doc_lists and meta_lists and dist_lists):
                logger.warning("ChromaDB query did not return one of the expected keys.")
                return []

            for doc, metadata, distance in zip(doc_lists[0], meta_lists[0], dist_lists[0]):
                similarity_score = 1 - distance
                if similarity_score >= score_threshold:
                    similar_agents.append({
                        'agent_id': metadata['agent_id'],
                        'similarity_score': similarity_score,
                        'content': doc,
                        'metadata': metadata
                    })
            logger.info(f"Benzer agent'lar bulundu: {len(similar_agents)}")
            return similar_agents
            
        except Exception as e:
            logger.error(f"Agent arama sırasında hata: {e}", exc_info=True)
            return []

    async def create_and_store_embeddings_from_df(self, df: pd.DataFrame) -> bool:
        """
        DataFrame'den embedding'ler oluşturur ve bunları ChromaDB'de saklar.
        Bu işlem, mevcut koleksiyonu temizler ve verileri yeniden doldurur.
        """
        if df.empty:
            logger.warning("DataFrame boş, embedding oluşturma işlemi atlandı.")
            return False

        try:
            self._reset_collection()
            logger.info("DataFrame'den embedding oluşturma ve depolama süreci başlatıldı.")

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=100,
                length_function=len
            )

            all_chunks, all_metadatas, all_ids = [], [], []

            logger.info("Dokümanlar parçalara ayrılıyor...")
            for index, row in df.iterrows():
                original_text = str(row.get('corpus', ''))
                agent_id = str(row.get('agent_id', 'unknown'))
                created_at = str(row.get('created_at', ''))

                chunks = text_splitter.split_text(original_text)
                for i, chunk in enumerate(chunks):
                    all_chunks.append(chunk)
                    all_metadatas.append({'agent_id': agent_id, 'created_at': created_at})
                    all_ids.append(f"{agent_id}_{index}_{i}")
            
            logger.info(f"Toplam {len(df)} doküman, {len(all_chunks)} parçaya ayrıldı.")

            if not all_chunks:
                logger.warning("Parçalanacak doküman bulunamadı.")
                return True # Koleksiyonu temizledik, bu bir başarı durumu.

            tokenizer = tiktoken.encoding_for_model(self.embedding_model_name)
            API_TOKEN_LIMIT = 250000 
            batches = []
            current_batch_tokens = 0
            current_batch_docs, current_batch_metadatas, current_batch_ids = [], [], []

            for i, doc in enumerate(all_chunks):
                token_count = len(tokenizer.encode(doc))
                if current_batch_tokens + token_count > API_TOKEN_LIMIT and current_batch_docs:
                    batches.append((current_batch_docs, current_batch_metadatas, current_batch_ids))
                    current_batch_docs, current_batch_metadatas, current_batch_ids = [], [], []
                    current_batch_tokens = 0
                
                current_batch_docs.append(doc)
                current_batch_metadatas.append(all_metadatas[i])
                current_batch_ids.append(all_ids[i])
                current_batch_tokens += token_count

            if current_batch_docs:
                batches.append((current_batch_docs, current_batch_metadatas, current_batch_ids))
            
            logger.info(f"{len(batches)} adet batch oluşturuldu.")

            for i, (batch_docs, batch_metadatas, batch_ids) in enumerate(batches):
                logger.info(f"Batch {i + 1}/{len(batches)} işleniyor...")
                try:
                    embeddings = await self.create_openai_embeddings(batch_docs)
                    if embeddings:
                        self.collection.add(
                            embeddings=embeddings,      # type: ignore
                            documents=batch_docs,
                            metadatas=batch_metadatas,  # type: ignore
                            ids=batch_ids
                        )
                except BadRequestError as e:
                    logger.error(f"Batch {i+1} işlenirken OpenAI API hatası (BadRequestError): {e}")
                    # Gerekirse burada daha detaylı hata yönetimi yapılabilir.
                except Exception as e:
                    logger.error(f"Batch {i + 1} işlenirken beklenmedik hata ve atlandı: {e}")

            logger.info("Embedding oluşturma ve depolama süreci başarıyla tamamlandı.")
            return True

        except Exception as e:
            logger.error(f"Embedding oluşturma ve depolama sırasında kritik hata: {e}", exc_info=True)
            return False

    def get_sync_client(self) -> OpenAI:
        """Senkron OpenAI istemcisini döndürür."""
        return self.sync_openai_client

    def load_knowledge_base(self, csv_file: str = "agent_knowledge_base.csv") -> pd.DataFrame:
        """Knowledge base CSV dosyasını yükler"""
        try:
            df = pd.read_csv(csv_file)
            logger.info(f"Knowledge base yüklendi: {len(df)} agent")
            return df
        except Exception as e:
            logger.error(f"Knowledge base yüklenirken hata: {e}")
            return pd.DataFrame()
        
    def get_agent_by_id(self, agent_id: str) -> Optional[Dict]:
        """Belirli bir agent'ın tüm chunk'larını getirir"""
        try:
            results = self.collection.get(
                where={"agent_id": agent_id}
            )

            if not results:
                return None
            
            documents = results.get('documents')
            metadatas = results.get('metadatas')

            if documents and metadatas:
                full_content = " ".join(documents)
                return {
                    'agent_id': agent_id,
                    'content': full_content,
                    'chunks': len(documents),
                    'metadata': metadatas[0] if metadatas else {}
                }
            return None
        except Exception as e:
            logger.error(f"Agent getirme sırasında hata: {e}")
            return None
    
    def get_collection_stats(self) -> Dict:
        """Koleksiyon istatistiklerini getirir"""
        try:
            count = self.collection.count()
            
            if count == 0:
                return {'total_chunks': 0, 'unique_agents': 0, 'collection_name': self.collection_name}

            # Sadece metadataları alarak verimliliği artır
            metadatas = self.collection.get(include=["metadatas"])['metadatas']
            
            if not metadatas:
                logger.warning("Metadatalar alınamadı veya boş.")
                return {'total_chunks': count, 'unique_agents': 0, 'collection_name': self.collection_name}

            unique_agents = set(m['agent_id'] for m in metadatas if m and 'agent_id' in m)
            
            return {
                'total_chunks': count,
                'unique_agents': len(unique_agents),
                'collection_name': self.collection_name
            }
            
        except Exception as e:
            logger.error(f"İstatistik alma sırasında hata: {e}", exc_info=True)
            return {
                'total_chunks': 0,
                'unique_agents': 0,
                'collection_name': self.collection_name
            }

async def main_async():
    # Test için
    # collection_name parametresi opsiyoneldir, isterseniz değiştirebilirsiniz.
    service = AgentEmbeddingService()
    
    # Knowledge base'i yükle
    df = service.load_knowledge_base()
    
    if not df.empty:
        # İstatistikleri göster
        stats = service.get_collection_stats()
        print(f"Koleksiyon istatistikleri: {stats}")
        
        # Test araması
        test_query = "customer service help"
        # rag_pipeline'dan gelen değerler kullanılacağı için burada manuel olarak sağlıyoruz.
        results = await service.search_similar_agents(test_query, top_k=5, score_threshold=0.7)
        print(f"Test araması sonuçları: {len(results)} agent bulundu")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main_async()) 