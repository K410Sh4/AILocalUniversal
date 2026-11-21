# NeuralDNA Environmental Integration 0.4 — Experimental Design and Validation Gate

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

> **Status: design and validation protocol only.** This document does not claim that environmental assessment is integrated into NeuralStem, that an evolutionary engine exists, or that any biological equivalence has been demonstrated.

## 1. Objective

Define a testable bridge between environmental assessment (0.3) and regional NeuralStem development (0.2), while preserving the separation between:

1. **NeuralDNA genotype:** inherited, versioned developmental predispositions and reaction norms.
2. **Epigenetic/developmental state:** acquired, reversible or stage-dependent expression state.
3. **Environmental assessment:** evidence about current and future conditions, with uncertainty and prediction history.
4. **NeuralStem phenotype:** the actual regional lineage and differentiated population produced under a niche and resource budget.
5. **Acquired memory:** experience and learned capability; not inherited automatically.

The target property is environmental contingency: the same genotype, exposed to different environmental histories, may produce different phenotypes, while repeated exposure to comparable conditions should produce reproducible outcomes under the same seed and policy.

## 2. Biological constraints translated into engineering rules

### 2.1 A cue must predict the selective environment, not merely describe the present

A cue is useful for anticipatory plasticity only when it predicts the future condition that determines which phenotype is advantageous. A signal that correlates with the current state but fails to predict the environment at the time the phenotype is expressed can cause maladaptive development.

**Design rule:** every cue record must declare its target variable and prediction horizon. Score the prediction against the realized target at that horizon, not automatically against the current state.

### 2.2 Volatility is not the same as unpredictability

A cyclic environment can change frequently and still be predictable. A stable environment can contain noisy, uninformative cues. The system must estimate separately:
- rate and magnitude of environmental change;
- predictability of transitions;
- uncertainty remaining after cue assessment;
- mismatch between predicted and realized selective conditions.

**Design rule:** do not map raw change rate directly to diversity reserve. Reserve should respond to residual uncertainty and the cost of being wrong, while cyclic predictability may support anticipatory specialization.

### 2.3 Plasticity has latency and developmental windows

A response that takes several development steps may arrive too late after an abrupt shift. Conversely, early developmental signals can be valuable when they reliably predict later conditions. Some traits may be reversible; others may be costly or impossible to reverse.

**Design rule:** each developmental response must declare latency, reversibility class, and the last useful decision point. A cue with a horizon shorter than the response latency must not trigger anticipatory specialization as if it were actionable.

### 2.4 Plasticity and bet-hedging are not interchangeable

Plasticity uses information to select a phenotype. Diversifying bet-hedging preserves multiple viable outcomes when information is insufficient. Conservative bet-hedging can reduce response magnitude. Their balance depends on cue reliability, environmental predictability, developmental latency, and costs.

**Design rule:** keep cue-driven fate bias and diversity reserve as independent controls. Do not treat reserve as random noise or force it to zero whenever cue reliability is high.

## 3. Proposed data flow — not yet implemented

```text
Environment observations
        |
        v
Cue registry (identity, source, target, horizon)
        |
        v
Assessment (calibration, uncertainty, change/predictability)
        |
        v
ReactionNorm + EpigeneticState
        |
        v
Regional DevelopmentPolicy
        |
        v
NeuralStem niche (demand, occupancy, resources, capacity)
        |
        v
Regional phenotype + measured outcomes
        |
        +------> cue calibration / developmental evaluation
        |
        +------> acquired memory (separate, non-heritable by default)
```

The assessment layer may recommend a policy; it must not directly mutate the inherited NeuralDNA. NeuralStem receives a bounded, explicit policy object. Its current lineage mechanics remain the authority for capacity, resource accounting, potency, and division limits.

## 4. Proposed policy contract

The future integration should pass an immutable policy containing, at minimum:

- cue/assessment identity and version;
- target environment and prediction horizon;
- calibrated cue reliability and predictive uncertainty;
- environmental change rate and residual unpredictability as separate values;
- plasticity sensitivity;
- diversity reserve;
- regional fate-bias multipliers;
- developmental latency and reversibility constraints;
- resource ceiling and policy provenance.

All numeric values must be finite and bounded. Unknown, stale, contradictory, or insufficient evidence must produce a conservative policy rather than silently defaulting to maximum plasticity.

The policy is an expression of genotype plus current state; it is not itself a genotype.

## 5. Mathematical candidate

Keep the existing 0.3 Beta-Bernoulli calibration as a narrow baseline for binary cue outcomes. Do not assume it is a sufficient general model for multiclass, continuous, correlated, or changing targets.

For a cue (c), define:
- (R_c): calibrated predictive reliability;
- (U_c): residual predictive uncertainty;
- (V): environmental change rate;
- (L): developmental response latency;
- (H_c): cue prediction horizon;
- (C_p): cost of plasticity;
- (C_m): cost of phenotype-environment mismatch.

A candidate actionability factor is:

```text
A_c = reliability_confidence(c)
      * max(0, 1 - U_c)
      * horizon_compatibility(H_c, L)
```

A candidate plasticity controller is:

```text
P = bounded_base + (bounded_max - bounded_base) * A_c * benefit_to_cost
```

A candidate reserve controller is:

```text
D = bounded_min + (bounded_max - bounded_min)
    * residual_uncertainty * mismatch_risk
```

These are **design hypotheses**, not validated laws or final equations. The functions `horizon_compatibility` and `benefit_to_cost` must be specified and tested before implementation. The reserve must not be driven by (V) alone: predictable cycles can have high change rate but low uncertainty.

## 6. Required pre-implementation experiment matrix

Use the same initial genotype, regional population, resource budget, and seeded environment sequences for every strategy. Include at least:

