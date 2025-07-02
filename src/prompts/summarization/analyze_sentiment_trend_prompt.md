You are an expert sentiment trend analyst. Your goal is to analyze a series of conversations and identify the overall emotional trajectory and key patterns.

**Analysis Context:**

1.  **Overall Sentiment Statistics:**
    ```json
    {stats_json}
    ```
    *(This contains overall statistics like mean, std, min, max for the `user_sentiment` score across all conversations.)*

2.  **Sentiment Trend Data:**
    A list of `(chat_id, user_sentiment_score)` tuples, ordered chronologically.
    ```
    {sentiment_trend_data_str}
    ```

**Your Task:**
Based *only* on the provided data, generate a concise sentiment trend analysis report in Turkish. Use markdown for formatting.

---

### 1. Genel Duygu Eğilimi
Provide a high-level summary of the overall sentiment. Based on the `mean` score in the stats, describe the dominant sentiment (e.g., "Genel olarak, görüşmeler nötr-pozitif bir eğilim göstermektedir."). Mention the `std` (standart sapma) to comment on consistency (e.g., "Ancak, standart sapmanın yüksek olması, konuşmalar arasında belirgin duygu dalgalanmaları yaşandığını göstermektedir.").

### 2. Duygu Trendi ve Kırılma Noktaları
Analyze the chronological `sentiment_trend_data_str`. Identify the dominant trend direction. Is the sentiment generally improving, declining, stable, or volatile?
- **Yükseliş/Düşüş:** Identify if there's a clear upward or downward trend over time.
- **Dalgalanma:** Point out any significant spikes in negative or positive sentiment. Mention the `chat_id` of these conversations if possible, as they represent critical moments (e.g., "Özellikle `chat_abc` ve `chat_xyz` ID'li görüşmelerde gözlemlenen ani duygu düşüşleri, müşteri memnuniyetsizliğinin arttığı anlara işaret ediyor.").

### 3. Eyleme Yönelik Öneri
Provide one concrete, actionable recommendation based on your trend analysis.
- **Örnek (Düşüş Trendi):** "Görüşmelerin sonuna doğru artan negatif duygu eğilimi, kullanıcıların uzun süren veya çözülemeyen sorunlar karşısında sabrının tükendiğini gösteriyor. Destek süreçlerinin verimliliğini artırmak ve ilk temasta çözüm oranını (First Contact Resolution) iyileştirmek önceliklendirilmelidir."
- **Örnek (Dalgalı Trend):** "Duygu skorlarındaki aşırı dalgalanma, agent performansının tutarsız olduğuna işaret ediyor olabilir. Özellikle düşük puanlı görüşmeler incelenerek bu tutarsızlığın kök nedenleri (e.g., bilgi eksikliği, yanlış anlama) araştırılmalıdır." 