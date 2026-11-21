// Copyright © 2026 K410Sh4. All rights reserved.
// SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

//! Local homeostatic regulation for the Brain Artificial (BA) substrate.
//!
//! This module is an isolated, deterministic experiment. It does not alter
//! signal ecology, phenotype, development, heredity, or K.BA runtime state.

use std::collections::BTreeSet;

pub type HomeostasisRegionId = u32;

#[derive(Clone, Debug, PartialEq)]
pub struct HomeostaticRegion {
    pub id: HomeostasisRegionId,
    pub state: f64,
    pub target: f64,
    pub lower_bound: f64,
    pub upper_bound: f64,
    /// Nonnegative proportional feedback gain (1/time).
    pub gain: f64,
    /// Maximum absolute correction rate (state units/time).
    pub max_adjustment_rate: f64,
    /// Available local regulatory reserve.
    pub energy_reserve: f64,
    /// Reserve consumed per unit of absolute correction.
    pub energy_cost_per_unit: f64,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct RegionHomeostasisReport {
    pub region_id: HomeostasisRegionId,
    pub state_before: f64,
    pub state_after: f64,
    pub disturbance_amount: f64,
    pub correction_amount: f64,
    /// Positive means material was removed at the upper/lower physical boundary.
    pub boundary_exchange: f64,
    pub energy_spent: f64,
    pub energy_remaining: f64,
    pub within_target: bool,
}

#[derive(Clone, Debug, PartialEq)]
pub struct HomeostasisStepReport {
    pub regions: Vec<RegionHomeostasisReport>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum HomeostasisError {
    EmptySystem,
    InvalidValue(&'static str),
    DuplicateRegion(HomeostasisRegionId),
    DuplicateDisturbance(HomeostasisRegionId),
    MissingRegion(HomeostasisRegionId),
    UnstableStep(HomeostasisRegionId),
}

impl HomeostaticRegion {
    pub fn validate(&self) -> Result<(), HomeostasisError> {
        let finite = [
            self.state,
            self.target,
            self.lower_bound,
            self.upper_bound,
            self.gain,
            self.max_adjustment_rate,
            self.energy_reserve,
            self.energy_cost_per_unit,
        ]
        .iter()
        .all(|value| value.is_finite());
        if !finite
            || self.lower_bound >= self.upper_bound
            || self.state < self.lower_bound
            || self.state > self.upper_bound
            || self.target < self.lower_bound
            || self.target > self.upper_bound
            || self.gain < 0.0
            || self.max_adjustment_rate < 0.0
            || self.energy_reserve < 0.0
            || self.energy_cost_per_unit <= 0.0
        {
            return Err(HomeostasisError::InvalidValue("region_state_or_parameters"));
        }
        Ok(())
    }

    /// Apply local negative feedback, bounded by actuator capacity and reserve.
    ///
    /// The Euler update is monotone for the unsaturated controller when
    /// gain * dt <= 1. Disturbance and correction are recorded as amounts.
    /// Any state clipped at a physical bound is exposed as boundary_exchange,
    /// rather than silently disappearing from the accounting.
    pub fn step(
        &mut self,
        dt: f64,
        disturbance_rate: f64,
        tolerance: f64,
    ) -> Result<RegionHomeostasisReport, HomeostasisError> {
        self.validate()?;
        if !dt.is_finite()
            || dt <= 0.0
            || !disturbance_rate.is_finite()
            || !tolerance.is_finite()
            || tolerance < 0.0
        {
            return Err(HomeostasisError::InvalidValue("step_parameters"));
        }
        if self.gain * dt > 1.0 + 1e-12 {
            return Err(HomeostasisError::UnstableStep(self.id));
        }

        let state_before = self.state;
        let raw_requested_rate = (self.target - self.state) * self.gain;
        if !raw_requested_rate.is_finite() {
            return Err(HomeostasisError::InvalidValue("step_overflow"));
        }
        let requested_rate =
            raw_requested_rate.clamp(-self.max_adjustment_rate, self.max_adjustment_rate);
        let requested_amount = requested_rate.abs() * dt;
        let disturbance_amount = disturbance_rate * dt;
        if !requested_rate.is_finite()
            || !requested_amount.is_finite()
            || !disturbance_amount.is_finite()
        {
            return Err(HomeostasisError::InvalidValue("step_overflow"));
        }
        let affordable_amount = self.energy_reserve / self.energy_cost_per_unit;
        let correction_amount = requested_amount.min(affordable_amount);
        let correction_rate = correction_amount.copysign(requested_rate) / dt;
        let energy_spent = correction_amount * self.energy_cost_per_unit;

        let unconstrained = self.state + disturbance_amount + correction_rate * dt;
        if !unconstrained.is_finite() {
            return Err(HomeostasisError::InvalidValue("state_overflow"));
        }
        let state_after = unconstrained.clamp(self.lower_bound, self.upper_bound);
        let boundary_exchange = unconstrained - state_after;

        self.state = state_after;
        self.energy_reserve = (self.energy_reserve - energy_spent).max(0.0);

        Ok(RegionHomeostasisReport {
            region_id: self.id,
            state_before,
            state_after,
            disturbance_amount,
            correction_amount: correction_rate * dt,
            boundary_exchange,
            energy_spent,
            energy_remaining: self.energy_reserve,
            within_target: (state_after - self.target).abs() <= tolerance,
        })
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct HomeostasisSystem {
    pub regions: Vec<HomeostaticRegion>,
}

impl HomeostasisSystem {
    pub fn validate(&self) -> Result<(), HomeostasisError> {
        if self.regions.is_empty() {
            return Err(HomeostasisError::EmptySystem);
        }
        let mut ids = BTreeSet::new();
        for region in &self.regions {
            if !ids.insert(region.id) {
                return Err(HomeostasisError::DuplicateRegion(region.id));
            }
            region.validate()?;
        }
        Ok(())
    }

    /// Advance every region independently. Omitted disturbance entries mean zero.
    pub fn step(
        &mut self,
        dt: f64,
        disturbances: &[(HomeostasisRegionId, f64)],
        tolerance: f64,
    ) -> Result<HomeostasisStepReport, HomeostasisError> {
        self.validate()?;
        if !dt.is_finite() || dt <= 0.0 || !tolerance.is_finite() || tolerance < 0.0 {
            return Err(HomeostasisError::InvalidValue("step_parameters"));
        }
        for region in &self.regions {
            if region.gain * dt > 1.0 + 1e-12 {
                return Err(HomeostasisError::UnstableStep(region.id));
            }
        }

        let mut supplied = BTreeSet::new();
        for (id, rate) in disturbances {
            if !rate.is_finite() || !(rate * dt).is_finite() {
                return Err(HomeostasisError::InvalidValue("disturbance_rate"));
            }
            if !supplied.insert(*id) {
                return Err(HomeostasisError::DuplicateDisturbance(*id));
            }
            if !self.regions.iter().any(|region| region.id == *id) {
                return Err(HomeostasisError::MissingRegion(*id));
            }
        }

        // Preflight on clones so an overflow or invalid region cannot leave
        // earlier regions mutated while later regions fail.
        let mut preflight = self.regions.clone();
        for region in &mut preflight {
            let disturbance = disturbances
                .iter()
                .find(|(id, _)| *id == region.id)
                .map_or(0.0, |(_, rate)| *rate);
            region.step(dt, disturbance, tolerance)?;
        }

        let mut reports = Vec::with_capacity(self.regions.len());
        for region in &mut self.regions {
            let disturbance = disturbances
                .iter()
                .find(|(id, _)| *id == region.id)
                .map_or(0.0, |(_, rate)| *rate);
            reports.push(region.step(dt, disturbance, tolerance)?);
        }
        Ok(HomeostasisStepReport { regions: reports })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn region(id: u32, target: f64) -> HomeostaticRegion {
        HomeostaticRegion {
            id,
            state: 0.0,
            target,
            lower_bound: -2.0,
            upper_bound: 2.0,
            gain: 0.5,
            max_adjustment_rate: 2.0,
            energy_reserve: 100.0,
            energy_cost_per_unit: 0.25,
        }
    }

    #[test]
    fn isolated_region_recovers_after_a_transient_disturbance() {
        let mut r = region(1, 0.0);
        r.step(0.1, 1.0, 0.02).unwrap();
        let disturbed = r.state;
        for _ in 0..100 {
            r.step(0.1, 0.0, 0.02).unwrap();
        }
        assert!(disturbed > 0.0);
        assert!(r.state.abs() < disturbed.abs());
        assert!(r.state.abs() < 0.02);
    }

    #[test]
    fn heterogeneous_regions_keep_distinct_local_targets() {
        let mut system = HomeostasisSystem {
            regions: vec![region(1, -0.5), region(2, 0.75)],
        };
        for _ in 0..100 {
            system.step(0.1, &[], 0.02).unwrap();
        }
        assert!((system.regions[0].state + 0.5).abs() < 0.02);
        assert!((system.regions[1].state - 0.75).abs() < 0.02);
        assert_ne!(system.regions[0].state, system.regions[1].state);
    }

    #[test]
    fn region_matrix_scales_without_global_target_averaging() {
        for count in [1, 2, 4, 8, 16] {
            let regions = (0..count)
                .map(|index| region(index as u32, if index % 2 == 0 { -0.5 } else { 0.75 }))
                .collect();
            let mut system = HomeostasisSystem { regions };
            for _ in 0..100 {
                system.step(0.1, &[], 0.02).unwrap();
            }
            for (index, r) in system.regions.iter().enumerate() {
                let expected = if index % 2 == 0 { -0.5 } else { 0.75 };
                assert!((r.state - expected).abs() < 0.02);
            }
        }
    }

    #[test]
    fn actuator_capacity_and_energy_reserve_bound_correction() {
        let mut r = region(1, 1.0);
        r.max_adjustment_rate = 0.1;
        r.energy_reserve = 0.005;
        let report = r.step(1.0, 0.0, 0.0).unwrap();
        assert!(report.correction_amount.abs() <= 0.1 + 1e-12);
        assert!((report.energy_spent - 0.005).abs() < 1e-12);
        assert_eq!(report.energy_remaining, 0.0);
        assert!(r.state <= 0.005 + 1e-12);
    }

    #[test]
    fn energy_accounting_is_explicit_and_never_creates_reserve() {
        let mut r = region(1, 1.0);
        let before = r.energy_reserve;
        let report = r.step(0.25, 0.0, 0.0).unwrap();
        assert!((before - report.energy_spent - report.energy_remaining).abs() < 1e-12);
        assert!(report.energy_spent >= 0.0);
    }

    #[test]
    fn physical_boundary_exchange_closes_the_state_ledger() {
        let mut r = region(1, 2.0);
        r.state = 1.9;
        let report = r.step(0.5, 1.0, 0.0).unwrap();
        let reconstructed = report.state_before
            + report.disturbance_amount
            + report.correction_amount
            - report.boundary_exchange;
        assert!((reconstructed - report.state_after).abs() < 1e-12);
        assert!(report.boundary_exchange > 0.0);
        assert_eq!(report.state_after, 2.0);
    }

    #[test]
    fn unstable_or_invalid_steps_are_rejected_before_mutation() {
        let mut r = region(1, 1.0);
        let before = r.clone();
        assert_eq!(r.step(3.0, 0.0, 0.1), Err(HomeostasisError::UnstableStep(1)));
        assert_eq!(r, before);
        assert!(matches!(
            r.step(f64::NAN, 0.0, 0.1),
            Err(HomeostasisError::InvalidValue(_))
        ));
        assert_eq!(r, before);
    }

    #[test]
    fn independent_regions_receive_only_their_own_disturbances() {
        let mut system = HomeostasisSystem {
            regions: vec![region(1, 0.0), region(2, 0.0)],
        };
        let report = system.step(0.1, &[(1, 1.0)], 0.0).unwrap();
        assert!(report.regions[0].state_after > 0.0);
        assert_eq!(report.regions[1].state_after, 0.0);
    }

    #[test]
    fn duplicate_and_unknown_disturbance_regions_are_rejected() {
        let mut system = HomeostasisSystem { regions: vec![region(1, 0.0)] };
        assert_eq!(
            system.step(0.1, &[(1, 0.1), (1, 0.2)], 0.0),
            Err(HomeostasisError::DuplicateDisturbance(1))
        );
        assert_eq!(
            system.step(0.1, &[(2, 0.1)], 0.0),
            Err(HomeostasisError::MissingRegion(2))
        );
    }

    #[test]
    fn failed_region_preflight_does_not_partially_mutate_the_system() {
        let mut first = region(1, 1.0);
        let before_first = first.clone();
        let mut second = region(2, 0.0);
        second.lower_bound = -1.7e308;
        second.upper_bound = 1.7e308;
        second.state = -1.0e308;
        second.target = 1.0e308;
        let before_second = second.clone();
        let mut system = HomeostasisSystem { regions: vec![first, second] };

        assert_eq!(
            system.step(0.1, &[], 0.0),
            Err(HomeostasisError::InvalidValue("step_overflow"))
        );
        assert_eq!(system.regions[0], before_first);
        assert_eq!(system.regions[1], before_second);
    }

    #[test]
    fn deterministic_replay_produces_identical_states_and_reports() {
        let mut a = HomeostasisSystem { regions: vec![region(1, 0.4), region(2, -0.3)] };
        let mut b = a.clone();
        for _ in 0..20 {
            let ra = a.step(0.1, &[(1, 0.2), (2, -0.1)], 0.01).unwrap();
            let rb = b.step(0.1, &[(1, 0.2), (2, -0.1)], 0.01).unwrap();
            assert_eq!(ra, rb);
        }
        assert_eq!(a, b);
    }

    #[test]
    fn zero_gain_and_zero_reserve_do_not_generate_correction() {
        let mut r = region(1, 1.0);
        r.gain = 0.0;
        let report = r.step(0.1, 0.0, 0.0).unwrap();
        assert_eq!(report.correction_amount, 0.0);
        r.gain = 0.5;
        r.energy_reserve = 0.0;
        let report = r.step(0.1, 0.0, 0.0).unwrap();
        assert_eq!(report.correction_amount, 0.0);
    }
}
