# BA Developmental Substrate 0.1 — Domain Contracts and Validation Gates

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

> **Status:** architecture specification and pre-implementation validation plan. This document does not claim that the developmental substrate is implemented.

## 1. Architectural decision

The audit established that the current Rust K.BA runtime graph represents capabilities, providers, executors and routes. It is not a model of the Brain Artificial itself.

The project therefore separates two independently versioned domains:

1. **K.BA Runtime Graph:** plans and coordinates operations, adapters, external providers, persistence and resource admission.
2. **BA Developmental Substrate:** represents the BA's own regions, units, local environments, signals, regulation, development, phenotype and lineages.

The BA substrate must not depend on an LLM, Transformer, Ollama, model weights or the K.BA planner to define its internal identity. External AI models may be optional providers through adapters, never the organismal substrate.

Proposed future Rust boundary: an independent `ba_core/` crate with deterministic simulation and versioned contracts. K.BA can host or coordinate it through a narrow interface; neither crate owns the other's state.

## 2. Biological principles translated into engineering hypotheses

### 2.1 Morphogenesis: source, transport, removal and interpretation

Developmental signaling is not just broadcast messages and not every pattern is a simple diffusion gradient. Spatial profiles can depend on localized/distributed production, diffusion or directed transport, removal, barriers, signal trapping, local feedback and the receiving unit's interpretation. Reaction-diffusion mechanisms can also produce patterns without a unit reading its absolute position. This motivates a family of signal mechanisms rather than one universal gradient model: explicit sources, transport edges, sinks, receptor sensitivity, temporal exposure, trapping and local reaction terms.

Evidence:
- Kicheva & Briscoe (2023), *Control of Tissue Development by Morphogens*, Annual Review of Cell and Developmental Biology. https://doi.org/10.1146/annurev-cellbio-020823-011522
- *Mobile signals, patterning, and positional information in root development* (2024), Plant Physiology. https://doi.org/10.1093/plphys/kiae532
- *Diffusion barriers imposed by tissue topology shape Hedgehog morphogen gradients* (2024), PNAS. https://doi.org/10.1073/pnas.2400677121

### 2.2 Ecology: local filtering and regional dispersal

A set of local niches connected by dispersal can preserve local specialists or overwhelm them with regionally abundant signals/organisms. The balance between environmental selection and dispersal matters; a fully connected global graph is not automatically optimal.

Evidence:
- *Biodiversity conservation through the lens of metacommunity ecology* (2020). https://doi.org/10.1111/nyas.14378
- Suzuki & Economo (2021), *From species sorting to mass effects: spatial network structure mediates the shift between metacommunity archetypes*. https://doi.org/10.1111/ecog.05453
- Moisset de Espanés et al. (2026), *Dispersal mode and spatial heterogeneity shape the interaction between adaptation and dispersal in multitrophic metacommunities*. https://doi.org/10.1038/s41598-026-59353-6

### 2.3 Homeostasis and metaplasticity

Homeostatic plasticity can regulate the operating range within which more selective plasticity occurs. This motivates separating local activity stabilization from task-specific connection changes. Do not collapse both into one scalar reward update.

Evidence:
- Li et al. (2019), *Homeostatic synaptic plasticity as a metaplasticity mechanism*. https://doi.org/10.1016/j.conb.2018.08.010

These are biological design inspirations, not proof that the proposed computational mechanisms will work. Every translation requires ablation, baselines and measured costs.

## 3. Proposed domain contracts

| Entity | Required state | Responsibility |
|---|---|---|
| `EnvironmentState` | schema/version, time-step, observable local conditions, resource availability, pressure signals, uncertainty/provenance | Describe the current environment without leaking hidden future state |
| `Niche` | stable ID, boundary, environmental constraints, resource profile, interaction rules | Define the local conditions under which units persist and specialize |
| `Region` | ID, parent, niche ID, local budget, units, subregions, boundary and neighbors | Maintain a local adaptive domain |
| `Subregion` | ID, parent region, niche modifiers, units, local connections | Represent a finer spatial/functional scale |
| `Unit` | ID, type, internal state, receptors, energy budget, activity range, plasticity state | Receive local stimuli, respond, learn and specialize |
| `Connection` | endpoints, direction/type, weight, delay, bandwidth, permeability, reliability, energy cost | Carry local interactions under physical/computational constraints |
| `SignalField` | signal class, concentration state, source map, transport topology, sinks, exposure state, optional reaction/trapping rules | Represent signals distributed through a spatial medium without assuming every pattern is a simple gradient |
| `Receptor` | signal class, sensitivity, threshold, response curve, adaptation and recovery state | Interpret signal concentration and exposure |
| `HomeostaticState` | target activity range, energy reserve, saturation, recovery rate, diversity floor | Keep local activity and resource use inside viable bounds |
| `DevelopmentProgram` | stages, prerequisites, differentiation rules, maturation criteria, rollback state | Build phenotype gradually from inherited predispositions and experience |
| `NeuralGenome` | schema, loci, lineage, inheritance permissions, provenance | Encode heritable predispositions and development rules |
| `EpigeneticState` | context marks, scope, origin, confidence, expiry/reversibility | Modulate expression without silently rewriting the genome |
| `PhenotypeSnapshot` | realized topology, unit/region configuration, schema, parent lineage, environment | Record the developed system, distinct from its genotype |
| `FitnessVector` | per-region performance, worst-region performance, retention, resilience, resource cost, diversity | Evaluate multi-objective survival/adaptation without hiding local collapse in a global mean |

