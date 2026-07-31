# 🔍 BESSAI Compliance & Traceability Matrix

This document provides direct, verifiable traceability mapping BESSAI Edge Gateway regulatory and cybersecurity controls to their exact source code implementations and automated test coverage.

---

## 🛡️ Control Traceability Matrix

| Standard / Control | Description | Code Component | Automated Verification Test |
|---|---|---|---|
| **NTSyCS Cap. 4.2** | Power ramp rate limit $\le 10\%/\text{min}$ | [`src/core/safety.py`](file:///c:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/open-bess-edge/src/core/safety.py) | [`tests/test_safety.py`](file:///c:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/open-bess-edge/tests/test_safety.py) |
| **NTSyCS Cap. 6.1** | Secure mTLS telemetry data channel | [`src/interfaces/ot_tls_config.py`](file:///c:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/open-bess-edge/src/interfaces/ot_tls_config.py) | [`tests/test_ot_tls.py`](file:///c:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/open-bess-edge/tests/test_ot_tls.py) |
| **IEC 62443 SL-1** | Basic authentication & input boundaries | [`src/interfaces/totp_auth.py`](file:///c:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/open-bess-edge/src/interfaces/totp_auth.py) | [`tests/test_totp_auth.py`](file:///c:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/open-bess-edge/tests/test_totp_auth.py) |
| **IEC 62443 SL-2** | Request rate limiting & perimeter defense | [`src/interfaces/server.py`](file:///c:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/open-bess-edge/src/interfaces/server.py) | [`tests/test_server.py`](file:///c:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/open-bess-edge/tests/test_server.py) |
| **BESSAI-SIM-001** | Simulator limits & physical boundary logic | [`src/drivers/simulator_driver.py`](file:///c:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/open-bess-edge/src/drivers/simulator_driver.py) | [`tests/interop/test_driver_contract.py`](file:///c:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/open-bess-edge/tests/interop/test_driver_contract.py) |
| **Self-Healing Loop** | Autonomous driver reconnection and heal | [`src/core/watchdog_manager.py`](file:///c:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/open-bess-edge/src/core/watchdog_manager.py) | [`tests/test_watchdog_manager.py`](file:///c:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/open-bess-edge/tests/test_watchdog_manager.py) |

---

## 🛠️ Verification Execution

To run the automated compliance verifications locally, invoke:
```bash
.venv/Scripts/pytest
```
