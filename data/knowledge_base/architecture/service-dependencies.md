---
document_id: ARCH-002
title: Core Service Dependency Map
document_type: architecture
service: platform
version: 0.1.0
last_reviewed: 2026-07-13
tags:
  - dependencies
  - service-map
  - root-cause-analysis
  - traces
---

# Core Service Dependency Map

## Purpose

This document describes the main service relationships used by the initial SafeOps incident scenarios.

It focuses on the service paths currently relevant to SafeOps and is not intended to describe every service in the OpenTelemetry Demo.

## Main Service Dependencies

| Service | Important Downstream Dependencies | Possible User Impact |
|---|---|---|
| Frontend Proxy | Frontend | Store pages and user interfaces may become unreachable |
| Frontend | Product Catalog, Recommendation, Cart, Checkout, Shipping | Pages may load slowly, display incomplete information, or fail |
| Recommendation | Product Catalog | Recommendations may become slow, incomplete, or unavailable |
| Cart | Valkey | Cart reads and updates may become slow or fail |
| Checkout | Cart, Currency, Payment, Product Catalog, Shipping, Email | Checkout may become slow or fail |
| Shipping | Quote | Shipping estimates may become slow or unavailable |

## Product Browsing Path

A simplified product-browsing request may follow this path:

Frontend Proxy
→ Frontend
→ Product Catalog
→ Recommendation

The Frontend may also interact with other services depending on the requested page and enabled features.

## Recommendation Request Path

A simplified Recommendation request is:

Frontend
→ Recommendation
→ Product Catalog

When Recommendation latency increases:

1. Inspect Recommendation latency and error metrics.
2. Inspect Recommendation traces.
3. Determine whether time is spent inside Recommendation or Product Catalog.
4. Inspect Recommendation logs.
5. Inspect Product Catalog only when traces or logs indicate a downstream problem.

## Checkout Request Path

A simplified checkout request is:

Frontend
→ Checkout
→ Cart
→ Currency
→ Payment
→ Product Catalog
→ Shipping
→ Email

The exact execution order may vary.

When checkout becomes slow:

1. Inspect a representative slow Checkout trace.
2. Compare the duration of its child spans.
3. Identify the slowest or failing dependency.
4. Inspect metrics for that dependency.
5. Inspect correlated logs.
6. Retrieve the relevant service guide or runbook.

## Root-Cause Localization Rule

The service where the user observes a symptom is not necessarily the service that caused the incident.

For example:

- A slow Checkout request may be caused by Payment.
- A Recommendation failure may be caused by Product Catalog.
- A slow Frontend request may be caused by a downstream service.

SafeOps should prioritize evidence in the following order:

1. Trace duration and error information
2. Service metrics
3. Correlated application logs
4. Known dependency relationships
5. Relevant operational documentation

## Investigation Guidance

SafeOps should not assign a root cause based only on the name of the affected user operation.

The root-cause hypothesis must include:

- The suspected service
- Supporting telemetry
- Relevant dependency information
- Missing evidence
- Confidence level