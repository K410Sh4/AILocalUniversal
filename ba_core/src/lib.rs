// Copyright © 2026 K410Sh4. All rights reserved.
// SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

//! Minimal deterministic spatial substrate for Brain Artificial (BA) experiments.
//!
//! This crate models local environmental niches, bounded phenotypic adaptation,
//! and conservative signal transport between regions. It is not an AI model,
//! a language model, or a claim of biological equivalence.

pub mod homeostasis;
pub mod signal_ecology;

use std::collections::BTreeSet;

pub type RegionId = u32;
pub type UnitId = u64;

/// Observable local environmental conditions, normalized to [0, 1].
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct EnvironmentState {
    pub conditions: [f64; 2],
}

/// A computational unit with a mutable phenotype and bounded plasticity.
#[derive(Clone, Debug, PartialEq)]
pub struct Unit {
    pub id: UnitId,
    pub phenotype: [f64; 2],
    pub sensitivity: [f64; 2],
    pub learning_rate: f64,
}

impl Unit {
    fn adapt_toward(&mut self, target: [f64; 2]) {
        for (axis, target_value) in target.iter().enumerate() {
            let delta =
                (target_value - self.phenotype[axis]) * self.sensitivity[axis] * self.learning_rate;
            self.phenotype[axis] = (self.phenotype[axis] + delta).clamp(0.0, 1.0);
        }
    }

    fn fitness_in(&self, environment: EnvironmentState) -> f64 {
        let distance = (self.phenotype[0] - environment.conditions[0]).abs()
            + (self.phenotype[1] - environment.conditions[1]).abs();
        (1.0 - distance / 2.0).clamp(0.0, 1.0)
    }
}

/// A spatial region exposed to its own observable niche.
#[derive(Clone, Debug, PartialEq)]
pub struct Region {
    pub id: RegionId,
    pub niche_id: u32,
    pub environment: EnvironmentState,
    /// Concentration of one abstract signal species, normalized to [0, 1].
    pub signal: f64,
    pub units: Vec<Unit>,
}

/// An undirected transport edge. Permeability 0 represents a complete barrier.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Connection {
    pub a: RegionId,
    pub b: RegionId,
    pub permeability: f64,
}

