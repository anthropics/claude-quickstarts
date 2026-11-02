"""Least-privilege policy for Managed Agents workers in OpenShell sandboxes.

The package keeps one loop running for every agent profile:

* grow: the reviewer approves a proposed network rule only when the sandbox's
  policy with that rule still proves to sit inside the profile's signed
  ceiling (``grow``);
* promote: grants that sessions approved and then used become the starting
  policy of the profile's next sessions (``promote``);
* shrink: starting grants that sessions stopped using are removed, and the
  smaller policy is proved to grant nothing the old one did not (``shrink``).
"""

__version__ = "0.1.0"
