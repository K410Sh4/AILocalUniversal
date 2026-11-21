# BA Core 0.3 — Spatial Signal Ecology

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

## Objective

Introduce explicit signal production, transport, uptake, degradation and receptor interpretation without merging them into one opaque update. This is a mechanistic substrate experiment for the Brain Artificial (BA), not a claim of biological equivalence.

## Biological basis

Developing tissues use signaling fields whose spatial and temporal profiles emerge from production, transport and removal. Transport can be nondirectional or directional; diffusion is important but not universal. Receptors and downstream signaling interpret exposure rather than simply copying concentration into behavior.

Kicheva & Briscoe (2023) describe production, transport and removal as major determinants of morphogen profiles (DOI: 10.1146/annurev-cellbio-020823-011522). Morphogen transport models distinguish free diffusion, reversible receptor binding, internalization and degradation (PMCID: PMC3710257). These findings motivate separating mechanisms here.

The receptor response uses a Hill-type curve only as a bounded phenomenological response. Its cooperativity parameter is not interpreted as a literal binding-site count; the Hill equation can misrepresent physical binding mechanisms when interpreted too literally (Weiss, 1997, PMID: 9285481).

## State and units

Each region stores positive volume, nonnegative signal concentration, nonnegative constant production rate (concentration/time), and nonnegative first-order uptake and degradation rates (1/time). Each undirected edge stores effective conductance (volume/time). Signal amount is volume multiplied by concentration.

## Numerical method

### Conservative transport

For edge (i,j), transferred amount during dt is:

F_ij = conductance_ij × dt × (c_i - c_j)

The same amount is subtracted from one region and added to the other. Unequal volumes are handled by dividing each amount change by that region's volume.

The explicit simultaneous update enforces, for every region i:

Σ_j conductance_ij × dt / volume_i ≤ 1

This sufficient bound keeps concentrations nonnegative for nonnegative initial concentrations. An impermeable barrier is represented by zero conductance.

### Exact local source/sink kinetics

After transport, each region follows:

dc/dt = q - (u + d)c

where q is production, u uptake and d degradation. The constant-coefficient reaction is integrated analytically:

c(t+dt) = c(t)e^(-k dt) + q(1-e^(-k dt))/k, where k=u+d.

When k=0, the update is c(t)+q dt. Integrated removal is split between uptake and degradation in proportion to their rates. A stable expm1 calculation and small-step series reduce cancellation.

### Receptor exposure

response = sensitivity × c^n / (c^n + K^n)

K and n are positive; sensitivity is in [0,1]. A log-domain implementation avoids overflow. This response is deliberately not yet coupled to plasticity or development.

## Validation gates

- Conservation of transport amount with unequal volumes.
- Explicit production/uptake/degradation mass ledger.
- Nonnegative state and per-region stability.
- Zero-conductance barriers.
- Exact reaction consistency under time-step partitioning.
- Determinism.
- Receptor monotonicity, half-saturation and bounded output.
- Invalid rates and non-finite values rejected.

## Deliberate exclusions

No directed transport, receptor internalization, receptor occupancy dynamics, signal binding reservoirs, feedback-regulated production, multiple interacting signal species, adaptation coupling, homeostasis, differentiation or heredity are claimed in 0.3. Those are subsequent hypotheses. Signal concentration is not yet allowed to change a unit's phenotype: that causal link must be tested separately against signal-free and local-environment baselines.

## Ownership

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

Third-party research remains under its own licenses and is cited for scientific context only.
