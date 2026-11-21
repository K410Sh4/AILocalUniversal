# NeuralDNA — Environmental Adaptation and Eco-Evolutionary Development

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

> Research specification. The first cue-assessment/reaction-norm primitive is implemented experimentally in `neural_dna/environment.py`; full environmental evolution and BA integration remain unimplemented.

## 1. Core design decision

NeuralDNA must not encode a fixed brain blueprint that merely expands when resources are available. It should encode a **developmental reaction system**: rules that assess environmental conditions, express different phenotypes, regulate plasticity and preserve variation from which selection can act.

The target is not to imitate biological anatomy literally. It is to reproduce useful causal principles:

1. Environment is sensed, not assumed.
2. Signals are evaluated for reliability and predictive value.
3. Phenotype is produced by the interaction of genotype, current environment, developmental history and resource constraints.
4. Fast adaptation and slow evolution operate on different clocks.
5. The system preserves diversity when future conditions are uncertain.
6. The organism can alter its local environment, which then changes later selection pressures.

## 2. Biological findings translated into engineering constraints

### 2.1 Environmental assessment precedes adaptive plasticity

Organisms distinguish environmental stimuli from cues that predict future conditions. A response to a signal is not automatically adaptive: it is useful only when the signal carries information about which phenotype will perform better.

**AILU consequence:** NeuralStem must not differentiate solely because a demand scalar is high. It must evaluate:
- observed signal;
- signal confidence / calibration;
- prediction error;
- time horizon over which the signal remains predictive;
- cost of expressing and later reversing a phenotype.

Cue reliability must be measured against outcomes. It cannot be inferred from signal magnitude alone.

### 2.2 Plasticity and bet-hedging are different strategies

Plasticity selects a phenotype using environmental information. Bet-hedging retains or produces multiple phenotypes to reduce the risk that all descendants fail under an unpredictable environment. They may coexist, but neither dominates in every environment.

**AILU consequence:** Keep a controllable reserve of alternative developmental paths when cues are unreliable or environmental shifts are abrupt. Reduce that reserve when cues are calibrated and predictive. The reserve is a diversity budget, not random noise.

### 2.3 Evolvability itself can evolve

Digital evolution experiments have found distinct routes to evolvability: mutational neighborhoods that make previously encountered environments easier to revisit, and mutation-rate changes that can help adaptation to novel environments.

**AILU consequence:** Mutation rate and mutation topology may become evolvable meta-parameters, but only after measuring beneficial, neutral and harmful mutations. Do not simply raise mutation rates under stress. Stress-triggered exploration must be bounded, reversible and evaluated against protected lineages.

### 2.4 Environments are heterogeneous and change at different rates

Populations often face multiple environments, asymmetric selection pressures and different frequencies of exposure. Optimizing for the latest environment can destroy performance elsewhere.

**AILU consequence:** Selection must evaluate a distribution of environmental histories, not one benchmark or the most recent task.

## 3. Four interacting timescales

| Timescale | Biological analogy | NeuralDNA / BA mechanism | What may change |
|---|---|---|---|
| Fast | Physiological / behavioral response | Runtime adaptation and sparse routing | Active regions, route priorities, temporary thresholds |
| Intermediate | Acclimation and developmental plasticity | Epigenetic state and NeuralStem differentiation | Expression of developmental programs, regional specialization |
| Slow | Heritable evolution | NeuralDNA selection, recombination and mutation | Reaction norms, developmental rules, architecture priors |
| Ecological | Niche construction and coevolution | BA modifies caches, indexes, specialist demand and local resource landscape | Future demand, costs and selection pressures |

These layers must not be conflated. Runtime feedback must not silently rewrite inherited NeuralDNA. An acquired memory is not automatically a heritable trait. A genotype changes only through an explicit, versioned evolutionary event.

## 4. Genotype → assessment → phenotype

Represent the developed phenotype as:

```text
Phenotype(t) = Develop(
    NeuralDNA,
    EpigeneticState(t),
    AssessedEnvironment(t),
    ResourceBudget(t)
)
```

The environmental assessment layer should estimate a distribution over relevant states, not emit a single unqualified label:

```text
Assessment = {
    observed_signals,
    estimated_environment,
    cue_reliability,
    uncertainty,
    prediction_error,
    change_rate,
    resource_pressure
}
```

The reaction norm maps this assessment into developmental choices:

```text
DevelopmentPolicy = f(
    inherited_reaction_norm,
    epigenetic_history,
    assessment,
    regional_demand,
    resource_budget
)
```

The same NeuralDNA should be capable of producing different regional organizations under different environments. That is the central experimental property to demonstrate.

## 5. Evolutionary objective

Do not select descendants by a single instantaneous reward. Evaluate each candidate over repeated environmental sequences and use long-horizon performance.

A starting objective is:

```text
fitness(candidate) =
    mean_over_sequences(
        mean_over_steps(log(epsilon + validated_quality))
        - lambda_resource * resource_cost
        - lambda_failure * failure_penalty
        - lambda_instability * instability
    )
```

Use geometric mean performance (equivalently mean log fitness) to expose catastrophic failure across environments. Keep quality, latency, memory, energy, stability and recovery as separately reported metrics; do not hide trade-offs inside one opaque score.

Selection should preserve a Pareto set or multiple niches:
- specialists that perform exceptionally in recurring environments;
- generalists that remain competent across many environments;
- exploratory lineages with promising novelty;
- protected historical lineages for regression and rollback.

## 6. Environmental benchmark matrix

Every evolutionary candidate must be tested against the same seeded scenario suite:

