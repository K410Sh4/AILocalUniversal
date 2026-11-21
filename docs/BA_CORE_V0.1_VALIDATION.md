# BA Core 0.1 — Validation Protocol

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

## Purpose

Validate the smallest executable substrate for the Brain Artificial (BA): local environmental niches, local phenotypic adaptation and spatial signal transport. This experiment does not claim to implement the complete BA, biological neurons, development or evolution.

## Hypotheses

- H1 — Local specialization: when regions have divergent environments, local adaptation should outperform a shared global phenotype on mean and worst-region fitness.
- H2 — Spatial permeability: signal exchange should depend on connection permeability; a zero-permeability boundary must block exchange.
- H3 — Conservation: transport alone must conserve total signal mass within numerical tolerance.
- H4 — Stability: invalid values and transport configurations that violate the explicit stability bound must be rejected.
- H5 — Reproducibility: identical initial states and ordered operations must produce identical results on the same build/target.

## Model and limits

The first model uses two normalized environmental dimensions and a simple bounded local adaptation rule:

`p[t+1] = clamp(p[t] + η · s · (e_local - p[t]), 0, 1)`

where `p` is the expressed phenotype, `η` is the learning rate, `s` is sensitivity and `e_local` is the currently observed local environment. This is a controlled phenotypic-plasticity baseline, not genetic evolution.

For signal transport, each undirected edge transfers a pairwise flux proportional to the concentration difference and edge permeability. All fluxes are computed from the same pre-step state and then applied simultaneously. Production, uptake, degradation and boundary loss are absent in 0.1 and must not be silently inferred.

## Initial automated tests

- Divergent two-niche local adaptation versus a shared-global-phenotype baseline.
- Mean and worst-region fitness.
- Signal mass conservation.
- Complete transport barrier.
- Bounded phenotype and deterministic replay.
- Rejection of non-finite environmental state.
- Validation of duplicate edges and transport stability.

## Required next experiments before any performance claim

1. Expand to 1, 2, 4, 8 and 16 regions.
2. Evaluate line, ring, grid, clustered and sparse irregular topologies.
3. Sweep learning rates, receptor sensitivities, permeability and environmental divergence.
4. Compare local-only, shared-global, neighbor-coupled and static baselines using paired initial states.
5. Test abrupt, gradual, periodic and stochastic environmental changes without exposing future states.
6. Report mean, worst-region and per-region fitness, adaptation time, variance and signal cost.
7. Add ablations for local adaptation and signal transport separately.
8. Run multiple deterministic initial conditions/seeds once explicit variation is introduced.

## Promotion rules

- No claim of advantage from a single topology or single environmental configuration.
- No global-mean improvement may conceal unacceptable worst-region collapse.
- No genetic/evolutionary claim until immutable lineage, heritable variation, reproduction and multi-generation selection are implemented and independently measured.
- No K.BA integration until the substrate API, benchmark protocol and resource costs are stable.

## Interpretation

A successful 0.1 test proves only that the specified numerical mechanisms behave as coded under tested conditions. It does not prove biological equivalence, general adaptive superiority, consciousness or complete BA development.
