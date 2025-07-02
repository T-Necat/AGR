import os
import logging
import pandas as pd
from typing import List, Dict, Any
from etl.data_processor import AgentDataProcessor
from vector_db.embedding_service import AgentEmbeddingService
import shutil
from dotenv import load_dotenv
import openai
from langchain.text_splitter import RecursiveCharacterTextSplitter
import tiktoken
import asyncio
import argparse

from src.config import get_settings

# Logging ve Konfigürasyon
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_batch_recursively(embedding_service: AgentEmbeddingService, docs: List[str], metadatas: List[Dict], ids: List[str]):
    """
    Bir batch'i işler ve ChromaDB'ye ekler. Token limiti hatası alınırsa,
    batch'i özyinelemeli olarak ikiye böler ve yeniden dener.
    """
    try:
        embeddings = embedding_service.create_openai_embeddings(docs)
        if embeddings:
            embedding_service.collection.add(
                embeddings=embeddings,      # type: ignore
                documents=docs,
                metadatas=metadatas,  # type: ignore
                ids=ids
            )
        return
    except openai.BadRequestError as e:
        # Hatanın token limitiyle ilgili olup olmadığını kontrol et
        if 'max_tokens_per_request' in str(e).lower():
            if len(docs) > 1:
                logger.warning(f"Token limiti aşıldı. {len(docs)} dokümanlık batch ikiye bölünüp yeniden denenecek.")
                mid_index = len(docs) // 2
                
                # Batch'i ikiye böl ve her bir parçayı özyinelemeli olarak işle
                process_batch_recursively(embedding_service, docs[:mid_index], metadatas[:mid_index], ids[:mid_index])
                process_batch_recursively(embedding_service, docs[mid_index:], metadatas[mid_index:], ids[mid_index:])
            else:
                # Tek bir doküman bile API limitinden büyükse, atla ve logla
                logger.error(f"Tek bir doküman ({ids[0]}) OpenAI API limitini aştığı için atlanacak. Hata: {e}")
        else:
            # Başka bir OpenAI hatası oluşursa logla ve bu batch'i atla
            logger.error(f"{len(docs)} dokümanlık batch işlenirken beklenmedik bir OpenAI hatası oluştu ve atlandı. Hata: {e}")
    except Exception as e:
        # Diğer beklenmedik hatalar
        logger.error(f"{len(docs)} dokümanlık batch işlenirken genel bir hata oluştu ve atlandı. Hata: {e}")

