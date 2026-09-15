#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for CENSipubClient (CEN API Telemetry Driver)
"""

import pytest
from unittest.mock import patch, MagicMock
from src.drivers.cen_sipub_client import (
    CENSipubClient,
)


@pytest.fixture
def client():
    return CENSipubClient(timeout_s=5.0)


@pytest.mark.asyncio
async def test_cen_sipub_url_whitelist(client):
    with pytest.raises(ValueError, match="URL de destino no permitida"):
        client._get_json_sync("https://malicious.com/api")


@pytest.mark.asyncio
async def test_get_marginal_costs_online(client):
    mock_data = {
        "barras": [
            {
                "nombre": "CHARRUA 220KV",
                "orden": 1,
                "valores": [
                    {"fecha": 1726000000, "valor": 45.2},
                    {"fecha": 1726003600, "valor": 52.8},
                ],
            },
            {
                "nombre": "POLPAICO 220KV",
                "orden": 2,
                "valores": [],
            },
        ]
    }
    with patch.object(client, "_get_json_sync", return_value=mock_data):
        readings = await client.get_marginal_costs_online()
        assert len(readings) == 1
        assert readings[0].node_name == "CHARRUA 220KV"
        assert readings[0].order == 1
        assert readings[0].timestamp == 1726003600
        assert readings[0].cmg_usd_mwh == 52.8


@pytest.mark.asyncio
async def test_get_system_demand_real(client):
    mock_data = {
        "data": [
            {"fecha": "2026-09-15", "hora": 18, "demanda": 9850.5},
            {"fecha": "2026-09-15", "hora": 19, "demanda": 10420.2},
        ]
    }
    with patch.object(client, "_get_json_sync", return_value=mock_data):
        demand = await client.get_system_demand_real()
        assert demand is not None
        assert demand.date == "2026-09-15"
        assert demand.hour == 19
        assert demand.demand_mw == 10420.2


@pytest.mark.asyncio
async def test_get_system_demand_real_empty(client):
    with patch.object(client, "_get_json_sync", return_value={"data": []}):
        demand = await client.get_system_demand_real()
        assert demand is None


def test_get_json_sync_network(client):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b'{"status": "ok"}'
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = client._get_json_sync("https://sipub.api.coordinador.cl/test")
        assert res == {"status": "ok"}


def test_get_json_sync_http_error(client):
    mock_resp = MagicMock()
    mock_resp.status = 500
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="CEN API returned status 500"):
            client._get_json_sync("https://sipub.api.coordinador.cl/test")
