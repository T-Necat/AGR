#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Temizlenen Verilerle Agent Knowledge Base Oluşturucu
Bu script, temizlenen verileri kullanarak yeni bir agent_knowledge_base.csv oluşturur.
"""

import pandas as pd
import json
import os
from typing import Dict, List, Optional
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CleanAgentDataProcessor:
    """Temizlenen AI Agent verilerini işleyen ve birleştiren sınıf"""
    
    def __init__(self, cleaned_data_dir: str = "cleaned_data"):
        self.cleaned_data_dir = Path(cleaned_data_dir)
        self.output_file = "clean_agent_knowledge_base.csv"
        
    def load_cleaned_persona_data(self) -> pd.DataFrame:
        """Temizlenen agent persona verilerini yükler"""
        try:
            persona_file = self.cleaned_data_dir / "cleaned_persona.csv"
            df = pd.read_csv(persona_file)
            logger.info(f"Temizlenen persona verisi yüklendi: {len(df)} kayıt")
            return df
        except Exception as e:
            logger.error(f"Temizlenen persona verisi yüklenirken hata: {e}")
            return pd.DataFrame()
    
    def load_cleaned_training_materials(self) -> pd.DataFrame:
        """Temizlenen training materials verilerini yükler"""
        try:
            training_file = self.cleaned_data_dir / "cleaned_training_materials.csv"
            df = pd.read_csv(training_file)
            logger.info(f"Temizlenen training materials yüklendi: {len(df)} kayıt")
            return df
        except Exception as e:
            logger.error(f"Temizlenen training materials yüklenirken hata: {e}")
            return pd.DataFrame()
    
    def load_cleaned_tasks_data(self) -> pd.DataFrame:
        """Temizlenen tasks verilerini yükler"""
        try:
            tasks_file = self.cleaned_data_dir / "cleaned_tasks.csv"
            df = pd.read_csv(tasks_file)
            logger.info(f"Temizlenen tasks verisi yüklendi: {len(df)} kayıt")
            return df
        except Exception as e:
            logger.error(f"Temizlenen tasks verisi yüklenirken hata: {e}")
            return pd.DataFrame()
    
    def load_cleaned_chat_messages(self) -> pd.DataFrame:
        """Temizlenen chat messages verilerini yükler"""
        try:
            chat_file = self.cleaned_data_dir / "cleaned_chat_messages.csv"
            df = pd.read_csv(chat_file)
            logger.info(f"Temizlenen chat messages yüklendi: {len(df)} kayıt")
            return df
        except Exception as e:
            logger.error(f"Temizlenen chat messages yüklenirken hata: {e}")
            return pd.DataFrame()
    
    def process_cleaned_training_materials(self, df: pd.DataFrame) -> pd.DataFrame:
        """Temizlenen training materials verilerini işler ve agent_id'ye göre gruplar"""
        if df.empty:
            return df
            
        # Question ve answer alanlarını birleştir
        df['training_content'] = df.apply(
            lambda row: f"Question: {row['question']} Answer: {row['answer']}" if pd.notna(row['question']) and pd.notna(row['answer']) else "",
            axis=1
        )
        
        # Agent_id'ye göre grupla ve birleştir
        grouped = df.groupby('agent_id')['training_content'].apply(
            lambda x: ' '.join(x.astype(str))
        ).reset_index()
        
        grouped.columns = ['agent_id', 'training_content']
        logger.info(f"Temizlenen training materials işlendi: {len(grouped)} unique agent")
        
        return grouped
    
    def process_cleaned_tasks_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Temizlenen tasks verilerini işler ve agent_id'ye göre gruplar"""
        if df.empty:
            return df
            
        # Tasks alanını kullan (zaten temizlenmiş)
        df['tasks_content'] = df['tasks'].fillna("")
        
        # Agent_id'ye göre grupla ve birleştir
        grouped = df.groupby('agent_id')['tasks_content'].apply(
            lambda x: ' '.join(x.astype(str))
        ).reset_index()
        
        grouped.columns = ['agent_id', 'tasks_content']
        logger.info(f"Temizlenen tasks verisi işlendi: {len(grouped)} unique agent")
        
        return grouped
    
    def process_cleaned_chat_messages(self, df: pd.DataFrame) -> pd.DataFrame:
        """Temizlenen chat messages verilerini işler ve agent_id'ye göre gruplar"""
        if df.empty:
            return df
            
        # Content alanını kullan (zaten temizlenmiş)
        df['chat_content'] = df['content'].fillna("")
        
        # Agent_id'ye göre grupla ve birleştir
        grouped = df.groupby('agent_id')['chat_content'].apply(
            lambda x: ' '.join(x.astype(str))
        ).reset_index()
        
        grouped.columns = ['agent_id', 'chat_content']
        logger.info(f"Temizlenen chat messages işlendi: {len(grouped)} unique agent")
        
        return grouped
    
    def merge_clean_data(self) -> pd.DataFrame:
        """Temizlenen tüm verileri birleştirir ve corpus oluşturur"""
        # Temizlenen verileri yükle
        persona_df = self.load_cleaned_persona_data()
        training_df = self.load_cleaned_training_materials()
        tasks_df = self.load_cleaned_tasks_data()
        chat_df = self.load_cleaned_chat_messages()
        
        # Verileri işle
        processed_training = self.process_cleaned_training_materials(training_df)
        processed_tasks = self.process_cleaned_tasks_data(tasks_df)
        processed_chat = self.process_cleaned_chat_messages(chat_df)
        
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
        
        # Chat messages ekle
        if not processed_chat.empty:
            merged_df = merged_df.merge(
                processed_chat, 
                on='agent_id', 
                how='left'
            )
        else:
            merged_df['chat_content'] = ""
        
        # Corpus oluştur - tüm içerikleri birleştir
        merged_df['corpus'] = merged_df.apply(
            lambda row: f"{row['persona']} {row['training_content']} {row['tasks_content']} {row['chat_content']}".strip(),
            axis=1
        )
        
        # Gereksiz sütunları temizle
        final_df = merged_df[['agent_id', 'corpus', 'created_at']].copy()
        
        # Boş corpus'ları filtrele
        corpus_series = final_df['corpus'].astype(str)
        mask = corpus_series.str.strip() != ""
        final_df = final_df[mask].copy()
        
        logger.info(f"Temizlenen veri birleştirme tamamlandı: {len(final_df)} agent")
        
        return final_df
    
    def save_clean_knowledge_base(self, df: pd.DataFrame) -> str:
        """Temiz knowledge base'i CSV olarak kaydeder"""
        try:
            df.to_csv(self.output_file, index=False)
            logger.info(f"Temiz knowledge base kaydedildi: {self.output_file}")
            return self.output_file
        except Exception as e:
            logger.error(f"Temiz knowledge base kaydedilirken hata: {e}")
            return ""
    
    def process_and_save(self) -> str:
        """Tüm temiz ETL sürecini çalıştırır"""
        logger.info("Temiz ETL süreci başlatılıyor...")
        
        # Temizlenen verileri birleştir
        merged_data = self.merge_clean_data()
        
        # Temiz knowledge base'i kaydet
        output_file = self.save_clean_knowledge_base(merged_data)
        
        logger.info("Temiz ETL süreci tamamlandı!")
        return output_file

def main():
    """Ana fonksiyon"""
    processor = CleanAgentDataProcessor()
    output_file = processor.process_and_save()
    
    if output_file:
        print(f"✅ Temiz agent knowledge base başarıyla oluşturuldu: {output_file}")
    else:
        print("❌ Temiz agent knowledge base oluşturulurken hata oluştu!")

if __name__ == "__main__":
    main() 