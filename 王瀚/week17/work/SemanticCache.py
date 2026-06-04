import hashlib
import struct
from typing import Any, Callable, Dict, List, Optional, Union

import redis
from redis.commands.search.field import TextField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition
from redis.commands.search.query import Query


def _to_bytes(vec: List[float], dtype: str = "float32") -> bytes:
    fmt = "f" if dtype == "float32" else "d"
    return struct.pack(f"{len(vec)}{fmt}", *vec)


def _hashify(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class SemanticCache:
    """基于 Redis 原生向量搜索的语义缓存，用于缓存 LLM 问答结果。

    借鉴 RedisVL SemanticCache 设计理念：
    - 使用 Redis Search 索引 + KNN 向量搜索替代 Faiss
    - 每条缓存条目存储为独立的 Redis Hash
    - 支持 TTL 自动过期、距离阈值过滤

    Args:
        name: 缓存索引名称，也用作 Redis key 前缀
        embedding_method: 将文本转换为向量嵌入的函数，签名 (str) -> List[float]
        ttl: 缓存条目过期时间（秒），默认 24 小时
        redis_url: Redis 连接 URL，如 "redis://localhost:6379"
        distance_threshold: 余弦距离阈值 [0-2]，越小匹配越严格，默认 0.1
        vector_dims: 嵌入向量维度，为 None 时自动从首次 embedding 推断
        dtype: 向量数据类型，"float32" 或 "float64"
    """

    RETURN_FIELDS = ["entry_id", "prompt", "response", "vector_distance"]
    VECTOR_FIELD = "prompt_vector"

    def __init__(
        self,
        name: str,
        embedding_method: Callable[[str], List[float]],
        ttl: int = 3600 * 24,
        redis_url: str = "redis://localhost:6379",
        distance_threshold: float = 0.1,
        vector_dims: Optional[int] = None,
        dtype: str = "float32",
    ):
        self.name = name
        self.ttl = ttl
        self.distance_threshold = distance_threshold
        self.embedding_method = embedding_method
        self.vector_dims = vector_dims
        self.dtype = dtype

        self.redis = redis.from_url(redis_url)
        self._index_name = f"{name}_idx"
        self._index_created = False

        if vector_dims:
            self._create_index(vector_dims)

    def _create_index(self, dims: int) -> None:
        if self._index_created:
            return
        try:
            self.redis.ft(self._index_name).info()
            self._index_created = True
            return
        except redis.exceptions.ResponseError:
            pass

        definition = IndexDefinition(prefix=[f"{self.name}:"])
        schema = [
            TextField("entry_id"),
            TextField("prompt"),
            TextField("response"),
            VectorField(
                self.VECTOR_FIELD,
                "HNSW",
                {
                    "TYPE": self.dtype.upper(),
                    "DIM": dims,
                    "DISTANCE_METRIC": "COSINE",
                },
            ),
        ]
        self.redis.ft(self._index_name).create_index(
            fields=schema, definition=definition
        )
        self._index_created = True

    def _make_key(self, entry_id: str) -> str:
        return f"{self.name}:{entry_id}"

    def store(
        self,
        prompt: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
    ) -> str:
        embedding = self.embedding_method(prompt)

        if not self._index_created:
            self._create_index(len(embedding))

        entry_id = _hashify(prompt)
        key = self._make_key(entry_id)

        mapping = {
            "entry_id": entry_id,
            "prompt": prompt,
            "response": response,
            self.VECTOR_FIELD: _to_bytes(embedding, self.dtype),
        }
        if metadata:
            mapping["metadata"] = str(metadata)

        self.redis.hset(key, mapping=mapping)

        expire_ttl = ttl if ttl is not None else self.ttl
        if expire_ttl:
            self.redis.expire(key, expire_ttl)

        return key

    def check(
        self,
        prompt: str,
        num_results: int = 1,
        distance_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        if not self._index_created:
            return []

        threshold = (
            distance_threshold
            if distance_threshold is not None
            else self.distance_threshold
        )
        embedding = self.embedding_method(prompt)

        query_str = (
            f"*=>[KNN {num_results} @{self.VECTOR_FIELD} $vec AS vector_distance]"
        )
        query = (
            Query(query_str)
            .return_fields(*self.RETURN_FIELDS)
            .paging(0, num_results)
            .dialect(2)
        )

        results = self.redis.ft(self._index_name).search(
            query, query_params={"vec": _to_bytes(embedding, self.dtype)}
        )

        cache_hits = []
        for doc in results.docs:
            distance = float(getattr(doc, "vector_distance", "2.0"))
            if distance <= threshold:
                cache_hits.append(
                    {
                        "entry_id": doc.entry_id,
                        "prompt": doc.prompt,
                        "response": doc.response,
                        "vector_distance": distance,
                    }
                )

        return cache_hits

    def delete(self, prompt: str) -> int:
        entry_id = _hashify(prompt)
        return self.redis.delete(self._make_key(entry_id))

    def clear(self) -> None:
        try:
            self.redis.ft(self._index_name).dropindex(delete_documents=True)
        except redis.exceptions.ResponseError:
            pass
        self._index_created = False

    def flush(self) -> None:
        self.redis.flushdb()
        self._index_created = False


if __name__ == "__main__":
    import numpy as np

    def mock_embedding(text: str) -> List[float]:
        np.random.seed(hash(text) % 2**32)
        vec = np.random.randn(768).astype(np.float32)
        return vec.tolist()

    cache = SemanticCache(
        name="semantic_cache",
        embedding_method=mock_embedding,
        ttl=360,
        redis_url="redis://localhost:6379",
        distance_threshold=0.5,
    )
    cache.clear()

    cache.store(prompt="hello world", response="hello world1232")
    print("check same prompt:", cache.check(prompt="hello world"))

    cache.store(prompt="hello my name", response="nihao")
    print("check after second store:", cache.check(prompt="hello world"))
