import hashlib
import struct
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np
import redis


def _to_bytes(vec: List[float], dtype: str = "float32") -> bytes:
    return np.array(vec, dtype=dtype).tobytes()


def _from_bytes(data: bytes, dtype: str = "float32") -> List[float]:
    return np.frombuffer(data, dtype=dtype).tolist()


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class EmbeddingsCache:
    """基于 Redis Hash 的嵌入向量缓存，避免重复计算 embedding。

    借鉴 RedisVL EmbeddingsCache 设计理念：
    - 使用 SHA256(content + model) 生成确定性 Redis key
    - 每条缓存存储为 Hash 结构（text, model_name, embedding, dimensions）
    - 支持 TTL、Pipeline 批量操作

    Args:
        name: 缓存名称，用作 Redis key 前缀
        ttl: 缓存过期时间（秒），默认 24 小时
        redis_url: Redis 连接 URL
        dtype: 向量数据类型，默认 "float32"
    """

    def __init__(
        self,
        name: str = "embeddings_cache",
        ttl: int = 3600 * 24,
        redis_url: str = "redis://localhost:6379",
        dtype: str = "float32",
    ):
        self.name = name
        self.ttl = ttl
        self.dtype = dtype
        self.redis = redis.from_url(redis_url)

    def _make_key(self, content: str, model_name: str = "") -> str:
        h = _content_hash(f"{content}:{model_name}")
        return f"{self.name}:{h}"

    def set(
        self,
        content: str,
        model_name: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
    ) -> str:
        key = self._make_key(content, model_name)
        mapping: Dict[str, Any] = {
            "text": content,
            "model_name": model_name,
            "embedding": _to_bytes(embedding, self.dtype),
            "dimensions": str(len(embedding)),
        }
        if metadata:
            mapping["metadata"] = str(metadata)

        self.redis.hset(key, mapping=mapping)

        expire_ttl = ttl if ttl is not None else self.ttl
        if expire_ttl:
            self.redis.expire(key, expire_ttl)

        return key

    def get(
        self, content: str, model_name: str
    ) -> Optional[Dict[str, Any]]:
        key = self._make_key(content, model_name)
        data = self.redis.hgetall(key)

        if not data:
            return None

        self.redis.expire(key, self.ttl)

        embedding_bytes = data.get("embedding") or data.get(b"embedding")
        embedding = _from_bytes(embedding_bytes, self.dtype) if embedding_bytes else []

        dims_raw = data.get("dimensions") or data.get(b"dimensions")
        dims = int(dims_raw) if dims_raw else len(embedding)

        text_val = data.get("text") or data.get(b"text")
        model_val = data.get("model_name") or data.get(b"model_name")

        return {
            "text": text_val.decode() if isinstance(text_val, bytes) else text_val,
            "model_name": (
                model_val.decode() if isinstance(model_val, bytes) else model_val
            ),
            "embedding": embedding,
            "dimensions": dims,
        }

    def mset(
        self,
        items: List[Dict[str, Any]],
        ttl: Optional[int] = None,
    ) -> List[str]:
        if not items:
            return []

        keys = []
        with self.redis.pipeline() as pipe:
            for item in items:
                key = self._make_key(item["content"], item.get("model_name", ""))
                keys.append(key)
                mapping: Dict[str, Any] = {
                    "text": item["content"],
                    "model_name": item.get("model_name", ""),
                    "embedding": _to_bytes(item["embedding"], self.dtype),
                    "dimensions": str(len(item["embedding"])),
                }
                pipe.hset(key, mapping=mapping)
            pipe.execute()

        expire_ttl = ttl if ttl is not None else self.ttl
        if expire_ttl:
            for key in keys:
                self.redis.expire(key, expire_ttl)

        return keys

    def mget(
        self, contents: List[str], model_name: str = ""
    ) -> List[Optional[Dict[str, Any]]]:
        if not contents:
            return []

        keys = [self._make_key(c, model_name) for c in contents]

        with self.redis.pipeline() as pipe:
            for key in keys:
                pipe.hgetall(key)
            raw_results = pipe.execute()

        results = []
        for i, data in enumerate(raw_results):
            if not data:
                results.append(None)
                continue

            self.redis.expire(keys[i], self.ttl)

            embedding_bytes = data.get("embedding") or data.get(b"embedding")
            embedding = (
                _from_bytes(embedding_bytes, self.dtype) if embedding_bytes else []
            )

            text_val = data.get("text") or data.get(b"text")
            model_val = data.get("model_name") or data.get(b"model_name")

            results.append(
                {
                    "text": (
                        text_val.decode() if isinstance(text_val, bytes) else text_val
                    ),
                    "model_name": (
                        model_val.decode()
                        if isinstance(model_val, bytes)
                        else model_val
                    ),
                    "embedding": embedding,
                    "dimensions": len(embedding),
                }
            )

        return results

    def delete(self, content: str, model_name: str = "") -> int:
        key = self._make_key(content, model_name)
        return self.redis.delete(key)

    def mdelete(self, contents: List[str], model_name: str = "") -> int:
        if not contents:
            return 0
        keys = [self._make_key(c, model_name) for c in contents]
        return self.redis.delete(*keys)

    def exists(self, content: str, model_name: str = "") -> bool:
        key = self._make_key(content, model_name)
        return bool(self.redis.exists(key))

    def clear(self) -> None:
        cursor = 0
        while True:
            cursor, keys = self.redis.scan(
                cursor=cursor, match=f"{self.name}:*", count=500
            )
            if keys:
                self.redis.delete(*keys)
            if cursor == 0:
                break


if __name__ == "__main__":
    cache = EmbeddingsCache(
        name="embedding_cache",
        ttl=360,
        redis_url="redis://localhost:6379",
    )
    cache.clear()

    test_embedding = np.random.rand(768).astype(np.float32).tolist()

    key = cache.set(
        content="hello world",
        model_name="all-MiniLM-L6-v2",
        embedding=test_embedding,
    )
    print("stored key:", key)

    result = cache.get(content="hello world", model_name="all-MiniLM-L6-v2")
    print("get result:", result["text"] if result else None)

    print("exists:", cache.exists("hello world", "all-MiniLM-L6-v2"))
    print("delete:", cache.delete("hello world", "all-MiniLM-L6-v2"))
    print("exists after delete:", cache.exists("hello world", "all-MiniLM-L6-v2"))
