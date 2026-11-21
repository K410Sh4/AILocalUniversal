use serde::{Deserialize, Serialize};
use std::fmt::{Display, Formatter};

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExecutionTarget {
    Cpu,
    Gpu,
    Npu,
    Remote,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct ResourceVector {
    /// CPU em millicores: 1000 representa um núcleo lógico completo.
    pub cpu_millis: u32,
    pub ram_bytes: u64,
    pub gpu_millis: u32,
    pub vram_bytes: u64,
    pub npu_units: u32,
}

impl ResourceVector {
    pub fn fits_within(&self, limit: &Self) -> bool {
        self.cpu_millis <= limit.cpu_millis
            && self.ram_bytes <= limit.ram_bytes
            && self.gpu_millis <= limit.gpu_millis
            && self.vram_bytes <= limit.vram_bytes
            && self.npu_units <= limit.npu_units
    }

    pub fn checked_add(&self, other: &Self) -> Option<Self> {
        Some(Self {
            cpu_millis: self.cpu_millis.checked_add(other.cpu_millis)?,
            ram_bytes: self.ram_bytes.checked_add(other.ram_bytes)?,
            gpu_millis: self.gpu_millis.checked_add(other.gpu_millis)?,
            vram_bytes: self.vram_bytes.checked_add(other.vram_bytes)?,
            npu_units: self.npu_units.checked_add(other.npu_units)?,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ResourceSnapshot {
    pub total: ResourceVector,
    pub available: ResourceVector,
    pub available_targets: Vec<ExecutionTarget>,
}

impl ResourceSnapshot {
    pub fn validate(&self) -> Result<(), ResourceError> {
        if !self.available.fits_within(&self.total) {
            return Err(ResourceError::AvailableExceedsTotal);
        }
        if self.available_targets.is_empty() {
            return Err(ResourceError::NoExecutionTarget);
        }
        Ok(())
    }

    pub fn supports(&self, target: ExecutionTarget) -> bool {
        self.available_targets.contains(&target)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct ResourceBudget {
    /// Limite de reserva simultânea administrado pelo runtime.
    pub max: ResourceVector,
}

impl ResourceBudget {
    pub fn new(max: ResourceVector, snapshot: &ResourceSnapshot) -> Result<Self, ResourceError> {
        snapshot.validate()?;
        if !max.fits_within(&snapshot.available) {
            return Err(ResourceError::BudgetExceedsAvailable);
        }
        Ok(Self { max })
    }

    /// Aplica o perfil de processamento ao orçamento lógico de CPU.
    ///
    /// RAM, VRAM e aceleradores ficam limitados pela disponibilidade informada,
    /// sem multiplicadores arbitrários. Esta reserva não é um cgroup nem garante
    /// uma porcentagem exata de utilização física.
    pub fn from_profile(
        snapshot: &ResourceSnapshot,
        profile: ProcessingProfile,
    ) -> Result<Self, ResourceError> {
        snapshot.validate()?;
        let cpu_cap =
            (u64::from(snapshot.total.cpu_millis) * u64::from(profile.cpu_percent())) / 100;
        let cpu_millis = cpu_cap.min(u64::from(snapshot.available.cpu_millis)) as u32;
        let max = ResourceVector {
            cpu_millis,
            ram_bytes: snapshot.available.ram_bytes,
            gpu_millis: snapshot.available.gpu_millis,
            vram_bytes: snapshot.available.vram_bytes,
            npu_units: snapshot.available.npu_units,
        };
        Self::new(max, snapshot)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ProcessingProfile {
    Light,
    Medium,
    Ultra,
}

impl ProcessingProfile {
    pub const fn cpu_percent(self) -> u8 {
        match self {
            Self::Light => 33,
            Self::Medium => 66,
            Self::Ultra => 95,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ResourceError {
    AvailableExceedsTotal,
    BudgetExceedsAvailable,
    NoExecutionTarget,
}

impl Display for ResourceError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> std::fmt::Result {
        write!(formatter, "{self:?}")
    }
}

impl std::error::Error for ResourceError {}
