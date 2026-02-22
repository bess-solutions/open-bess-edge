# BESSAI Certified Program

**Version:** 1.0.0  
**Date:** 2026-02-22  
**Status:** Active

---

## What is BESSAI Certified?

**BESSAI Certified** is a badge that hardware manufacturers, driver developers, and system integrators can earn to certify that their device or implementation is fully compatible with the BESSAI Edge Gateway ecosystem.

Certification means:
- The device's driver passes the full [BESSAI Interoperability Test Suite](interop_test_suite.md)
- The driver conforms to [BESSAI-SPEC-001](../specs/BESSAI-SPEC-001.md) (BESSDriver Interface)
- The device profile JSON is included in the official `registry/` directory
- Users of BESSAI know they can deploy with your device with confidence

---

## Certification Levels

| Level | Requirements | Badge |
|---|---|---|
| **Compatible** | Passes Category A (contract tests) — no hardware testing required | ![Compatible](https://img.shields.io/badge/BESSAI-Compatible-blue) |
| **Certified** | Passes Categories A + B + C (full hardware validation) | ![Certified](https://img.shields.io/badge/BESSAI-Certified-green) |
| **Certified+** | Certified + Category D (SafetyGuard integration) + real-world deployment evidence | ![Certified+](https://img.shields.io/badge/BESSAI-Certified%2B-brightgreen) |

---

## Certified Devices

| Device | Manufacturer | Level | Driver | Certified Date |
|---|---|---|---|---|
| SUN2000-100KTL | Huawei | Certified+ | `src/drivers/modbus_driver.py` | 2026-02-22 (self) |
| SMA Sunny Tripower | SMA Solar | Compatible | `src/drivers/sma_driver.py` | 2026-02-22 (self) |
| MultiPlus-II | Victron Energy | Compatible | `src/drivers/victron_driver.py` | 2026-02-22 (self) |
| GEN24 Plus | Fronius | Compatible | `src/drivers/fronius_driver.py` | 2026-02-22 (self) |

*"(self)" = self-certification by BESS Solutions. Independent certification by manufacturer pending.*

---

## How to Get Certified

### Step 1: Implement the Driver

Implement the `DataProvider` protocol as defined in BESSAI-SPEC-001. Your driver should live in its own repository or package.

### Step 2: Run the Test Suite

```bash
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge
pip install -r requirements.txt -r requirements-dev.txt

# Run with your driver
pytest tests/interop/ \
  --driver-class="your_package.YourDriver" \
  --driver-args='{"host":"192.168.1.100","port":502}' \
  --junit-xml=certification_results.xml -v
```

### Step 3: Create a Device Profile

Create a device profile JSON following the schema in BESSAI-SPEC-001 §7. Save it as `registry/<manufacturer>_<model>.json`.

### Step 4: Open a Pull Request

Open a PR to the `open-bess-edge` repository with:
- Your device profile JSON in `registry/`
- The JUnit XML test results (`certification_results.xml`)
- A brief description of your device and deployment context

**PR title format:** `chore(registry): add [Manufacturer] [Model] — BESSAI [Level] certification`

### Step 5: Review

The BESSAI Maintainers will review your PR within 5 business days. They will verify:
- Test results are complete and all required tests pass
- Device profile JSON is valid and accurate
- Driver code (if included) follows BESSAI coding standards

Upon approval, your device will be listed in this document and you may use the BESSAI Certified badge in your product materials.

---

## Badge Usage

After certification, you may use the following badge in your README, documentation, and product materials:

```markdown
[![BESSAI Certified](https://img.shields.io/badge/BESSAI-Certified-green)](https://github.com/bess-solutions/open-bess-edge/blob/main/docs/interoperability/BESSAI-CERTIFIED.md)
```

---

## Certification Maintenance

- Certifications are valid for **1 year** from the date of issue, or until a new MAJOR version of BESSAI-SPEC-001 is released.
- Upon a new SPEC major version, certified devices must re-run the test suite within 6 months.
- BESS Solutions reserves the right to revoke certification if a device is found to be non-conformant in production deployments.

---

## Contact

For certification inquiries: ingenieria@bess-solutions.cl  
Subject line: `BESSAI Certification — [Manufacturer] [Model]`
