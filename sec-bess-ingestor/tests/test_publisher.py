"""
tests/test_publisher.py — Tests unitarios para publisher/github_publisher.py
Tests ejecutan 100% en dry-run, sin llamadas reales a GitHub API.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from publisher.github_publisher import GitHubPublisher


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_report(tmp_path):
    """Crea archivos de reporte de prueba."""
    full = tmp_path / "gap_analysis_test.md"
    summary = tmp_path / "gap_summary_test.md"
    full.write_text("# Reporte de prueba\n\nContenido completo.", encoding="utf-8")
    summary.write_text("## Resumen de prueba\n\n3 brechas críticas.", encoding="utf-8")
    return str(full), str(summary)


class TestGitHubPublisherDryRun:
    def test_dry_run_does_not_require_token(self):
        """En dry-run, no lanzar error aunque no hay token."""
        pub = GitHubPublisher(dry_run=True, token="")
        assert pub.dry_run is True

    def test_no_token_raises_without_dry_run(self):
        """Sin dry-run y sin token, debe lanzar RuntimeError."""
        import unittest.mock as mock
        import publisher.github_publisher as pub_module
        # Patch el símbolo exacto que usa __init__: GITHUB_TOKEN en el módulo del publisher
        with mock.patch.object(pub_module, "GITHUB_TOKEN", ""):
            with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
                GitHubPublisher(dry_run=False, token="")



    def test_publish_dry_run_returns_results(self, sample_report):
        full_path, summary_path = sample_report
        pub = GitHubPublisher(dry_run=True, token="")
        results = pub.publish(full_path, summary_path)
        assert isinstance(results, dict)
        assert "full_report" in results
        assert "summary" in results
        assert "pull_request" in results

    def test_publish_dry_run_no_real_http(self, sample_report):
        """Verificar que en dry-run NO se hacen peticiones HTTP reales."""
        full_path, summary_path = sample_report
        pub = GitHubPublisher(dry_run=True, token="")
        with patch.object(pub._session, "request") as mock_req:
            pub.publish(full_path, summary_path)
            mock_req.assert_not_called()

    def test_api_method_dry_run(self):
        pub = GitHubPublisher(dry_run=True, token="")
        result = pub._api("get", "/repos/test/test/contents/file.md")
        assert result.get("dry_run") is True
