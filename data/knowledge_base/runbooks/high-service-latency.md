---
document_id: RB-001
title: High Service Latency Runbook
document_type: runbook
service: any
version: 0.1.0
last_reviewed: 2026-07-13
tags:
  - latency
  - traces
  - metrics
  - dependency
  - troubleshooting
---

# High Service Latency Runbook

## Trigger

Use this runbook when:

- Users report slow responses.
- Request latency exceeds the expected baseline.
- Tail latency increases significantly.
- A service-level objective may be at risk.
- A user flow becomes noticeably slower.

## Objective

Determine whether latency originates from:

1. Internal service processing
2. A downstream dependency
3. CPU or memory pressure
4. Increased request volume
5. Repeated errors or retries
6. A recent deployment or configuration change

## Required Evidence

Collect:

- Request latency over time
- Request rate over time
- Error rate over time
- At least one representative slow trace
- At least one healthy trace for comparison
- Relevant service logs
- CPU metrics
- Memory metrics
- Recent deployment or configuration information when available

## Investigation Procedure

### Step 1 — Confirm the Symptom

Determine:

- Which service or user flow is affected?
- When did latency begin?
- Is the problem continuous or intermittent?
- Are all requests affected?
- Is the latency increase significant compared with the normal baseline?

### Step 2 — Inspect Metrics

Look for:

- Increased request volume
- Increased error rate
- CPU saturation
- Memory pressure
- Sudden latency changes
- Gradual latency degradation

Metrics help identify the time window and scale of the incident.

### Step 3 — Inspect Traces

Compare slow and healthy traces.

Identify:

- The longest span
- Failed spans
- Repeated dependency calls
- Internal service processing time
- Downstream service time
- Unusual retries

### Step 4 — Inspect Logs

Search the suspected service and dependency logs for:

- Timeouts
- Connection failures
- Exceptions
- Retry activity
- Resource warnings
- Failed requests

### Step 5 — Form Root-Cause Hypotheses

Each hypothesis should include:

- Suspected root cause
- Supporting evidence
- Contradictory evidence
- Missing evidence
- Confidence level

## Decision Guidance

### Slow Downstream Span

Likely direction:

Investigate the downstream dependency.

### Normal Downstream Spans but Slow Parent Span

Likely direction:

Investigate internal application processing.

### High Latency and High CPU

Likely direction:

Investigate:

- Compute saturation
- Increased traffic
- Inefficient processing
- Expensive repeated operations

### High Latency and Increasing Memory

Likely direction:

Use the Memory Exhaustion Runbook.

### High Latency and Increased Errors

Likely direction:

Investigate:

- Dependency failures
- Timeouts
- Retry behavior
- Recent deployments
- Configuration changes

### High Latency with Normal Resource Usage

Likely direction:

Investigate:

- Network delay
- Slow downstream calls
- External dependencies
- Locking or waiting behavior

## Remediation Guidance

Prefer low-risk actions first:

1. Collect additional evidence.
2. Reduce uncertainty.
3. Identify the specific affected component.
4. Recommend targeted mitigation.
5. Request approval before any state-changing action.

Do not restart every service as a default response.

## Approval Requirement

Restarting a service, changing configuration, rolling back a deployment, or changing a feature flag requires explicit human approval.