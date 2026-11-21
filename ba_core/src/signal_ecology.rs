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
pub struct SignalEdge { pub a: u32, pub b: u32, pub conductance: f64 }
#[derive(Clone, Debug, PartialEq)]
pub struct SignalEcology { pub regions: Vec<SignalRegion>, pub edges: Vec<SignalEdge> }
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct SignalStepReport {
    pub initial_mass: f64, pub produced_mass: f64, pub uptake_mass: f64,
    pub degraded_mass: f64, pub final_mass: f64, pub mass_balance_residual: f64,
}
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct SignalReceptor { pub half_saturation: f64, pub cooperativity: f64, pub sensitivity: f64 }
#[derive(Clone, Debug, PartialEq)]
pub enum SignalError {
    EmptyEcology, InvalidValue(&'static str), DuplicateRegion(u32), MissingRegion(u32),
    DuplicateEdge(u32,u32), UnstableTransport(u32), NumericalFailure,
}

impl SignalEcology {
    pub fn validate(&self, dt: f64) -> Result<(), SignalError> {
        if self.regions.is_empty() { return Err(SignalError::EmptyEcology); }
        if !positive_finite(dt) { return Err(SignalError::InvalidValue("dt")); }
        let mut ids = std::collections::BTreeSet::new();
        for r in &self.regions {
            if !ids.insert(r.id) { return Err(SignalError::DuplicateRegion(r.id)); }
            if !positive_finite(r.volume) || !nonnegative_finite(r.concentration)
                || !nonnegative_finite(r.production_rate) || !nonnegative_finite(r.uptake_rate)
                || !nonnegative_finite(r.degradation_rate) {
                return Err(SignalError::InvalidValue("region_parameters"));
            }
        }
        let mut pairs = std::collections::BTreeSet::new();
        let mut loads = vec![0.0_f64; self.regions.len()];
        for edge in &self.edges {
            if !nonnegative_finite(edge.conductance) { return Err(SignalError::InvalidValue("conductance")); }
            let a = self.index(edge.a).ok_or(SignalError::MissingRegion(edge.a))?;
            let b = self.index(edge.b).ok_or(SignalError::MissingRegion(edge.b))?;
            let pair = if edge.a < edge.b {(edge.a,edge.b)} else {(edge.b,edge.a)};
            if !pairs.insert(pair) { return Err(SignalError::DuplicateEdge(pair.0,pair.1)); }
            loads[a] += edge.conductance * dt / self.regions[a].volume;
            loads[b] += edge.conductance * dt / self.regions[b].volume;
        }
        for (i,load) in loads.iter().enumerate() {
            if !load.is_finite() || *load > 1.0 + 1e-12 {
                return Err(SignalError::UnstableTransport(self.regions[i].id));
            }
        }
        Ok(())
    }

