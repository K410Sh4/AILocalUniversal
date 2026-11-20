"""Synchronize JSON hardware examples from the Python canonical presets.

Run:
    python scripts/sync_neuralinjector_profiles.py
    python scripts/sync_neuralinjector_profiles.py --check
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "examples" / "neuralinjector" / "hardware" / "profiles"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when JSON examples differ from the Python canonical presets",
    )
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    from core.neuralinjector.resources import CANONICAL_PROFILES, serialize_hardware_profile

    mismatches: list[str] = []
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    for profile in CANONICAL_PROFILES:
        path = PROFILE_DIR / f"{profile.profile_id}.json"
        expected = json.dumps(
            serialize_hardware_profile(profile),
            ensure_ascii=False,
            indent=2,
        ) + "\n"
        actual = path.read_text(encoding="utf-8") if path.exists() else None
        if actual != expected:
            mismatches.append(str(path.relative_to(ROOT)))
            if not args.check:
                path.write_text(expected, encoding="utf-8")

    if args.check and mismatches:
        print("Perfis JSON divergentes:")
        for mismatch in mismatches:
            print(f" - {mismatch}")
        return 1
    if mismatches:
        print("Perfis sincronizados:")
        for mismatch in mismatches:
            print(f" - {mismatch}")
    else:
        print("Perfis JSON já estão sincronizados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
