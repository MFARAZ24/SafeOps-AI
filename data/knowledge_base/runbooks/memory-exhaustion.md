---
document_id: RB-002
title: Memory Exhaustion and Continuous Memory Growth Runbook
document_type: runbook
service: any
version: 0.1.0
last_reviewed: 2026-07-13
tags:
  - memory
  - memory-leak
  - garbage-collection
  - recommendation
  - resource-exhaustion
---

# Memory Exhaustion and Continuous Memory Growth Runbook

## Trigger

Use this runbook when:

- Service memory usage rises continuously.
- Memory does not return close to its previous baseline.
- The service may be at risk of an out-of-memory failure.
- Request latency increases while memory usage rises.
- Garbage collection activity increases without stabilizing memory usage.
- Service restarts temporarily reduce memory usage but the issue later returns.

## Objective

Determine whether the behavior is caused by:

- A memory leak
- Unbounded cache growth
- Increased request volume
- Expected cache warming
- Large request payloads
- Retained objects
- Increased concurrency
- Unexpected application behavior

## Required Evidence

Collect:

- Memory usage over time
- Request rate over time
- Request latency over time
- Error rate over time
- Garbage collection activity
- CPU utilization
- Representative traces
- Relevant application logs
- Feature-flag state when available
- Recent deployment or configuration changes

## Investigation Procedure

### Step 1 — Validate the Memory Trend

Determine:

- Is memory increasing continuously?
- Does memory decrease after garbage collection?
- Did the growth begin at a specific time?
- Does the growth correlate with increased traffic?
- Does memory stabilize after the workload stabilizes?

### Step 2 — Compare Memory with Workload

Inspect request volume.

A memory increase may be expected when traffic increases.

However, if request volume remains stable while memory grows continuously, investigate:

- Memory leaks
- Unbounded caches
- Retained application objects
- Repeated accumulation of state

### Step 3 — Inspect Runtime Metrics

Look for:

- Increasing runtime memory
- Increased garbage collection activity
- Increased CPU utilization
- Increasing request latency
- Increased error rate
- Service instability

### Step 4 — Inspect Traces

Determine whether:

- Requests become slower as memory usage increases.
- Internal service processing becomes more expensive.
- Repeated internal operations are visible.
- A downstream request returns unusually large amounts of data.
- Dependency latency is normal while internal processing becomes slower.

### Step 5 — Inspect Logs

Search for:

- Cache-related activity
- Memory warnings
- Allocation failures
- Out-of-memory errors
- Repeated processing of the same objects
- Runtime exceptions
- Garbage collection warnings
- Service restarts

## Diagnosis Guidance

### Continuous Growth with Stable Traffic

Strongly investigate:

- Memory leak
- Unbounded cache growth
- Retained objects
- Application state that is never released

### Memory Growth that Stabilizes

Consider:

- Expected cache warming
- Normal runtime initialization
- Temporary traffic increase

Continue monitoring before assigning a root cause.

### Memory Growth Proportional to Traffic

Consider:

- Higher concurrency
- Queued work
- Increased workload
- Capacity limitations

### Memory Growth with Increasing Garbage Collection

Possible interpretation:

The runtime is attempting to reclaim memory but cannot return usage to its previous baseline.

Investigate retained objects, unbounded state, or memory leaks.

## Recommendation Service Investigation

When Recommendation memory grows continuously:

1. Inspect Recommendation runtime memory.
2. Inspect garbage collection behavior.
3. Compare request rate with memory growth.
4. Inspect Recommendation request latency.
5. Inspect Recommendation error rate.
6. Inspect Recommendation traces.
7. Search Recommendation logs.
8. Check approved feature-flag state.
9. Compare behavior with a healthy time period.

Possible causes include:

- Unbounded recommendation cache
- Retained product data
- Memory leak
- Increased workload

## Containment Options

Possible containment actions include:

- Reduce test traffic.
- Disable an approved failure scenario.
- Restart the affected service after human approval.
- Increase monitoring frequency.
- Preserve diagnostic evidence before restarting.

## Important Safety Rule

Restarting a service may temporarily reduce memory usage.

A restart does not prove the root cause and does not repair the underlying software defect.

Restarting a service requires explicit human approval.

## Root-Cause Reporting

The final SafeOps report should include:

- Observed memory pattern
- Relevant workload behavior
- Runtime evidence
- Supporting logs
- Relevant trace evidence
- Most likely cause
- Alternative explanations
- Confidence level
- Recommended next action