    /// Simultaneous conservative transport followed by exact local linear kinetics.
    pub fn step(&mut self, dt: f64) -> Result<SignalStepReport, SignalError> {
        self.validate(dt)?;
        let initial_mass = self.total_mass();
        let mut delta = vec![0.0; self.regions.len()];
        for edge in &self.edges {
            let a = self.index(edge.a).expect("validated region");
            let b = self.index(edge.b).expect("validated region");
            let amount = edge.conductance * dt
                * (self.regions[a].concentration - self.regions[b].concentration);
            delta[a] -= amount; delta[b] += amount;
        }
        for (i,r) in self.regions.iter_mut().enumerate() {
            r.concentration += delta[i] / r.volume;
            if !nonnegative_finite(r.concentration) { return Err(SignalError::NumericalFailure); }
        }
        let mut produced = 0.0; let mut uptake_total = 0.0; let mut degraded = 0.0;
        for r in &mut self.regions {
            let c0=r.concentration; let q=r.production_rate;
            let u=r.uptake_rate; let d=r.degradation_rate; let k=u+d;
            produced += q*r.volume*dt;
            if k == 0.0 { r.concentration=c0+q*dt; }
            else {
                let x=k*dt; let one_minus_decay=-(-x).exp_m1();
                let source_integral=if x<1e-3 {
                    dt*(x/2.0-x*x/6.0+x.powi(3)/24.0-x.powi(4)/120.0+x.powi(5)/720.0)
                } else { dt-one_minus_decay/k };
                let removed=(c0*one_minus_decay+q*source_integral)*r.volume;
                uptake_total += removed*u/k; degraded += removed*d/k;
                r.concentration=c0*(-x).exp()+q*one_minus_decay/k;
            }
            if !nonnegative_finite(r.concentration) { return Err(SignalError::NumericalFailure); }
        }
        let final_mass=self.total_mass();
        let residual=initial_mass+produced-uptake_total-degraded-final_mass;
        if !residual.is_finite() { return Err(SignalError::NumericalFailure); }
        Ok(SignalStepReport { initial_mass, produced_mass:produced, uptake_mass:uptake_total,
            degraded_mass:degraded, final_mass, mass_balance_residual:residual })
    }
    pub fn total_mass(&self)->f64 { self.regions.iter().map(|r|r.volume*r.concentration).sum() }
    fn index(&self,id:u32)->Option<usize> { self.regions.iter().position(|r|r.id==id) }
}

impl SignalReceptor {
    pub fn validate(&self)->Result<(),SignalError> {
        if !positive_finite(self.half_saturation)||!positive_finite(self.cooperativity)
            ||!unit_interval(self.sensitivity) {
            return Err(SignalError::InvalidValue("receptor_parameters"));
        }
        Ok(())
    }
    /// Hill-type phenomenological response; cooperativity is not a binding-site count.
    pub fn response(&self,c:f64)->Result<f64,SignalError> {
        self.validate()?;
        if !nonnegative_finite(c) { return Err(SignalError::InvalidValue("concentration")); }
        if c==0.0 { return Ok(0.0); }
        let x=self.cooperativity*(c.ln()-self.half_saturation.ln());
        let occupancy=if x>=0.0 {1.0/(1.0+(-x).exp())}
            else {let e=x.exp();e/(1.0+e)};
        Ok(self.sensitivity*occupancy)
    }
}
fn positive_finite(v:f64)->bool {v.is_finite()&&v>0.0}
fn nonnegative_finite(v:f64)->bool {v.is_finite()&&v>=0.0}
fn unit_interval(v:f64)->bool {v.is_finite()&&(0.0..=1.0).contains(&v)}

#[cfg(test)]
mod tests {
    use super::*;
    fn region(id:u32,volume:f64,concentration:f64)->SignalRegion {
        SignalRegion{id,volume,concentration,production_rate:0.0,uptake_rate:0.0,degradation_rate:0.0}
    }
    fn pair()->SignalEcology {
        SignalEcology{regions:vec![region(1,1.0,1.0),region(2,2.0,0.0)],
            edges:vec![SignalEdge{a:1,b:2,conductance:0.2}]}
    }
    #[test] fn transport_conserves_amount_with_unequal_volumes(){
        let mut e=pair();let before=e.total_mass();e.step(0.5).unwrap();
        assert!((e.total_mass()-before).abs()<1e-12);
        assert!(e.regions.iter().all(|r|r.concentration>=0.0));
    }
    #[test] fn impermeable_barrier_preserves_local_concentrations(){
        let mut e=pair();e.edges[0].conductance=0.0;e.step(1.0).unwrap();
        assert_eq!(e.regions[0].concentration,1.0);assert_eq!(e.regions[1].concentration,0.0);
    }
    #[test] fn source_uptake_and_degradation_close_mass_ledger(){
        let mut e=SignalEcology{regions:vec![region(1,3.0,0.8)],edges:vec![]};
        e.regions[0].production_rate=0.4;e.regions[0].uptake_rate=0.3;e.regions[0].degradation_rate=0.2;
        let r=e.step(0.7).unwrap();assert!(r.mass_balance_residual.abs()<1e-11);
        assert!(r.produced_mass>0.0&&r.uptake_mass>0.0&&r.degraded_mass>0.0);
    }
    #[test] fn exact_reaction_is_consistent_when_time_is_partitioned(){
        let mut a=SignalEcology{regions:vec![region(1,2.0,1.3)],edges:vec![]};
        a.regions[0].production_rate=0.25;a.regions[0].uptake_rate=0.4;a.regions[0].degradation_rate=0.15;
        let mut b=a.clone();a.step(1.0).unwrap();for _ in 0..10{b.step(0.1).unwrap();}
        assert!((a.regions[0].concentration-b.regions[0].concentration).abs()<1e-12);
    }
    #[test] fn stability_is_checked_per_region_volume(){
        let mut e=pair();e.edges[0].conductance=3.0;
        assert_eq!(e.validate(0.5),Err(SignalError::UnstableTransport(1)));
    }
    #[test] fn ecology_is_deterministic(){
        let mut a=pair();let mut b=pair();a.regions[0].production_rate=0.1;b.regions[0].production_rate=0.1;
        for _ in 0..20{a.step(0.05).unwrap();b.step(0.05).unwrap();}assert_eq!(a,b);
    }
    #[test] fn receptor_response_is_monotonic_bounded_and_half_saturated(){
        let r=SignalReceptor{half_saturation:2.0,cooperativity:1.0,sensitivity:0.8};
        let low=r.response(0.5).unwrap();let half=r.response(2.0).unwrap();let high=r.response(1e100).unwrap();
        assert!(low<half&&half<high);assert!((half-0.4).abs()<1e-12);assert!(high<=0.8);
    }
    #[test] fn zero_signal_has_zero_receptor_response(){
        let r=SignalReceptor{half_saturation:1.0,cooperativity:2.0,sensitivity:1.0};
        assert_eq!(r.response(0.0).unwrap(),0.0);
    }
    #[test] fn invalid_rates_are_rejected(){
        let mut e=pair();e.regions[0].uptake_rate=-0.1;
        assert_eq!(e.validate(0.1),Err(SignalError::InvalidValue("region_parameters")));
    }
}