/// Deterministic spatial substrate. Region and unit ordering is preserved.
#[derive(Clone, Debug, PartialEq)]
pub struct World {
    pub regions: Vec<Region>,
    pub connections: Vec<Connection>,
    pub diffusion_rate: f64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ValidationError {
    EmptyWorld,
    InvalidValue(&'static str),
    DuplicateRegion(RegionId),
    DuplicateUnit(UnitId),
    MissingRegion(RegionId),
    DuplicateConnection(RegionId, RegionId),
    UnstableTransport(RegionId),
}

impl World {
    /// Validate identifiers, normalized values and explicit diffusion stability.
    pub fn validate(&self) -> Result<(), ValidationError> {
        if self.regions.is_empty() {
            return Err(ValidationError::EmptyWorld);
        }
        if !self.diffusion_rate.is_finite() || !(0.0..=1.0).contains(&self.diffusion_rate) {
            return Err(ValidationError::InvalidValue("diffusion_rate"));
        }

        let mut region_ids = BTreeSet::new();
        let mut unit_ids = BTreeSet::new();
        for region in &self.regions {
            if !region_ids.insert(region.id) {
                return Err(ValidationError::DuplicateRegion(region.id));
            }
            if !valid_unit_interval(region.signal)
                || region
                    .environment
                    .conditions
                    .iter()
                    .any(|v| !valid_unit_interval(*v))
            {
                return Err(ValidationError::InvalidValue("region_state"));
            }
            for unit in &region.units {
                if !unit_ids.insert(unit.id) {
                    return Err(ValidationError::DuplicateUnit(unit.id));
                }
                if !valid_unit_interval(unit.learning_rate)
                    || unit.phenotype.iter().any(|v| !valid_unit_interval(*v))
                    || unit.sensitivity.iter().any(|v| !valid_unit_interval(*v))
                {
                    return Err(ValidationError::InvalidValue("unit_state"));
                }
            }
        }

        let mut pairs = BTreeSet::new();
        let mut transport_load = vec![0.0_f64; self.regions.len()];
        for edge in &self.connections {
            if !valid_unit_interval(edge.permeability) {
                return Err(ValidationError::InvalidValue("permeability"));
            }
            let a = self
                .region_index(edge.a)
                .ok_or(ValidationError::MissingRegion(edge.a))?;
            let b = self
                .region_index(edge.b)
                .ok_or(ValidationError::MissingRegion(edge.b))?;
            let pair = if edge.a < edge.b {
                (edge.a, edge.b)
            } else {
                (edge.b, edge.a)
            };
            if !pairs.insert(pair) {
                return Err(ValidationError::DuplicateConnection(pair.0, pair.1));
            }
            transport_load[a] += self.diffusion_rate * edge.permeability;
            transport_load[b] += self.diffusion_rate * edge.permeability;
        }
        for (index, load) in transport_load.iter().enumerate() {
            if *load > 1.0 + 1e-12 {
                return Err(ValidationError::UnstableTransport(self.regions[index].id));
            }
        }
        Ok(())
    }

    /// One simultaneous, pairwise signal-transport step.
    ///
    /// The update conserves total signal mass (within floating-point tolerance).
    /// Production, uptake, degradation and boundary sinks are intentionally not
    /// implicit; they must be introduced as explicit mechanisms in later versions.
    pub fn transport_signals(&mut self) -> Result<(), ValidationError> {
        self.validate()?;
        let mut delta = vec![0.0; self.regions.len()];
        for edge in &self.connections {
            let a = self.region_index(edge.a).expect("validated region");
            let b = self.region_index(edge.b).expect("validated region");
            let flux = self.diffusion_rate
                * edge.permeability
                * (self.regions[a].signal - self.regions[b].signal);
            delta[a] -= flux;
            delta[b] += flux;
        }
        for (region, change) in self.regions.iter_mut().zip(delta) {
            region.signal = (region.signal + change).clamp(0.0, 1.0);
        }
        Ok(())
    }

    /// Adapt each unit only to its own region's currently observable conditions.
    pub fn adapt_locally(&mut self) -> Result<(), ValidationError> {
        self.validate()?;
        for region in &mut self.regions {
            for unit in &mut region.units {
                unit.adapt_toward(region.environment.conditions);
            }
        }
        Ok(())
    }

    /// Mean unit fitness against each unit's own local environment.
    pub fn mean_local_fitness(&self) -> f64 {
        let mut total = 0.0;
        let mut count = 0usize;
        for region in &self.regions {
            for unit in &region.units {
                total += unit.fitness_in(region.environment);
                count += 1;
            }
        }
        if count == 0 {
            0.0
        } else {
            total / count as f64
        }
    }

    /// Worst regional mean fitness; prevents global averages hiding local collapse.
    pub fn worst_region_fitness(&self) -> f64 {
        self.regions
            .iter()
            .map(|region| {
                if region.units.is_empty() {
                    0.0
                } else {
                    region
                        .units
                        .iter()
                        .map(|u| u.fitness_in(region.environment))
                        .sum::<f64>()
                        / region.units.len() as f64
                }
            })
            .fold(1.0, f64::min)
    }

    fn region_index(&self, id: RegionId) -> Option<usize> {
        self.regions.iter().position(|region| region.id == id)
    }
}

/// Side-by-side metrics for local adaptation and a shared-global-environment baseline.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct AdaptationComparison {
    pub region_count: usize,
    pub local_mean_fitness: f64,
    pub local_worst_region_fitness: f64,
    pub shared_global_mean_fitness: f64,
    pub shared_global_worst_region_fitness: f64,
}

/// Compare local adaptation with a baseline where every unit receives the same
/// region-averaged environmental conditions. Both start from identical states.
pub fn compare_local_to_shared_global(
    initial: &World,
    steps: usize,
) -> Result<AdaptationComparison, ValidationError> {
    initial.validate()?;
    let mut local = initial.clone();
    let mut shared = initial.clone();

    let mut global_conditions = [0.0; 2];
    for region in &initial.regions {
        for (axis, value) in region.environment.conditions.iter().enumerate() {
            global_conditions[axis] += *value;
        }
    }
    for value in &mut global_conditions {
        *value /= initial.regions.len() as f64;
    }

    for _ in 0..steps {
        local.adapt_locally()?;
        for region in &mut shared.regions {
            for unit in &mut region.units {
                unit.adapt_toward(global_conditions);
            }
        }
    }

    Ok(AdaptationComparison {
        region_count: initial.regions.len(),
        local_mean_fitness: local.mean_local_fitness(),
        local_worst_region_fitness: local.worst_region_fitness(),
        shared_global_mean_fitness: shared.mean_local_fitness(),
        shared_global_worst_region_fitness: shared.worst_region_fitness(),
    })
}

fn valid_unit_interval(value: f64) -> bool {
    value.is_finite() && (0.0..=1.0).contains(&value)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn unit(id: UnitId) -> Unit {
        Unit {
            id,
            phenotype: [0.5, 0.5],
            sensitivity: [1.0, 1.0],
            learning_rate: 0.2,
        }
    }

    fn region(
        id: RegionId,
        niche_id: u32,
        conditions: [f64; 2],
        signal: f64,
        unit_id: u64,
    ) -> Region {
        Region {
            id,
            niche_id,
            environment: EnvironmentState { conditions },
            signal,
            units: vec![unit(unit_id)],
        }
    }

    fn two_niche_world() -> World {
        World {
            regions: vec![
                region(1, 10, [0.0, 0.0], 1.0, 101),
                region(2, 20, [1.0, 1.0], 0.0, 202),
            ],
            connections: vec![Connection {
                a: 1,
                b: 2,
                permeability: 0.5,
            }],
            diffusion_rate: 0.25,
        }
    }

    #[test]
    fn local_adaptation_outperforms_shared_global_phenotype_in_divergent_niches() {
        let mut local = two_niche_world();
        let mut shared = two_niche_world();
        let global = [0.5, 0.5];

        for _ in 0..30 {
            local.adapt_locally().unwrap();
            for region in &mut shared.regions {
                for unit in &mut region.units {
                    unit.adapt_toward(global);
                }
            }
        }

        assert!(local.mean_local_fitness() > shared.mean_local_fitness() + 0.20);
        assert!(local.worst_region_fitness() > shared.worst_region_fitness());
    }

    fn matrix_world(region_count: usize) -> World {
        let mut regions = Vec::with_capacity(region_count);
        let mut connections = Vec::with_capacity(region_count.saturating_sub(1));
        for index in 0..region_count {
            let conditions = if index % 2 == 0 {
                [0.0, 0.0]
            } else {
                [1.0, 1.0]
            };
            regions.push(region(
                index as u32 + 1,
                index as u32 + 100,
                conditions,
                (index % 2) as f64,
                index as u64 + 1,
            ));
            if index > 0 {
                connections.push(Connection {
                    a: index as u32,
                    b: index as u32 + 1,
                    permeability: 0.2,
                });
            }
        }
        World {
            regions,
            connections,
            diffusion_rate: 0.2,
        }
    }

    #[test]
    fn local_adaptation_matrix_covers_one_to_sixteen_regions() {
        for region_count in [1, 2, 4, 8, 16] {
            let report = compare_local_to_shared_global(&matrix_world(region_count), 30).unwrap();
            assert_eq!(report.region_count, region_count);
            if region_count == 1 {
                assert!(
                    (report.local_mean_fitness - report.shared_global_mean_fitness).abs() < 1e-12
                );
            } else {
                assert!(report.local_mean_fitness > report.shared_global_mean_fitness);
                assert!(
                    report.local_worst_region_fitness > report.shared_global_worst_region_fitness
                );
            }
        }
    }

    #[test]
    fn local_adaptation_improves_monotonically_across_learning_rate_sweep() {
        let mut previous = 0.0;
        for learning_rate in [0.05, 0.2, 0.5, 1.0] {
            let mut world = matrix_world(2);
            for region in &mut world.regions {
                region.units[0].learning_rate = learning_rate;
            }
            let report = compare_local_to_shared_global(&world, 10).unwrap();
            assert!(report.local_mean_fitness >= previous);
            previous = report.local_mean_fitness;
        }
    }

    #[test]
    fn signal_transport_remains_conservative_across_spatial_topologies() {
        let topologies = vec![
            vec![(1, 2), (2, 3), (3, 4)],
            vec![(1, 2), (2, 3), (3, 4), (4, 1)],
            vec![(1, 2), (1, 3), (2, 4), (3, 4)],
            vec![(1, 2), (1, 3), (1, 4)],
            vec![(1, 2), (3, 4)],
        ];
        for topology in topologies {
            let mut world = matrix_world(4);
            world.connections = topology
                .into_iter()
                .map(|(a, b)| Connection {
                    a,
                    b,
                    permeability: 0.2,
                })
                .collect();
            let before: f64 = world.regions.iter().map(|region| region.signal).sum();
            world.transport_signals().unwrap();
            let after: f64 = world.regions.iter().map(|region| region.signal).sum();
            assert!((before - after).abs() < 1e-12);
            assert!(world
                .regions
                .iter()
                .all(|region| (0.0..=1.0).contains(&region.signal)));
        }
    }

    #[test]
    fn transport_conserves_signal_mass() {
        let mut world = two_niche_world();
        let before: f64 = world.regions.iter().map(|r| r.signal).sum();
        world.transport_signals().unwrap();
        let after: f64 = world.regions.iter().map(|r| r.signal).sum();
        assert!((before - after).abs() < 1e-12);
    }

    #[test]
    fn impermeable_barrier_blocks_transport() {
        let mut world = two_niche_world();
        world.connections[0].permeability = 0.0;
        let before: Vec<f64> = world.regions.iter().map(|r| r.signal).collect();
        world.transport_signals().unwrap();
        let after: Vec<f64> = world.regions.iter().map(|r| r.signal).collect();
        assert_eq!(before, after);
    }

    #[test]
    fn adaptation_is_bounded_and_reproducible() {
        let mut a = two_niche_world();
        let mut b = two_niche_world();
        for _ in 0..50 {
            a.adapt_locally().unwrap();
            b.adapt_locally().unwrap();
        }
        assert_eq!(a, b);
        for region in a.regions {
            for unit in region.units {
                assert!(unit.phenotype.iter().all(|v| (0.0..=1.0).contains(v)));
            }
        }
    }

    #[test]
    fn invalid_non_finite_environment_is_rejected() {
        let mut world = two_niche_world();
        world.regions[0].environment.conditions[0] = f64::NAN;
        assert_eq!(
            world.validate(),
            Err(ValidationError::InvalidValue("region_state"))
        );
    }

    #[test]
    fn transport_rejects_unstable_combined_edge_load() {
        let mut world = two_niche_world();
        world.regions.push(region(3, 30, [0.5, 0.5], 0.0, 303));
        world.diffusion_rate = 1.0;
        world.connections[0].permeability = 1.0;
        world.connections.push(Connection {
            a: 1,
            b: 3,
            permeability: 1.0,
        });
        assert_eq!(world.validate(), Err(ValidationError::UnstableTransport(1)));
    }
}
