# OpenShell policy advisor guide

These two files are NVIDIA OpenShell's policy advisor guide, unmodified, from
[OpenShell v0.1.2](https://github.com/NVIDIA/OpenShell/tree/v0.1.2/crates/openshell-supervisor-process/src/skills)
(Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES, Apache License 2.0
in `LICENSE` beside this file; see also `NOTICE` at the project root).

OpenShell's supervisor installs them at `/etc/openshell/skills/` itself, but
under the 0.1.2 docker driver the workload runs non-root with no capabilities
and cannot be written to, so they never arrive (ISSUES.md). The sandbox image
copies them there instead. Replace them with the same files from the OpenShell
release you run.
