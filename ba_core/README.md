# BA Core 0.3 — Spatial Signal Ecology

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

ba-core is an independent experimental substrate for the **Brain Artificial (BA)**, a distinct adaptive and developmental system. It is not a conventional Artificial Intelligence model, LLM or model executor.

## 0.3 additions

- Separate regional signal sources, transport, uptake and degradation.
- Volume-aware amount conservation across unequal regions.
- Explicit transport stability bound.
- Exact local linear source/sink integration.
- Auditable production/uptake/degradation mass ledger.
- Bounded Hill-type receptor exposure, without assuming the Hill coefficient equals receptor count.
- Deterministic tests for conservation, barriers, stability, reaction partitioning and receptor response.

## Deliberately excluded

No coupling of signals to phenotype, no directed transport, receptor internalization, binding reservoirs, feedback-regulated sources, homeostasis, differentiation or heredity. Those require independent validation.

## Run

```sh
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all-targets
```

See the 0.1 validation protocol, 0.2 benchmark matrix and 0.3 signal ecology validation document.
