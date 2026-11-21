# NeuralDNA 0.7 — Spatial Communication and Niche Topology

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

> **Status:** isolated synthetic benchmark. This is not the Brain Artificial (BA) runtime, not a biological model, and not evidence of biological equivalence. No integration into NeuralStem is authorized by this experiment alone.

## 1. Research question

When should a developing region exchange information with nearby regions, and when does communication across distant or ecologically different regions corrupt local adaptation?

The 0.6 experiment established that a single global signal can aggregate noise in a shared niche but can fail when regions occupy divergent niches. Version 0.7 adds spatial organization: who can communicate with whom, how local signals are aggregated, how delay and packet loss affect usefulness, and whether communication boundaries should follow environmental boundaries.

**Primary hypothesis:** communication is beneficial when connected regions share predictive environmental structure; communication becomes harmful when it mixes incompatible niches or its latency/loss exceeds the predictive value of the signal.

## 2. Biological principles translated into testable abstractions

The design is grounded in mechanisms that are structurally different but complementary:

1. **Short-range cell signaling.** Some bacterial quorum-sensing signals remain local because uptake and degradation restrict their propagation. Local communication can reveal nearby community composition instead of a misleading global average.
2. **Morphogen gradients.** Developmental signals are shaped by production, transport, removal, concentration, exposure duration, and the state of the receiving cell. A signal is not simply a broadcasted label.
3. **Metacommunity ecology.** Local environmental filtering and dispersal interact. Excessive dispersal can replace locally adapted communities with regionally dominant types; too little dispersal can isolate populations and reduce exchange.
4. **Neural network communication.** Biological network communication involves topology, transmission delay, and metabolic cost. Connectivity is not free and more edges are not automatically better.
5. **Homeostasis and modularity.** Local subsystems need enough autonomy to preserve specialized responses while retaining controlled routes for coordination.

These are functional inspirations, not literal biological implementations.

### Research references

- Xu & Vinothkanna (2026), *Bacterial quorum-sensing systems in cell–cell communication*, FEMS Microbiology Reviews. https://doi.org/10.1093/femsre/fuag020
- *Spatial structure: shaping the ecology and evolution of microbial communities* (2026), FEMS Microbiology Reviews. https://doi.org/10.1093/femsre/fuaf067
- *Short-range quorum sensing controls horizontal gene transfer at micron scale in bacterial communities* (2021), Nature Communications. https://doi.org/10.1038/s41467-021-22649-4
- Kicheva & Briscoe (2023), *Control of Tissue Development by Morphogens*, Annual Review of Cell and Developmental Biology. https://doi.org/10.1146/annurev-cellbio-020823-011522
- *From species sorting to mass effects: spatial network structure mediates the shift between metacommunity archetypes* (2021), Ecography. https://doi.org/10.1111/ecog.05453
- *Brain network communication: concepts, models and applications* (2023), Nature Reviews Neuroscience. https://doi.org/10.1038/s41583-023-00718-5

## 3. What was tested before implementation

The parameter space was decomposed before coding:

| Variable | Values / control | Expected failure mode |
|---|---|---|
| Topology | line, ring, complete, clustered | isolation, overmixing, or useful local exchange |
| Region count | 1 to 8 in unit tests; 8 in CI benchmark | degenerate graphs and scaling |
| Niche structure | one shared niche; two spatially clustered niches | false consensus across boundaries |
| Local cue accuracy | 0.70–0.99 | noise aggregation versus noise propagation |
| Development latency | fixed, explicit | signal must target the phenotype's payoff time |
| Communication latency | fixed, explicit | stale signals |
| Signal anticipation | below, equal to, above delay | under/over-compensation |
| Message loss | 0–1 | brittle reliance on communication |
| Communication cost | 0–<1 | coordination with no net benefit |
| Randomness | paired deterministic seeds | irreproducible comparisons |

Analytical expectations:
- With one region, a ring must have zero self-edges.
- With a shared niche and independent cue noise, a sufficiently large local neighborhood can improve the estimate by aggregating independent observations.
- With spatially clustered but distinct niches, within-cluster exchange should outperform an all-to-all global vote.
- At 100% message loss, no neighbor signal may be used.
- If signal anticipation does not compensate for communication delay, a cyclic environment should expose stale messages.
- Adaptive communication must not be assumed superior: calibration, plasticity, and message costs may outweigh accuracy gains.

