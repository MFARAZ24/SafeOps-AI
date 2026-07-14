---
document_id: ARCH-001
title: OpenTelemetry Demo System Overview
document_type: architecture
service: platform
version: 0.1.0
last_reviewed: 2026-07-13
tags:
  - architecture
  - microservices
  - observability
  - telemetry
  - service-topology
---

# OpenTelemetry Demo System Overview

## Purpose

The OpenTelemetry Astronomy Shop is the reference application that SafeOps investigates during development and evaluation.

It is a distributed e-commerce application composed of multiple services. A single user request may pass through several services, so the service where a user observes a problem may not be the service that caused the problem.

## Example User Flows

### Product Browsing

A typical product-browsing request may involve:

1. Frontend Proxy
2. Frontend
3. Product Catalog
4. Recommendation
5. Cart

The exact services involved depend on the requested page and enabled application features.

### Checkout

A checkout request begins in the Frontend and is coordinated by the Checkout service.

Checkout may communicate with:

- Cart
- Currency
- Payment
- Product Catalog
- Shipping
- Email

A failure in one downstream service may increase overall checkout latency or cause checkout to fail.

## Observability Signals

SafeOps uses three main types of telemetry evidence.

### Logs

Logs record discrete application events such as:

- Request processing
- Warnings
- Exceptions
- Dependency failures
- Timeouts
- Service lifecycle events

Logs primarily answer:

What happened?

### Metrics

Metrics record numeric measurements over time, such as:

- Request rate
- Error rate
- Request latency
- CPU utilization
- Memory utilization
- Runtime memory
- Garbage collection activity

Metrics primarily answer:

How much, how often, or how fast?

### Traces

Distributed traces show how one request traveled through multiple services.

Traces primarily answer:

Where did the request spend time, and which dependency failed?

## Investigation Process

SafeOps should:

1. Begin with the reported symptom.
2. Identify the affected user flow.
3. Inspect service metrics for abnormal trends.
4. Use traces to localize latency or errors.
5. Use logs to obtain detailed failure evidence.
6. Retrieve relevant service documentation and runbooks.
7. Generate a root-cause hypothesis supported by evidence.
8. Clearly separate observed facts from assumptions.
9. Request human approval before executing a risky action.

## Investigation Principle

The service where the user observes a symptom is not always the root cause.

For example:

- Slow checkout may be caused by Payment.
- Slow recommendations may be caused by Product Catalog.
- A slow frontend request may be caused by a downstream dependency.

SafeOps should use traces, metrics, logs, service dependencies, and operational documentation before assigning a root cause.

## Operational Boundary

The OpenTelemetry Demo is an isolated development environment.

SafeOps must never assume that access to the demo environment grants permission to execute actions against real production infrastructure.