SERVICE_DEPENDENCIES = {
    "frontend": {
        "upstream_services": [],
        "downstream_services": [
            "checkout",
            "recommendation",
            "product-catalog",
        ],
        "databases": [],
        "message_queues": [],
    },
    "checkout": {
        "upstream_services": [
            "frontend",
        ],
        "downstream_services": [
            "cart",
            "payment",
            "shipping",
            "product-catalog",
        ],
        "databases": [],
        "message_queues": [],
    },
    "recommendation": {
        "upstream_services": [
            "frontend",
        ],
        "downstream_services": [
            "product-catalog",
        ],
        "databases": [],
        "message_queues": [],
    },
    "payment": {
        "upstream_services": [
            "checkout",
        ],
        "downstream_services": [],
        "databases": [
            "payment-postgres",
        ],
        "message_queues": [],
    },
    "product-catalog": {
        "upstream_services": [
            "frontend",
            "checkout",
            "recommendation",
        ],
        "downstream_services": [],
        "databases": [
            "product-catalog-db",
        ],
        "message_queues": [],
    },
    "cart": {
        "upstream_services": [
            "checkout",
        ],
        "downstream_services": [],
        "databases": [
            "cart-redis",
        ],
        "message_queues": [],
    },
    "shipping": {
        "upstream_services": [
            "checkout",
        ],
        "downstream_services": [],
        "databases": [],
        "message_queues": [],
    },
}


METRIC_SNAPSHOTS = {
    "checkout": {
        "service": "checkout",
        "observed_at": "2026-07-21T20:10:00+00:00",
        "request_rate_rps": 41.8,
        "error_rate_percent": 4.7,
        "p50_latency_ms": 382.0,
        "p95_latency_ms": 2810.0,
        "p99_latency_ms": 4215.0,
        "cpu_percent": 67.2,
        "memory_percent": 58.4,
    },
    "recommendation": {
        "service": "recommendation",
        "observed_at": "2026-07-21T20:10:00+00:00",
        "request_rate_rps": 24.3,
        "error_rate_percent": 1.2,
        "p50_latency_ms": 88.0,
        "p95_latency_ms": 241.0,
        "p99_latency_ms": 490.0,
        "cpu_percent": 51.6,
        "memory_percent": 92.8,
    },
    "payment": {
        "service": "payment",
        "observed_at": "2026-07-21T20:10:00+00:00",
        "request_rate_rps": 38.5,
        "error_rate_percent": 6.1,
        "p50_latency_ms": 510.0,
        "p95_latency_ms": 3260.0,
        "p99_latency_ms": 4670.0,
        "cpu_percent": 74.8,
        "memory_percent": 63.1,
    },
    "product-catalog": {
        "service": "product-catalog",
        "observed_at": "2026-07-21T20:10:00+00:00",
        "request_rate_rps": 69.2,
        "error_rate_percent": 0.4,
        "p50_latency_ms": 42.0,
        "p95_latency_ms": 103.0,
        "p99_latency_ms": 188.0,
        "cpu_percent": 37.9,
        "memory_percent": 45.2,
    },
}


LOG_RECORDS = [
    {
        "timestamp": "2026-07-21T20:09:42+00:00",
        "service": "recommendation",
        "severity": "warning",
        "message": (
            "Process memory exceeded 90 percent; "
            "cache entry count continues to increase."
        ),
        "trace_id": "trace-rec-001",
    },
    {
        "timestamp": "2026-07-21T20:08:15+00:00",
        "service": "recommendation",
        "severity": "info",
        "message": (
            "Garbage collection completed; "
            "resident memory did not return to baseline."
        ),
        "trace_id": "trace-rec-002",
    },
    {
        "timestamp": "2026-07-21T20:07:03+00:00",
        "service": "recommendation",
        "severity": "error",
        "message": (
            "Product catalog lookup timed out after 2000 ms."
        ),
        "trace_id": "trace-rec-003",
    },
    {
        "timestamp": "2026-07-21T20:09:52+00:00",
        "service": "checkout",
        "severity": "error",
        "message": (
            "Checkout request failed because the "
            "payment operation exceeded its deadline."
        ),
        "trace_id": "trace-checkout-001",
    },
    {
        "timestamp": "2026-07-21T20:09:40+00:00",
        "service": "payment",
        "severity": "warning",
        "message": (
            "Database connection pool utilization reached "
            "95 percent."
        ),
        "trace_id": "trace-checkout-001",
    },
    {
        "timestamp": "2026-07-21T20:06:18+00:00",
        "service": "payment",
        "severity": "error",
        "message": (
            "Payment database query exceeded "
            "the configured timeout."
        ),
        "trace_id": "trace-payment-002",
    },
    {
        "timestamp": "2026-07-21T20:05:11+00:00",
        "service": "product-catalog",
        "severity": "info",
        "message": (
            "Product catalog cache refresh completed successfully."
        ),
        "trace_id": "trace-catalog-001",
    },
]


DEPLOYMENT_RECORDS = [
    {
        "deployment_id": "deploy-checkout-042",
        "service": "checkout",
        "version": "2.4.1",
        "deployed_at": "2026-07-21T19:35:00+00:00",
        "status": "successful",
        "commit_sha": "9ac18d2",
        "deployed_by": "release-bot",
    },
    {
        "deployment_id": "deploy-checkout-041",
        "service": "checkout",
        "version": "2.4.0",
        "deployed_at": "2026-07-18T14:20:00+00:00",
        "status": "successful",
        "commit_sha": "37bc102",
        "deployed_by": "release-bot",
    },
    {
        "deployment_id": "deploy-recommendation-018",
        "service": "recommendation",
        "version": "1.8.0",
        "deployed_at": "2026-07-21T18:50:00+00:00",
        "status": "successful",
        "commit_sha": "d82f19a",
        "deployed_by": "release-bot",
    },
    {
        "deployment_id": "deploy-recommendation-017",
        "service": "recommendation",
        "version": "1.7.3",
        "deployed_at": "2026-07-15T16:05:00+00:00",
        "status": "successful",
        "commit_sha": "4fc227b",
        "deployed_by": "release-bot",
    },
    {
        "deployment_id": "deploy-payment-031",
        "service": "payment",
        "version": "3.1.2",
        "deployed_at": "2026-07-21T19:30:00+00:00",
        "status": "successful",
        "commit_sha": "be7f561",
        "deployed_by": "release-bot",
    },
]