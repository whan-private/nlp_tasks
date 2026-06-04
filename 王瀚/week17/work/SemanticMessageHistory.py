import hashlib
import struct
import time
from typing import Any, Callable, Dict, List, Optional, Union

import redis
from redis.commands.search.field import (
    NumericField,
    TagField,
    TextField,
    VectorField,
)
from redis.commands.search.indexDefinition import IndexDefinition
from redis.commands.search.query import Query


def _to_bytes(vec: List[float], dtype: str = "float32") -> bytes:
    fmt = "f" if dtype == "float32" else "d"
    return struct.pack(f"{len(vec)}{fmt}", *vec)


def _make_id() -> str:
    return hashlib.sha256(f"{time.time_ns()}".encode()).hexdigest()[:16]


VALID_ROLES = {"system", "user", "llm", "tool"}


class SemanticMessageHistory:
    """基于 Redis 向量搜索的语义对话历史管理。

    借鉴 RedisVL SemanticMessageHistory 设计理念：
    - 每条消息存储为独立的 Redis Hash（而非 JSON 大 blob）
    - get_recent: 按时间排序获取最近消息
    - get_relevant: 通过向量语义搜索获取相关上下文
    - 支持 role 过滤（system/user/llm/tool）
    - 支持 session 隔离

    Args:
        name: 索引名称，也用作 session 标识和 key 前缀
        embedding_method: 文本 -> 向量嵌入函数，签名 (str) -> List[float]
        ttl: 消息过期时间（秒），默认 24 小时
        redis_url: Redis 连接 URL
        distance_threshold: 语义搜索距离阈值 [0-2]，默认 0.3
        vector_dims: 嵌入向量维度，为 None 时自动推断
        dtype: 向量数据类型
    """

    VECTOR_FIELD = "vector_field"
    RETURN_FIELDS = [
        "entry_id",
        "session_tag",
        "role",
        "content",
        "timestamp",
        "metadata",
    ]

    def __init__(
        self,
        name: str,
        embedding_method: Callable[[str], List[float]],
        ttl: int = 3600 * 24,
        redis_url: str = "redis://localhost:6379",
        distance_threshold: float = 0.3,
        vector_dims: Optional[int] = None,
        dtype: str = "float32",
    ):
        self.name = name
        self.embedding_method = embedding_method
        self.ttl = ttl
        self.distance_threshold = distance_threshold
        self.vector_dims = vector_dims
        self.dtype = dtype
        self.session_tag = name

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
            TagField("entry_id"),
            TagField("session_tag"),
            TagField("role"),
            TextField("content"),
            NumericField("timestamp", sortable=True),
            TextField("metadata"),
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

    def _validate_role(self, role: str) -> None:
        if role not in VALID_ROLES:
            raise ValueError(
                f"Invalid role '{role}'. Must be one of: {VALID_ROLES}"
            )

    def add_message(
        self,
        message: Dict[str, Any],
        session_tag: Optional[str] = None,
    ) -> str:
        return self.add_messages([message], session_tag)[0]

    def add_messages(
        self,
        messages: List[Dict[str, Any]],
        session_tag: Optional[str] = None,
    ) -> List[str]:
        tag = session_tag or self.session_tag
        keys = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            self._validate_role(role)

            embedding = self.embedding_method(content)

            if not self._index_created:
                self._create_index(len(embedding))

            entry_id = _make_id()
            key = self._make_key(entry_id)

            mapping: Dict[str, Any] = {
                "entry_id": entry_id,
                "session_tag": tag,
                "role": role,
                "content": content,
                "timestamp": str(time.time()),
                self.VECTOR_FIELD: _to_bytes(embedding, self.dtype),
            }
            if "metadata" in msg:
                mapping["metadata"] = str(msg["metadata"])
            if "tool_call_id" in msg:
                mapping["tool_call_id"] = str(msg["tool_call_id"])

            self.redis.hset(key, mapping=mapping)
            if self.ttl:
                self.redis.expire(key, self.ttl)
            keys.append(key)

        return keys

    def get_recent(
        self,
        top_k: int = 5,
        role: Optional[Union[str, List[str]]] = None,
        session_tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        tag = session_tag or self.session_tag

        if role:
            roles = [role] if isinstance(role, str) else role
            role_filter = " | ".join(f"@role:{{{r}}}" for r in roles)
            filter_str = f"@session_tag:{{{tag}}} ({role_filter})"
        else:
            filter_str = f"@session_tag:{{{tag}}}"

        query = (
            Query(filter_str)
            .return_fields(*self.RETURN_FIELDS)
            .sort_by("timestamp", asc=False)
            .paging(0, top_k)
            .dialect(2)
        )

        results = self.redis.ft(self._index_name).search(query)

        messages = []
        for doc in results.docs:
            messages.append(self._doc_to_dict(doc))

        return messages[::-1]

    def get_relevant(
        self,
        prompt: str,
        top_k: int = 5,
        role: Optional[Union[str, List[str]]] = None,
        session_tag: Optional[str] = None,
        distance_threshold: Optional[float] = None,
        fall_back: bool = False,
    ) -> List[Dict[str, Any]]:
        if not self._index_created:
            return []

        threshold = (
            distance_threshold
            if distance_threshold is not None
            else self.distance_threshold
        )
        tag = session_tag or self.session_tag
        embedding = self.embedding_method(prompt)

        if role:
            roles = [role] if isinstance(role, str) else role
            role_filter = " | ".join(f"@role:{{{r}}}" for r in roles)
            pre_filter = f"@session_tag:{{{tag}}} ({role_filter})"
        else:
            pre_filter = f"@session_tag:{{{tag}}}"

        query_str = (
            f"{pre_filter}=>[KNN {top_k} @{self.VECTOR_FIELD} $vec AS vector_distance]"
        )
        query = (
            Query(query_str)
            .return_fields(*self.RETURN_FIELDS, "vector_distance")
            .sort_by("vector_distance")
            .paging(0, top_k)
            .dialect(2)
        )

        results = self.redis.ft(self._index_name).search(
            query, query_params={"vec": _to_bytes(embedding, self.dtype)}
        )

        messages = []
        for doc in results.docs:
            distance = float(getattr(doc, "vector_distance", "2.0"))
            if distance <= threshold:
                msg = self._doc_to_dict(doc)
                msg["vector_distance"] = distance
                messages.append(msg)

        if not messages and fall_back:
            return self.get_recent(top_k=top_k, role=role, session_tag=session_tag)

        return messages

    def count(self, session_tag: Optional[str] = None) -> int:
        tag = session_tag or self.session_tag
        query = Query(f"@session_tag:{{{tag}}}").paging(0, 0).dialect(2)
        results = self.redis.ft(self._index_name).search(query)
        return results.total

    def clear(self) -> None:
        try:
            self.redis.ft(self._index_name).dropindex(delete_documents=True)
        except redis.exceptions.ResponseError:
            pass
        self._index_created = False

    @staticmethod
    def _doc_to_dict(doc) -> Dict[str, Any]:
        result = {"id": doc.id}
        for field in SemanticMessageHistory.RETURN_FIELDS:
            val = getattr(doc, field, None)
            result[field] = val.decode() if isinstance(val, bytes) else val
        return result


if __name__ == "__main__":
    import numpy as np

    def mock_embedding(text: str) -> List[float]:
        np.random.seed(hash(text) % 2**32)
        vec = np.random.randn(768).astype(np.float32)
        return vec.tolist()

    history = SemanticMessageHistory(
        name="my-session",
        embedding_method=mock_embedding,
        redis_url="redis://localhost:6379",
        distance_threshold=0.7,
    )
    history.clear()

    history.add_messages(
        [
            {"role": "user", "content": "hello, how are you?"},
            {"role": "llm", "content": "I'm doing fine, thanks."},
            {"role": "user", "content": "what is the weather going to be today?"},
            {"role": "llm", "content": "I don't know", "metadata": {"model": "gpt-4"}},
        ]
    )

    print("get_recent top_k=1:", history.get_recent(top_k=1))
    print("get_recent role=user:", history.get_recent(role="user", top_k=1))
    print("\nget_relevant 'weather':", history.get_relevant("weather", top_k=1))
    print("get_relevant 'thanks':", history.get_relevant("thanks", top_k=1))
    print("\nmessage count:", history.count())
