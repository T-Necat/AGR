import pandas as pd
import json
import os
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentDataProcessor:
    """AI Agent verilerini işleyen ve birleştiren sınıf"""
    
    def __init__(self, data_dir: str = "ai_agent_data_june_18_25_"):
        self.data_dir = data_dir
        self.output_file = "agent_knowledge_base.csv"
        
    def load_persona_data(self) -> pd.DataFrame:
        """Agent persona verilerini yükler"""
        try:
            persona_file = os.path.join(self.data_dir, "ai_agent_persona_june_18_25.csv")
            df = pd.read_csv(persona_file)
            logger.info(f"Persona verisi yüklendi: {len(df)} kayıt")
            return df
        except Exception as e:
            logger.error(f"Persona verisi yüklenirken hata: {e}")
            return pd.DataFrame()
    
    def load_training_materials(self) -> pd.DataFrame:
        """Training materials verilerini yükler"""
        try:
            training_file = os.path.join(self.data_dir, "ai_agent_training_materials_june_18_25.csv")
            df = pd.read_csv(training_file)
            logger.info(f"Training materials yüklendi: {len(df)} kayıt")
            return df
        except Exception as e:
            logger.error(f"Training materials yüklenirken hata: {e}")
            return pd.DataFrame()
    
    def load_tasks_data(self) -> pd.DataFrame:
        """Tasks verilerini yükler"""
        try:
            tasks_file = os.path.join(self.data_dir, "ai_agent_tasks_june_18_25.csv")
            df = pd.read_csv(tasks_file)
            logger.info(f"Tasks verisi yüklendi: {len(df)} kayıt")
            return df
        except Exception as e:
            logger.error(f"Tasks verisi yüklenirken hata: {e}")
            return pd.DataFrame()
    
    def process_training_materials(self, df: pd.DataFrame) -> pd.DataFrame:
        """Training materials verilerini işler ve agent_id'ye göre gruplar"""
        if df.empty:
            return df
            
        # JSON formatındaki data alanını parse et
        def parse_json_data(data_str):
            try:
                if pd.isna(data_str) or data_str == "":
                    return ""
                data = json.loads(data_str)
                if isinstance(data, dict):
                    # Question-Answer formatı
                    if "question" in data and "answer" in data:
                        return f"Question: {data['question']} Answer: {data['answer']}"
                    # Diğer formatlar için
                    return str(data)
                return str(data)
            except json.JSONDecodeError:
                return str(data_str)
        
        df['processed_data'] = df['data'].apply(parse_json_data)
        
        # Agent_id'ye göre grupla ve birleştir
        grouped = df.groupby('agent_id')['processed_data'].apply(
            lambda x: ' '.join(x.astype(str))
        ).reset_index()
        
        grouped.columns = ['agent_id', 'training_content']
        logger.info(f"Training materials işlendi: {len(grouped)} unique agent")
        
        return grouped
    
    def process_tasks_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Tasks verilerini işler ve agent_id'ye göre gruplar"""
        if df.empty:
            return df
            
        # JSON formatındaki tasks alanını parse et
        def parse_tasks(tasks_str):
            try:
                if pd.isna(tasks_str) or tasks_str == "":
                    return ""
                tasks = json.loads(tasks_str)
                if isinstance(tasks, list):
                    task_descriptions = []
                    for task in tasks:
                        if isinstance(task, dict) and 'value' in task:
                            if isinstance(task['value'], dict):
                                if 'about' in task['value']:
                                    task_descriptions.append(f"Task: {task['value']['about']}")
                                elif 'message' in task['value']:
                                    task_descriptions.append(f"Message: {task['value']['message']}")
                                else:
                                    task_descriptions.append(str(task['value']))
                            else:
                                task_descriptions.append(str(task['value']))
                        else:
                            task_descriptions.append(str(task))
                    return ' '.join(task_descriptions)
                return str(tasks)
            except json.JSONDecodeError:
                return str(tasks_str)
        
        df['processed_tasks'] = df['tasks'].apply(parse_tasks)
        
        # Agent_id'ye göre grupla ve birleştir
        grouped = df.groupby('agent_id')['processed_tasks'].apply(
            lambda x: ' '.join(x.astype(str))
        ).reset_index()
        
        grouped.columns = ['agent_id', 'tasks_content']
        logger.info(f"Tasks verisi işlendi: {len(grouped)} unique agent")
        
        return grouped
    
    def merge_data(self):  # type: ignore
        """Tüm verileri birleştirir ve corpus oluşturur"""
        # Verileri yükle
        persona_df = self.load_persona_data()
        training_df = self.load_training_materials()
        tasks_df = self.load_tasks_data()
        
        # Training materials ve tasks verilerini işle
        processed_training = self.process_training_materials(training_df)
        processed_tasks = self.process_tasks_data(tasks_df)
        
        # Persona verisi ile birleştir (outer join)
        merged_df = persona_df.copy()
        
        # Training materials ekle
        if not processed_training.empty:
            merged_df = merged_df.merge(
                processed_training, 
                on='agent_id', 
                how='left'
            )
        else:
            merged_df['training_content'] = ""
        
        # Tasks ekle
        if not processed_tasks.empty:
            merged_df = merged_df.merge(
                processed_tasks, 
                on='agent_id', 
                how='left'
            )
        else:
            merged_df['tasks_content'] = ""
        
        # Corpus oluştur
        merged_df['corpus'] = merged_df.apply(
            lambda row: f"{row['persona']} {row['training_content']} {row['tasks_content']}".strip(),
            axis=1
        )
        
        # Gereksiz sütunları temizle
        final_df = merged_df[['agent_id', 'corpus', 'created_at']].copy()
        
        # Boş corpus'ları filtrele
        corpus_series = pd.Series(final_df['corpus'].astype(str))
        mask = corpus_series.str.strip() != ""
        final_df = final_df[mask].copy()
        
        logger.info(f"Veri birleştirme tamamlandı: {len(final_df)} agent")
        
        return final_df
    
    def save_knowledge_base(self, df):  # type: ignore
        """Knowledge base'i CSV olarak kaydeder"""
        try:
            df.to_csv(self.output_file, index=False)
            logger.info(f"Knowledge base kaydedildi: {self.output_file}")
            return self.output_file
        except Exception as e:
            logger.error(f"Knowledge base kaydedilirken hata: {e}")
            return ""
    
    def process_and_save(self) -> str:
        """Tüm ETL sürecini çalıştırır"""
        logger.info("ETL süreci başlatılıyor...")
        
        # Verileri birleştir
        merged_data = self.merge_data()
        
        # Knowledge base'i kaydet
        output_file = self.save_knowledge_base(merged_data)
        
        logger.info("ETL süreci tamamlandı!")
        return output_file

if __name__ == "__main__":
    processor = AgentDataProcessor()
    output_file = processor.process_and_save()
    print(f"Knowledge base oluşturuldu: {output_file}") 