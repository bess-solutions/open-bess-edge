import sys
from pathlib import Path
import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

def create_onnx_model(output_path: Path, input_dim: int, output_dim: int, name: str, W_init: np.ndarray | None = None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)

    # Simple model structure
    if W_init is not None:
        W1 = W_init.astype(np.float32)
    else:
        W1 = rng.normal(0, 0.3, (output_dim, input_dim)).astype(np.float32)
    b1 = np.zeros(output_dim, dtype=np.float32)

    nodes = [
        helper.make_node("Gemm", ["obs", "W1", "b1"], ["action"],
                         transB=1, alpha=1.0, beta=1.0),
    ]

    graph = helper.make_graph(
        nodes,
        name,
        inputs=[helper.make_tensor_value_info("obs", TensorProto.FLOAT, [None, input_dim])],
        outputs=[helper.make_tensor_value_info("action", TensorProto.FLOAT, [None, output_dim])],
        initializer=[
            numpy_helper.from_array(W1, name="W1"),
            numpy_helper.from_array(b1, name="b1"),
        ],
    )

    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    onnx.checker.check_model(model)
    onnx.save(model, str(output_path))
    print(f"Generated {output_path} (input: {input_dim}, output: {output_dim})")

def main():
    repo_root = Path(__file__).resolve().parent.parent
    bess_tech_root = repo_root.parent

    # 1. Generate dispatch_policy.onnx (input 4, output 1)
    # Output must be soc_pct * 0.8, where input = [soc_pct, power_kw, temp_c, hour_of_day]
    W_dispatch = np.array([[0.8, 0.0, 0.0, 0.0]], dtype=np.float32)
    create_onnx_model(
        repo_root / "models" / "dispatch_policy.onnx",
        input_dim=4,
        output_dim=1,
        name="dispatch_policy",
        W_init=W_dispatch
    )


    # 2. Generate rl_arbitrage.onnx (input 4, output 3) in BESS Tech root / models
    create_onnx_model(
        bess_tech_root / "models" / "rl_arbitrage.onnx",
        input_dim=4,
        output_dim=3,
        name="rl_arbitrage"
    )

    # 3. Generate the 8 DRL models (input 8, output 1) with .onnx.data extension
    nodes = [
        "Cardones", "Charrua", "Crucero", "Hualpen",
        "Lo_Aguirre", "Maitencillo", "Polpaico", "Quillota"
    ]
    for node in nodes:
        create_onnx_model(
            repo_root / "models" / f"{node}_drl_cen_v1.onnx.data",
            input_dim=8,
            output_dim=1,
            name=f"{node}_drl"
        )

if __name__ == "__main__":
    main()
