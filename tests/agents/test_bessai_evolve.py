# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/agents/test_bessai_evolve.py
====================================
Integration tests for BEP-0303 BESSAIEvolve orchestrator.

Uses a micro-configuration (population=4, generations=2, eval_days=2)
to keep test runtime under 30 seconds. Tests cover:
- Full evolution loop runs without error
- Population file written to disk
- History file appended correctly
- Promotion signal written when candidate qualifies
- run_evolution() returns correct exit code
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.agents.bessai_evolve import BESSAIEvolve, run_evolution
from src.agents.population_manager import PROMOTION_THRESHOLD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_evolve(tmp_path: Path, **kwargs: object) -> BESSAIEvolve:
    """Create a fast BESSAIEvolve instance for testing."""
    defaults = dict(
        population_size=4,
        n_generations=2,
        n_eval_days=2,
        n_winners=2,
        tournament_k=2,
        n_offspring=3,
        sigma=0.15,
        seed=0,
        population_dir=tmp_path,
    )
    defaults.update(kwargs)  # type: ignore[arg-type]
    return BESSAIEvolve(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# BESSAIEvolve.run()
# ---------------------------------------------------------------------------


class TestBESSAIEvolveRun:
    def test_run_returns_summary(self, tmp_path: Path) -> None:
        engine = make_evolve(tmp_path)
        summary = engine.run()
        assert "n_generations" in summary
        assert "baseline_fitness" in summary
        assert "promoted" in summary
        assert summary["n_generations"] == 2

    def test_baseline_fitness_positive(self, tmp_path: Path) -> None:
        engine = make_evolve(tmp_path)
        summary = engine.run()
        assert summary["baseline_fitness"] > 0.0

    def test_population_file_written(self, tmp_path: Path) -> None:
        engine = make_evolve(tmp_path)
        engine.run()
        pop_file = tmp_path / "population.json"
        assert pop_file.exists(), "population.json must be written after run"

    def test_population_file_valid_json(self, tmp_path: Path) -> None:
        engine = make_evolve(tmp_path)
        engine.run()
        with (tmp_path / "population.json").open() as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_history_file_appended(self, tmp_path: Path) -> None:
        engine = make_evolve(tmp_path)
        engine.run()
        history_file = tmp_path / "history.jsonl"
        assert history_file.exists(), "history.jsonl must be written after run"
        lines = history_file.read_text().strip().splitlines()
        assert len(lines) >= 1

    def test_history_records_valid(self, tmp_path: Path) -> None:
        engine = make_evolve(tmp_path)
        engine.run()
        with (tmp_path / "history.jsonl").open() as f:
            records = [json.loads(line) for line in f if line.strip()]
        for record in records:
            assert "generation" in record
            assert "best_fitness" in record
            assert "mean_fitness" in record
            assert record["best_fitness"] >= record["mean_fitness"] - 1e-6

    def test_best_candidate_written_after_best_ever(self, tmp_path: Path) -> None:
        # The first run will always establish a new best (no prior best)
        engine = make_evolve(tmp_path)
        engine.run()
        # best_candidate.json should exist (first run is always a new record)
        best_file = tmp_path / "best_candidate.json"
        assert best_file.exists(), "best_candidate.json should be written on first run"

    def test_best_candidate_valid(self, tmp_path: Path) -> None:
        engine = make_evolve(tmp_path)
        engine.run()
        with (tmp_path / "best_candidate.json").open() as f:
            data = json.load(f)
        assert "id" in data
        assert "fitness" in data
        assert "params" in data

    def test_idempotent_second_run(self, tmp_path: Path) -> None:
        """Second run should not crash and should load existing population."""
        engine = make_evolve(tmp_path)
        s1 = engine.run()
        s2 = engine.run()
        # Both runs should complete successfully
        assert s1["n_generations"] == s2["n_generations"] == 2


# ---------------------------------------------------------------------------
# run_evolution() CLI wrapper
# ---------------------------------------------------------------------------


class TestRunEvolution:
    def test_returns_zero_or_two(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exit code must be 0 (no promotion) or 2 (promoted)."""
        monkeypatch.chdir(tmp_path)
        code = run_evolution(generations=1, population=3, eval_days=1)
        assert code in (0, 2), f"Unexpected exit code: {code}"


# ---------------------------------------------------------------------------
# PopulationManager.should_promote (integration)
# ---------------------------------------------------------------------------


class TestPromotionThreshold:
    def test_promotion_threshold_constant(self) -> None:
        """Threshold must remain ≥ 1.0 (never demote below baseline)."""
        assert PROMOTION_THRESHOLD >= 1.0

    def test_promotion_requires_safety(self, tmp_path: Path) -> None:
        """Candidate with safety violations must NOT be promoted."""
        from src.agents.candidate_generator import PolicyCandidate
        from src.agents.population_manager import PopulationManager

        mgr = PopulationManager(
            population_path=tmp_path / "pop.json",
            history_path=tmp_path / "hist.jsonl",
            best_path=tmp_path / "best.json",
        )
        # Build a candidate with high fitness but safety violations
        cand = PolicyCandidate(
            id="test-cand",
            generation=1,
            params={},
            fitness=1.50,
            metadata={"total_safety_violations": 3},
        )
        assert not mgr.should_promote(cand), (
            "Candidate with safety violations should never be promoted"
        )
