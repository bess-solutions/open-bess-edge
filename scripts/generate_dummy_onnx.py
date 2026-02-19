"""
scripts/generate_dummy_onnx.py
================================
Generates a minimal ONNX model for local testing of the ONNXDispatcher.

Model: Linear dispatch policy
  Input:  [soc_pct, power_kw, temp_c, hour_of_day]  (shape: 1x4, float32)
  Output: [dispatch_target_kw]                        (shape: 1x1, float32)
  Formula: target_kw = soc_pct * 0.8

This is a placeholder model. In production, the ONNX model is produced by
training a Ray RLlib policy and exporting it via onnxmltools or torch.onnx.

Usage:
    python scripts/generate_dummy_onnx.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

try:
    import onnx
    from onnx import TensorProto, helper
    _ONNX_AVAILABLE = True
except ImportError:
    _ONNX_AVAILABLE = False

try:
    import onnxruntime as ort
    _ORT_AVAILABLE = True
except ImportError:
    _ORT_AVAILABLE = False


def create_dummy_onnx_model() -> "onnx.ModelProto":
    """Create a minimal linear dispatch ONNX model.

    Graph: input (1x4) → MatMul (4x1 weights) → output (1x1)
    Weights: [0.8, 0.0, 0.0, 0.0] → target_kw ≈ soc_pct * 0.8
    """
    # Weight matrix [4, 1]: only soc_pct (index 0) has weight 0.8
    weights = np.array([[0.8], [0.0], [0.0], [0.0]], dtype=np.float32)
    weight_tensor = helper.make_tensor(
        name="W",
        data_type=TensorProto.FLOAT,
        dims=[4, 1],
        vals=weights.flatten().tolist(),
    )

    # Graph definition
    input_ = helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 4])
    output = helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 1])

    matmul_node = helper.make_node(
        op_type="MatMul",
        inputs=["input", "W"],
        outputs=["output"],
    )

    graph = helper.make_graph(
        nodes=[matmul_node],
        name="DummyDispatchPolicy",
        inputs=[input_],
        outputs=[output],
        initializer=[weight_tensor],
    )

    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.doc_string = (
        "Dummy dispatch policy for BESSAI testing. "
        "target_kw = soc_pct * 0.8. "
        "Replace with a trained Ray RLlib export in production."
    )
    onnx.checker.check_model(model)
    return model


def main() -> None:
    if not _ONNX_AVAILABLE:
        print("ERROR: 'onnx' package not installed. Run: pip install onnx")
        raise SystemExit(1)

    model = create_dummy_onnx_model()
    output_path = Path("models/dispatch_policy.onnx")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, str(output_path))
    print(f"[OK] Dummy ONNX model saved: {output_path}")

    # Quick smoke test with onnxruntime
    if _ORT_AVAILABLE:
        sess = ort.InferenceSession(str(output_path))
        test_input = np.array([[90.0, 50.0, 25.0, 14.0]], dtype=np.float32)
        outputs = sess.run(None, {"input": test_input})
        target_kw = float(outputs[0][0][0])
        print(f"  Smoke test -> input SOC=90% -> dispatch_target_kw={target_kw:.2f} kW")
        assert abs(target_kw - 72.0) < 1.0, f"Expected ~72.0, got {target_kw}"
        print("  [OK] Smoke test passed.")
    else:
        print("  [WARN] onnxruntime not installed - skipping smoke test.")


if __name__ == "__main__":
    main()
