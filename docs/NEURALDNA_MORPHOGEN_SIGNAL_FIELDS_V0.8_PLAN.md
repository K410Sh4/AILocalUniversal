# NeuralDNA 0.8 — Morphogen-like Signal Fields: Design and Validation Plan

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

> **Status: pre-implementation design and mathematical validation plan.** No signal-field runtime or BA integration is implemented in this document.

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

For region (i) and signal class (k), track free signal concentration (C_{i,k}). Each region can produce a signal based on a forecast it has already made. The field is transported over weighted spatial edges, then altered by local degradation and uptake.

A graph-diffusion step is:

`C^{diff}_{i,k} = C_{i,k} + Delta t,D
sum_j g_{ij}(C_{j,k}-C_{i,k})`

where:
- (D) is the transport coefficient;
- (g_{ij}=g_{ji}geq0) is edge conductance;
- conductance incorporates edge permeability and distance;
- the symmetric flux preserves total signal under closed-boundary diffusion before sources and sinks.

After transport, apply local decay and saturable uptake:

`C^{decay}_{i,k}=C^{diff}_{i,k}e^{-lambda_iDelta t}`

`U_{i,k}= min(C^{decay}_{i,k},
V_{max,i}Delta t,rac{C^{decay}_{i,k}}{K_{m,i}+C^{decay}_{i,k}})`

`C_{i,k}(t+Delta t)=max(0,C^{decay}_{i,k}-U_{i,k}+P_{i,k}Delta t)`

where (lambda_i) is degradation, (V_{max,i}) is maximum uptake, (K_{m,i}) controls uptake saturation, and (P_{i,k}) is local production.

Receiver response is a saturating threshold function:

`R_{i,k}=rac{C_{i,k}^{n_i}}{K_{d,i}^{n_i}+C_{i,k}^{n_i}}`

A separate exposure state can model duration:

`X_{i,k}(t+Delta t)=X_{i,k}(t)e^{-gamma_iDelta t}
+R_{i,k}Delta t`

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
| Transport (D) | zero → low → medium → high | When does the field become too mixed? |
| Distance | near → intermediate → far | How does physical separation affect signal? |
| Edge permeability | 0 → 1 | Can niche boundaries restrict cross-talk? |
| Degradation (lambda) | zero → fast | How far does a signal persist? |
| Uptake (V_{max}) | zero → high | Does local absorption sharpen the field? |
| Uptake saturation (K_m) | low → high | Does receiver/source saturation change range? |
| Sensitivity (K_d) | low → high | Which concentrations trigger a response? |
| Hill coefficient (n) | 1 → 4 | Does response become more switch-like? |
| Exposure clearance (gamma) | slow → fast | Does duration matter beyond peak concentration? |
| Production (P) | sparse → distributed | How do local sources and multiple sources interact? |
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

## 8. Evolutionary boundary

This stage models only environmental signal transport and receiver response. It does not change:
- inherited NeuralDNA genotype;
- epigenetic/regulatory inheritance;
- NeuralStem lineage or differentiation;
- regional population sizes;
- mutation, recombination, or selection.

A signal-induced temporary response must not be mislabeled as genetic evolution. Any future hereditary change requires an explicit reproduction/lineage process and multi-generation fitness evaluation.

## 9. Decision gate

Implement the 0.8 benchmark only after the numerical invariants above are covered by tests. Do not integrate signal fields into NeuralStem or the Brain Artificial runtime until the model beats the 0.7 baselines across matched environmental regimes and the improvement remains after accounting for transport, uptake, calibration, and computation costs.

The Brain Artificial (BA) remains a distinct artificial developmental and adaptive system, not conventional AI. K.IA remains a separate coordination runtime. External AI models are optional tools and do not define BA's internal architecture.

## 10. Ownership and third-party boundaries

The original design, equations as applied to this project, parameterization, benchmark protocol, tests, code, and documentation authored for AILocal Universal are project materials.

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

Scientific principles and publications remain attributed to their authors. This document does not claim ownership of morphogenesis, quorum sensing, diffusion, ecology, or third-party research.
