# NeuralDNA 0.9 — Field-Coupled Regional Adaptation: Design Gate

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

> **Status: pre-implementation experimental design.** No regional adaptation controller or NeuralStem integration is implemented in this stage.

## 1. Why 0.9 follows 0.8

NeuralDNA 0.7 established that topology and niche boundaries determine whether regional communication preserves or destroys useful local information. NeuralDNA 0.8 implemented and tested a continuous field primitive with transport, degradation, saturable uptake, receiver sensitivity, and exposure memory.

The next question is now specific:

**Can a region use a physically constrained local signal field to improve prediction of the environment in which its developing specialization will operate, without losing local adaptation through cross-niche mixing or stale signals?**

This stage combines the 0.5 anticipatory-development model, the 0.6 regional-niche model, the 0.7 topology model, and the 0.8 signal-field primitive in a benchmark only.

## 2. Biological principles

The controller is informed by four linked biological principles:

- **Local environmental selection:** a region's response should fit its own niche, not an average of unrelated environments.
- **Signal field:** information spreads through a medium and is shaped by transport, production, degradation, uptake, and receptor sensitivity.
- **Developmental timing:** a signal is useful only if it predicts conditions during the period when the developed phenotype provides value.
- **Homeostasis and history:** a region can combine current cues with acquired transition history, but neither acquired history nor temporary signal exposure is hereditary genotype.

The ecological balance between local selection and dispersal is non-monotonic in many metacommunity models. Greater exchange can initially support coexistence, then overwhelm local adaptation when regional mixing dominates. The benchmark must therefore sweep the transport range rather than assume that either zero or maximal diffusion is best.

## 3. Causal model and information boundary

At decision time (t):
1. Each region observes its own current state and produces a noisy local cue about the environment at (t + L_{development}).
2. The region emits a one-hot signal class derived only from that cue.
3. The 0.8 field transports, removes, and transforms emitted signals.
4. The receiving region observes local field response/exposure, not the future target.
5. A controller chooses among local cue, acquired local history, and field-derived prediction.
6. The environment at (t + L_{development}) is revealed only to score the decision and update calibration after the outcome.

No future target may enter the source generator, field transport, receiver policy, or calibration before the outcome is observed.

## 4. Variables to test

| Variable | Sweep | Hypothesis |
|---|---|---|
| Transport coefficient | 0, low, medium, high | Wider range helps only when connected regions share environmental structure |
| Degradation | low → high | Faster removal shortens memory and range |
| Uptake | zero → high | Local absorption can sharpen niche boundaries |
| Edge permeability | 0, partial, 1 | Physical/functional barriers reduce cross-niche interference |
| Receiver threshold | low → high | Weak fields should not dominate local evidence |
| Hill coefficient | 1 → 4 | Switch-like versus graded receiver response |
| Exposure clearance | slow → fast | Controls stale-signal persistence after environmental shifts |
| Source strength | low → high | Stronger sources improve reach but can saturate receivers |
| Local cue reliability | 0.55 → 0.99 | Determines whether field pooling has independent information to aggregate |
| Development latency | short → long | Determines which forecast horizon has payoff |
| Environmental volatility | stable, cycle, drift, abrupt, stochastic | Separates predictable change from residual uncertainty |
| Spatial autocorrelation | homogeneous, clustered, alternating, random | Determines whether local field pooling is useful |
| Niche boundary permeability | closed → open | Tests whether field transport should cross ecological boundaries |

Use paired seeds and independent cue-noise streams. Keep the same source forecasts across communication strategies.

## 5. Strategies and baselines

- **local_cue:** use the region's own anticipatory cue.
- **local_history:** use the region's acquired transition model.
- **global_mode:** use the 0.7 global aggregate.
- **discrete_neighbor:** use the 0.7 neighborhood message baseline.
- **field_only:** use the 0.8 field-derived regional signal.
- **adaptive_field:** choose among local cue, local history, and field signal using only previously observed calibration outcomes.

The field-only and adaptive-field strategies must be compared against the best simple baseline, not only against a weak global strategy.

