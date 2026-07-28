# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_server_totp_rate_limit.py
======================================
Unit tests for TOTP setpoint authentication gate and Rate Limiter middleware.
"""

import os

import pyotp
import pytest
from aiohttp.test_utils import TestClient, TestServer
from src.interfaces.server import _RATE_LIMIT_STORE, BESSAIServer


@pytest.fixture
def reset_rate_limit():
    _RATE_LIMIT_STORE.clear()
    yield
    _RATE_LIMIT_STORE.clear()


@pytest.mark.asyncio
async def test_setpoint_requires_totp_when_mfa_secret_set(reset_rate_limit):
    secret = "JBSWY3DPEHPK3PXP"
    os.environ["DASHBOARD_MFA_SECRET"] = secret
    server = BESSAIServer(site_id="TEST-SITE")
    app = server._app

    try:
        async with TestClient(TestServer(app)) as client:
            # Request without TOTP token -> 401
            resp = await client.post("/api/v1/setpoint", json={"target_kw": 50.0})
            assert resp.status == 401
            body = await resp.json()
            assert body["error"] == "unauthorized"

            # Request with invalid TOTP token -> 401
            headers_invalid = {"X-TOTP-Token": "000000"}
            resp_invalid = await client.post(
                "/api/v1/setpoint", json={"target_kw": 50.0}, headers=headers_invalid
            )
            assert resp_invalid.status == 401

            # Request with valid TOTP token -> 202 (Happy Path with MFA)
            valid_token = pyotp.TOTP(secret).now()
            headers_valid = {"X-TOTP-Token": valid_token}
            resp_valid = await client.post(
                "/api/v1/setpoint",
                json={"target_kw": 75.0, "strategy": "arbitrage"},
                headers=headers_valid,
            )
            assert resp_valid.status == 202
            body_valid = await resp_valid.json()
            assert body_valid["status"] == "accepted"
            assert body_valid["target_kw"] == 75.0
    finally:
        os.environ.pop("DASHBOARD_MFA_SECRET", None)


@pytest.mark.asyncio
async def test_setpoint_accepted_in_dev_mode(reset_rate_limit):
    os.environ.pop("DASHBOARD_MFA_SECRET", None)
    server = BESSAIServer(site_id="TEST-SITE")
    app = server._app

    async with TestClient(TestServer(app)) as client:
        resp = await client.post("/api/v1/setpoint", json={"target_kw": 100.0})
        assert resp.status == 202
        body = await resp.json()
        assert body["status"] == "accepted"
        assert body["target_kw"] == 100.0


@pytest.mark.asyncio
async def test_rate_limiter_enforces_limit(reset_rate_limit):
    server = BESSAIServer(site_id="TEST-SITE")
    app = server._app

    async with TestClient(TestServer(app)) as client:
        # First 300 requests should be 200 OK
        for _ in range(300):
            resp = await client.get("/health")
            assert resp.status == 200

        # 301st request should return 429 Too Many Requests
        resp_blocked = await client.get("/health")
        assert resp_blocked.status == 429
        body = await resp_blocked.json()
        assert body["error"] == "too_many_requests"
