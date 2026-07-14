---
document_id: SVC-001
title: Recommendation Service Operational Guide
document_type: service
service: recommendation
version: 0.1.0
last_reviewed: 2026-07-13
tags:
  - recommendation
  - product-catalog
  - memory
  - latency
  - troubleshooting
---

# Recommendation Service Operational Guide

## Purpose

The Recommendation service returns suggested products based on product identifiers associated with the user's browsing context.

The service depends on Product Catalog to obtain information about available products.

## Important Dependencies

### Upstream Service

- Frontend

### Downstream Services

- Product Catalog
- Feature-flag service

## Common User Symptoms

Users may experience:

- Recommendations load slowly.
- No recommendations are displayed.
- Product pages load slowly.
- Recommendation requests fail.
- Product recommendations are incomplete.

## Important Telemetry

### Metrics

Inspect:

- Request rate
- Request latency
- Error rate
- Runtime memory
- CPU utilization
- Garbage collection activity
- Recommendation count

Metrics help determine:

- When the problem began
- Whether the problem is growing
- Whether traffic increased
- Whether memory or CPU usage is abnormal

### Traces

Inspect:

- Total Recommendation request duration
- Product Catalog child-span duration
- Error status
- Exception information
- Repeated internal operations

Traces should help distinguish:

- Internal Recommendation latency
- Product Catalog latency
- Dependency failures

### Logs

Search for:

- Product identifiers received by Recommendation
- Product retrieval failures
- Exceptions
- Timeout messages
- Cache-related activity
- Memory-related warnings

## Common Failure Patterns

### Product Catalog Dependency Failure

Possible evidence:

- Product Catalog spans are slow or contain errors.
- Recommendation latency increases.
- Recommendation logs contain product retrieval failures.
- Product Catalog metrics show elevated latency or errors.

Recommended investigation:

1. Inspect Product Catalog metrics.
2. Inspect Product Catalog logs.
3. Compare healthy and unhealthy traces.

### Internal Recommendation Memory Growth

Possible evidence:

- Runtime memory increases continuously.
- Memory does not return close to its previous baseline.
- Garbage collection activity increases.
- Request latency rises as memory pressure increases.
- Request volume remains relatively stable.

Possible causes include:

- Unbounded cache growth
- Retained objects
- Memory leak
- Unexpected request behavior

### Internal Processing Latency

Possible evidence:

- Recommendation spans are slow.
- Product Catalog spans remain normal.
- CPU utilization increases.
- Internal processing consumes most of the trace duration.

## Investigation Procedure

1. Confirm that Recommendation latency, errors, or memory are abnormal.
2. Determine when the behavior began.
3. Compare current metrics with a healthy period.
4. Inspect representative traces.
5. Determine whether the problem is internal or downstream.
6. Search correlated Recommendation logs.
7. Retrieve the relevant runbook.
8. Generate a root-cause hypothesis.
9. State supporting evidence.
10. State missing or contradictory evidence.
11. Assign a confidence level.

## Safe Actions

SafeOps may automatically:

- Query Recommendation metrics.
- Retrieve Recommendation traces.
- Search Recommendation logs.
- Retrieve service documentation.
- Compare healthy and unhealthy periods.
- Inspect approved feature-flag state.

## Approval-Required Actions

SafeOps must request human approval before:

- Restarting Recommendation
- Changing configuration
- Changing feature-flag state through an automated tool
- Clearing service state
- Executing a remediation script

## Important Limitation

Restarting Recommendation may temporarily reduce memory pressure, but a restart does not identify or repair the underlying software defect.