IDs and schemas must be stable and versioned. Unknown future fields must not be silently interpreted as trusted capabilities. A unit is a computational primitive, not a claim of a literal biological neuron or cell.

## 4. Four timescales — never conflate them

1. **Fast response:** signal transport, receptor response and unit activity.
2. **Within-lifetime adaptation:** local plasticity, reinforcement, decay, consolidation and homeostasis.
3. **Development:** differentiation, subregion formation, maturation and structural reorganization.
4. **Across generations:** lineage, heritable variation, recombination, mutation, selection and inheritance.

A temporary signal response is not a developmental change. A developmental change is not a genetic mutation. A successful task is not automatically evidence of reproductive fitness.

## 5. Local-first adaptation loop

```text
Current local environment
    -> local sources / resource fields
    -> transport through bounded topology
    -> receptor sensitivity + exposure
    -> unit response
    -> local interaction and behavior
    -> measured outcome and energy cost
    -> local plasticity + homeostatic regulation
    -> candidate differentiation / structural change
    -> evaluation across environments
    -> preserve, rollback or (later) inherit
```

Regional aggregation is allowed, but local evidence remains available. A global signal is advisory and must be weighted by reliability, relevance, latency, spatial distance and local disagreement. Do not force consensus when niches diverge.

## 6. Core invariants

- Environment observations are time-stamped; future hidden targets never enter the policy input.
- Local state changes must be attributable to signals, actions, resource constraints or explicit development rules.
- Signal mass changes only through declared production, uptake, degradation or boundary loss.
- Transport must respect edge permeability, distance, topology and bounded latency.
- Unit activity, resource use and connection growth must have explicit ceilings and recovery mechanisms.
- Homeostasis must not erase rare but useful specializations; maintain a configurable diversity reserve.
- Plasticity and structural change must be reversible until independently promoted.
- Genomes and parent lineages remain immutable; descendants are new versioned candidates.
- External model outputs are untrusted provider results, not inherited biological state or ground truth.
- K.BA execution/resource policies cannot mutate the BA genotype directly.

## 7. Pre-implementation test matrix

| Dimension | Required cases |
|---|---|
| Region count | 1, 2, 4, 8, 16 |
| Topology | isolated, line, ring, grid, clustered, sparse irregular |
| Environmental structure | homogeneous, clustered, gradient, patchy, rapidly changing |
| Niche divergence | none, moderate, high |
| Signal mechanism | diffusion, directed transport, reaction-diffusion, trapping, local feedback, hybrid |
| Signal loss | degradation, uptake, blocked edges, partial barriers, message loss |
| Delay | zero, fixed latency, variable latency, stale signal |
| Resource stress | abundant, constrained, sudden shortage, region-specific scarcity |
| Adaptation | local-only, global-only, neighbor, field-based, adaptive-local, hybrid |
| Development | no differentiation, staged differentiation, reversible specialization |
| Evolution | one lineage, multiple lineages, controlled mutation, recombination, selection |
| Failure | region disconnect, corrupted snapshot, unstable rates, energy depletion, missing provider |

Paired seeds and identical environments are mandatory. Compare against simple local-only and static baselines before claiming an adaptive advantage.

## 8. Required metrics

Report more than global mean:
- mean and worst-region fitness;
- variance and distribution of regional performance;
- time to adapt after environmental change;
- retention of previously useful specialization;
- interference and cross-niche contamination;
- signal cost, energy cost, compute, memory and I/O;
- recovery after disconnection or resource loss;
- diversity retained and number of collapsed regions;
- development cost and rollback frequency.

A policy that improves global mean while destroying one niche fails the preservation criterion unless the trade-off was explicitly specified and accepted.

## 9. Integration gates

**Gate A — numerical substrate:** deterministic state transitions, bounded values, conservation/decay tests, reproducible seeds and snapshot validation.

**Gate B — local adaptation:** outperform local/static baselines across heterogeneous niches without unacceptable worst-region regression.

**Gate C — homeostasis and development:** demonstrate stability, recovery, specialization retention and controlled differentiation.

**Gate D — lineage/evolution:** demonstrate multi-generation improvement and diversity retention; no hereditary integration before this gate.

**Gate E — K.BA integration:** versioned bridge only after the substrate has independent benchmarks and a stable API.

Do not merge this design into the runtime as an implementation claim. This PR is the contract boundary and validation plan only.

## 10. Ownership and third-party boundaries

Original domain contracts, architecture, benchmark protocols, implementation and documentation authored for AILocal Universal are covered by:

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

Scientific concepts and publications remain attributed to their authors. No claim is made over biological processes, research papers, third-party tools, Neuralink hardware, firmware, APIs, SDKs, data, marks or patents.
