# BA Core 0.1 — Spatial Adaptation Substrate

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

`ba-core` is an independent Rust experiment for the **Brain Artificial (BA)**. The BA is a distinct adaptive and developmental system, not a conventional Artificial Intelligence model. This crate is neither an LLM nor a model executor.

## Included in 0.1

- Regions with independently observable local environmental conditions (two normalized dimensions).
- Local units with bounded phenotype and receptor-like sensitivity.
- Local phenotypic adaptation, separate from inherited/genetic change.
- Pairwise spatial signal transport with explicit permeability.
- A conservative simultaneous transport update.
- Validation for identifiers, finite normalized state and transport stability.
- Mean and worst-region fitness metrics.

## Deliberately not included

No genetic inheritance, mutation, reproduction, developmental differentiation, reaction-diffusion chemistry, energy economy, persistence or K.BA bridge is claimed in this version. Those mechanisms require separate hypotheses and tests.

## Run

```sh
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all-targets
```

See [the validation protocol](../docs/BA_CORE_V0.1_VALIDATION.md) for experimental gates and interpretation limits.