## 4. Model and contracts

Each region has:
- its own environmental sequence;
- a noisy local cue;
- an acquired local transition model;
- local calibration estimates;
- a set of allowed neighbors.

The graph is undirected and deterministic:
- **line:** only adjacent regions;
- **ring:** adjacent regions plus wraparound;
- **complete:** all regions can exchange messages;
- **clustered:** regions exchange only within their declared niche cluster.

A sender predicts the environmental state at horizon:

`H_{send} = L_{development} + A`

where `A` is the explicit signal-anticipation setting. The message arrives after `L_{communication}`. Correct alignment requires `A = L_{communication}` for this simplified fixed-delay experiment.

The receiving region aggregates only messages that were emitted by its allowed neighbors and survived message loss. The decision policy does not receive the future target state. Future states are used only to create noisy forecasts and score outcomes.

### Separation of state

- **Inherited genotype:** not modified in this experiment.
- **Epigenetic/regulatory state:** not modified in this experiment.
- **Acquired regional history:** local transition estimates learned from past observations.
- **Environmental evidence:** local cues and delayed neighbor messages.
- **Selection/evolution:** not implemented in this benchmark; no claim of genetic evolution is made.

This separation prevents online predictor calibration from being mislabeled as hereditary evolution.

## 5. Strategies compared

- `local_cue`: use only the local cue.
- `global_signal`: use a modal signal from every region.
- `neighbor_signal`: use the modal signal from allowed neighbors; fall back to the local cue if no message arrives.
- `local_history`: use only the acquired local transition model.
- `adaptive_network`: select among local cue, local history, global signal, and neighbor signal using past calibration outcomes.

The adaptive policy is an experimental baseline, not a selected BA architecture.

## 6. Metrics

- Geometric-mean fitness under explicit mismatch and coordination costs.
- Accuracy of local, global, neighbor, history, and selected predictions.
- Frequency of global and neighbor signal use.
- Message delivery rate.
- Regional environmental divergence.
- Mean graph degree.

The fitness equation is a synthetic comparison score, not biological fitness or a calibrated measure of survival.

## 7. Validation gates

The automated tests cover:
- exact line, ring, complete, and clustered graph connectivity;
- no communication across niche boundaries in clustered topology;
- deterministic paired-seed replay;
- bounded metrics for every strategy;
- improved local aggregation under a shared noisy niche;
- preservation of local information across divergent clusters;
- global mixing failure under incompatible niches;
- zero neighbor use under complete message loss;
- adaptive use of neighbor information when useful;
- anticipation matching communication delay;
- no self-communication for a one-region ring;
- invalid parameter rejection.

CI executes Ruff, the complete Python test suite, the prior anticipatory benchmark, this spatial benchmark, and Rust tests.

## 8. Known simplifications and next experiments

This version does **not** yet model:
- continuous physical distance;
- signal concentration, diffusion, uptake, degradation, or receptor saturation;
- multiple signal species or inhibitory/excitatory signals;
- bandwidth limits, message queues, congestion, or multi-hop routes;
- heterogeneous link costs;
- dynamic topology or adaptive rewiring;
- co-evolution of communication structure and regional specialization;
- population turnover, migration, mutation, or recombination.

The clustered graph is a deliberately simple compartment abstraction, not a physical tissue geometry. A complete graph is a stress baseline for overmixing, not a biological default.

### Next research gate

Version 0.8 should add distance-dependent signal attenuation and decay, followed by dynamic connection costs. The signal model should distinguish:
- production strength;
- transport distance and delay;
- environmental uptake/degradation;
- receiver sensitivity;
- exposure duration;
- local baseline and saturation.

Only after this is validated should we test adaptive rewiring. Rewiring must compare the marginal gain in prediction/coordination with energy, delay, interference, and lost local autonomy.

**Do not integrate 0.7 into NeuralStem yet.** First obtain stable paired-seed results, parameter sweeps, and ablations.

## 9. Ownership and third-party boundaries

The original code, tests, experimental protocol, architecture, and documentation created for this benchmark are AILocal Universal project materials.

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

Scientific principles and publications remain general knowledge and belong to their respective authors/publishers. This project does not claim ownership of biological mechanisms, third-party research, or external software.
