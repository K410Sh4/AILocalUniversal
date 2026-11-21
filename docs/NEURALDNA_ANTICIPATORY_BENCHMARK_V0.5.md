# NeuralDNA Anticipatory Benchmark 0.5

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

> **Status: isolated benchmark and hypothesis test.** This stage does not integrate environmental policy into NeuralStem, modify NeuralDNA genotype, or claim biological equivalence.

## 1. Objective

Test whether environmental assessment can distinguish a cue that describes the present from a cue that predicts the environment when a developed phenotype becomes active.

The experiment isolates four quantities:

- **Environmental change rate:** how often the environment changes.
- **Transition predictability:** uncertainty in the next state after observing the current state.
- **Cue predictive value:** how accurately a cue predicts the environment at response time.
- **Developmental latency:** the interval between receiving a cue and expressing the selected phenotype.

The question is not whether the system recognizes the current environment. It is whether it chooses a developmental response that remains useful when that response becomes active.

## 2. Biological basis

The design follows three findings from plasticity and bet-hedging research:

1. Anticipatory plasticity requires cues that predict the future selective environment, not merely the current state.
2. A longer interval between cue perception and selection can reduce predictive reliability.
3. Plasticity and bet-hedging can coexist when environmental variation has both predictable and unpredictable components.

References:
- [Harbingers of change: Towards a mechanistic understanding of anticipatory plasticity in animal systems (2025)](https://doi.org/10.1111/1365-2435.70071).
- [Bet-hedging via dispersal aids the evolution of plastic responses to unreliable cues (2023)](https://doi.org/10.1111/jeb.14182).
- [When Unreliable Cues Are Good Enough (2013)](https://doi.org/10.1086/671161).
- [Evolution of phenotypic plasticity during environmental fluctuations (2025)](https://doi.org/10.1093/jeb/voaf078).

These works motivate the hypotheses; they do not validate this artificial model.

## 3. Experimental model

The environment has three abstract states. Each trial creates a reproducible environmental sequence and a cue sequence from an independent random stream.

A cue received at time t predicts the state at t+H, where H is its prediction horizon. A developmental response becomes active at t+L, where L is its latency.

The cue is scored against the state at t+L, not automatically against the state at t. A cue can therefore describe the present accurately and still be useless when development finishes.

### Environment processes

| Process | Change rate | Transition structure |
|---|---|---|
| Stable | Low | Persistent state |
| Cycle | High | Deterministic, repeatable transitions |
| Stochastic | Variable/high | Probabilistic transitions |
| Abrupt | Low on average | Sudden regime change |
| Drift | Gradual | Deterministic moving state |

The cycle process can change at every step while having near-zero conditional transition entropy. This tests whether the system confuses volatility with unpredictability.

### Acquired environmental model

A bounded Markov transition estimator learns from observed transitions. It is an **acquired environmental state**, not inherited genotype and not an epigenetic mutation.

The estimator forecasts the state at the response horizon. Its normalized forecast entropy is retained as a diagnostic. Separately, both the cue and history predictors are calibrated against the realized state at the response horizon. The adaptive controller assigns cue-guided plasticity only to the cue's measured advantage over the acquired history forecast. Diversity reserve follows a convex response to residual uncertainty: reserve = 0.02 + 0.75 × residual_uncertainty². This keeps reserve small when at least one predictor is reliable and increases it rapidly when both are weak. Decayed transition evidence allows old environmental patterns to gradually lose influence after a regime change.

### Cue calibration

The cue and history trackers evaluate predictions against the environment at the response time. Both use a three-state chance baseline of 1/3, rather than assuming binary random-guess accuracy of 1/2. Predictive skill is discounted by evidence volume. The controller measures the cue's advantage over the history model instead of assuming that any accurate cue is better than an already stronger environmental forecast.

The cue generator uses the future trace only to synthesize a signal with a controlled predictive relationship. The decision policy receives the cue token, current environmental observation, and acquired transition model; the future state is used only by the evaluator to score the result. This is a synthetic experimental setup, not privileged future access in the agent.

## 4. Compared strategies

- **Generalist:** fixed robust phenotype.
- **Plastic:** always follows the current cue.
- **Hedge:** follows the cue while reserving half the population for a diversified portfolio.
- **History:** uses only the acquired transition model.
- **Adaptive:** combines cue-guided specialization, history-based prediction, and diversity reserve.
- **Adaptive plasticity:** ablation without diversity reserve.
- **Adaptive reserve:** ablation without cue-guided specialization.

The synthetic fitness function exposes the trade-off between a matching specialist, a mismatched specialist, a generalist, and a diversified population. Plasticity and reserve costs are explicit.

The benchmark reports geometric-mean fitness, cue accuracy at response, history forecast accuracy, mean plasticity, mean reserve, forecast-distribution uncertainty, environmental change rate, and transition entropy.

## 5. Hypotheses

- A reliable cue whose horizon matches developmental latency should support anticipatory specialization.
- A cue that describes only the current state should lose value when the environment changes before development completes.
- A deterministic fast cycle should have high volatility but low transition entropy.
- A stochastic environment should have greater residual forecast uncertainty than a deterministic cycle.
- A history-based predictor should exploit stable or cyclic regularities even when the external cue is noisy.
- Diversity reserve should respond to residual uncertainty and fitness trade-offs, not raw change rate alone.
- No strategy should be assumed universally superior; outcomes depend on cue reliability, environmental structure, latency, and phenotype costs.

## 6. Validation and limits

Automated tests cover determinism, bounded outputs, horizon/latency alignment, the volatility-versus-entropy distinction, reserve response to residual uncertainty, whether adaptive plasticity follows the predictor with greater measured skill, and suppression of stale current-only cues.

The benchmark is synthetic and deliberately small. It does not yet model cue identity, multiple or correlated cues, individual differences in perception, continuous environmental variables, sensitive developmental windows, reversibility, migration, inter-regional communication, multi-generation inheritance, mutation, recombination, or natural selection.

A three-state Markov predictor can miss higher-order periodic structure and regime changes. Compare it with alternative predictors before using it as a production environmental assessor.

Synthetic fitness values are engineering parameters, not empirical biological measurements.

## 7. Integration gate

Do not connect this benchmark's controller to NeuralStem yet. First:

1. Run paired-seed experiments across all scenarios.
2. Record where cue-based, history-based, and diversified strategies win or fail.
3. Sweep cue horizon, developmental latency, cue accuracy, transition memory, and mismatch cost.
4. Add multi-region scenarios with different local transition structures.
5. Confirm that reserve does not rise solely because change rate is high.
6. Define provenance for acquired environmental state and its reset/forgetting behavior.
7. Only then specify a versioned EnvironmentalDevelopmentPolicy contract.

Do not combine this stage with mutation, recombination, or multi-generation selection. Keep each causal mechanism independently testable.

## 8. Ownership and provenance

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

This document and the original benchmark implementation record the project's design choices, hypotheses, parameterization, test protocol, and implementation. Scientific concepts and cited publications remain attributable to their respective authors and are not claimed as exclusive property. See LICENSE, NOTICE.md, THIRD_PARTY_NOTICES.md, and docs/PROJECT_IP_REGISTER.md.