| Environment sequence | Cue quality | What it tests |
|---|---|---|
| Stable | Reliable | Avoid unnecessary developmental churn |
| Stable | Noisy | Separate cue noise from environmental change |
| Gradual drift | Reliable with lead time | Track a moving optimum without excessive lag |
| Gradual drift | Delayed / stale | Detect when evidence loses predictive value |
| Fast predictable cycle | Reliable | Learn recurring transitions without confusing volatility with uncertainty |
| Fast stochastic change | Unreliable | Preserve alternatives under genuine uncertainty |
| Abrupt shift | Initially reliable, then reversed | Forget stale evidence and recover |
| Adversarial cue | Systematically misleading | Prevent confident but harmful specialization |
| Multi-niche | Region-specific cues | Avoid one global policy overriding local requirements |
| Resource shock | Any cue quality | Preserve homeostasis and critical residents under constrained capacity |
| Novel regime | Unknown cue statistics | Fail safely and retain exploratory diversity |

Compare at least:
A. Existing NeuralStem with fixed policy.  
B. Fixed plasticity.  
C. Cue-assessed plasticity only.  
D. Diversity reserve only.  
E. Cue-assessed plasticity plus independent reserve.  
F. E with developmental latency/reversibility constraints.

Use identical seeds and paired comparisons. Report mean and geometric-mean validated quality, worst-case quality, failure rate, adaptation lag, recovery time, cue calibration error, phenotype diversity, retained prior performance, resource use, and lineage conservation. Include confidence intervals and ablations; do not promote a policy based on one seed or one scenario.

## 7. Invariants that every future implementation must preserve

1. Same seed and same inputs produce the same result.
2. Regional progenitor count never exceeds niche capacity.
3. No unselected resident progenitor is silently discarded.
4. Resource use never exceeds the available budget.
5. Every input and output probability is finite and bounded.
6. Differentiated + progenitor accounting equals initial population plus explicitly recorded divisions.
7. An environmental observation cannot mutate the inherited genotype.
8. Cue calibration is isolated by cue identity, target, horizon, and (where needed) region.
9. Stale evidence loses influence according to an explicit retention policy.
10. A high change rate does not automatically imply high uncertainty or maximum diversity reserve.
11. A cue cannot drive anticipatory specialization when its horizon is shorter than the response latency.
12. Failure or missing evidence selects a documented safe fallback.

## 8. Audit finding in the 0.3 synthetic experiment

The current experiment compares cue labels against the environment state at the same step. This tests contemporaneous classification, not anticipatory prediction of a future selective environment. It is useful as a first mechanism smoke test, but it does not validate cue horizon, developmental latency, or anticipatory plasticity.

Before using its results to justify NeuralStem integration, extend the experiment so cues predict a future state after a configurable lead time, and score the cue against that future state. Include cases where the cue predicts the current state accurately but the future state poorly, and vice versa. Keep the original benchmark as a baseline for comparability.

The 0.3 experiment also uses a synthetic fitness function and simplified three-state environment. Its scores are not biological evidence and do not measure K.IA or BA capability.

## 9. Implementation gates

Do not implement the integration until all of the following are met:

- The current PR #15–#17 test suites have actually run on their exact heads.
- The NeuralStem 0.2 capacity regression is confirmed by CI.
- The new predictive-horizon benchmark is implemented and its invariants are tested.
- The strategy comparison demonstrates when each policy wins and where it fails.
- Cue identity, target, horizon, persistence, and reset/forgetting semantics are specified.
- The integration contract does not violate genotype / epigenome / acquired-memory separation.
- Multi-region tests show local environmental cues do not collapse into one global response.
- Resource and population accounting remain conserved under all tested parameter combinations.

Only after these gates should the next code stage introduce a versioned integration object (provisionally `EnvironmentalDevelopmentPolicy`) and connect it to NeuralStem. Do not add recombination, mutation, or multi-generation selection in the same change; isolate causal mechanisms so failures remain attributable.

## 10. Scientific basis

- Hill, Pfennig & Pfennig (2024), “Assessment and the regulation of adaptive phenotypic plasticity,” *Development* 151(20), dev203101. https://doi.org/10.1242/dev.203101
- Sekajova et al. (2025), “Evolution of phenotypic plasticity during environmental fluctuations,” *Journal of Evolutionary Biology* 38(9), 1246–1255. https://doi.org/10.1093/jeb/voaf078
- “Harbingers of change: Towards a mechanistic understanding of anticipatory plasticity in animal systems” (2025), *Functional Ecology* 39(11), 2999–3020. https://doi.org/10.1111/1365-2435.70071
- Draghi (2023), “Bet-hedging via dispersal aids the evolution of plastic responses to unreliable cues,” *Journal of Evolutionary Biology* 36(6), 893–905. https://doi.org/10.1111/jeb.14182
- “The evolution of sensitive periods beyond early ontogeny: Bridging theory and data” (2024), *Functional Ecology* 39(11), 2962–2973. https://doi.org/10.1111/1365-2435.14615

Biological findings are translated into engineering hypotheses, not claimed as proof that the artificial system is biologically equivalent.

## 11. Ownership and provenance

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

This document records the project's original architecture, design choices, hypotheses, test plans, and implementation boundaries under the repository's proprietary project notice. Scientific concepts, cited publications, third-party code, datasets, and external materials remain subject to their respective authorship and licenses. This notice does not claim exclusive ownership over abstract scientific facts, biological mechanisms, or ideas that are not protected by copyright. See `LICENSE`, `NOTICE.md`, `THIRD_PARTY_NOTICES.md`, and `docs/PROJECT_IP_REGISTER.md`.

