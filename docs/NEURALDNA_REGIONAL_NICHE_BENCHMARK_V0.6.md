# NeuralDNA Regional Niche Benchmark 0.6

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

> **Status: isolated multi-region benchmark and hypothesis test.** This stage does not modify NeuralStem, the inherited genotype, or the BA runtime.

## 1. Biological question

A multicellular organism does not experience one perfectly uniform environment. Cells and tissues occupy local microenvironments shaped by neighboring cells, soluble signals, extracellular matrix, physical constraints, nutrient and oxygen gradients, and local feedback. A shared organism-level signal can coordinate behavior, but it can also erase information that is essential to a local niche.

The computational question is:

**When should a BA region trust its local environmental evidence, and when should it accept information shared by other regions?**

This benchmark treats each cognitive region as a local niche. Regional adaptation is evaluated separately before any organism-wide aggregation.

## 2. Biological grounding

The design borrows functional principles, not literal biological mechanisms:

- **Local niche:** resident units respond to the local ecosystem rather than assuming that a global average describes every location.
- **Spatial heterogeneity:** different regions can have different transition structures and therefore different useful response policies.
- **Short-range communication:** shared signals have a transport delay and a cost. A signal may be informative when emitted and stale when received.
- **Signal anticipation:** a sender can compensate for transport delay only when it has reliable information about the future state at the time the signal arrives.
- **Homeostasis and diversity:** a region should retain a limited reserve when its best predictor is weak, rather than forcing all regions into one phenotype.
- **Multi-scale coordination:** global coordination is useful when regions share a niche; local autonomy is useful when niches diverge.

Recent research emphasizes that spatial organization, local gradients, boundaries, and cell-cell interactions affect cellular behavior and tissue function. A 2026 review distinguishes a biological niche as an ecosystem from a merely proximity-based neighborhood or computational spatial domain. This distinction motivates explicit local-environment contracts rather than a single undifferentiated global state.

References:
- Liu & Li (2026), *A unified framework for defining and analyzing spatial niches in spatial omics data analysis*, Nature Genetics. https://doi.org/10.1038/s41588-026-02813-6
- Truong et al. (2026), *Strategies to control cellular spatial organization in microphysiological systems*, Microsystems & Nanoengineering. https://doi.org/10.1038/s41378-025-01141-9
- *Spatial structure: shaping the ecology and evolution of microbial communities* (2026), FEMS Microbiology Reviews. https://doi.org/10.1093/femsre/fuaf067
- Keshavarz & Ebrahimkhani (2026), *Synthetic tissue ecology: Ecological control of developmental self-organization across scales*, Cell Systems. https://doi.org/10.1016/j.cels.2026.101699

These publications motivate the hypotheses; they do not validate the artificial model or imply biological equivalence.

## 3. Experimental variables

| Variable | Meaning | Tested effect |
|---|---|---|
| Region count | Number of local niches | Scaling and aggregation |
| Regional process | Stable, cycle, stochastic, or drift | Local predictability |
| Cue accuracy | Reliability of local and emitted signals | Trust calibration |
| Development latency | Time between decision and phenotype expression | Anticipatory requirement |
| Communication latency | Delay before a shared signal arrives | Staleness |
| Signal anticipation | Extra forecast horizon used by the sender | Compensation for transport delay |
| Communication cost | Penalty when a region uses a shared signal | Coordination trade-off |
| Regional divergence | Fraction of regions in different target states | Degree of niche heterogeneity |

The benchmark uses paired seeds and independent random streams for local cues and shared signals.

## 4. Shared signal model

Each region emits a prediction about its own future state. The shared channel broadcasts the modal prediction from all regions. A receiving region sees that signal only after the configured communication delay.

The required forecast horizon is:

`H_{signal} = L_{development} + L_{communication}`

The benchmark exposes `signal_anticipation` separately. If anticipation does not compensate for communication latency, the received signal can be stale. The evaluator compares predictions with the realized future state, but that future state is never provided to the decision policy.

This is a deliberately simple communication model. It does not yet model topology, distance-dependent attenuation, bandwidth, packet loss, or multi-hop routing.

## 5. Compared strategies

- **local_cue:** specialize from the region's own cue.
- **global_signal:** use the shared signal, falling back to local history before the signal arrives.
- **local_history:** forecast from the region's acquired Markov transition model.
- **adaptive_local:** select between local cue and local history; maintain a reserve when both are uncertain.
- **adaptive_network:** select among local cue, local history, and shared signal; pay communication cost when the shared channel is selected.

The acquired transition model and predictor calibration are region-specific. They are runtime experience, not inherited genotype and not epigenetic marks.

## 6. Required hypotheses

1. In a common niche with independent signal noise, aggregation can improve shared-signal reliability.
2. In divergent niches, local cues should outperform a shared majority signal for at least some regions.
3. An adaptive network should use shared signals when they add predictive value, not merely because they are available.
4. A shared signal delayed by communication latency should become stale when the sender does not anticipate that delay.
5. Matching signal anticipation to transport delay should recover performance only when the environment is sufficiently predictable.
6. Regional diversity reserve should respond to predictive uncertainty, not raw environmental change rate.
7. No communication strategy should dominate across all niche configurations.

## 7. Validation gate

Automated tests cover determinism, bounded outputs, local-vs-global performance under divergent niches, noise aggregation in a shared stochastic niche, adaptive signal selection, communication-delay compensation, and invalid parameter rejection.

Before integration into NeuralStem, run paired-seed sweeps over:
- 1, 2, 4, 8, and 16 regions;
- stable, cyclic, stochastic, abrupt, and gradual-drift niches;
- cue reliability and cue-horizon mismatch;
- development and communication latency;
- signal anticipation and communication cost;
- local/global signal loss and correlated errors;
- alternative aggregation rules and region-specific network topologies.

Report per-region distributions and worst-region performance, not only a global mean. A high average must not conceal a region that is consistently harmed by global coordination.

Do not add mutation, recombination, or multi-generation selection in this stage. Do not connect the controller to NeuralStem until the local/shared policy demonstrates repeatable gains over local-only and global-only baselines.

## 8. Limits

The model has discrete states, synthetic cues, a majority-vote broadcast, and simple multiplicative fitness. It omits continuous spatial fields, cell populations, developmental morphogens, real signal transport, energy budgets, topology learning, and biological regulatory networks. Its output is an engineering comparison, not a biological claim.

The next experimental refinement should introduce spatially structured regions and weighted neighborhood communication. Only after that should the project define a production `RegionalEnvironmentalPolicy` contract.

## 9. Ownership and provenance

This document, benchmark implementation, tests, and original experimental protocol are original AILocal Universal project materials, subject to the project's proprietary license. Scientific concepts and cited publications remain attributable to their respective authors.
