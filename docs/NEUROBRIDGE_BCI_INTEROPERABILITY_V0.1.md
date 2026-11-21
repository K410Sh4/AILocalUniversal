# NeuroBridge — BCI interoperability architecture 0.1

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

> **Status: architecture proposal only.** No implant connection, neural-signal acquisition, stimulation, clinical workflow, or medical-device functionality is implemented by this document.

## 1. Objective

Prepare AILocal Universal and the BA to interoperate with brain-computer interfaces (BCIs) without making the BA dependent on a single manufacturer.

The Brain Artificial (BA) is a distinct artificial developmental and adaptive system, not conventional Artificial Intelligence, an LLM, or a Transformer. K.IA is a separate coordination runtime. A BCI is an optional human-computer input/output channel; it is not the BA's brain, training substrate, or source of authority.

The long-term goal is **safe co-adaptation**:
- the person learns to express intentions through the interface;
- an authorized BCI system decodes signals into supported intents;
- the BA learns a user-approved mapping between decoded intents and digital tasks;
- feedback lets the person correct the BA and lets the interface calibration improve;
- the person retains control, consent, and the ability to stop or reset the adaptation.

This can support a person's learning to operate an approved BCI and the BA's adaptation to user-confirmed intent mappings. It does **not** mean the BA can directly train, rewrite, stimulate, or modify human neural tissue. Any closed-loop neural stimulation or therapeutic training would be a separate medical-device/clinical system requiring provider authorization, clinical oversight, ethics review, and regulatory approval; it is outside this project scope.

## 2. What is publicly documented about Neuralink

Neuralink describes an implant that records neural activity near neurons and electronics that transmit processed signals to its application, which decodes the stream into actions and intents. Its public Telepathy material describes cursor navigation and mouse clicks; it also states that experimental capabilities are not available to every participant and that the devices remain investigational, not approved by the FDA or other regulatory authorities.