async def main():
    """
    Veritabanını sıfırdan ve tutarlı bir şekilde yeniden inşa eder.
    Bu script, projenin en önemli adımıdır ve tutarlı bir vektör veritabanı oluşturur.
    """
    parser = argparse.ArgumentParser(description="Agent verilerini işler ve vektör veritabanını yeniden oluşturur.")
    parser.add_argument(
        "--data-dir", 
        type=str, 
        default="src/data",
        help="İşlenecek ham verilerin bulunduğu klasör."
    )
    args = parser.parse_args()

    settings = get_settings()
    db_path = settings.CHROMA_PERSIST_DIRECTORY
    knowledge_base_file = settings.KNOWLEDGE_BASE_FILE

    try:
        logger.info("="*50 + "\nAdım 1: ETL süreci başlatılıyor...")
        etl_processor = AgentDataProcessor(data_dir=args.data_dir)
        etl_processor.process_and_save()
        logger.info(f"ETL süreci tamamlandı.")

        logger.info("="*50)
        logger.info("Adım 2: OpenAI ile Vektör Veritabanı Kurulumu...")

        if os.path.exists(db_path):
            logger.info(f"Mevcut veritabanı klasörü '{db_path}' temizleniyor...")
            shutil.rmtree(db_path)

        embedding_service = AgentEmbeddingService() # Bu zaten ayarları içeriden kullanıyor
        
        df = pd.read_csv(knowledge_base_file)
        
        logger.info("OpenAI API'si ile embedding'ler oluşturuluyor... Bu işlem API kullanımınıza ve veri boyutuna göre zaman alabilir ve maliyet oluşturabilir.")

        # Metinleri modelin token limitine uygun şekilde parçalara ayırmak için Text Splitter oluştur
        # text-embedding-3-small modelinin limiti 8191 token'dır. Güvenli bir aralık için daha küçük bir değer seçiyoruz.
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            length_function=len # Basit bir uzunluk fonksiyonu, tiktoken daha doğru sonuç verir ama bu da genellikle yeterlidir.
        )

        all_chunks = []
        all_metadatas = []
        all_ids = []

        logger.info("Dokümanlar işleniyor ve küçük parçalara (chunk) ayrılıyor...")
        for index, row in df.iterrows():
            original_text = str(row['corpus'])
            agent_id = str(row['agent_id'])
            created_at = str(row['created_at'])
            
            chunks = text_splitter.split_text(original_text)
            
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metadatas.append({'agent_id': agent_id, 'created_at': created_at})
                all_ids.append(f"{agent_id}_{index}_{i}")

        logger.info(f"Toplam {len(df)} doküman, {len(all_chunks)} parçaya ayrıldı.")

        # Token tabanlı dinamik batch'leme
        # Modelin adı embedding_service'den alınır, böylece doğru tokenizer kullanılır
        tokenizer = tiktoken.encoding_for_model(embedding_service.embedding_model_name)
        
        # Güvenlik payı ile birlikte API'nin istek başına token limiti
        API_TOKEN_LIMIT = 250000 

        batches = []
        current_batch_tokens = 0
        current_batch_docs = []
        current_batch_metadatas = []
        current_batch_ids = []

        for i, doc in enumerate(all_chunks):
            token_count = len(tokenizer.encode(doc))
            
            if current_batch_tokens + token_count > API_TOKEN_LIMIT and current_batch_docs:
                # Mevcut batch limiti aşıyorsa, bunu listeye ekle ve yenisini başlat
                batches.append((current_batch_docs, current_batch_metadatas, current_batch_ids))
                current_batch_docs = []
                current_batch_metadatas = []
                current_batch_ids = []
                current_batch_tokens = 0
            
            current_batch_docs.append(doc)
            current_batch_metadatas.append(all_metadatas[i])
            current_batch_ids.append(all_ids[i])
            current_batch_tokens += token_count

        if current_batch_docs:
            # Son kalan batch'i de ekle
            batches.append((current_batch_docs, current_batch_metadatas, current_batch_ids))

        logger.info(f"Token tabanlı dinamik gruplama ile {len(batches)} adet batch oluşturuldu.")

        for i, (batch_docs, batch_metadatas, batch_ids) in enumerate(batches):
            logger.info(f"Batch {i + 1}/{len(batches)} işleniyor... (Bu batch'te {len(batch_docs)} doküman var)")
            try:
                embeddings = await embedding_service.create_openai_embeddings(batch_docs)
                if embeddings:
                    embedding_service.collection.add(
                        embeddings=embeddings,      # type: ignore
                        documents=batch_docs,
                        metadatas=batch_metadatas,  # type: ignore
                        ids=batch_ids
                    )
            except Exception as e:
                logger.error(f"Batch {i + 1} işlenirken hata oluştu ve atlandı: {e}")
                continue
    
        logger.info("="*50 + "\nVERİTABANI YENİDEN İNŞA ETME İŞLEMİ TAMAMLANDI!")
        logger.info(f"OpenAI tabanlı yeni veritabanı '{db_path}' içinde oluşturuldu.")

    except Exception as e:
        logger.error(f"Kritik hata: {e}", exc_info=True)

def run_etl():
    """ETL sürecini başlatır"""
    # ... existing code ...

if __name__ == "__main__":
    # Load environment variables from .env file
    load_dotenv()
    asyncio.run(main()) 