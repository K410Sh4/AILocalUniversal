# NeuralDNA 0.8 — Morphogen-like Signal Fields: Design and Validation Plan

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

> **Status: isolated signal-field primitive implemented with numerical tests.** No adaptation policy, NeuralStem integration, or BA runtime integration is implemented.

## 1. Why 0.8 follows 0.7

NeuralDNA 0.7 showed that a network's communication topology can preserve or destroy local environmental information. In the clustered-niche experiment:
- within-cluster signal accuracy reached 0.995;
- global signal accuracy fell to 0.500;
- a complete graph's neighbor aggregate fell to 0.124 because each region received more signals from the other niche than from its own;
- acquired local transition history reached 0.991 accuracy and 0.9741 synthetic fitness.

The next step should not add adaptive rewiring yet. The current model uses discrete message delivery. Biology suggests a deeper intermediate mechanism: **signals exist in an environment, spread through it, are absorbed or degraded, and are interpreted according to receiver sensitivity and exposure time.**

## 2. Biological grounding

Three complementary mechanisms motivate this stage:

1. **Morphogen source–transport–removal.** Developmental gradients are shaped by localized or distributed production, transport, and removal. Diffusion alone is not enough to explain every gradient; binding, tissue geometry, transport, and clearance influence the effective range.
2. **Signal uptake and degradation.** Some bacterial quorum-sensing systems restrict communication to very short distances because nearby cells absorb or remove signals. Local sensing can therefore track neighborhood composition more accurately than a global average.
3. **Metacommunity dispersal.** The balance between local environmental selection and movement between patches affects whether local specialists persist or are overwhelmed by regional mixing. Network topology and spatial autocorrelation alter this balance.

References:
- Kicheva & Briscoe (2023), *Control of Tissue Development by Morphogens*, Annual Review of Cell and Developmental Biology. https://doi.org/10.1146/annurev-cellbio-020823-011522
- Stapornwongkul & Vincent (2021), *Generation of extracellular morphogen gradients: the case for diffusion*, Nature Reviews Genetics. https://doi.org/10.1038/s41576-021-00342-y
- Berezhkovskii & Shvartsman (2013), *Kinetics of receptor occupancy during morphogen gradient formation*, Journal of Chemical Physics. https://doi.org/10.1063/1.4811654
- *Short-range quorum sensing controls horizontal gene transfer at micron scale in bacterial communities* (2021), Nature Communications. https://doi.org/10.1038/s41467-021-22649-4
- Suzuki & Economo (2021), *From species sorting to mass effects: spatial network structure mediates the shift between metacommunity archetypes*, Ecography. https://doi.org/10.1111/ecog.05453

These findings motivate testable abstractions; they do not validate this computational model or imply that BA is biologically equivalent to a tissue or brain.

## 3. Proposed signal-field abstraction

For region index `i` and signal class `k`, track free signal concentration `C[i,k]`. Each region can produce a signal based on a forecast it has already made. The field is transported over weighted spatial edges, then altered by local degradation and uptake.

A graph-diffusion step is:

```text
Cdiff[i,k] = C[i,k] + dt * D * sum_j(g[i,j] * (C[j,k] - C[i,k]))
```

where:
- `D` is the transport coefficient;
- `g[i,j] = g[j,i] >= 0` is edge conductance;
- conductance incorporates edge permeability and distance;
- symmetric flux preserves total signal under closed-boundary diffusion before sources and sinks.

After transport, apply local decay and saturable uptake:

```text
Cdecay[i,k] = Cdiff[i,k] * exp(-lambda[i] * dt)
uptake[i,k] = min(
    Cdecay[i,k],
    Vmax[i] * dt * Cdecay[i,k] / (Km[i] + Cdecay[i,k])
)
Cnext[i,k] = max(0, Cdecay[i,k] - uptake[i,k] + P[i,k] * dt)
```

where `lambda[i]` is degradation, `Vmax[i]` is maximum uptake, `Km[i]` controls uptake saturation, and `P[i,k]` is local production.

Receiver response is a saturating threshold function:

```text
response[i,k] = Cnext[i,k]^n[i] / (Kd[i]^n[i] + Cnext[i,k]^n[i])
```

A separate exposure state can model duration:

```text
exposure_next[i,k] = exposure[i,k] * exp(-gamma[i] * dt)
                    + response[i,k] * dt
```

This separates:
- free signal concentration;
- removal from the environment;
- receiver sensitivity;
- time-integrated exposure.

It avoids treating every received signal as a binary, equally trustworthy message.

## 4. Numerical safety and stability gates

The diffusion operator must not create negative concentrations or artificial signal mass.

- Use symmetric edge conductances.
- Use adaptive substeps such that `Δt · D · max_i(Σ_j g_ij) ≤ 0.45` for the explicit diffusion update.
- Enforce a configurable maximum substep budget and reject parameter combinations that exceed it.
- Apply exact exponential decay.
- Cap saturable uptake at available concentration.
- Add production only after the transport/removal update.
- Verify mass conservation in a closed, source-free, sink-free graph.
- Verify total signal decreases only through declared sinks or boundary loss.
- Reject NaN, infinity, negative rates, negative distances, and invalid Hill parameters.
- Keep all source, transport, and receiver parameters independently configurable.

The 0.45 stability margin is a numerical safety bound for this explicit update, not a biological constant. If a different integration scheme is selected, derive and test its stability condition before use.

## 5. Pre-implementation variable matrix

