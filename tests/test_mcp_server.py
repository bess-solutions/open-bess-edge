# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_mcp_server.py
========================
Unit tests for the Python-based MCP server tools.
Uses mocks for Modbus and file system interactions to prevent global state dependencies.
"""

import os
import json
import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_server.server import (
    get_battery_health,
    diagnose_faults,
    predict_rul,
    cyber_hygiene_check,
    verify_compliance_certificate
)
from src.core.certificate_validator import (
    GLOBAL_CERTIFIER,
    BESSComplianceCertifier,
    BLOCKCHAIN_CERTIFICATE_LEDGER
)

# ---------------------------------------------------------------------------
# Test: get_battery_health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_battery_health_success_simulator() -> None:
    """Verifica la telemetría del simulador Modbus en caso exitoso."""
    # Mockear UniversalDriver
    mock_driver = MagicMock()
    mock_driver.is_connected = True
    mock_driver.connect = AsyncMock()
    mock_driver.disconnect = AsyncMock()
    mock_driver.read_tag = AsyncMock()

    # Configurar valores leídos de Modbus
    mock_driver.read_tag.side_effect = lambda tag: {
        "soc": 85.5,
        "temp_c": 26.2,
        "active_power": 1200.0,
        "ac_voltage": 220.5,
        "frequency": 50.02
    }[tag]

    with patch("mcp_server.server.UniversalDriver", return_value=mock_driver):
        result_str = await get_battery_health(unit_id=1, profile="simulator.json")
        result = json.loads(result_str)

        assert result["unit_id"] == 1
        assert result["connected"] is True
        assert result["telemetry"]["soc_pct"] == 85.5
        assert result["telemetry"]["temp_c"] == 26.2
        assert "SOH not exposed" in result["status"]
        
        mock_driver.connect.assert_awaited_once()
        mock_driver.disconnect.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_battery_health_failure_fail_fast() -> None:
    """Verifica que si no hay conexión Modbus se lance un error rápido (Zero Mock)."""
    mock_driver = MagicMock()
    mock_driver.is_connected = False
    mock_driver.connect = AsyncMock(side_effect=ConnectionError("Host unreachable"))

    with patch("mcp_server.server.UniversalDriver", return_value=mock_driver):
        with pytest.raises(RuntimeError) as exc_info:
            await get_battery_health(unit_id=1, profile="simulator.json")
        
        assert "No se pudo conectar al BESS" in str(exc_info.value)

# ---------------------------------------------------------------------------
# Test: diagnose_faults
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_diagnose_faults_ok_simulator() -> None:
    """Verifica el diagnóstico de estado normal (sin fallas)."""
    mock_driver = MagicMock()
    mock_driver.is_connected = True
    mock_driver.connect = AsyncMock()
    mock_driver.disconnect = AsyncMock()
    mock_driver.read_tag = AsyncMock(return_value=256.0) # Running

    with patch("mcp_server.server.UniversalDriver", return_value=mock_driver):
        result_str = await diagnose_faults(unit_id=1, profile="simulator.json")
        result = json.loads(result_str)

        assert result["status"] == "Running"
        assert len(result["active_faults"]) == 0

@pytest.mark.asyncio
async def test_diagnose_faults_critical_simulator() -> None:
    """Verifica el diagnóstico cuando el inversor reporta estado de falla (512)."""
    mock_driver = MagicMock()
    mock_driver.is_connected = True
    mock_driver.connect = AsyncMock()
    mock_driver.disconnect = AsyncMock()
    mock_driver.read_tag = AsyncMock(return_value=512.0) # Fault

    with patch("mcp_server.server.UniversalDriver", return_value=mock_driver):
        result_str = await diagnose_faults(unit_id=1, profile="simulator.json")
        result = json.loads(result_str)

        assert result["status"] == "Fault"
        assert "Critical Fault State Active" in result["active_faults"][0]

# ---------------------------------------------------------------------------
# Test: predict_rul
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_predict_rul_success(tmp_path: Path) -> None:
    """Verifica el cálculo de RUL a partir de un archivo Parquet con datos reales."""
    # Crear un dataset parquet de prueba
    temp_df = pd.DataFrame({
        "temp_c": [25.0, 30.0, 35.0, 20.0, 45.0],
        "timestamp": pd.date_range("2026-06-16", periods=5, freq="h")
    })
    temp_file = tmp_path / "test_degradation.parquet"
    temp_df.to_parquet(temp_file)

    result_str = await predict_rul(unit_id=1, dataset_path=str(temp_file))
    result = json.loads(result_str)

    assert result["unit_id"] == 1
    assert result["total_records_hours"] == 5
    assert result["mean_ambient_temp_c"] == 31.0
    assert result["projected_remaining_hours"] > 0
    assert "Arrhenius" in result["status"]

@pytest.mark.asyncio
async def test_predict_rul_file_not_found() -> None:
    """Verifica el fallo rápido si no existe el archivo Parquet."""
    with pytest.raises(FileNotFoundError) as exc_info:
        await predict_rul(unit_id=1, dataset_path="nonexistent_file.parquet")
    
    assert "No hay datos históricos" in str(exc_info.value)

# ---------------------------------------------------------------------------
# Test: cyber_hygiene_check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cyber_hygiene_check_doc_fallback() -> None:
    """Verifica la higiene de seguridad cayendo al playbook del repositorio (en dev)."""
    def exists_wrapper(self_obj):
        path_str = str(self_obj)
        if "sshd_config" in path_str or "openssl.cnf" in path_str:
            return False
        if "cybersecurity.md" in path_str:
            return True
        return False

    with patch("pathlib.Path.exists", new=exists_wrapper):
        result_str = await cyber_hygiene_check(host_ip="localhost")
        result = json.loads(result_str)

        assert result["overall_status"] == "COMPLIANT"
        assert result["security_level_achieved"] == "SL-2 (Operational - Recommended)"
        assert result["ssh_compliance"]["details"]["policy_defined"] is True

# ---------------------------------------------------------------------------
# Test: verify_compliance_certificate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_compliance_certificate_success() -> None:
    """Verifica que un certificado válido y registrado pase la verificación."""
    cert = GLOBAL_CERTIFIER.issue_certificate(
        site_id="SITE-CL-001",
        company="BESS Solutions",
        compliance_score=99.5
    )
    cert_json = json.dumps(cert)
    
    result_str = await verify_compliance_certificate(cert_json)
    result = json.loads(result_str)
    
    assert result["valid"] is True
    assert result["details"]["site_id"] == "SITE-CL-001"
    assert result["details"]["blockchain_registration"]["status"] == "ACTIVE"

@pytest.mark.asyncio
async def test_verify_compliance_certificate_tampered() -> None:
    """Verifica que si se alteran los datos del certificado, la firma falle."""
    cert = GLOBAL_CERTIFIER.issue_certificate(
        site_id="SITE-CL-002",
        company="BESS Solutions",
        compliance_score=95.0
    )
    # Alterar el score de cumplimiento
    cert["data"]["compliance_score"] = 100.0
    cert_json = json.dumps(cert)
    
    result_str = await verify_compliance_certificate(cert_json)
    result = json.loads(result_str)
    
    assert result["valid"] is False
    assert "firma digital no coincide" in result["reason"]

@pytest.mark.asyncio
async def test_verify_compliance_certificate_wrong_key() -> None:
    """Verifica que un certificado firmado por otra entidad no sea de confianza."""
    rogue_certifier = BESSComplianceCertifier()
    cert = rogue_certifier.issue_certificate(
        site_id="SITE-CL-003",
        company="Rogue Operator",
        compliance_score=98.0
    )
    cert_json = json.dumps(cert)
    
    result_str = await verify_compliance_certificate(cert_json)
    result = json.loads(result_str)
    
    assert result["valid"] is False
    assert "firma digital no coincide" in result["reason"]

@pytest.mark.asyncio
async def test_verify_compliance_certificate_unregistered() -> None:
    """Verifica que un certificado no registrado en el ledger blockchain falle."""
    cert = GLOBAL_CERTIFIER.issue_certificate(
        site_id="SITE-CL-004",
        company="BESS Solutions",
        compliance_score=99.0
    )
    # Remover temporalmente de la blockchain simulada
    cert_hash = cert["cert_hash"]
    entry = BLOCKCHAIN_CERTIFICATE_LEDGER.pop(cert_hash, None)
    
    try:
        cert_json = json.dumps(cert)
        result_str = await verify_compliance_certificate(cert_json)
        result = json.loads(result_str)
        
        assert result["valid"] is False
        assert "no se encuentra registrado" in result["reason"]
    finally:
        # Restaurar
        if entry:
            BLOCKCHAIN_CERTIFICATE_LEDGER[cert_hash] = entry

@pytest.mark.asyncio
async def test_verify_compliance_certificate_invalid_json() -> None:
    """Verifica el fallo ante un JSON mal formado."""
    result_str = await verify_compliance_certificate("invalid-json{")
    result = json.loads(result_str)
    
    assert result["valid"] is False
    assert "no es un JSON válido" in result["reason"]
