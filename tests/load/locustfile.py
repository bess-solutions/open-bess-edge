import os
from locust import HttpUser, task, between

class BESSAITier1LoadTest(HttpUser):
    """
    Tier-1 Load Testing Scenario for the BESSAI Edge Gateway.
    Simulates traffic from multiple edge nodes components hitting critical endpoints.
    Requires the server to be running (e.g. `python standalone_api.py`).
    """
    wait_time = between(0.5, 2.0)

    @task(3)
    def call_fleet_summary(self):
        """Simulate high-frequency requests to the fleet coordinator layer."""
        with self.client.get("/fleet/summary", catch_response=True) as response:
            if response.status_code == 200:
                if response.elapsed.total_seconds() > 0.100:
                    response.failure(f"SLA violation: >100ms latency ({response.elapsed.total_seconds():.3f}s)")
            elif response.status_code == 404:
                response.failure("Fleet summary not found")

    @task(1)
    def call_metrics(self):
        """Simulate Prometheus scraping the /metrics endpoint."""
        with self.client.get("/metrics", catch_response=True) as response:
            if response.status_code == 200:
                if response.elapsed.total_seconds() > 0.100:
                    response.failure(f"SLA violation: >100ms latency ({response.elapsed.total_seconds():.3f}s)")
            else:
                response.failure("Metrics scrape failed")