| Variable | Sweep / controls | Main question |
|---|---|---|
| Transport `D` | zero → low → medium → high | When does the field become too mixed? |
| Distance | near → intermediate → far | How does physical separation affect signal? |
| Edge permeability | 0 → 1 | Can niche boundaries restrict cross-talk? |
| Degradation `lambda` | zero → fast | How far does a signal persist? |
| Uptake `Vmax` | zero → high | Does local absorption sharpen the field? |
| Uptake saturation `Km` | low → high | Does receiver/source saturation change range? |
| Sensitivity `Kd` | low → high | Which concentrations trigger a response? |
| Hill coefficient `n` | 1 → 4 | Does response become more switch-like? |
| Exposure clearance `gamma` | slow → fast | Does duration matter beyond peak concentration? |
| Production `P` | sparse → distributed | How do local sources and multiple sources interact? |
| Spatial autocorrelation | high → medium → low | Does topology match the environmental pattern? |
| Niche barrier | absent → partial → closed | Does a boundary preserve local specialization? |
| Time step | coarse → refined | Are results numerically stable? |

## 6. Required theoretical outcomes before implementation

1. **No transport:** (D=0) must prevent signal from crossing edges.
2. **Conservation:** symmetric diffusion without sources/sinks must conserve total signal to numerical tolerance.
3. **Distance decay:** with a localized source and positive degradation, steady concentration should decline with distance in a line-like domain.
4. **Removal:** increasing degradation or uptake must not increase total field mass under otherwise identical conditions.
5. **Boundary isolation:** zero permeability must block transport across that edge.
6. **Range control:** higher transport should expand signal range, while stronger removal should shorten it.
7. **Niche mixing:** excessive transport across divergent niches should increase cross-niche interference.
8. **Local advantage:** within-niche transport should aggregate useful information without forcing a global consensus.
9. **Exposure:** a brief high-amplitude pulse and a sustained lower-amplitude signal may produce different receiver responses; tests must distinguish peak from duration.
10. **Robustness:** results should converge under time-step refinement and remain finite/nonnegative across the validated parameter domain.

## 7. Comparison baselines

The eventual benchmark must compare:
- no communication;
- discrete neighbor messages from 0.7;
- global broadcast from 0.7;
- diffusion without removal;
- diffusion plus degradation;
- diffusion plus degradation and uptake;
- diffusion with niche barriers;
- local acquired history.

All comparisons use paired seeds and identical source forecasts. A future target is never passed to a receiver policy.

## 8. Initial CI results

The first complete GitHub Actions validation passed on commit `cc52dee22eea65cce7a57f4f5e7fb6406cd3b2fd` (run `44908558276`). Ruff, the complete Python test suite, the 0.5–0.7 benchmarks, the 0.8 field benchmark, and Rust formatting/lint/tests all passed.

The field benchmark used a seven-region line, one persistent source at the first region, 80 steps, and identical source strength. The observed concentration profiles were:

| Scenario | Diffusion | Degradation | Uptake | Total mass | Concentration profile (source → far end) |
|---|---:|---:|---:|---:|---|
| Low transport | 0.05 | 0.10 | 0.00 | 10.0050 | 7.2732, 2.0220, 0.5257, 0.1365, 0.0354, 0.0092, 0.0029 |
| Medium transport | 0.25 | 0.10 | 0.00 | 9.9987 | 4.5433, 2.5545, 1.3637, 0.7324, 0.4017, 0.2360, 0.1672 |
| High transport | 0.80 | 0.10 | 0.00 | 9.9972 | 2.9446, 2.1766, 1.5591, 1.1390, 0.8631, 0.6966, 0.6183 |
| High removal | 0.25 | 0.80 | 0.25 | 0.9522 | 0.8151, 0.1230, 0.0128, 0.0013, 0.0001, 0.0000, 0.0000 |

### Interpretation

- Raising transport spread the signal farther and flattened the gradient while total mass stayed near 10.0. This is redistribution, not signal creation.
- Increasing degradation and uptake reduced total mass to 0.9522 and sharply localized the remaining signal.
- The numerical tests passed for closed-system mass conservation, no-transport isolation, monotonic source gradients, permeability barriers, uptake/degradation effects, receiver sensitivity, exposure duration, time-step refinement, signal-class separation, high-transport stability, and invalid parameter rejection.
- The high-removal case demonstrates that uptake and degradation can create a short-range field without requiring hard-coded communication cutoffs.

This validates the primitive's tested numerical behavior under the benchmark's assumptions. It does not validate a BA adaptation policy, a biological tissue model, or an improvement in regional environmental fitness.

## 9. Evolutionary boundary

This stage models only environmental signal transport and receiver response. It does not change:
- inherited NeuralDNA genotype;
- epigenetic/regulatory inheritance;
- NeuralStem lineage or differentiation;
- regional population sizes;
- mutation, recombination, or selection.

A signal-induced temporary response must not be mislabeled as genetic evolution. Any future hereditary change requires an explicit reproduction/lineage process and multi-generation fitness evaluation.

## 10. Decision gate

The isolated 0.8 field primitive now implements symmetric graph diffusion, adaptive stable substeps, exact first-order decay, bounded saturable uptake, Hill-like receiver response, and exposure memory. Its tests must establish the numerical invariants above. This primitive is not yet a regional adaptation policy. Do not integrate signal fields into NeuralStem or the Brain Artificial runtime until a separate environmental benchmark beats the 0.7 baselines across matched regimes and the improvement remains after accounting for transport, uptake, calibration, and computation costs.

The Brain Artificial (BA) remains a distinct artificial developmental and adaptive system, not conventional AI. K.IA remains a separate coordination runtime. External AI models are optional tools and do not define BA's internal architecture.

## 11. Ownership and third-party boundaries

The original design, equations as applied to this project, parameterization, benchmark protocol, tests, code, and documentation authored for AILocal Universal are project materials.

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

Scientific principles and publications remain attributed to their authors. This document does not claim ownership of morphogenesis, quorum sensing, diffusion, ecology, or third-party research.
