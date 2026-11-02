"""Generated gRPC client for the OpenShell gateway (see scripts/gen-proto.sh).

protoc writes the generated modules with top-level imports of each other
(``import datamodel_pb2``), so this package puts its own directory on the
import path before they load.
"""

import os
import sys

_here = os.path.dirname(__file__)
if _here not in sys.path:
    sys.path.append(_here)

try:
    import openshell_pb2  # noqa: E402
    import openshell_pb2_grpc  # noqa: E402
    import sandbox_pb2  # noqa: E402
except ImportError as err:  # pragma: no cover
    raise ImportError("the OpenShell gRPC client is not generated; run scripts/gen-proto.sh") from err
