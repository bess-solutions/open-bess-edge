# BESSAI Federated Learning — Private Module

> **⚠️ This directory contains a stub for the public repository.**
>
> The Federated Learning client and server are **proprietary** and maintained in:
> `bess-solutions/bessai-core` (private, authorized personnel only).

## For BESSAI deployments

The FL infrastructure is distributed as part of the private `bessai-agents` package:

```bash
pip install bessai-agents --extra-index-url https://pypi.bess-solutions.cl
```

## Architecture (overview only)

```
BESS Edge Node (fl_client)  ──→  FL Server (fl_server)
    local model update              global aggregation
    gradient encryption             federated average
    privacy-preserving              model distribution
```

*Contact: ingenieria@bess-solutions.cl*
