# Third-party software and model notices

This file records the direct dependencies and development/build tools declared by the project at the time this notice was prepared. Versions in `pyproject.toml` are ranges, not a lockfile. The licenses of resolved transitive dependencies and individual Qt modules must be checked from the exact installed distributions before each release.

## Runtime and platform

| Component | Declared use | License / terms | Project relationship |
|---|---|---|---|
| Python | Runtime, Python 3.11+ | Python Software Foundation License (PSF-2.0) | External interpreter; not relicensed by this project |
| PySide6 / Qt for Python | Desktop UI, `PySide6>=6.7,<7` | Community distributions are offered under LGPL/GPL options; Qt commercial licensing is also available. Verify the exact wheel and each Qt module. | Third-party runtime dependency |
| Shiboken6 / Qt libraries | Installed as part of the Qt for Python stack | License depends on the distributed component and selected Qt licensing option | Third-party dependency; preserve each applicable notice |
| HTTPX | HTTP client, `httpx>=0.27,<1` | BSD-3-Clause | Third-party runtime dependency |
| Ollama | Separate local model server/API | MIT for the Ollama software repository | External application; this repository uses its API and does not relicense Ollama |

## Development and build tools

| Component | Declared use | License |
|---|---|---|
| pytest | Tests, `pytest>=8.0` | MIT |
| pytest-asyncio | Async test support, `pytest-asyncio>=0.23` | Apache-2.0 |
| Ruff | Linting, `ruff>=0.5` | MIT |
| setuptools | Build backend, `setuptools>=77.0.3` | MIT |
| wheel | Build support | MIT |

## Model weights, adapters, and datasets

Model weights are not the Ollama server and are not covered by the Ollama software license. Each downloaded model, LoRA/DoRA adapter, tokenizer, dataset, evaluation set, and other model artifact may have its own license, acceptable-use policy, attribution requirements, or commercial-use restrictions. Check the model card and license of the exact artifact and version before downloading, packaging, sharing, or commercial use.

The example model names in documentation do not grant rights to their weights. No model weights are included or relicensed by this repository unless a future artifact explicitly states otherwise.

## Qt / PySide6 distribution warning

The project code is proprietary, but that does not override the license of Qt for Python. Qt for Python documents LGPL/GPL and commercial licensing options. The LGPL route can permit a proprietary application, but distribution must satisfy the applicable conditions, which can include providing the corresponding source for the LGPL library and allowing users to replace or relink the library. Packaging, static linking, frozen executables, and use of GPL-only Qt modules require a specific review before distributing binaries.

Do not assume that `pip install pyside6` means every possible Qt module is available under the same terms. Inspect the actual modules shipped and the license files included in the exact installed wheel.

## Inventory maintenance

Before a public binary release or commercial distribution:

1. Resolve and lock exact dependency versions.
2. Generate a complete Software Bill of Materials (SBOM) including transitive dependencies.
3. Inspect the license metadata and full license files for each resolved package.
4. Include required notices and source/relinking materials for LGPL/GPL components where applicable.
5. Verify the separate licenses for every model, adapter, dataset, font, icon, and other bundled asset.
6. Do not distribute a component whose terms conflict with the distribution plan until it has been replaced, removed, or separately licensed.

## License references

- [Python license](https://docs.python.org/3/license.html)
- [Qt for Python licensing](https://doc.qt.io/qtforpython-6/licenses.html)
- [Qt commercial use and LGPL/GPL obligations](https://www.qt.io/development/open-source-lgpl-obligations)
- [HTTPX project](https://github.com/encode/httpx)
- [pytest project](https://github.com/pytest-dev/pytest)
- [pytest-asyncio project](https://github.com/pytest-dev/pytest-asyncio)
- [Ruff project](https://github.com/astral-sh/ruff)
- [setuptools project](https://github.com/pypa/setuptools)
- [wheel project](https://github.com/pypa/wheel)
- [Ollama license](https://github.com/ollama/ollama/blob/main/LICENSE)

This is an inventory of the declared direct dependencies, not a certification of every transitive package. Exact versions and license terms can change.
