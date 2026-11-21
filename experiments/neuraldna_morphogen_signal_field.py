"""Morphogen-like spatial signal field primitive for NeuralDNA 0.8.

This is a numerical research abstraction, not a biological tissue model or BA runtime.

Copyright © 2026 K410Sh4. All rights reserved.
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SignalEdge:
    left: int
    right: int
    distance: float
    permeability: float = 1.0


@dataclass(frozen=True, slots=True)
class SignalFieldConfig:
    time_step: float = 1.0
    diffusion: float = 0.1
    degradation: float | tuple[float, ...] = 0.05
    uptake_vmax: float | tuple[float, ...] = 0.0
    uptake_km: float | tuple[float, ...] = 1.0
    sensitivity_kd: float | tuple[float, ...] = 1.0
    hill_coefficient: float | tuple[float, ...] = 2.0
    exposure_clearance: float | tuple[float, ...] = 0.1
    max_substeps: int = 10000


@dataclass(frozen=True, slots=True)
class SignalFieldSnapshot:
    concentrations: tuple[tuple[float, ...], ...]
    responses: tuple[tuple[float, ...], ...]
    exposures: tuple[tuple[float, ...], ...]
    total_mass: float
    diffusion_substeps: int


def _expand_parameter(
    value: float | tuple[float, ...],
    region_count: int,
    name: str,
    *,
    strictly_positive: bool = False,
) -> tuple[float, ...]:
    values = value if isinstance(value, tuple) else (value,) * region_count
    if len(values) != region_count:
        raise ValueError(f"{name} must be scalar or contain one value per region")
    for item in values:
        if not math.isfinite(item):
            raise ValueError(f"{name} values must be finite")
        if item < 0.0 or (strictly_positive and item <= 0.0):
            qualifier = "positive" if strictly_positive else "non-negative"
            raise ValueError(f"{name} values must be {qualifier}")
    return values


def _hill_response(concentration: float, threshold: float, coefficient: float) -> float:
    if concentration <= 0.0:
        return 0.0
    log_ratio = coefficient * (math.log(concentration) - math.log(threshold))
    if log_ratio >= 50.0:
        return 1.0
    if log_ratio <= -50.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-log_ratio))


class SignalField:
    """Discrete reaction-diffusion field with saturable uptake and exposure memory."""

    def __init__(
        self,
        region_count: int,
        signal_classes: int,
        edges: tuple[SignalEdge, ...],
        config: SignalFieldConfig,
    ) -> None:
        if not isinstance(region_count, int) or region_count < 1:
            raise ValueError("region_count must be a positive integer")
        if not isinstance(signal_classes, int) or signal_classes < 1:
            raise ValueError("signal_classes must be a positive integer")
        if not math.isfinite(config.time_step) or config.time_step <= 0.0:
            raise ValueError("time_step must be finite and positive")
        if not math.isfinite(config.diffusion) or config.diffusion < 0.0:
            raise ValueError("diffusion must be finite and non-negative")
        if not isinstance(config.max_substeps, int) or config.max_substeps < 1:
            raise ValueError("max_substeps must be a positive integer")

        self.region_count = region_count
        self.signal_classes = signal_classes
        self.config = config
        self.degradation = _expand_parameter(
            config.degradation, region_count, "degradation"
        )
        self.uptake_vmax = _expand_parameter(
            config.uptake_vmax, region_count, "uptake_vmax"
        )
        self.uptake_km = _expand_parameter(
            config.uptake_km, region_count, "uptake_km", strictly_positive=True
        )
        self.sensitivity_kd = _expand_parameter(
            config.sensitivity_kd, region_count, "sensitivity_kd",
            strictly_positive=True,
        )
        self.hill_coefficient = _expand_parameter(
            config.hill_coefficient, region_count, "hill_coefficient",
            strictly_positive=True,
        )
        self.exposure_clearance = _expand_parameter(
            config.exposure_clearance, region_count, "exposure_clearance"
        )

        self.edges = tuple(edges)
        self.conductances: list[tuple[int, int, float]] = []
        seen_edges: set[tuple[int, int]] = set()
        row_sums = [0.0] * region_count
        for edge in self.edges:
            if not isinstance(edge.left, int) or not isinstance(edge.right, int):
                raise ValueError("edge endpoints must be integers")
            if not 0 <= edge.left < region_count or not 0 <= edge.right < region_count:
                raise ValueError("edge endpoint is outside the region range")
            if edge.left == edge.right:
                raise ValueError("self-edges are not allowed")
            pair = tuple(sorted((edge.left, edge.right)))
            if pair in seen_edges:
                raise ValueError("duplicate undirected edge")
            seen_edges.add(pair)
            if not math.isfinite(edge.distance) or edge.distance <= 0.0:
                raise ValueError("edge distance must be finite and positive")
            if (
                not math.isfinite(edge.permeability)
                or not 0.0 <= edge.permeability <= 1.0
            ):
                raise ValueError("edge permeability must be finite and in [0, 1]")
            conductance = edge.permeability / (edge.distance**2)
            self.conductances.append((edge.left, edge.right, conductance))
            row_sums[edge.left] += conductance
            row_sums[edge.right] += conductance

        self._max_row_sum = max(row_sums, default=0.0)
        self._concentrations = [
            [0.0] * signal_classes for _ in range(region_count)
        ]
        self._exposures = [[0.0] * signal_classes for _ in range(region_count)]
        self._step_count = 0

    def step(
        self,
        production: tuple[tuple[float, ...], ...],
    ) -> SignalFieldSnapshot:
        """Advance the field by one configured time step.

        Production values are rates, not future environmental states. Each region
        supplies one non-negative production rate per signal class.
        """
        if len(production) != self.region_count:
            raise ValueError("production must contain one row per region")
        for row in production:
            if len(row) != self.signal_classes:
                raise ValueError("production rows must match signal_classes")
            if any(not math.isfinite(value) or value < 0.0 for value in row):
                raise ValueError("production rates must be finite and non-negative")

        dt = self.config.time_step
        max_rate = self.config.diffusion * self._max_row_sum
        if not math.isfinite(max_rate):
            raise ValueError("diffusion stability rate overflowed")
        substeps = max(1, math.ceil(dt * max_rate / 0.45))
        if substeps > self.config.max_substeps:
            raise ValueError("required diffusion substeps exceed max_substeps")
        sub_dt = dt / substeps

        # Symmetric edge fluxes preserve total mass during closed-boundary diffusion.
        # Split production around each substep to reduce timestep-ordering bias.
        for _ in range(substeps):
            for region in range(self.region_count):
                for signal in range(self.signal_classes):
                    self._concentrations[region][signal] += (
                        production[region][signal] * sub_dt * 0.5
                    )

            delta = [
                [0.0] * self.signal_classes for _ in range(self.region_count)
            ]
            for left, right, conductance in self.conductances:
                rate = self.config.diffusion * sub_dt * conductance
                for signal in range(self.signal_classes):
                    flux = rate * (
                        self._concentrations[right][signal]
                        - self._concentrations[left][signal]
                    )
                    delta[left][signal] += flux
                    delta[right][signal] -= flux
            for region in range(self.region_count):
                for signal in range(self.signal_classes):
                    self._concentrations[region][signal] = max(
                        0.0,
                        self._concentrations[region][signal]
                        + delta[region][signal],
                    )

            # Exact first-order degradation and bounded saturable uptake.
            for region in range(self.region_count):
                decay_factor = math.exp(-self.degradation[region] * sub_dt)
                for signal in range(self.signal_classes):
                    concentration = (
                        self._concentrations[region][signal] * decay_factor
                    )
                    uptake = (
                        self.uptake_vmax[region]
                        * sub_dt
                        * concentration
                        / (self.uptake_km[region] + concentration)
                    )
                    concentration = max(
                        0.0, concentration - min(concentration, uptake)
                    )
                    concentration += production[region][signal] * sub_dt * 0.5
                    self._concentrations[region][signal] = concentration

                    response = _hill_response(
                        concentration,
                        self.sensitivity_kd[region],
                        self.hill_coefficient[region],
                    )
                    self._exposures[region][signal] = (
                        self._exposures[region][signal]
                        * math.exp(-self.exposure_clearance[region] * sub_dt)
                        + response * sub_dt
                    )

        self._step_count += 1
        return self.snapshot(substeps)

    def snapshot(self, diffusion_substeps: int = 1) -> SignalFieldSnapshot:
        concentrations = tuple(tuple(row) for row in self._concentrations)
        responses = tuple(
            tuple(
                _hill_response(
                    concentration,
                    self.sensitivity_kd[region],
                    self.hill_coefficient[region],
                )
                for concentration in row
            )
            for region, row in enumerate(concentrations)
        )
        exposures = tuple(tuple(row) for row in self._exposures)
        total_mass = math.fsum(value for row in concentrations for value in row)
        return SignalFieldSnapshot(
            concentrations=concentrations,
            responses=responses,
            exposures=exposures,
            total_mass=total_mass,
            diffusion_substeps=diffusion_substeps,
        )


def run() -> None:
    """Small reproducible field-physics benchmark; no adaptation policy is applied."""
    edges = tuple(
        SignalEdge(index, index + 1, distance=1.0)
        for index in range(6)
    )
    scenarios = (
        ("low_transport", 0.05, 0.10, 0.0),
        ("medium_transport", 0.25, 0.10, 0.0),
        ("high_transport", 0.80, 0.10, 0.0),
        ("high_removal", 0.25, 0.80, 0.25),
    )
    for name, diffusion, degradation, uptake in scenarios:
        field = SignalField(
            7,
            1,
            edges,
            SignalFieldConfig(
                diffusion=diffusion,
                degradation=degradation,
                uptake_vmax=uptake,
                uptake_km=0.5,
                sensitivity_kd=0.2,
                hill_coefficient=2.0,
                exposure_clearance=0.2,
            ),
        )
        for _ in range(80):
            field.step(((1.0,),) + ((0.0,),) * 6)
        result = field.snapshot()
        profile = tuple(round(row[0], 4) for row in result.concentrations)
        print(
            f"{name:18s} mass={result.total_mass:.4f} "
            f"substeps={result.diffusion_substeps} profile={profile}"
        )


if __name__ == "__main__":
    run()
