# BESSAI Open Alliance — Hackathon 2026

**"Build the Open Grid: BESS Hardware Drivers & AI Dispatch"**

**Date:** May 15-17, 2026  
**Format:** 48-hour virtual + hybrid hub in Santiago, Chile  
**Registration:** [GitHub Discussions — Hackathon 2026](https://github.com/bess-solutions/open-bess-edge/discussions)  
**Status:** Open for Registration (Draft)

---

## About

The first **BESSAI Open Alliance Hackathon** invites engineers, data scientists, and energy sector professionals from around the world to contribute open-source components to the `open-bess-edge` ecosystem.

> **Goal:** Accelerate the expansion of supported hardware drivers from 4 to 10+, and launch the first external DRL dispatch agents using BEP-0200 (`BESSArbitrageEnv`).

---

## Challenge Tracks

### Track 1 — Hardware Driver Development 🔌

Build a new `DataProvider` driver for a BESS device not yet in the `registry/`.

**Target devices (suggested, not limited to):**
| Manufacturer | Model | Protocol |
|---|---|---|
| BYD | Battery-Box Premium HVS | Modbus TCP |
| CATL | EnerD | CAN / Modbus |
| Tesla | Powerpack 2 | Modbus TCP / Proprietary API |
| LG Energy Solution | RESU Prime | CAN / SunSpec |
| Pylontech | US5000 | RS485 |
| Alpha-ESS | Smile5 | Modbus TCP |

**Deliverable:** Pull Request to `open-bess-edge` with:
- `registry/<manufacturer>_<model>.json` (device profile)
- `src/drivers/<manufacturer>_driver.py` (or link to external package)
- Test results from `pytest tests/interop/`
- README section with wiring diagram or connection guide

**Winner criteria:**
- Completeness of BESSAI-SPEC-001 conformance
- Quality of documentation
- Reproducibility on a simulator

---

### Track 2 — DRL Dispatch Agent 🤖

Train and submit a DRL agent using `BESSArbitrageEnv` (BEP-0200).

**Challenge:** Achieve the highest 7-day simulated revenue (USD) trading against a synthetic Chilean CMg profile, beating the `ArbitragePolicy` baseline by ≥25%.

**Rules:**
- Agent must use `BESSArbitrageEnv` from `src/agents/bess_rl_env.py`
- Any RL framework allowed: Ray RLlib, Stable Baselines3, CleanRL, etc.
- Model must be exportable to ONNX and loadable by `ONNXArbitrageAgent`
- Training code must be open-source and reproducible

**Deliverable:** 
- ONNX model file + training script
- Benchmark report comparing to `ArbitragePolicy` baseline
- PR or GitHub Gist with complete code

**Winner criteria:**
- Average daily revenue (USD) over 7-day sim
- Benchmark uplift vs `ArbitragePolicy` (target: ≥+25%)
- Code quality and reproducibility

---

### Track 3 — Documentation & Tutorials 📚

Create educational content for the BESSAI community.

**Ideas:**
- Video tutorial: "Deploy BESSAI on Raspberry Pi 5 in 30 minutes"
- Blog post: "BESS Arbitrage 101 — From CMg curves to DRL agents"
- Translation of README.md to Spanish, Portuguese, German, or Chinese
- Quickstart guide for AWS IoT / Azure IoT Hub integration
- Jupyter notebook: "Analyzing BESS performance with BESSAI telemetry"

**Deliverable:** Published content (GitHub repo, blog, YouTube) with PR to `open-bess-edge` docs or tutorials

**Winner criteria:**
- Clarity and accuracy
- Originality and usefulness
- Quality of Spanish/Portuguese/German/Chinese translations

---

## Prizes

| Place | Track 1 (Driver) | Track 2 (DRL Agent) | Track 3 (Docs) |
|---|---|---|---|
| 🥇 1st | $300 USD + BESSAI Certified badge | $300 USD | $200 USD |
| 🥈 2nd | $150 USD + BESSAI Compatible badge | $150 USD | $100 USD |
| 🏅 Special | Best LATAM submission: $100 USD | | |
| All submissions | BESSAI Contributor badge (GitHub) | | |

> All Prize Winners are invited as founding **Associate Members** of the BESSAI Open Alliance.

---

## Registration & Timeline

| Date | Milestone |
|---|---|
| Apr 1, 2026 | Registration opens (GitHub Discussion) |
| May 1, 2026 | Team confirmation + track selection |
| May 15, 2026 | Hackathon begins (00:00 UTC) |
| May 17, 2026 | Submissions close (23:59 UTC) |
| May 22, 2026 | Winners announced |
| May 31, 2026 | Best PRs merged to `main` |

---

## Mentors & Judges

| Name | Organization | Track |
|---|---|---|
| BESSAI Engineering Team | BESS Solutions | All tracks |
| *[Open — seeking judge from Huawei/BYD]* | OEM Partner | Track 1 |
| *[Open — seeking judge from LF Energy]* | LF Energy | All tracks |
| *[Open — seeking academic judge]* | Universidad de Chile (TBC) | Track 2 |

---

## Resources

- [`docs/tutorials/connecting_real_hardware.md`](../tutorials/connecting_real_hardware.md) — Driver development guide
- [`src/agents/bess_rl_env.py`](../../src/agents/bess_rl_env.py) — Gymnasium environment (Track 2)
- [`src/agents/arbitrage_policy.py`](../../src/agents/arbitrage_policy.py) — Baseline policy (Track 2)
- [`docs/specs/BESSAI-SPEC-001.md`](../specs/BESSAI-SPEC-001.md) — Driver interface spec
- [Simulation Registry](../simulation_registry.md) — Available BESS simulators

---

## Hackathon Discord

Join the BESSAI Discord server for real-time support during the hackathon:  
**https://discord.gg/bessai** *(invite link to be created)*

---

*Organized by BESS Solutions under the BESSAI Open Alliance initiative.*  
*For sponsorship inquiries: ingenieria@bess-solutions.cl*
