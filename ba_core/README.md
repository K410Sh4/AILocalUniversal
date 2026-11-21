# BA Core 0.4 — Adaptive Homeostasis

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

ba-core is an independent experimental substrate for the **Brain Artificial (BA)**, a distinct adaptive and developmental system. It is not a conventional Artificial Intelligence model, LLM or model executor.

## 0.4 additions

- Independent local homeostatic regulation per region.
- Bounded negative feedback with explicit timestep stability guard.
- Finite actuator capacity and finite local regulatory reserve.
- Explicit energy and state/boundary ledgers.
- Heterogeneous regional targets are preserved; no forced global homogenization.
- Deterministic disturbance, recovery, resource and scaling tests.

## Deliberate exclusions

No moving set points/allostasis, anticipatory control, intermittent regulation, reserve replenishment, inter-region coordination, signal coupling, phenotype changes, structural homeostasis, differentiation, heredity or K.BA integration. These require independent validation.

## Run

```sh
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all-targets
```

See the 0.1 validation protocol, 0.2 benchmark matrix, 0.3 signal ecology and 0.4 homeostasis documents.
