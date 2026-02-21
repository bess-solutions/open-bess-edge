# ADR-0004: Use ONNX Runtime for Offline Edge Inference

## Status
✅ Accepted — 2026-02-19

## Context

The BESSAI Edge Gateway requires on-device (edge) inference of a dispatch policy model that decides whether to charge, discharge, or hold the battery based on current state and CMg price forecasts.

Requirements:
- **Fully offline**: the edge device may not have internet connectivity
- **Hardware agnostic**: must run on x86-64 and ARM64 (Raspberry Pi, industrial PCs)
- **No GPU required**: must run on CPU-only hardware
- **Framework agnostic input**: the training pipeline uses scikit-learn or Ray RLlib (PyTorch backend); the deployment artifact must not lock the runtime to a specific framework
- **Fast inference**: dispatch decision must complete in < 100ms per cycle
- **Int8 quantization support**: for 3× faster inference on CPU-constrained edge devices

Alternatives considered:
- **PyTorch with `torch.jit.script`**: framework-specific, adds ~1GB to Docker image
- **TensorFlow Lite**: good for ARM but poor x86 support; not compatible with scikit-learn exports
- **Direct scikit-learn pickle**: framework-specific, no hardware optimization, pickle security risks
- **Custom C/C++ inference**: maximum performance but prohibitive maintenance cost for a Python project

## Decision

Use **ONNX Runtime** (`onnxruntime`) as the inference engine for all ML models deployed to the edge.

Key implementation details in `src/interfaces/onnx_dispatcher.py`:
- Models stored as `.onnx` files in `models/` directory
- Auto-discovery of int8-quantized models (`dispatch_policy_int8.onnx`) if available
- CPU execution provider only (no CUDA dependency)
- Graceful fallback: if model file is missing or inference fails, returns `None` → SafetyGuard decides
- Inference time tracked in Prometheus: `bess_onnx_inference_ms`

**Export pipeline:**
```
scikit-learn/Ray RLlib → skl2onnx / torch.onnx.export → .onnx → onnxruntime-quantization (int8)
```

## Consequences

### Positive
- **Framework agnostic**: the deployment artifact (`.onnx`) is independent of training framework
- **Multi-architecture**: ONNX Runtime publishes official wheels for `linux/amd64` and `linux/arm64`
- **Int8 quantization**: ~3× faster inference, ~4× smaller model on CPU (tested on Ridge + GBM models)
- **Offline capable**: zero network calls during inference
- **Auditable**: `.onnx` files can be inspected with Netron or `onnx.checker`

### Negative
- **Export step required**: training pipeline must include ONNX export, not just model.fit()
- **Dynamic shapes**: some models require careful input shape specification at export time
- **Limited operator support**: very custom PyTorch ops may not be exportable (not an issue for our current Ridge/GBM/PPO models)

### Neutral
- The placeholder `dispatch_policy.onnx` (dummy model: `target_kw = soc × 0.8`) is included for testing without real training data
- When a real model is trained via `bessai-cen-data/scripts/train_price_model.py`, it replaces this artifact
