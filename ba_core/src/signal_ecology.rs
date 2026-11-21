// Copyright © 2026 K410Sh4. All rights reserved.
// SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

//! Explicit spatial signal ecology for Brain Artificial (BA) experiments.
//! Transport, production, uptake, degradation and receptor interpretation are
//! separate mechanisms. Region volume converts concentration to conserved amount.

#[derive(Clone, Debug, PartialEq)]
pub struct SignalRegion {
    pub id: u32,
    pub volume: f64,
    pub concentration: f64,
    pub production_rate: f64,
    pub uptake_rate: f64,
    pub degradation_rate: f64,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct SignalEdge {
    pub a: u32,
    pub b: u32,
    pub conductance: f64,
}

#[derive(Clone, Debug, PartialEq)]
pub struct SignalEcology {
    pub regions: Vec<SignalRegion>,
    pub edges: Vec<SignalEdge>,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct SignalStepReport {
    pub initial_mass: f64,
    pub produced_mass: f64,
    pub uptake_mass: f64,
    pub degraded_mass: f64,
    pub final_mass: f64,
    pub mass_balance_residual: f64,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct SignalReceptor {
    pub half_saturation: f64,
    pub cooperativity: f64,
    pub sensitivity: f64,
}

#[derive(Clone, Debug, PartialEq)]
pub enum SignalError {
    EmptyEcology,
    InvalidValue(&'static str),
    DuplicateRegion(u32),
    MissingRegion(u32),
    DuplicateEdge(u32, u32),
    UnstableTransport(u32),
    NumericalFailure,
}

impl SignalEcology {
    pub fn validate(&self, dt: f64) -> Result<(), SignalError> {
        if self.regions.is_empty() {
            return Err(SignalError::EmptyEcology);
        }
        if !positive_finite(dt) {
            return Err(SignalError::InvalidValue("dt"));
        }

        let mut ids = std::collections::BTreeSet::new();
        for region in &self.regions {
            if !ids.insert(region.id) {
                return Err(SignalError::DuplicateRegion(region.id));
            }
            if !positive_finite(region.volume)
                || !nonnegative_finite(region.concentration)
                || !nonnegative_finite(region.production_rate)
                || !nonnegative_finite(region.uptake_rate)
                || !nonnegative_finite(region.degradation_rate)
                || !(region.uptake_rate + region.degradation_rate).is_finite()
                || !(region.volume * region.concentration).is_finite()
                || !(region.production_rate * region.volume * dt).is_finite()
            {
                return Err(SignalError::InvalidValue("region_parameters"));
            }
        }

        let mut pairs = std::collections::BTreeSet::new();
        let mut loads = vec![0.0_f64; self.regions.len()];
        for edge in &self.edges {
            if !nonnegative_finite(edge.conductance)
                || !(edge.conductance * dt).is_finite()
            {
                return Err(SignalError::InvalidValue("conductance"));
            }
            let a = self
                .index(edge.a)
                .ok_or(SignalError::MissingRegion(edge.a))?;
            let b = self
                .index(edge.b)
                .ok_or(SignalError::MissingRegion(edge.b))?;
            let pair = if edge.a < edge.b {
                (edge.a, edge.b)
            } else {
                (edge.b, edge.a)
            };
            if !pairs.insert(pair) {
                return Err(SignalError::DuplicateEdge(pair.0, pair.1));
            }
            loads[a] += edge.conductance * dt / self.regions[a].volume;
            loads[b] += edge.conductance * dt / self.regions[b].volume;
        }
        for (index, load) in loads.iter().enumerate() {
            if !load.is_finite() || *load > 1.0 + 1e-12 {
                return Err(SignalError::UnstableTransport(
                    self.regions[index].id,
                ));
            }
        }
        Ok(())
    }

    /// Simultaneous conservative transport followed by exact local linear kinetics.
    pub fn step(&mut self, dt: f64) -> Result<SignalStepReport, SignalError> {
        self.validate(dt)?;
        let initial_mass = self.total_mass();
        if !initial_mass.is_finite() {
            return Err(SignalError::NumericalFailure);
        }
        let mut delta_amount = vec![0.0; self.regions.len()];

        for edge in &self.edges {
            let a = self.index(edge.a).expect("validated region");
            let b = self.index(edge.b).expect("validated region");
            let amount = edge.conductance
                * dt
                * (self.regions[a].concentration - self.regions[b].concentration);
            delta_amount[a] -= amount;
            delta_amount[b] += amount;
        }

        for (index, region) in self.regions.iter_mut().enumerate() {
            region.concentration += delta_amount[index] / region.volume;
            if !nonnegative_finite(region.concentration) {
                return Err(SignalError::NumericalFailure);
            }
        }

        let mut produced_mass = 0.0;
        let mut uptake_mass = 0.0;
        let mut degraded_mass = 0.0;

        for region in &mut self.regions {
            let initial_concentration = region.concentration;
            let source = region.production_rate;
            let uptake = region.uptake_rate;
            let degradation = region.degradation_rate;
            let total_rate = uptake + degradation;
            if !(total_rate * dt).is_finite() {
                return Err(SignalError::NumericalFailure);
            }
            produced_mass += source * region.volume * dt;

            if total_rate == 0.0 {
                region.concentration = initial_concentration + source * dt;
            } else {
                let x = total_rate * dt;
                let one_minus_decay = -(-x).exp_m1();
                let source_integral = if x < 1e-3 {
                    dt * (x / 2.0 - x * x / 6.0 + x.powi(3) / 24.0
                        - x.powi(4) / 120.0
                        + x.powi(5) / 720.0)
                } else {
                    dt - one_minus_decay / total_rate
                };

                let removed = (initial_concentration * one_minus_decay
                    + source * source_integral)
                    * region.volume;
                uptake_mass += removed * uptake / total_rate;
                degraded_mass += removed * degradation / total_rate;
                region.concentration = initial_concentration * (-x).exp()
                    + source * one_minus_decay / total_rate;
            }

            if !nonnegative_finite(region.concentration) {
                return Err(SignalError::NumericalFailure);
            }
        }

        let final_mass = self.total_mass();
        if !produced_mass.is_finite()
            || !uptake_mass.is_finite()
            || !degraded_mass.is_finite()
            || !final_mass.is_finite()
        {
            return Err(SignalError::NumericalFailure);
        }
        let residual =
            initial_mass + produced_mass - uptake_mass - degraded_mass - final_mass;
        if !residual.is_finite() {
            return Err(SignalError::NumericalFailure);
        }

        Ok(SignalStepReport {
            initial_mass,
            produced_mass,
            uptake_mass,
            degraded_mass,
            final_mass,
            mass_balance_residual: residual,
        })
    }

    pub fn total_mass(&self) -> f64 {
        self.regions
            .iter()
            .map(|region| region.volume * region.concentration)
            .sum()
    }

    fn index(&self, id: u32) -> Option<usize> {
        self.regions.iter().position(|region| region.id == id)
    }
}

impl SignalReceptor {
    pub fn validate(&self) -> Result<(), SignalError> {
        if !positive_finite(self.half_saturation)
            || !positive_finite(self.cooperativity)
            || !unit_interval(self.sensitivity)
        {
            return Err(SignalError::InvalidValue("receptor_parameters"));
        }
        Ok(())
    }

    /// Hill-type phenomenological response; cooperativity is not a binding-site count.
    pub fn response(&self, concentration: f64) -> Result<f64, SignalError> {
        self.validate()?;
        if !nonnegative_finite(concentration) {
            return Err(SignalError::InvalidValue("concentration"));
        }
        if concentration == 0.0 {
            return Ok(0.0);
        }

        let log_ratio = self.cooperativity
            * (concentration.ln() - self.half_saturation.ln());
        let occupancy = if log_ratio >= 0.0 {
            1.0 / (1.0 + (-log_ratio).exp())
        } else {
            let value = log_ratio.exp();
            value / (1.0 + value)
        };
        Ok(self.sensitivity * occupancy)
    }
}

fn positive_finite(value: f64) -> bool {
    value.is_finite() && value > 0.0
}

fn nonnegative_finite(value: f64) -> bool {
    value.is_finite() && value >= 0.0
}

fn unit_interval(value: f64) -> bool {
    value.is_finite() && (0.0..=1.0).contains(&value)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn region(id: u32, volume: f64, concentration: f64) -> SignalRegion {
        SignalRegion {
            id,
            volume,
            concentration,
            production_rate: 0.0,
            uptake_rate: 0.0,
            degradation_rate: 0.0,
        }
    }

    fn pair() -> SignalEcology {
        SignalEcology {
            regions: vec![region(1, 1.0, 1.0), region(2, 2.0, 0.0)],
            edges: vec![SignalEdge {
                a: 1,
                b: 2,
                conductance: 0.2,
            }],
        }
    }

    #[test]
    fn transport_conserves_amount_with_unequal_volumes() {
        let mut ecology = pair();
        let before = ecology.total_mass();
        ecology.step(0.5).unwrap();
        assert!((ecology.total_mass() - before).abs() < 1e-12);
        assert!(ecology.regions.iter().all(|r| r.concentration >= 0.0));
    }

    #[test]
    fn impermeable_barrier_preserves_local_concentrations() {
        let mut ecology = pair();
        ecology.edges[0].conductance = 0.0;
        ecology.step(1.0).unwrap();
        assert_eq!(ecology.regions[0].concentration, 1.0);
        assert_eq!(ecology.regions[1].concentration, 0.0);
    }

    #[test]
    fn source_uptake_and_degradation_close_mass_ledger() {
        let mut ecology = SignalEcology {
            regions: vec![region(1, 3.0, 0.8)],
            edges: vec![],
        };
        ecology.regions[0].production_rate = 0.4;
        ecology.regions[0].uptake_rate = 0.3;
        ecology.regions[0].degradation_rate = 0.2;
        let report = ecology.step(0.7).unwrap();
        assert!(report.mass_balance_residual.abs() < 1e-11);
        assert!(report.produced_mass > 0.0);
        assert!(report.uptake_mass > 0.0);
        assert!(report.degraded_mass > 0.0);
    }

    #[test]
    fn exact_reaction_is_consistent_when_time_is_partitioned() {
        let mut whole = SignalEcology {
            regions: vec![region(1, 2.0, 1.3)],
            edges: vec![],
        };
        whole.regions[0].production_rate = 0.25;
        whole.regions[0].uptake_rate = 0.4;
        whole.regions[0].degradation_rate = 0.15;
        let mut divided = whole.clone();
        whole.step(1.0).unwrap();
        for _ in 0..10 {
            divided.step(0.1).unwrap();
        }
        assert!(
            (whole.regions[0].concentration - divided.regions[0].concentration).abs()
                < 1e-12
        );
    }

    #[test]
    fn stability_is_checked_per_region_volume() {
        let mut ecology = pair();
        ecology.edges[0].conductance = 3.0;
        assert_eq!(
            ecology.validate(0.5),
            Err(SignalError::UnstableTransport(1))
        );
    }

    #[test]
    fn ecology_is_deterministic() {
        let mut first = pair();
        let mut second = pair();
        first.regions[0].production_rate = 0.1;
        second.regions[0].production_rate = 0.1;
        for _ in 0..20 {
            first.step(0.05).unwrap();
            second.step(0.05).unwrap();
        }
        assert_eq!(first, second);
    }

    #[test]
    fn receptor_response_is_monotonic_bounded_and_half_saturated() {
        let receptor = SignalReceptor {
            half_saturation: 2.0,
            cooperativity: 1.0,
            sensitivity: 0.8,
        };
        let low = receptor.response(0.5).unwrap();
        let half = receptor.response(2.0).unwrap();
        let high = receptor.response(1e100).unwrap();
        assert!(low < half && half < high);
        assert!((half - 0.4).abs() < 1e-12);
        assert!(high <= 0.8);
    }

    #[test]
    fn zero_signal_has_zero_receptor_response() {
        let receptor = SignalReceptor {
            half_saturation: 1.0,
            cooperativity: 2.0,
            sensitivity: 1.0,
        };
        assert_eq!(receptor.response(0.0).unwrap(), 0.0);
    }

    #[test]
    fn transport_conserves_amount_across_spatial_sizes_and_topologies() {
        for count in [1_usize, 2, 4, 8, 16] {
            let regions = (0..count)
                .map(|index| {
                    region(
                        index as u32,
                        0.5 + index as f64 * 0.1,
                        (index % 3) as f64,
                    )
                })
                .collect::<Vec<_>>();
            let mut edges = Vec::new();
            for index in 1..count {
                edges.push(SignalEdge {
                    a: 0,
                    b: index as u32,
                    conductance: 0.001,
                });
            }
            let mut ecology = SignalEcology { regions, edges };
            let before = ecology.total_mass();
            ecology.step(0.1).unwrap();
            assert!((ecology.total_mass() - before).abs() < 1e-10);
            assert!(ecology.regions.iter().all(|r| r.concentration >= 0.0));
        }
    }

    #[test]
    fn invalid_rates_are_rejected() {
        let mut ecology = pair();
        ecology.regions[0].uptake_rate = -0.1;
        assert_eq!(
            ecology.validate(0.1),
            Err(SignalError::InvalidValue("region_parameters"))
        );
    }
}
