# Minimal stub for flwr (Flower Federated Learning) — optional dep
from __future__ import annotations

from typing import Any

class server:  # noqa: N801
    @staticmethod
    def start_server(
        server_address: str = ...,
        config: Any = ...,
        strategy: Any = ...,
        **kwargs: Any,
    ) -> None: ...

class client:  # noqa: N801
    @staticmethod
    def start_numpy_client(
        server_address: str,
        client: Any,
        **kwargs: Any,
    ) -> None: ...
    @staticmethod
    def start_client(
        server_address: str,
        client: Any,
        **kwargs: Any,
    ) -> None: ...

class common:  # noqa: N801
    class Parameters:
        def __init__(self, tensors: list[bytes], tensor_type: str) -> None: ...

    class FitRes:
        parameters: Any
        num_examples: int

    class EvaluateRes:
        loss: float
        num_examples: int
        metrics: dict[str, Any]
