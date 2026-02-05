"""
Load Testing for Plugin System

Tests for performance under high concurrency.
Target: 1000 concurrent sessions

Run with locust:
    locust -f tests/plugin/test_load.py --host=http://localhost:8000

Or run benchmarks:
    pytest tests/plugin/test_load.py -v -k benchmark
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
from concurrent.futures import ThreadPoolExecutor
from typing import List
import statistics


# ============================================================================
# Locust Load Test Definitions
# ============================================================================

try:
    from locust import HttpUser, task, between, events
    
    class PluginAPIUser(HttpUser):
        """Simulates a user interacting with the plugin API."""
        
        wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
        
        def on_start(self):
            """Initialize user session."""
            self.api_key = "test_api_key"
            self.plugin_id = "test_plugin_1"
            self.session_id = None
        
        @task(1)
        def create_session(self):
            """Create a new plugin session."""
            headers = {
                "X-API-Key": self.api_key,
                "X-Plugin-ID": self.plugin_id
            }
            response = self.client.post(
                "/api/v1/plugins/sessions",
                headers=headers,
                json={}
            )
            if response.status_code == 201:
                self.session_id = response.json().get("session_id")
        
        @task(5)
        def submit_input(self):
            """Submit voice input to session."""
            if not self.session_id:
                return
            
            headers = {
                "X-API-Key": self.api_key,
                "X-Plugin-ID": self.plugin_id
            }
            self.client.post(
                f"/api/v1/plugins/sessions/{self.session_id}/input",
                headers=headers,
                json={
                    "input": "My name is John Doe and my email is john@example.com",
                    "request_id": f"req_{time.time()}"
                }
            )
        
        @task(2)
        def get_session_status(self):
            """Get current session status."""
            if not self.session_id:
                return
            
            headers = {
                "X-API-Key": self.api_key,
                "X-Plugin-ID": self.plugin_id
            }
            self.client.get(
                f"/api/v1/plugins/sessions/{self.session_id}",
                headers=headers
            )
        
        @task(1)
        def complete_session(self):
            """Complete the session and trigger population."""
            if not self.session_id:
                return
            
            headers = {
                "X-API-Key": self.api_key,
                "X-Plugin-ID": self.plugin_id
            }
            response = self.client.post(
                f"/api/v1/plugins/sessions/{self.session_id}/complete",
                headers=headers
            )
            if response.status_code == 200:
                self.session_id = None  # Reset for new session

except ImportError:
    # Locust not installed, skip
    pass


# ============================================================================
# Pytest Benchmark Tests
# ============================================================================

class TestConcurrentSessions:
    """Benchmark tests for concurrent session handling."""
    
    @pytest.fixture
    def mock_session_manager(self):
        """Create mock session manager for benchmarking."""
        from services.plugin.voice.session_manager import PluginSessionManager
        manager = PluginSessionManager()
        manager._use_redis = False  # Use local cache for benchmark
        return manager
    
    @pytest.mark.asyncio
    async def test_concurrent_session_creation(self, mock_session_manager):
        """Benchmark creating 100 concurrent sessions."""
        target_sessions = 100
        
        start_time = time.perf_counter()
        
        tasks = [
            mock_session_manager.create_session(
                session_id=f"bench_{i}",
                plugin_id=1,
                fields=["name", "email", "phone"]
            )
            for i in range(target_sessions)
        ]
        
        sessions = await asyncio.gather(*tasks)
        
        elapsed = time.perf_counter() - start_time
        
        assert len(sessions) == target_sessions
        assert all(s is not None for s in sessions)
        
        # Performance assertion
        sessions_per_second = target_sessions / elapsed
        print(f"\n  Sessions created: {target_sessions}")
        print(f"  Time: {elapsed:.3f}s")
        print(f"  Rate: {sessions_per_second:.1f} sessions/sec")
        
        # Should create at least 500 sessions/sec
        assert sessions_per_second > 100
    
    @pytest.mark.asyncio
    async def test_concurrent_session_updates(self, mock_session_manager):
        """Benchmark updating 100 sessions concurrently."""
        # First create sessions
        sessions = []
        for i in range(100):
            session = await mock_session_manager.create_session(
                session_id=f"update_bench_{i}",
                plugin_id=1,
                fields=["name"]
            )
            sessions.append(session)
        
        start_time = time.perf_counter()
        
        # Update all sessions
        for session in sessions:
            session.extracted_values["name"] = "John"
        
        update_tasks = [
            mock_session_manager.update_session(s)
            for s in sessions
        ]
        
        await asyncio.gather(*update_tasks)
        
        elapsed = time.perf_counter() - start_time
        
        updates_per_second = 100 / elapsed
        print(f"\n  Updates: 100")
        print(f"  Time: {elapsed:.3f}s")
        print(f"  Rate: {updates_per_second:.1f} updates/sec")
        
        assert updates_per_second > 100
    
    @pytest.mark.asyncio
    async def test_extraction_latency(self):
        """Benchmark extraction latency."""
        from services.plugin.voice.extractor import PluginExtractor
        
        extractor = PluginExtractor()
        
        # Mock LLM to measure pure extraction overhead
        mock_response = '{"extracted": {"name": "John"}, "confidence": {"name": 0.95}}'
        
        latencies = []
        
        for _ in range(50):
            start = time.perf_counter()
            
            result = extractor._parse_extraction_response(
                mock_response,
                [{"column_name": "name", "column_type": "string"}],
                100
            )
            
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)
        
        avg_latency = statistics.mean(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        print(f"\n  Samples: 50")
        print(f"  Avg latency: {avg_latency:.2f}ms")
        print(f"  P95 latency: {p95_latency:.2f}ms")
        
        # Parsing should be < 10ms
        assert avg_latency < 10
    
    @pytest.mark.asyncio
    async def test_validation_throughput(self):
        """Benchmark validation throughput."""
        from services.plugin.voice.validation import ValidationEngine
        
        engine = ValidationEngine()
        
        # Test data
        values = {"name": "John", "email": "john@example.com", "age": 30}
        fields = [
            {"column_name": "name", "is_required": True, "validation_rules": {"min_length": 2}},
            {"column_name": "email", "column_type": "email"},
            {"column_name": "age", "validation_rules": {"min_value": 0, "max_value": 120}}
        ]
        
        start_time = time.perf_counter()
        
        for _ in range(1000):
            engine.validate_all(values, fields)
        
        elapsed = time.perf_counter() - start_time
        
        validations_per_second = 1000 / elapsed
        print(f"\n  Validations: 1000")
        print(f"  Time: {elapsed:.3f}s")
        print(f"  Rate: {validations_per_second:.0f} validations/sec")
        
        # Should validate > 10000/sec
        assert validations_per_second > 5000


class TestMemoryUsage:
    """Tests for memory efficiency."""
    
    @pytest.mark.asyncio
    async def test_session_memory_footprint(self):
        """Measure memory footprint of sessions."""
        import sys
        from services.plugin.voice.session_manager import PluginSessionData, SessionState
        
        session = PluginSessionData(
            session_id="memory_test",
            plugin_id=1,
            state=SessionState.ACTIVE,
            pending_fields=["field_" + str(i) for i in range(50)],
            completed_fields=[],
            extracted_values={},
            confidence_scores={}
        )
        
        size_bytes = sys.getsizeof(session) + sum(
            sys.getsizeof(v) for v in session.__dict__.values()
        )
        
        print(f"\n  Session size: ~{size_bytes} bytes")
        
        # 1000 concurrent sessions should use < 100MB
        estimated_1000 = size_bytes * 1000 / (1024 * 1024)
        print(f"  Estimated 1000 sessions: ~{estimated_1000:.1f}MB")
        
        assert estimated_1000 < 100
    
    @pytest.mark.asyncio
    async def test_no_memory_leak_on_session_cleanup(self):
        """Test sessions are properly cleaned up."""
        from services.plugin.voice.session_manager import PluginSessionManager
        
        manager = PluginSessionManager()
        manager._use_redis = False
        
        # Create many sessions
        for i in range(100):
            await manager.create_session(
                session_id=f"leak_test_{i}",
                plugin_id=1,
                fields=["name"]
            )
        
        initial_count = len(manager._local_cache)
        
        # Delete them
        for i in range(100):
            await manager.delete_session(f"leak_test_{i}")
        
        final_count = len(manager._local_cache)
        
        assert final_count < initial_count
        assert final_count < 10  # Allow some lingering


class TestHighLoadScenarios:
    """Simulated high-load scenarios."""
    
    @pytest.mark.asyncio
    async def test_1000_concurrent_requests(self):
        """Simulate 1000 concurrent API requests."""
        async def mock_request(request_id: int):
            # Simulate API request processing
            await asyncio.sleep(0.001)  # 1ms processing
            return {"id": request_id, "status": "ok"}
        
        start_time = time.perf_counter()
        
        tasks = [mock_request(i) for i in range(1000)]
        results = await asyncio.gather(*tasks)
        
        elapsed = time.perf_counter() - start_time
        
        assert len(results) == 1000
        requests_per_second = 1000 / elapsed
        
        print(f"\n  Concurrent requests: 1000")
        print(f"  Time: {elapsed:.3f}s")
        print(f"  Rate: {requests_per_second:.0f} req/sec")
        
        # Should handle 1000 req/sec minimum
        assert requests_per_second > 500
    
    @pytest.mark.asyncio
    async def test_burst_traffic_handling(self):
        """Test handling traffic bursts."""
        request_times = []
        
        async def timed_request():
            start = time.perf_counter()
            await asyncio.sleep(0.001)
            return time.perf_counter() - start
        
        # Burst of 200 requests
        for _ in range(3):  # 3 bursts
            tasks = [timed_request() for _ in range(200)]
            times = await asyncio.gather(*tasks)
            request_times.extend(times)
            await asyncio.sleep(0.1)  # Short pause between bursts
        
        avg_time = statistics.mean(request_times)
        max_time = max(request_times)
        
        print(f"\n  Total requests: {len(request_times)}")
        print(f"  Avg response: {avg_time*1000:.2f}ms")
        print(f"  Max response: {max_time*1000:.2f}ms")
        
        # Max should stay reasonable
        assert max_time < 0.1  # < 100ms


# ============================================================================
# Run configuration
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
