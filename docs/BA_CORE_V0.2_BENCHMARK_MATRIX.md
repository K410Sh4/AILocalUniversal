# BA Core 0.2 — Spatial Benchmark Matrix

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

## Purpose

Expand the first BA substrate experiment beyond a two-region demonstration. This version compares local adaptation with a shared-global-environment baseline and checks signal transport across representative spatial topologies.

## Paired comparison

Both policies start from identical region and unit states and receive the same number of update steps:

- **Local policy:** each unit adapts to the currently observable conditions of its own region.
- **Shared-global baseline:** every unit receives the arithmetic mean of current region conditions.

Metrics are measured against each unit's actual local environment:
- mean fitness;
- worst-region fitness;
- region count.

The baseline is intentionally simple and transparent. It is not claimed to represent every possible global coordination strategy.

## Automated matrix

Region counts: 1, 2, 4, 8 and 16.

Environmental pattern: alternating divergent niches with two normalized conditions.

Additional sensitivity sweep: learning rates 0.05, 0.2, 0.5 and 1.0.

Signal topologies:
- line;
- ring;
- 2×2 grid;
- star/cluster;
- sparse disconnected pairs.

The topology tests verify transport invariants and signal conservation. They do not yet assert that signal transport improves adaptation; coupling signals to receptors and behavior is a later independent hypothesis.

## Expected interpretation

- With one region, local and shared-global policies should be equivalent because no inter-region divergence exists.
- With multiple divergent regions, local specialization should improve both mean and worst-region fitness relative to the shared-global baseline.
- Transport topology must not change total signal mass in a transport-only step.
- No result here proves genetic evolution, development, or universal superiority.

## Next experimental gate

After this matrix passes, introduce explicit signal sources, uptake, degradation and receptor exposure as separate mechanisms. Then test whether local signal fields improve adaptation under spatial barriers and changing niches without cross-niche homogenization. Do not merge those mechanisms into a single opaque update rule.
