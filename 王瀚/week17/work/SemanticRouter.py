import hashlib
import struct
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import redis
from redis.commands.search.field import TagField, TextField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition
from redis.commands.search.query import Query


def _to_bytes(vec: List[float], dtype: str = "float32") -> bytes:
    fmt = "f" if dtype == "float32" else "d"
    return struct.pack(f"{len(vec)}{fmt}", *vec)


def _hashify(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class Route:
    """路由定义，包含名称、参考文本和匹配阈值。

    Attributes:
        name: 路由名称（如 "greeting", "refund"）
        references: 参考文本列表，用于定义该路由的语义空间
        metadata: 路由附带的元数据
        distance_threshold: 余弦距离阈值 [0-2]，越小匹配越严格
    """

    name: str
    references: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    distance_threshold: float = 0.3


@dataclass
class RouteMatch:
    """路由匹配结果。

    Attributes:
        name: 匹配的路由名称，无匹配时为 None
        distance: 向量距离，无匹配时为 None
    """

    name: Optional[str] = None
    distance: Optional[float] = None


class SemanticRouter:
    """基于 Redis 向量搜索的语义路由器，将用户输入分类到预定义路由。

    借鉴 RedisVL SemanticRouter 设计理念：
    - 每个 Route 的 reference 文本被向量化后存入 Redis
    - 查询时对输入文本做向量化，通过 KNN 搜索最近邻
    - 按路由粒度的 distance_threshold 过滤，返回最佳匹配

    Args:
        name: 路由器名称，用作 Redis key 前缀和索引名
        routes: 路由定义列表
        embedding_method: 文本 -> 向量嵌入函数，签名 (str) -> List[float]
        redis_url: Redis 连接 URL
        vector_dims: 嵌入向量维度，为 None 时自动推断
        dtype: 向量数据类型
    """

    VECTOR_FIELD = "vector"

    def __init__(
        self,
        name: str,
        routes: List[Route],
        embedding_method: Callable[[str], List[float]],
        redis_url: str = "redis://localhost:6379",
        vector_dims: Optional[int] = None,
        dtype: str = "float32",
    ):
        self.name = name
        self.routes = routes
        self.embedding_method = embedding_method
        self.dtype = dtype
        self.vector_dims = vector_dims

        self.redis = redis.from_url(redis_url)
        self._index_name = f"{name}_idx"
        self._index_created = False

        if vector_dims:
            self._create_index(vector_dims)

        self._load_routes()

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
            TagField("reference_id"),
            TagField("route_name"),
            TextField("reference"),
            VectorField(
                self.VECTOR_FIELD,
                "FLAT",
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

    def _load_routes(self) -> None:
        for route in self.routes:
            for ref in route.references:
                embedding = self.embedding_method(ref)

                if not self._index_created:
                    self._create_index(len(embedding))

                ref_id = _hashify(f"{route.name}:{ref}")
                key = f"{self.name}:{ref_id}"

                self.redis.hset(
                    key,
                    mapping={
                        "reference_id": ref_id,
                        "route_name": route.name,
                        "reference": ref,
                        self.VECTOR_FIELD: _to_bytes(embedding, self.dtype),
                    },
                )

    def route(self, text: str, top_k: int = 1) -> RouteMatch:
        if not self._index_created:
            return RouteMatch()

        embedding = self.embedding_method(text)
        max_k = max(top_k, len(self.routes) * 5)

        query_str = (
            f"*=>[KNN {max_k} @{self.VECTOR_FIELD} $vec AS vector_distance]"
        )
        query = (
            Query(query_str)
            .return_fields("route_name", "reference", "vector_distance")
            .sort_by("vector_distance")
            .paging(0, max_k)
            .dialect(2)
        )

        results = self.redis.ft(self._index_name).search(
            query, query_params={"vec": _to_bytes(embedding, self.dtype)}
        )

        best_match = RouteMatch()

        for doc in results.docs:
            route_name = doc.route_name
            if isinstance(route_name, bytes):
                route_name = route_name.decode()
            distance = float(getattr(doc, "vector_distance", "2.0"))

            matched_route = next(
                (r for r in self.routes if r.name == route_name), None
            )
            if matched_route and distance <= matched_route.distance_threshold:
                if best_match.name is None or distance < best_match.distance:
                    best_match = RouteMatch(name=route_name, distance=distance)
                if best_match.name and top_k == 1:
                    break

        return best_match

    def __call__(self, text: str, top_k: int = 1) -> RouteMatch:
        return self.route(text, top_k=top_k)

    def get_routes(self) -> List[Route]:
        return list(self.routes)

    def add_route(self, route: Route) -> None:
        self.routes.append(route)
        for ref in route.references:
            embedding = self.embedding_method(ref)

            if not self._index_created:
                self._create_index(len(embedding))

            ref_id = _hashify(f"{route.name}:{ref}")
            key = f"{self.name}:{ref_id}"

            self.redis.hset(
                key,
                mapping={
                    "reference_id": ref_id,
                    "route_name": route.name,
                    "reference": ref,
                    self.VECTOR_FIELD: _to_bytes(embedding, self.dtype),
                },
            )

    def clear(self) -> None:
        try:
            self.redis.ft(self._index_name).dropindex(delete_documents=True)
        except redis.exceptions.ResponseError:
            pass
        self._index_created = False


if __name__ == "__main__":
    import numpy as np

    def mock_embedding(text: str) -> List[float]:
        np.random.seed(hash(text) % 2**32)
        vec = np.random.randn(768).astype(np.float32)
        return vec.tolist()

    routes = [
        Route(
            name="greeting",
            references=["Hi, good morning", "hello", "hi there", "good afternoon"],
            metadata={"type": "greeting"},
            distance_threshold=0.5,
        ),
        Route(
            name="farewell",
            references=["bye", "goodbye", "see you later"],
            metadata={"type": "farewell"},
            distance_threshold=0.5,
        ),
        Route(
            name="refund",
            references=["如何退货", "我想退款", "退货流程"],
            metadata={"type": "refund"},
            distance_threshold=0.5,
        ),
    ]

    router = SemanticRouter(
        name="topic-router",
        routes=routes,
        embedding_method=mock_embedding,
        redis_url="redis://localhost:6379",
    )
    router.clear()
    router = SemanticRouter(
        name="topic-router",
        routes=routes,
        embedding_method=mock_embedding,
        redis_url="redis://localhost:6379",
    )

    result = router("Hi, good morning")
    print(f"route result: {result}")

    result = router("如何退货")
    print(f"route result: {result}")

    result = router("今天天气怎么样")
    print(f"route result (no match expected): {result}")
