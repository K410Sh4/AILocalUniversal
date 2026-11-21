# NeuralDNA Environmental Assessment 0.3

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

> Experimental module. It does not yet evolve NeuralDNA populations or build a complete BA.

## Purpose

Implement the first feedback loop required for environment-driven development: assess whether an environmental cue has actually predicted outcomes before allowing it to strongly influence plasticity.

## Model

Each cue owns an independent `CueCalibration` with a Beta-Bernoulli evidence model:

```text
successes(t+1) = retention * successes(t) + observed_correct
failures(t+1)  = retention * failures(t)  + observed_incorrect
reliability    = (prior_success + successes) /
                 (prior_success + prior_failure + successes + failures)
confidence     = evidence / (evidence + prior_strength)
signed_evidence = confidence * (2 * reliability - 1)
```

The retention parameter discounts stale evidence. This is important in changing environments: a cue that used to be predictive must lose influence when its predictions begin failing.

The inherited `ReactionNorm` converts calibrated evidence and measured environmental volatility into two separate controls:

- `plasticity`: increases only when evidence supports the cue;
- `diversity_reserve`: increases with volatility when cue evidence is weak or unreliable.

```text
plasticity = base + (maximum - base) * max(0, signed_evidence)
diversity  = base_reserve + (maximum_reserve - base_reserve)
             * volatility * (1 - max(0, signed_evidence))
```

This is a deliberately transparent starting rule, not a biologically calibrated law. It keeps adaptation and bet-hedging distinct and exposes their trade-off for experiments.

## Validation performed before commit

A local independent mathematical prototype checked:
- no evidence remains conservative;
- reliable cues increase plasticity;
- unreliable cues do not drive plasticity;
- volatility increases diversity reserve when evidence is weak;
- forgetting permits adaptation after cue reliability reverses;
- output bounds hold over a grid of 484 evidence-count/volatility combinations.

The committed Python test file defines 16 collected test cases. The repository CI for this branch has not yet run; therefore these tests are not reported as passed.

## Limits

- Cue calibration is currently one tracker per cue; persistence, cue registry and source identity are not implemented.
- Volatility is an input supplied by the environment monitor; its estimator is not implemented here.
- No evolutionary selection, crossover, mutation, genotype fitness or multi-generation lineage exists yet.
- The reaction norm returns developmental controls; NeuralStem does not yet consume these controls.
- The model is an engineering abstraction, not a direct simulation of biological learning.

## Next experiments

1. Validate volatility estimators under stable, cyclic, gradual, abrupt and stochastic environment sequences.
2. Connect reaction expressions to NeuralStem without allowing transient feedback to overwrite inherited genotype.
3. Compare fixed plasticity, cue-gated plasticity, bet-hedging and their combination.
4. Evaluate over multiple seeded environment sequences using geometric mean validated fitness and worst-case performance.
5. Only then introduce population-level NeuralDNA selection and coevolution of reaction norms.

## Scientific basis

- Hill, Pfennig & Pfennig (2024), *Assessment and the regulation of adaptive phenotypic plasticity*, Development 151(20), dev203101. https://doi.org/10.1242/dev.203101
- Sekajova et al. (2025), *Evolution of phenotypic plasticity during environmental fluctuations*, Journal of Evolutionary Biology 38(9), 1246–1255. https://doi.org/10.1093/jeb/voaf078
- Kumawat et al. (2025), *Evolution takes multiple paths to evolvability when facing environmental change*, PNAS 122(1), e2413930121. https://doi.org/10.1073/pnas.2413930121

Research concepts and third-party publications retain their respective authorship and licensing.

## Project ownership

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
