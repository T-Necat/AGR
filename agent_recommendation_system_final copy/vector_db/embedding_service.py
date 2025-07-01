import os
import logging
import pandas as pd
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional
from dotenv import load_dotenv
from openai import OpenAI, BadRequestError
import tiktoken
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Çevre değişkenlerini yükle ve Logging ayarları
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentEmbeddingService:
    """OpenAI API'si kullanarak vektör oluşturan ve yöneten servis"""

    def __init__(self,
                 persist_directory: str = "./chroma_db_openai",
                 embedding_model_name: str = "text-embedding-3-small",
                 collection_name: str = "agents_openai"):

        self.persist_directory = persist_directory
        self.embedding_model_name = embedding_model_name
        self.collection_name = collection_name

        # OpenAI istemcisini başlat
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY çevre değişkeni ayarlanmalıdır.")
        self.openai_client = OpenAI(api_key=api_key)
        
        logger.info(f"OpenAI embedding modeli kullanılacak: {self.embedding_model_name}")

        self.client = chromadb.PersistentClient(path=persist_directory, settings=Settings(anonymized_telemetry=False, allow_reset=True))
        self.collection = self._get_or_create_collection()
        logger.info(f"Embedding servisi başlatıldı: {persist_directory}")

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

    def create_openai_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Verilen metin listesi için OpenAI embedding'leri oluşturur."""
        if not texts:
            return []
        
        response = self.openai_client.embeddings.create(
            input=texts,
            model=self.embedding_model_name
        )
        return [embedding.embedding for embedding in response.data]

    def search_similar_agents(self,
                            query: str,
                            top_k: int = 5,
                            score_threshold: float = 0.5) -> List[Dict]:
        """Sorguya benzer agent'ları arar."""
        try:
            logger.info(f"OpenAI ile arama yapılıyor: query='{query}', top_k={top_k}, score_threshold={score_threshold}")
            query_embedding = self.create_openai_embeddings([query])[0]

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

    def create_and_store_embeddings_from_df(self, df: pd.DataFrame) -> bool:
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
                    embeddings = self.create_openai_embeddings(batch_docs)
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

if __name__ == "__main__":
    # Test için
    service = AgentEmbeddingService()
    
    # Knowledge base'i yükle
    df = service.load_knowledge_base()
    
    if not df.empty:
        # İstatistikleri göster
        stats = service.get_collection_stats()
        print(f"Koleksiyon istatistikleri: {stats}")
        
        # Test araması
        test_query = "customer service help"
        results = service.search_similar_agents(test_query)
        print(f"Test araması sonuçları: {len(results)} agent bulundu") 