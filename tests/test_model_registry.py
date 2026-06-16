# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA
"""
tests/test_model_registry.py
============================
Unit tests for the ModelRegistryClient.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
from src.core.model_registry import ModelRegistryClient


class TestModelRegistryClient:
    """Tests for ModelRegistryClient functionality."""

    def test_init_defaults(self) -> None:
        client = ModelRegistryClient()
        assert client.registry_url.startswith("http")
        assert client.cache_dir.name == "models"
        assert client.enabled is True

    def test_init_custom(self, tmp_path: Path) -> None:
        client = ModelRegistryClient(
            registry_url="https://custom-registry.com",
            cache_dir=tmp_path,
            enabled=False,
        )
        assert client.registry_url == "https://custom-registry.com"
        assert client.cache_dir == tmp_path
        assert client.enabled is False

    def test_get_model_cached(self, tmp_path: Path) -> None:
        # Create a dummy model file in cache
        model_file = tmp_path / "Cardones_drl_cen_v1.onnx.data"
        model_file.write_bytes(b"dummy-cached-model")

        client = ModelRegistryClient(cache_dir=tmp_path)
        path = client.get_model("Cardones")
        assert path == model_file
        assert path.read_bytes() == b"dummy-cached-model"

    @patch("httpx.Client.get")
    def test_get_model_download_success(self, mock_get: MagicMock, tmp_path: Path) -> None:
        # Mock successful HTTP download
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.content = b"dummy-downloaded-model"
        mock_get.return_value = mock_response

        client = ModelRegistryClient(cache_dir=tmp_path)
        path = client.get_model("Polpaico")

        expected_path = tmp_path / "Polpaico_drl_cen_v1.onnx.data"
        assert path == expected_path
        assert path.exists()
        assert path.read_bytes() == b"dummy-downloaded-model"
        mock_get.assert_called_once_with(f"{client.registry_url}/Polpaico_drl_cen_v1.onnx.data")

    @patch("httpx.Client.get")
    def test_get_model_download_fail_fallback_to_default(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        # Mock a 404 response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        client = ModelRegistryClient(cache_dir=tmp_path)
        path = client.get_model("Quillota")

        expected_path = tmp_path / "Quillota_drl_cen_v1.onnx.data"
        assert path == expected_path
        assert not path.exists()

    @patch("httpx.Client.get")
    def test_get_model_download_network_error_fallback_to_cache(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        # Mock a network connection timeout
        mock_get.side_effect = httpx.ConnectTimeout("Connection timed out")

        # Create cached version
        model_file = tmp_path / "Charrua_drl_cen_v1.onnx.data"
        model_file.write_bytes(b"cached-version")

        client = ModelRegistryClient(cache_dir=tmp_path)
        path = client.get_model("Charrua")

        assert path == model_file
        assert path.read_bytes() == b"cached-version"

    def test_get_model_disabled_fallback_to_default(self, tmp_path: Path) -> None:
        default_policy = tmp_path / "dispatch_policy.onnx"
        default_policy.write_bytes(b"default-policy")

        client = ModelRegistryClient(cache_dir=tmp_path, enabled=False)
        path = client.get_model("Crucero")

        assert path == default_policy
