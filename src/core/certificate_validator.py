# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/certificate_validator.py
==================================
Cryptographic certificate signer and verifier for Open BESS Edge compliance.
Uses ECDSA P-256 for signing and validates hashes against an immutable ledger (blockchain)
according to the ASTM D8558-24 standard.
"""

import hashlib
import json
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

# Simulación global de ledger de transacciones inmutable (Blockchain)
# En un despliegue real, esto se almacena en un Smart Contract público o consorciado.
BLOCKCHAIN_CERTIFICATE_LEDGER = {}


class BESSComplianceCertifier:
    """
    Entidad Certificadora para Open BESS Edge.
    En producción, interactúa con un Hardware Security Module (HSM) vía PKCS#11
    para firmar digitalmente usando llaves que nunca salen del hardware.
    """

    def __init__(self, private_key_pem: bytes | None = None):
        if private_key_pem:
            from cryptography.hazmat.primitives import serialization

            self._private_key = serialization.load_pem_private_key(private_key_pem, password=None)
        else:
            self._private_key = ec.generate_private_key(ec.SECP256R1())
        self.public_key = self._private_key.public_key()

    def get_public_key_pem(self) -> bytes:
        """Exporta la llave pública en formato PEM."""
        from cryptography.hazmat.primitives import serialization

        return self.public_key.public_key_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def issue_certificate(self, site_id: str, company: str, compliance_score: float) -> dict:
        """
        Genera, firma criptográficamente y registra un certificado de cumplimiento Open BESS Edge.
        """
        cert_data = {
            "site_id": site_id,
            "company": company,
            "compliance_score": compliance_score,
            "standard_version": "v1.0",
            "issue_date": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        # Serialización consistente (ordenando llaves) para evitar desajustes de firma
        serialized_data = json.dumps(cert_data, sort_keys=True).encode("utf-8")

        # Firma digital usando ECDSA P-256 + SHA256 (simula comando HSM)
        signature = self._private_key.sign(serialized_data, ec.ECDSA(hashes.SHA256()))

        # Generar hash de integridad (ASTM D8558-24)
        cert_hash = hashlib.sha256(serialized_data + signature).hexdigest()

        # Registrar hash en la blockchain simulada
        BLOCKCHAIN_CERTIFICATE_LEDGER[cert_hash] = {
            "registered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "status": "ACTIVE",
            "site_id": site_id,
        }

        return {"data": cert_data, "signature_hex": signature.hex(), "cert_hash": cert_hash}


class BESSComplianceVerifier:
    """
    Verificador de Certificados Open BESS Edge.
    Valida la firma criptográfica usando la llave pública de la entidad emisora,
    recalcula el hash de integridad y valida su estatus en el ledger Blockchain.
    """

    def __init__(
        self,
        public_key_pem: bytes | None = None,
        public_key_obj: ec.EllipticCurvePublicKey | None = None,
    ):
        if public_key_obj:
            self.public_key = public_key_obj
        elif public_key_pem:
            from cryptography.hazmat.primitives import serialization

            self.public_key = serialization.load_pem_public_key(public_key_pem)
        else:
            raise ValueError(
                "Debe proveer la llave pública en formato PEM o como objeto EllipticCurvePublicKey."
            )

    def verify(self, certificate: dict) -> dict:
        """
        Verifica la autenticidad e integridad de un certificado.

        Retorna un diccionario detallando el estatus de la validación:
        {
           "valid": bool,
           "reason": str,
           "details": dict
        }
        """
        try:
            # 1. Recuperar campos
            data_bytes = json.dumps(certificate["data"], sort_keys=True).encode("utf-8")
            signature_bytes = bytes.fromhex(certificate["signature_hex"])
            cert_hash = certificate["cert_hash"]

            # 2. Verificar firma ECDSA
            self.public_key.verify(signature_bytes, data_bytes, ec.ECDSA(hashes.SHA256()))

            # 3. Recalcular y validar hash de integridad (ASTM D8558-24)
            calculated_hash = hashlib.sha256(data_bytes + signature_bytes).hexdigest()
            if calculated_hash != cert_hash:
                return {
                    "valid": False,
                    "reason": "El hash del certificado no coincide con el contenido calculado localmente.",
                    "details": {},
                }

            # 4. Validar contra el Ledger inmutable
            if cert_hash not in BLOCKCHAIN_CERTIFICATE_LEDGER:
                return {
                    "valid": False,
                    "reason": "El certificado no se encuentra registrado en el Ledger Blockchain de confianza.",
                    "details": {},
                }

            ledger_entry = BLOCKCHAIN_CERTIFICATE_LEDGER[cert_hash]
            if ledger_entry["status"] != "ACTIVE":
                return {
                    "valid": False,
                    "reason": f"El certificado ha sido revocado o suspendido. Estado actual: {ledger_entry['status']}",
                    "details": ledger_entry,
                }

            return {
                "valid": True,
                "reason": "Certificado auténtico, íntegro y verificado activamente en Blockchain.",
                "details": {
                    "site_id": certificate["data"]["site_id"],
                    "blockchain_registration": ledger_entry,
                },
            }

        except InvalidSignature:
            return {
                "valid": False,
                "reason": "La firma digital no coincide con la llave pública. El certificado ha sido alterado.",
                "details": {},
            }
        except KeyError as exc:
            return {
                "valid": False,
                "reason": f"Estructura de certificado inválida, falta la clave: {exc}",
                "details": {},
            }
        except Exception as exc:
            return {
                "valid": False,
                "reason": f"Fallo interno del motor de verificación: {exc}",
                "details": {},
            }


# Instancia global por defecto para firma y verificación del nodo
GLOBAL_CERTIFIER = BESSComplianceCertifier()