## 6. Required tests before implementation

1. **No-diffusion equivalence:** with (D=0), a region must not receive information from other regions.
2. **Within-niche pooling:** when regions share a predictable environment and have independent cue noise, field pooling may improve accuracy over a single cue.
3. **Boundary protection:** zero permeability must prevent cross-niche signal transfer.
4. **Cross-niche mixing:** open boundaries and excessive transport must be able to degrade local accuracy in deliberately divergent environments.
5. **Signal persistence:** slower clearance should increase post-shift lag when the environment changes abruptly.
6. **Removal recovery:** stronger degradation/uptake should reduce old-signal persistence; it may also reduce useful range.
7. **Receiver thresholds:** weak exposure must not override a more reliable local predictor merely because it is nonzero.
8. **Developmental horizon:** field cues must target the phenotype payoff horizon, not the current environment by default.
9. **No lookahead:** future target changes must not alter the policy input before the outcome is observed.
10. **Adaptive controller restraint:** when the field is uninformative, the controller should stop using it rather than force communication.
11. **Cost accounting:** include source production, transport, uptake, exposure memory, and controller computation in the synthetic cost model.
12. **Determinism:** paired seeds and replay must produce identical outputs.

## 7. Metrics

- Geometric-mean synthetic fitness across development/payoff windows.
- Accuracy of local cue, local history, field prediction, and selected prediction.
- Calibration and Brier score for probabilistic predictions, if the field exposes calibrated distributions.
- Adaptation lag after abrupt regime changes.
- Cross-niche interference rate.
- Effective field range and concentration/exposure profiles.
- Signal mass removed by degradation/uptake.
- Transport and receiver computation cost.
- Local/regional diversity and recovery after environmental shifts.

Accuracy alone is insufficient: a field can predict well but impose costs that reduce total fitness.

## 8. Evolutionary boundary

This experiment is a lifetime environmental-response benchmark. It does not change inherited genotype, epigenetic inheritance, NeuralStem lineages, population size, mutation, or recombination.

The learned transition model and predictor calibration are acquired state. Field exposure is a temporary regulatory input. Neither is a heritable change unless a later, explicit lineage mechanism copies a validated trait into offspring under controlled selection.

## 9. Integration gate

Do not integrate the controller into NeuralStem or the Brain Artificial (BA) runtime until:
- the field beats local-history and local-cue baselines in the environmental regimes where it is expected to help;
- gains survive parameter sweeps and ablations;
- cross-niche harm is bounded;
- adaptation lag after shifts is acceptable;
- all signal and compute costs are included;
- no-lookahead and deterministic replay tests pass.

A failed hypothesis is a useful result. The objective is not to prove that field communication always helps, but to discover the conditions under which local regions should communicate, remain autonomous, or change their signal range.

The Brain Artificial (BA) remains a distinct artificial developmental and adaptive system, not conventional AI. K.IA remains a separate coordination runtime.

## 10. Research references

- Kicheva & Briscoe (2023), *Control of Tissue Development by Morphogens*, Annual Review of Cell and Developmental Biology. https://doi.org/10.1146/annurev-cellbio-020823-011522
- Suzuki & Economo (2021), *From species sorting to mass effects: spatial network structure mediates the shift between metacommunity archetypes*, Ecography. https://doi.org/10.1111/ecog.05453
- *Short-range quorum sensing controls horizontal gene transfer at micron scale in bacterial communities* (2021), Nature Communications. https://doi.org/10.1038/s41467-021-22649-4
- Stapornwongkul & Vincent (2021), *Generation of extracellular morphogen gradients: the case for diffusion*, Nature Reviews Genetics. https://doi.org/10.1038/s41576-021-00342-y

These publications support the research questions about signal range, local uptake, spatial mixing, and regional adaptation. They do not validate this project's specific algorithm or establish biological equivalence.

## 11. Ownership and scientific attribution

The original research design, causal contracts, benchmark protocol, tests, and code authored for AILocal Universal are proprietary project materials.

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

Scientific concepts and cited research remain attributed to their respective authors; this project claims only its original expression and implementation.
