#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA
"""
scripts/generate_dummy_onnx.py
==============================
Generates a minimal valid ONNX model for CI/CD benchmarks and tests.
Used by performance-regression.yml and model-drift.yml when no real
trained model is available.

The model approximates a DRL policy:
  input:  [batch, 3]  → [soc, cmg_normalized, time_of_day]
  output: [batch, 1]  → [-1.0, 1.0]  (charge/discharge action)

Usage:
    python scripts/generate_dummy_onnx.py [--output models/policy.onnx]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def generate_dummy_onnx(output_path: Path) -> bool:
    """Generate a minimal ONNX model with Linear → Tanh structure."""
    try:
        import numpy as np
        import onnx
        from onnx import TensorProto, helper, numpy_helper

        # Model: input (1,3) → Gemm (3→8) → Tanh → Gemm (8→1) → Tanh → output (1,1)
        rng = np.random.default_rng(42)

        W1 = rng.normal(0, 0.3, (8, 3)).astype(np.float32)
        b1 = np.zeros(8, dtype=np.float32)
        W2 = rng.normal(0, 0.3, (1, 8)).astype(np.float32)
        b2 = np.zeros(1, dtype=np.float32)

        nodes = [
            helper.make_node("Gemm", ["obs", "W1", "b1"], ["h1"],
                             transB=1, alpha=1.0, beta=1.0),
            helper.make_node("Tanh", ["h1"], ["h1_act"]),
            helper.make_node("Gemm", ["h1_act", "W2", "b2"], ["raw_action"],
                             transB=1, alpha=1.0, beta=1.0),
            helper.make_node("Tanh", ["raw_action"], ["action"]),
        ]

        graph = helper.make_graph(
            nodes,
            "bessai_policy",
            inputs=[helper.make_tensor_value_info("obs", TensorProto.FLOAT, [None, 3])],
            outputs=[helper.make_tensor_value_info("action", TensorProto.FLOAT, [None, 1])],
            initializer=[
                numpy_helper.from_array(W1, name="W1"),
                numpy_helper.from_array(b1, name="b1"),
                numpy_helper.from_array(W2, name="W2"),
                numpy_helper.from_array(b2, name="b2"),
            ],
        )

        model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
        model.doc_string = (
            "BESSAI dummy DRL policy — for CI benchmarks only. "
            "Replace with a real trained model in production."
        )
        onnx.checker.check_model(model)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        onnx.save(model, str(output_path))
        print(f"✅ Dummy ONNX model saved → {output_path}")
        print("   Input: obs [batch, 3] → Output: action [batch, 1]")
        return True

    except ImportError as e:
        print(f"⚠️  ONNX not available ({e}) — creating placeholder file")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Write a zero-byte placeholder so path checks don't fail
        output_path.write_bytes(b"")
        return False
    except Exception as e:
        print(f"❌ Failed to generate ONNX model: {e}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate dummy ONNX model for BESSAI CI")
    parser.add_argument(
        "--output", type=Path,
        default=Path("models/bessai_policy_dummy.onnx"),
        help="Output path for the ONNX model"
    )
    args = parser.parse_args()

    ok = generate_dummy_onnx(args.output)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
