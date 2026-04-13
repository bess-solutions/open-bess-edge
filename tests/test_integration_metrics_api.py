from src.interfaces.fleet_coordinator import FleetCoordinator, FleetSiteState
from src.interfaces.lca_engine import LCAEngine
from src.interfaces.metrics import generate_metrics


def test_metrics_registry_contains_new_commercial_metrics():
    """Verify that the new v2.17.1 metrics are exported by Prometheus."""
    registry_output = generate_metrics().decode("utf-8")
    assert "bess_carbon_viability_score" in registry_output
    assert "bess_injection_kw_capacity" in registry_output
    assert "bess_fleet_latency_ms" in registry_output

def test_lca_engine_exports_carbon_viability_score():
    """Verify LCAEngine updates the CARBON_VIABILITY_SCORE gauge."""
    engine = LCAEngine(site_id="test_site_cl")
    # By default, CL has a high EF, score should be >= 2
    score = engine.carbon_viability_score
    metrics_out = generate_metrics().decode("utf-8")
    expected_metric_line = f'bess_carbon_viability_score{{region="CL",site_id="test_site_cl"}} {float(score)}'
    assert expected_metric_line in metrics_out

def test_fleet_coordinator_exports_injection_kw():
    """Verify FleetCoordinator updates the INJECTION_KW_CAPACITY gauge on register and update."""
    fleet = FleetCoordinator()
    site = FleetSiteState(site_id="test_fleet_site", node="TestNode", soc_pct=50.0, max_power_kw=500.0)
    fleet.register_site(site)

    # Injection capacity -> (50 - 10) / 100 * 500 * 2 = 400.0 kW
    metrics_out = generate_metrics().decode("utf-8")
    expected_metric_line = 'bess_injection_kw_capacity{fleet_site="test_fleet_site",site_id="edge"} 400.0'
    assert expected_metric_line in metrics_out

def test_fleet_coordinator_exports_latency():
    """Verify FleetCoordinator records latency across operations."""
    fleet = FleetCoordinator()
    site = FleetSiteState(site_id="test_fleet_site", node="TestNode", soc_pct=50.0, max_power_kw=500.0)
    fleet.register_site(site)

    fleet.fleet_summary()
    fleet.compute_setpoints(100.0, mode="discharge")

    metrics_out = generate_metrics().decode("utf-8")
    assert 'bess_fleet_latency_ms_count{operation="summary",site_id="edge"}' in metrics_out
    assert 'bess_fleet_latency_ms_count{operation="compute_setpoints",site_id="edge"}' in metrics_out