Official references:
- Neuralink, [Technology](https://neuralink.com/technology/).
- Neuralink, [Telepathy — device control](https://neuralink.com/trials/device-control/).
- Neuralink, [PRIME Study brochure](https://neuralink.com/pdfs/PRIME-Study-Brochure.pdf).

**Integration finding:** the public materials reviewed describe Neuralink's own device/app workflow, not a public third-party N1 raw-signal SDK or general-purpose external application API. Therefore, a direct N1 connection is not currently an implementable assumption. The Neuralink adapter must remain a provider placeholder until Neuralink publishes or grants an authorized interface and its technical/legal conditions are reviewed.

No private protocol reverse engineering, undocumented radio access, bypass of vendor controls, or unauthorized extraction is permitted.

## 3. Neuralink open-source technology that may be useful

Neuralink has published **datarepo**, a Python catalog for querying and documenting multimodal data sources. Its public repository carries the Apache License 2.0. Neuralink's announcement explains that the catalog component was open-sourced, while explicitly clarifying that this was not a release of Neuralink's own neural data.

Potential AILU use:
- catalog authorized user-owned calibration sessions;
- relate session metadata, evaluation outcomes, and user-approved recordings;
- create local read-only query views for research and reproducibility.

It is **not** an N1 device SDK, live neural stream decoder, implant connector, or source of Neuralink participant data. It is not added as a dependency in this stage. Any future adoption requires a dependency-footprint, security, transitive-license, and local-hardware audit, while preserving Apache-2.0 notices and obligations.

References:
- [Neuralink datarepo repository](https://github.com/neuralinkcorp/datarepo).
- [Neuralink announcement: datarepo](https://neuralink.com/updates/datarepo/).
- [datarepo LICENSE.md — Apache-2.0](https://github.com/neuralinkcorp/datarepo/blob/main/LICENSE.md).

## 4. Proposed architecture

Human intent
→ Approved BCI device + vendor-controlled decoder
→ Authorized provider SDK / documented interface
→ Provider Adapter (Neuralink or another BCI)
→ Normalized Intent Event
→ Consent + Privacy + Safety Gateway
→ BA input / NAPA perception / K.IA context planner
→ Task proposal + confidence + risk classification
→ User confirmation when required
→ Allowlisted digital action adapter
→ User feedback / correction
→ Local calibration and BA personalization

### Components

1. **BCI Provider Adapter:** isolates vendor-specific SDKs, transport, authentication, capability discovery, and device lifecycle.
2. **Intent Normalizer:** maps only documented decoded outputs into stable AILU events; preserves source confidence and timestamps.
3. **Consent and Privacy Gateway:** binds each session to explicit scopes, retention, export, and revocation.
4. **Safety Gateway:** rejects stale, malformed, ambiguous, low-confidence, unauthorized, or out-of-scope events.
5. **BA Input:** treats decoded intent events as uncertain environmental/user observations, not commands with unconditional authority. NAPA/K.IA may assist with routing and task planning but do not define the BA's developmental architecture.
6. **K.IA Planner:** proposes tasks and checks capability, risk, and permissions before execution.
7. **Action Adapter:** initially supports reversible digital UI actions only, subject to the vendor's permitted interface.
8. **Co-adaptation Evaluator:** measures calibration drift, false activations, correction rate, latency, and user-confirmed success.

The BA must not directly depend on Neuralink-specific data structures. Provider adapters translate into the stable NeuroBridge contract.

## 5. Normalized event contract (proposal)

Every accepted event should include:
- schema version;
- provider and device capability identifier;
- pseudonymous session identifier;
- monotonic timestamp and sequence number;
- decoded intent/action class;
- confidence and calibration version when supplied by the provider;
- provenance and decoder version;
- consent scope and expiration;
- optional user confirmation/correction reference.

Do not assume raw spike trains, electrode channels, neural recordings, or clinical metadata are available. Missing provider fields remain unknown; the adapter must not invent them.

Raw neural recordings are excluded from the default BA memory path. They must never be silently copied into prompts, semantic memory, NeuralDNA, model training corpora, or .neuralinjector packages.

## 6. Co-adaptation: human and BA

The biological inspiration is reciprocal adaptation, not unilateral control.

- **Human-side learning:** the participant learns a stable mapping between intended actions and the BCI's decoded control vocabulary, following the device provider's approved calibration process.
- **BA-side adaptation:** the BA adapts only its local interpretation and task preferences from explicit corrections and confirmed outcomes; this is adaptation of the artificial system, not neural stimulation or direct alteration of the person's brain.
- **Shared calibration:** both sides can improve task performance over time, but each update has independent provenance and rollback.
- **Uncertainty:** confidence is calibrated per user, task, and session. A confident cursor signal must not be treated as a confident instruction to perform an unrelated high-impact task.
- **No forced learning:** no hidden reinforcement, manipulative feedback, or stimulation-based training is part of this architecture.

A future clinical rehabilitation workflow would require independent clinical design, ethics review, medical oversight, and regulatory authorization. It is outside this software proposal.

## 7. Safety, privacy, and security invariants

- Explicit, granular, revocable consent for every session and data category.
- Local-first processing and data minimization by default.
- Encryption at rest and authenticated transport where supported.
- No raw neural data retention unless separately enabled and justified.
- Short-lived event buffers; explicit retention and deletion controls.
- Fail closed on disconnect, stale timestamps, replay, sequence gaps, malformed data, or revoked consent.
- Allowlisted reversible actions first; high-impact actions require explicit confirmation.
- Emergency stop, pause, and immediate disconnect must be available independently of the BA.
- No autonomous shell execution, financial transfer, medical decision, or physical actuation from a neural event.
- No neural stimulation, implant parameter changes, or firmware control.
- No bypass of device safeguards or vendor access controls.
- All calibration updates are versioned, attributable, bounded, and reversible.

## 8. Validation stages

1. **Offline simulation:** synthetic decoded-intent events, noise, latency, dropout, drift, and false-positive injection.
2. **Recorded non-sensitive datasets:** only datasets whose license and consent permit the intended use.
3. **Desktop input adapter:** standard mouse/keyboard events in a sandbox with confirmation and emergency stop.
4. **Provider SDK evaluation:** only after a documented and authorized SDK/API is available.
5. **Human factors and safety review:** independent review before any participant-facing test.
6. **Clinical pathway:** only with the device provider, clinical team, ethics approval, and applicable regulatory authorization.

Initial metrics:
- intent classification precision/recall where ground truth is available;
- false activations per hour;
- missed-intent rate;
- calibration time and drift;
- end-to-end latency and event age;
- user correction and confirmation rate;
- safe rejection rate;
- performance under signal loss and device disconnect.

## 9. Licensing and provenance

The original NeuroBridge architecture, normalized contracts, tests, documentation, and independent provider-adapter code authored for AILocal Universal are project materials under:

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

This does not grant ownership of Neuralink's devices, software, trademarks, patents, trade secrets, protocols, or data. It does not relicense datarepo or any other third-party software. If datarepo is later used, its Apache-2.0 license and required notices remain applicable to that component. No Neuralink source code is copied into this proposal.

The project must not imply sponsorship, endorsement, partnership, compatibility certification, or authorization by Neuralink.

## 10. Integration gate

Do not implement a Neuralink-specific connector until all of the following exist:
- a public or contractually authorized SDK/API;
- documented authentication, event schema, data rights, and usage terms;
- permission to integrate with the relevant device/app workflow;
- security and privacy review;
- provider-side confirmation that the integration does not interfere with device safeguards.

Until then, only the vendor-neutral event simulator and desktop-side adapter may be developed. The BA remains independent and useful without any implant.
