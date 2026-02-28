# BESSAI AI Agents — Private Module

> **⚠️ This directory is a stub for the public repository.**
>
> The BESSAI AI Agent modules (DRL, MARL, MILP, CMA-ES, evolutionary algorithms)
> are **proprietary** and maintained in a **private repository**:
> `bess-solutions/bessai-core` (access: authorized personnel only).

## For BESSAI Gateway Users

The AI dispatch agents are distributed as a private package:

```bash
# Internal PyPI (requires authorization from BESS Solutions SpA)
pip install bessai-agents --extra-index-url https://pypi.bess-solutions.cl
```

## For Open-Source Gateway Deployments

The `open-bess-edge` gateway runs without AI agents in **Rule-Based Mode**:
- All NTSyCS compliance modules operate independently (`ComplianceStack`)
- Dispatch is determined by operator setpoints or simple SOC-based rules
- AI-enhanced dispatch (PPO/MARL arbitrage) requires the `bessai-agents` package

## Modules (private)

| Module | Capability |
|---|---|
| `drl_agent` | PPO/SAC dispatch optimization |
| `marl_env` | Multi-agent energy market simulation |
| `milp_optimizer` | Mixed-integer linear dispatch |
| `bessai_evolve_v2` | Evolutionary hyperparameter tuning |
| `degradation_model` | Battery SoH prediction |
| `arbitrage_policy` | Energy arbitrage policy |
| `bess_rl_env_cen` | CEN market RL environment |

---

*Contact: ingenieria@bess-solutions.cl to request access to `bessai-core`*
