# C++ Demo Project

> A modern C++23 demo project showcasing an application built with CMake and pixi for reproducible builds.

## Features

- **C++23** — Modern standard with `CMAKE_CXX_EXTENSIONS OFF` for strict conformance
- **CMake 3.25+** — Modern CMake with presets, install rules, and optional Doxygen integration
- **Pixi** — Reproducible builds via conda-forge; all tooling managed, no system installs required
- **Multiple build presets** — Debug, Release
- **clang-format** — Enforced code style with WebKit-based configuration
- **clang-tidy** — Static analysis with moderate check set (bugprone, cert, modernize, performance, readability)

## Prerequisites

Install [pixi](https://pixi.sh). That's it — all other tools (CMake, Ninja, GCC/Clang) are managed by pixi via conda-forge.

```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

## Getting Started

### Configure

```bash
pixi run configure          # uses 'dev' preset by default
pixi run configure release  # or specify a preset
```

### Build

```bash
pixi run build              # builds all targets (dev preset)
pixi run build release cpp-demo  # specific preset and target
```

### Test

```bash
pixi run demo               # runs the demo app
```

## Build Presets

| Preset | Description |
|--------|-------------|
| `dev` | Debug build with GCC (default) |
| `release` | Optimized release build |


