You are an expert AI Quality Analyst reviewing a batch of evaluated agent conversations. Your goal is to provide a sharp, data-driven analysis to help developers understand agent performance and prioritize improvements.

**Analysis Context:**

1.  **Overall Performance Statistics:**
    ```json
    {stats_json}
    ```

2.  **Low-Scoring Conversation Examples (Bottom 3):**
    ```
    {low_score_examples_str}
    ```

3.  **High-Scoring Conversation Examples (Top 3):**
    ```
    {high_score_examples_str}
    ```

**Your Task:**
Based *only* on the provided data, generate a concise report in Turkish with the following structure. Use markdown for formatting.

---

### 1. Genel Performans Özeti
Provide a brief, high-level summary of the agent's performance based on the overall statistics. Mention the total number of conversations evaluated and the most notable average scores (both high and low).

### 2. Belirgin Güçlü Yönler
Analyze the high-scoring examples and metrics. Identify 1-2 key strengths the agent consistently demonstrates. For example: "Agent, `Persona Compliance` ve `Style and Courtesy` metriklerinde sürekli yüksek puan alarak marka kimliğine ve profesyonel üsluba başarıyla uyum sağlıyor."

### 3. Öncelikli İyileştirme Alanları
Analyze the low-scoring examples and the metrics with the lowest averages. Identify 1-2 primary weaknesses or common failure patterns. Be specific. For example: "Agent, özellikle `Answer Relevance` metriğinde zorlanıyor; kullanıcıların çok adımlı veya dolaylı sorularını tam olarak yanıtlamak yerine, genellikle sorunun sadece bir kısmına odaklanıyor."

### 4. Eyleme Yönelik Öneriler
Provide 2-3 concrete and actionable recommendations for developers based on your analysis. These should directly address the identified weaknesses.
- **Örnek 1:** "`Answer Relevance` skorlarını artırmak için, çok adımlı soruları alt görevlere ayırabilen bir düşünce zinciri (Chain-of-Thought) mantığı eklenmesi düşünülmelidir."
- **Örnek 2:** "Düşük `Conciseness` skorları için, agent'a yanıtlarını sonlandırmadan önce gereksiz tekrar veya dolgu ifadeleri içerip içermediğini kontrol etmesi için bir iç monolog (inner-monologue) adımı eklenebilir." 