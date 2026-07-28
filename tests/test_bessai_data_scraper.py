# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_bessai_data_scraper.py
==================================
Unit tests for ``scripts.bessai_data_scraper``.
"""

import os
from unittest.mock import MagicMock, patch

from scripts.bessai_data_scraper import _date_range, scrape_cmg


def test_date_range():
    start, end = _date_range(7)
    assert isinstance(start, str)
    assert isinstance(end, str)


@patch("requests.get")
def test_scrape_cmg_reads_env_key(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "last_page": 1,
        "data": [
            {
                "fecha": "2026-06-01",
                "hora": 12,
                "nombre_barra": "BAQUEDANO 220KV",
                "cmg_usd_mwh_": 45.2,
            }
        ],
    }
    mock_get.return_value = mock_response

    os.environ["CEN_API_KEY"] = "test_key_123"
    df = scrape_cmg(n_days=1)

    assert df is not None
    assert mock_get.called
    call_args = mock_get.call_args[1]
    assert call_args["params"]["user_key"] == "test_key_123"
