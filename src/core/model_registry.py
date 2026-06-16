# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA
"""
src/core/model_registry.py
==========================
BESSAI Edge Gateway — Cloud Model Registry Downloader Client.

Downloads custom ONNX prediction models dynamically from GCP/DigitalOcean hosting
according to the node/bar configuration, enabling zero-code deployments.
"""

from __future__ import annotations

import structlog
from pathlib import Path
import httpx
from src.core.config import settings

logger = structlog.get_logger("bess.edge.model_registry")


class ModelRegistryClient:
    """Client to download and cache custom ONNX models from the Cloud Model Registry."""

    def __init__(
        self,
        registry_url: str | None = None,
        cache_dir: Path | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.registry_url = (registry_url or settings.MODEL_REGISTRY_URL).rstrip("/")
        self.cache_dir = cache_dir or (Path(__file__).resolve().parents[2] / "models")
        self.enabled = enabled if enabled is not None else settings.MODEL_REGISTRY_ENABLED

    def get_model(self, model_name: str, force_update: bool = False) -> Path:
        """
        Get the path to a valid ONNX model.
        Attempts to download the model from the cloud registry if not cached locally.

        Parameters
        ----------
        model_name : Name of the model/node (e.g., 'Maitencillo' or 'dispatch_policy')
        force_update : Force download even if the model exists in the local cache.

        Returns
        -------
        Path to the ONNX model file.
        """
        # Standardize filename format
        if model_name.endswith(".onnx") or model_name.endswith(".onnx.data"):
            filename = model_name
        else:
            # If it's a SEN node, it uses the DRL format
            if model_name in [
                "Cardones", "Charrua", "Crucero", "Hualpen",
                "Lo_Aguirre", "Maitencillo", "Polpaico", "Quillota"
            ]:
                filename = f"{model_name}_drl_cen_v1.onnx.data"
            else:
                filename = f"{model_name}.onnx"

        local_path = self.cache_dir / filename
        fallback_path = self.cache_dir / "dispatch_policy.onnx"

        if not self.enabled:
            logger.info("model_registry.disabled_by_config", model=filename)
            return local_path if local_path.exists() else fallback_path

        if local_path.exists() and not force_update:
            logger.debug("model_registry.cache_hit", path=str(local_path))
            return local_path

        # Attempt to download from cloud registry
        download_url = f"{self.registry_url}/{filename}"
        logger.info("model_registry.download_start", url=download_url, target=str(local_path))

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(download_url)
                if resp.status_code == 200:
                    local_path.write_bytes(resp.content)
                    logger.info("model_registry.download_success", path=str(local_path))
                    return local_path
                else:
                    logger.warning(
                        "model_registry.download_failed_status",
                        status_code=resp.status_code,
                        url=download_url,
                    )
        except Exception as exc:
            logger.warning(
                "model_registry.download_error",
                error=str(exc),
                url=download_url,
            )

        # Return the local path (even if it does not exist) to let the caller handle the missing model error
        if local_path.exists():
            logger.info("model_registry.fallback_to_local_cache", path=str(local_path))
        else:
            logger.warning("model_registry.model_not_available", path=str(local_path))
        return local_path