| Environment | Characteristics | Main question |
|---|---|---|
| Stable | Low variance, persistent demand | Does plasticity waste resources? |
| Gradual drift | Slowly moving optimum | Can developmental memory track change without lag? |
| Cyclic | Recurring states | Can the system reuse adaptations without catastrophic forgetting? |
| Abrupt shift | Sudden change in demand or resource | How quickly can it recover? |
| Noisy cues | Signals poorly predict outcomes | Does assessment prevent maladaptive plasticity? |
| Multi-niche | Different regions need different capabilities simultaneously | Does specialization coexist without collapse? |
| Novel environment | Conditions outside the training distribution | Does the lineage retain evolvability? |
| Resource shock | Sudden RAM/VRAM/latency pressure | Can it reorganize while preserving critical functions? |

Compare at least these baselines:

A. Fixed genotype and fixed development.  
B. Fixed genotype with direct plastic response.  
C. Plastic response gated by measured cue reliability.  
D. Bet-hedging / diversity reserve without plastic response.  
E. Plasticity plus adaptive diversity reserve.  
F. E plus evolution of reaction norms and developmental rules.

## 7. Required measurements and acceptance gates

Measure:
- geometric mean validated quality across environment sequences;
- worst-environment performance and failure probability;
- adaptation lag after a change;
- recovery after resource shocks;
- cue calibration and prediction error;
- phenotype / regional diversity;
- retained performance in previously encountered environments;
- performance in novel environments;
- mutation yield: beneficial, neutral and harmful changes;
- compute, RAM, VRAM, energy and development time.

Do not promote a mechanism because it wins one seed or one environment. Require repeated seeds, confidence intervals, ablations and comparison to the fixed baseline. Preserve the full scenario suite and all seeds for reproducibility.

## 8. Corrections required before environmental evolution

The NeuralStem 0.2 implementation is a bounded lineage simulator, not an environmental evolutionary system. Its regions are independent, its fate choice is dominant, and its demand signal is not assessed for reliability or future predictive value.

A capacity edge case was also identified in 0.2: overflow handling could remove a resident progenitor that had not divided. The implementation was corrected so non-dividing residents are retained and newly generated daughters that cannot occupy the niche commit to differentiation. A dedicated regression test was added. The CI result is still required before treating the correction as verified in the repository environment.

The parameter sweep in the committed test enumerates **373,248** combinations, not 653,184. The documentation and PR description must use the code-derived count. The test suite defines 17 collected cases (14 test functions, one parameterized across four values); CI has not yet confirmed them.

## 9. Current repository state

- NeuralStem 0.2 implements bounded regional lineage dynamics; the capacity regression correction and environmental design are in PR #16.
- NeuralDNA Environmental Assessment 0.3 adds Beta-Bernoulli cue calibration with forgetting and a reaction norm that separates cue-supported plasticity from a volatility-sensitive diversity reserve; it is isolated in PR #17.
- PR #17 has not yet passed repository CI. The local independent mathematical prototype checked 484 evidence/volatility combinations, but that does not substitute for executing the committed test suite.
- No population-level evolutionary selection, crossover, mutation, multi-region communication or niche-construction feedback is implemented yet.

## 10. Implementation sequence

1. Stabilize and validate NeuralStem 0.2, including capacity regression and CI.
2. Implement environmental signals and assessment as an isolated deterministic module.
3. Test cue reliability, uncertainty and prediction error independently of development.
4. Implement reaction norms and compare plasticity against fixed development.
5. Add diversity reserve / bet-hedging and test cue-reliability thresholds.
6. Add multi-niche interaction and resource competition.
7. Add a multi-generation NeuralDNA population engine with protected lineages.
8. Evolve reaction norms and developmental rules before allowing topology growth.
9. Add bounded mutation-rate adaptation and mutational-neighborhood analysis.
10. Integrate successful mechanisms with BA/K.IA; keep runtime adaptation, acquired memory and heritable genotype as separate state domains.


## 10. First synthetic evidence

The 0.3 branch includes `experiments/neuraldna_reaction_norm_sweep.py` and a report in `docs/NEURALDNA_ENVIRONMENTAL_ASSESSMENT_V0.3.md`. In a three-state toy environment, cue-assessed plasticity plus a diversity reserve substantially reduced the collapse seen with fixed plasticity under noisy/adversarial cues, while remaining below fixed plasticity when cues were perfectly reliable. It did not dominate the fixed baseline in every scenario. This is exactly why cue reliability, volatility and strategy costs must be measured instead of hard-coded as universal rules. The experiment is synthetic and does not yet test NeuralStem development or multi-generation genetic evolution.

## 11. Scientific references

- Hill, Pfennig & Pfennig (2024), *Assessment and the regulation of adaptive phenotypic plasticity*, Development 151(20), dev203101. https://doi.org/10.1242/dev.203101
- Sekajova et al. (2025), *Evolution of phenotypic plasticity during environmental fluctuations*, Journal of Evolutionary Biology 38(9), 1246–1255. https://doi.org/10.1093/jeb/voaf078
- Kumawat et al. (2025), *Evolution takes multiple paths to evolvability when facing environmental change*, PNAS 122(1), e2413930121. https://doi.org/10.1073/pnas.2413930121
- *Evolutionary Adaptation in Heterogeneous and Changing Environments* (2025), Evolution 79(1), 119. https://doi.org/10.1093/evolut/qpae150
- Laland (2024), *Understanding niche construction and phenotypic plasticity as causes of natural selection*, Palaeontology 67(4), e12719. https://doi.org/10.1111/pala.12719

Scientific findings and third-party texts remain the property of their authors and publishers. This specification and the original AILU implementation proposals are covered by the project notice below.

## 12. Project ownership

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

This notice applies to original project code, schemas, documentation and implementation designs. It does not claim ownership of biological principles, scientific discoveries, cited papers or third-party code.
