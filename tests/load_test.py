"""Load test script for the AegisOps AI API."""

import argparse
import concurrent.futures
import statistics
import sys
import time
import os
from typing import Tuple

# Add the root directory to the sys so that we can import aegisops
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient

from aegisops.api.app import app


client = TestClient(app)


def make_request(endpoint: str) -> Tuple[bool, float]:
    """Make a single request to the endpoint and return success and elapsed time."""
    start = time.perf_counter()
    try:
        response = client.get(endpoint)
        elapsed = time.perf_counter() - start
        return response.status_code < 400, elapsed
    except Exception as e:
        elapsed = time.perf_counter() - start
        print(f"Request failed with exception: {e}", file=sys.stderr)
        return False, elapsed


def run_load_test(endpoint: str, num_requests: int, concurrency: int) -> None:
    """Run a load test against the specified endpoint."""
    print(f"Starting load test: {num_requests} requests to {endpoint} with {concurrency} concurrent workers...")
    start_time = time.perf_counter()

    success_count = 0
    response_times = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        # Submit all tasks
        future_to_request = {
            executor.submit(make_request, endpoint): i for i in range(num_requests)
        }
        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_request):
            success, elapsed = future.result()
            if success:
                success_count += 1
                response_times.append(elapsed)

    total_time = time.perf_counter() - start_time

    if response_times:
        avg_response = statistics.mean(response_times)
        median_response = statistics.median(response_times)
        min_response = min(response_times)
        max_response = max(response_times)
        # Calculate 95th percentile
        sorted_times = sorted(response_times)
        index_95 = int(0.95 * len(sorted_times))
        p95_response = sorted_times[index_95]
    else:
        avg_response = median_response = min_response = max_response = p95_response = 0.0

    print("\nLoad Test Results:")
    print(f"  Total time: {total_time:.2f} seconds")
    print(f"  Total requests: {num_requests}")
    print(f"  Successful requests: {success_count}")
    print(f"  Failed requests: {num_requests - success_count}")
    print(f"  Requests per second: {num_requests / total_time:.2f}")
    if response_times:
        print(f"  Average response time: {avg_response * 1000:.2f} ms")
        print(f"  Median response time: {median_response * 1000:.2f} ms")
        print(f"  Min response time: {min_response * 1000:.2f} ms")
        print(f"  Max response time: {max_response * 1000:.2f} ms")
        print(f"  95th percentile response time: {p95_response * 1000:.2f} ms")
    else:
        print("  No successful requests to compute response time statistics.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load test for the AegisOps AI API.")
    parser.add_argument(
        "--endpoint",
        default="/health/live",
        help="Endpoint to test (default: /health/live)",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=100,
        help="Total number of requests to make (default: 100)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Number of concurrent workers (default: 10)",
    )
    args = parser.parse_args()

    run_load_test(
        endpoint=args.endpoint,
        num_requests=args.requests,
        concurrency=args.concurrency,
    )


if __name__ == "__main__":
    main()