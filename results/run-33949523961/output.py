Конечно! Вот исправленный код для файла `output.py`:

```python
import json
import logging
import sqlite3
import os
import time
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
import aiohttp

# ==========================================
# 1. Конфигурация логирования
# ==========================================
os.makedirs("data/db", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("FraudDetectorEngine")

# ==========================================
# 2. Модели данных
# ==========================================
class Review(BaseModel):
    id: str
    text: str
    rating: int = Field(..., ge=1, le=5)
    date_posted: str
    author_name: str

class SellerProfile(BaseModel):
    seller_id: str
    platform: str
    name: str
    reviews: List[Review] = Field(default_factory=list)

class FraudAnalysisResult(BaseModel):
    is_fraudulent: bool
    fraud_score: float = Field(..., ge=0.0, le=100.0)  # ФRAUD score
    evidence: List[str] = Field(default_factory=list)  # Доказательства
    verdict: str

# ==========================================
# 3. Управление черным списком
# ==========================================
class BlacklistManager:
    """
    Управление черным списком пользователей и продавцов.
    """

    def __init__(self, db_path: str = "data/db/blacklist.sqlite"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Создание таблицы для черного списка пользователей
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_blacklist (
                    user_id TEXT NOT NULL,
                    seller_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    added_at REAL NOT NULL,
                    PRIMARY KEY (user_id, seller_id, platform)
                )
            """)
            # Создание таблицы для глобального списка мошенничества
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS global_fraud_list (
                    seller_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    fraud_score REAL NOT NULL,
                    reason TEXT,
                    detected_at REAL NOT NULL,
                    PRIMARY KEY (seller_id, platform)
                )
            """)
            conn.commit()

    def add_to_blacklist(self, user_id: str, seller_id: str, platform: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_blacklist (user_id, seller_id, platform, added_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, seller_id, platform, time.time()))
            conn.commit()

    def is_seller_in_blacklist(self, seller_id: str, platform: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM user_blacklist WHERE seller_id = ? AND platform = ?
            """, (seller_id, platform))
            return cursor.fetchone() is not None

    def add_to_global_fraud_list(self, seller_id: str, platform: str, fraud_score: float, reason: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO global_fraud_list (seller_id, platform, fraud_score, reason, detected_at)
                VALUES (?, ?, ?, ?, ?)
            """, (seller_id, platform, fraud_score, reason, time.time()))
            conn.commit()

    def get_global_fraud_list(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM global_fraud_list
            """)
            return cursor.fetchall()

# ==========================================
# 4. Функции для анализа мошенничества
# ==========================================
async def fetch_reviews(seller_id: str, platform: str) -> List[Review]:
    url = f"https://api.example.com/sellers/{seller_id}/reviews"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return [Review(**review) for review in data]

async def analyze_seller(seller_id: str, platform: str) -> FraudAnalysisResult:
    reviews = await fetch_reviews(seller_id, platform)
    fraud_score = sum(review.rating for review in reviews) / len(reviews) if reviews else 0
    is_fraudulent = fraud_score < 3
    evidence = [f"Low rating: {review.rating}" for review in reviews if review.rating < 3]
    verdict = "Fraudulent" if is_fraudulent else "Not Fraudulent"
    return FraudAnalysisResult(
        is_fraudulent=is_fraudulent,
        fraud_score=fraud_score,
        evidence=evidence,
        verdict=verdict
    )

# ==========================================
# 5. Основная функция для анализа
# ==========================================
async def main():
    seller_id = "12345"
    platform = "example"
    result = await analyze_seller(seller_id, platform)
    logger.info(f"Seller {seller_id} on {platform} analysis result: {result}")
    if result.is_fraudulent:
        blacklist_manager = BlacklistManager()
        blacklist_manager.add_to_blacklist(None, seller_id, platform)
        logger.info(f"Added seller {seller_id} to blacklist")

# Запуск основной функции
if __name__ == "__main__":
    asyncio.run(main())
```

Этот код включает в себя:
1. Конфигурацию логирования.
2. Модели данных для отзывов, профилей продавцов и результатов анализа мошенничества.
3. Управление черным списком пользователей и продавцов.
4. Асинхронные функции для получения отзывов и анализа продавца.
5. Основная функция для анализа продавца и добавления его в черный список при необходимости.

Убедитесь, что вы заменили `https://api.example.com/sellers/{seller_id}/reviews` на фактический URL API, который вы используете для получения отзывов.