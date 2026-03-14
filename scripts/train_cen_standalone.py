"""
scripts/train_cen_standalone.py
================================
BEP-0200 Phase 3 — PPO Trainer sin Ray RLlib.

Entrena un agente PPO sobre BESSArbitrageEnvCEN usando datos reales CEN/SEN.
Usa PyTorch puro (sin Ray) para compatibilidad con Python 3.12+.
Exporta ONNX compatible con ONNXDispatcher edge.

Uso:
    python scripts/train_cen_standalone.py \\
        --iterations 200 --node Maitencillo \\
        --out models/drl_arbitrage_cen_v1.onnx

Salida:
    models/drl_arbitrage_cen_v1.onnx   — modelo deployable edge
    reports/bep0200_phase3_results.json — métricas de entrenamiento

Dependencias:
    pip install torch gymnasium onnx numpy
    (sin Ray — funciona en Python 3.14+)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(_REPO_ROOT))  # add src to path


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="BEP-0200 Phase 3: Train BESS DRL policy (PyTorch PPO, no Ray).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--iterations", type=int, default=200,
                   help="PPO training iterations (episodes)")
    p.add_argument("--node", type=str, default="Maitencillo",
                   help="CEN node for training")
    p.add_argument("--out", type=str, default="models/drl_arbitrage_cen_v1.onnx",
                   help="Output ONNX model path")
    p.add_argument("--cmg-data", type=str,
                   default=str(_REPO_ROOT.parent / "bessai-web" / "data" / "cmg_data.json"),
                   help="Path to cmg_data.json")
    p.add_argument("--capacity-kwh", type=float, default=200.0)
    p.add_argument("--max-power-kw", type=float, default=100.0)
    p.add_argument("--lr", type=float, default=3e-4, help="Learning rate")
    p.add_argument("--gamma", type=float, default=0.99, help="Discount factor")
    p.add_argument("--hidden", type=int, default=64, help="Hidden layer size")
    p.add_argument("--batch-size", type=int, default=256, help="Minibatch size")
    p.add_argument("--steps-per-iter", type=int, default=512,
                   help="Steps to collect per iteration")
    p.add_argument("--reports-dir", type=str, default="reports")
    p.add_argument("--all-nodes", action="store_true",
                   help="Train one model per CEN node and save each to models/")
    return p.parse_args()


# ---------------------------------------------------------------------------
# PPO Actor-Critic Network
# ---------------------------------------------------------------------------

def build_policy_net(obs_dim: int = 8, act_dim: int = 1, hidden: int = 64):
    """Simple MLP policy: obs → action mean (tanh bounded)."""
    import torch
    import torch.nn as nn

    class PolicyNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.shared = nn.Sequential(
                nn.Linear(obs_dim, hidden),
                nn.Tanh(),
                nn.Linear(hidden, hidden),
                nn.Tanh(),
            )
            self.actor_mean = nn.Linear(hidden, act_dim)
            self.actor_log_std = nn.Parameter(torch.zeros(act_dim))
            self.critic = nn.Linear(hidden, 1)

        def forward(self, obs):
            h = self.shared(obs)
            mean = torch.tanh(self.actor_mean(h))
            value = self.critic(h)
            return mean, value

        def get_action(self, obs):
            import torch
            mean, value = self(obs)
            std = self.actor_log_std.exp()
            dist = torch.distributions.Normal(mean, std)
            action = dist.sample()
            action = torch.clamp(action, -1.0, 1.0)
            log_prob = dist.log_prob(action).sum(-1)
            return action, log_prob, value.squeeze(-1)

        def evaluate(self, obs, action):
            import torch
            mean, value = self(obs)
            std = self.actor_log_std.exp()
            dist = torch.distributions.Normal(mean, std)
            log_prob = dist.log_prob(action).sum(-1)
            entropy = dist.entropy().sum(-1)
            return log_prob, value.squeeze(-1), entropy

    return PolicyNet()


# ---------------------------------------------------------------------------
# PPO Training Loop
# ---------------------------------------------------------------------------

def collect_rollout(env, policy, steps: int, device):
    """Collect `steps` environment steps using the current policy."""
    import torch

    obs_buf, act_buf, logp_buf, val_buf, rew_buf, done_buf = [], [], [], [], [], []

    obs, _ = env.reset()
    for _ in range(steps):
        obs_t = torch.FloatTensor(obs).unsqueeze(0).to(device)
        with torch.no_grad():
            action, log_prob, value = policy.get_action(obs_t)
        action_np = action.squeeze(0).cpu().numpy()
        next_obs, reward, terminated, truncated, _ = env.step(action_np)
        done = terminated or truncated

        obs_buf.append(obs)
        act_buf.append(action_np)
        logp_buf.append(log_prob.item())
        val_buf.append(value.item())
        rew_buf.append(float(reward))
        done_buf.append(float(done))

        obs = next_obs if not done else env.reset()[0]

    return (
        np.array(obs_buf, dtype=np.float32),
        np.array(act_buf, dtype=np.float32),
        np.array(logp_buf, dtype=np.float32),
        np.array(val_buf, dtype=np.float32),
        np.array(rew_buf, dtype=np.float32),
        np.array(done_buf, dtype=np.float32),
    )


def compute_returns(rewards: np.ndarray, dones: np.ndarray, gamma: float) -> np.ndarray:
    """Compute discounted returns (GAE simplified)."""
    T = len(rewards)
    returns = np.zeros(T, dtype=np.float32)
    running = 0.0
    for t in reversed(range(T)):
        running = rewards[t] + gamma * running * (1.0 - dones[t])
        returns[t] = running
    return returns


def ppo_update(policy, optimizer, obs, actions, old_logp, returns, values,
               batch_size: int = 256, clip_eps: float = 0.2, entropy_coef: float = 0.01,
               device=None):
    """Run one epoch of PPO updates."""
    import torch

    advantages = returns - values
    adv_mean = advantages.mean()
    adv_std = advantages.std() + 1e-8
    advantages = (advantages - adv_mean) / adv_std

    obs_t = torch.FloatTensor(obs).to(device)
    act_t = torch.FloatTensor(actions).to(device)
    old_logp_t = torch.FloatTensor(old_logp).to(device)
    ret_t = torch.FloatTensor(returns).to(device)
    adv_t = torch.FloatTensor(advantages).to(device)

    T = len(obs)
    total_loss = 0.0
    n_updates = 0
    for _ in range(4):  # 4 epochs per iteration
        idx = np.random.permutation(T)
        for start in range(0, T, batch_size):
            mb = idx[start:start + batch_size]
            log_prob, value, entropy = policy.evaluate(obs_t[mb], act_t[mb])
            ratio = (log_prob - old_logp_t[mb]).exp()
            clipped = torch.clamp(ratio, 1 - clip_eps, 1 + clip_eps)
            actor_loss = -torch.min(ratio * adv_t[mb], clipped * adv_t[mb]).mean()
            critic_loss = (ret_t[mb] - value).pow(2).mean()
            loss = actor_loss + 0.5 * critic_loss - entropy_coef * entropy.mean()

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy.parameters(), 0.5)
            optimizer.step()
            total_loss += loss.item()
            n_updates += 1

    return total_loss / max(n_updates, 1)


# ---------------------------------------------------------------------------
# ONNX Export
# ---------------------------------------------------------------------------

def export_onnx(policy, output_path: str, obs_dim: int = 12) -> None:
    """Export the policy actor to ONNX (obs input → action output)."""
    import onnx
    import torch

    policy.eval()

    class ActorOnly(torch.nn.Module):
        def __init__(self, net):
            super().__init__()
            self.net = net

        def forward(self, obs):
            mean, _ = self.net(obs)
            return mean  # deterministic action = mean

    actor = ActorOnly(policy)
    dummy = torch.zeros(1, obs_dim, dtype=torch.float32)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        actor,
        dummy,
        str(out),
        opset_version=17,
        input_names=["obs"],
        output_names=["action"],
        dynamic_axes={"obs": {0: "batch"}, "action": {0: "batch"}},
    )
    onnx.checker.check_model(str(out))
    print(f"[PPO] ONNX exported: {out} (obs_dim={obs_dim})")



# ---------------------------------------------------------------------------
# Train one node
# ---------------------------------------------------------------------------

def train_node(
    node: str,
    args: argparse.Namespace,
    output_path: str,
) -> dict:
    """Train PPO on a single CEN node. Returns training metrics."""
    import torch
    from src.agents.bess_rl_env_cen import BESSArbitrageEnvCEN

    device = torch.device("cpu")
    print(f"\n[PPO] ═══ Node: {node} ═══")

    env = BESSArbitrageEnvCEN(
        cmg_data_path=args.cmg_data,
        node=node,
        capacity_kwh=args.capacity_kwh,
        max_power_kw=args.max_power_kw,
        use_weather=True,  # 12-dim obs when cmg_weather_features.json is available
    )

    obs_dim = env.observation_space.shape[0]  # 12 with weather, 8 without
    print(f"  obs_dim={obs_dim} ({'weather-enriched' if obs_dim == 12 else 'base'})")
    policy = build_policy_net(obs_dim=obs_dim, act_dim=1, hidden=args.hidden).to(device)

    optimizer = torch.optim.Adam(policy.parameters(), lr=args.lr)

    t0 = time.monotonic()
    rewards_per_iter = []
    best_reward = float("-inf")

    for i in range(1, args.iterations + 1):
        obs, actions, logp, values, rewards, dones = collect_rollout(
            env, policy, args.steps_per_iter, device
        )
        returns = compute_returns(rewards, dones, args.gamma)
        loss = ppo_update(
            policy, optimizer,
            obs, actions, logp, returns, values,
            batch_size=args.batch_size,
            device=device,
        )

        ep_reward = float(rewards.sum())
        rewards_per_iter.append(ep_reward)

        if ep_reward > best_reward:
            best_reward = ep_reward

        if i % 20 == 0 or i == 1:
            elapsed = time.monotonic() - t0
            print(
                f"  [Iter {i:04d}/{args.iterations}] "
                f"reward={ep_reward:.2f} USD | "
                f"loss={loss:.4f} | "
                f"elapsed={elapsed:.0f}s"
            )

    elapsed_total = time.monotonic() - t0
    print(
        f"[PPO] Done: {node} | "
        f"best_reward={best_reward:.2f} USD | "
        f"total={elapsed_total:.0f}s"
    )

    export_onnx(policy, output_path, obs_dim=obs_dim)

    # Quick latency check
    import torch
    import onnxruntime as ort
    sess = ort.InferenceSession(output_path)
    dummy = np.random.rand(1, obs_dim).astype(np.float32)
    latencies = []
    for _ in range(50):
        t0l = time.perf_counter()
        sess.run(None, {sess.get_inputs()[0].name: dummy})
        latencies.append((time.perf_counter() - t0l) * 1000)
    p95 = float(np.percentile(latencies, 95))
    print(f"[PPO] Latency p95={p95:.2f}ms {'✅' if p95 < 49 else '⚠️'}")

    return {
        "node": node,
        "iterations": args.iterations,
        "best_reward_usd": best_reward,
        "elapsed_s": round(elapsed_total, 1),
        "latency_p95_ms": round(p95, 2),
        "latency_ok": p95 < 49.0,
        "rewards_per_iter": rewards_per_iter[-20:],  # last 20 for compactness
        "output_model": output_path,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    try:
        import torch  # noqa: F401
    except ImportError:
        print("[ERROR] Install: pip install torch --index-url https://download.pytorch.org/whl/cpu")
        sys.exit(1)

    from src.agents.bess_rl_env_cen import CEN_NODES

    nodes_to_train = CEN_NODES if args.all_nodes else [args.node]
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    for node in nodes_to_train:
        if args.all_nodes:
            out_path = f"models/{node}_drl_cen_v1.onnx"
        else:
            out_path = args.out

        result = train_node(node, args, out_path)
        all_results.append(result)

    report = {
        "phase": "BEP-0200-Phase3",
        "mode": "training_standalone_ppo",
        "trainer": "PyTorch-PPO (no Ray)",
        "python_version": sys.version.split()[0],
        "nodes": all_results,
        "status": "COMPLETE",
    }

    report_path = reports_dir / "bep0200_phase3_results.json"
    with report_path.open("w") as fh:
        json.dump(report, fh, indent=2)

    print(f"\n[PPO] ✅ All training done. Report: {report_path}")
    print(f"[PPO] Models: {', '.join(r['output_model'] for r in all_results)}")


if __name__ == "__main__":
    main()
