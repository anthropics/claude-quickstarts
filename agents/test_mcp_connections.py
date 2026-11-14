"""Tests for MCP connection handling and cleanup on initialization failure."""

import asyncio
from contextlib import AsyncExitStack
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from agents.utils import connections
from agents.utils.connections import (
    MCPConnection,
    create_mcp_connection,
    setup_mcp_connections,
)


class DummyRWContext:
    def __init__(self):
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return AsyncMock(), AsyncMock()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.exited = True


class TestMCPConnectionCleanup(unittest.IsolatedAsyncioTestCase):
    """Test resource cleanup during MCP connection lifecycle."""

    async def test_aenter_cleans_up_on_initialize_failure(self):
        """Ensure transport and session are closed if initialize() raises."""
        rw_ctx = DummyRWContext()

        class FailingConnection(MCPConnection):
            async def _create_rw_context(self):
                return rw_ctx

        conn = FailingConnection()

        with patch("agents.utils.connections.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.initialize.side_effect = RuntimeError(
                "MCP initialization rejected"
            )
            mock_session_cls.return_value = mock_session

            with self.assertRaises(RuntimeError) as ctx:
                await conn.__aenter__()

            self.assertIn("MCP initialization rejected", str(ctx.exception))
            # Verify the transport was entered and then properly exited/unwound
            self.assertTrue(rw_ctx.entered)
            self.assertTrue(rw_ctx.exited)
            # Verify session context was entered and exited
            mock_session.__aenter__.assert_awaited_once()
            mock_session.__aexit__.assert_awaited_once()
            # Verify state is cleared
            self.assertIsNone(conn.session)
            self.assertIsNone(conn._stack)

    async def test_setup_mcp_connections_cleans_up_failed_initialization(self):
        """Ensure setup_mcp_connections unwinds failed connections without leaking."""
        rw_ctx = DummyRWContext()

        class FailingConnection(MCPConnection):
            async def _create_rw_context(self):
                return rw_ctx

        conn = FailingConnection()

        with patch("agents.utils.connections.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.initialize.side_effect = RuntimeError(
                "Server crashed during init"
            )
            mock_session_cls.return_value = mock_session

            with patch.object(
                connections, "create_mcp_connection", return_value=conn
            ):
                async with AsyncExitStack() as stack:
                    tools = await setup_mcp_connections(
                        [{"type": "stdio", "command": "dummy"}], stack
                    )
                    self.assertEqual(tools, [])
                    # The failed connection should not be registered in the outer stack
                    self.assertEqual(len(stack._exit_callbacks), 0)

            # Ensure transport cleanup completed during initialization failure
            self.assertTrue(rw_ctx.entered)
            self.assertTrue(rw_ctx.exited)
            self.assertIsNone(conn.session)

    async def test_successful_connection_lifecycle(self):
        """Ensure normal connection enters and exits cleanly."""
        rw_ctx = DummyRWContext()

        class SuccessfulConnection(MCPConnection):
            async def _create_rw_context(self):
                return rw_ctx

        conn = SuccessfulConnection()

        with patch("agents.utils.connections.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.initialize.return_value = None
            mock_session_cls.return_value = mock_session

            async with conn as entered_conn:
                self.assertIs(entered_conn, conn)
                self.assertTrue(rw_ctx.entered)
                self.assertFalse(rw_ctx.exited)
                self.assertIsNotNone(conn.session)
                mock_session.initialize.assert_awaited_once()

            # After exit block
            self.assertTrue(rw_ctx.exited)
            self.assertIsNone(conn.session)
            self.assertIsNone(conn._stack)

    async def test_stdio_child_process_terminated_on_initialization_failure(self):
        """Verify real stdio child process does not leak when initialization fails."""
        server_code = (
            "import json, os, pathlib, sys\n"
            "pathlib.Path(sys.argv[1]).write_text(str(os.getpid()))\n"
            "for line in sys.stdin:\n"
            "    try:\n"
            "        msg = json.loads(line)\n"
            "    except Exception:\n"
            "        continue\n"
            "    if msg.get('method') == 'initialize':\n"
            "        print(json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'error': {'code': -32603, 'message': 'refused'}}), flush=True)\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            server_file = Path(tmpdir) / "server.py"
            pid_file = Path(tmpdir) / "pid"
            server_file.write_text(server_code)
            config = {
                "type": "stdio",
                "command": sys.executable,
                "args": [str(server_file), str(pid_file)],
            }
            conn = create_mcp_connection(config)
            with self.assertRaises(Exception):
                async with conn:
                    pass

            self.assertTrue(pid_file.exists())
            pid = int(pid_file.read_text().strip())
            # Give OS process scheduler brief moment to reap
            await asyncio.sleep(0.2)

            is_alive = False
            if sys.platform == "win32":
                res = subprocess.run(
                    f'tasklist /fi "PID eq {pid}"',
                    shell=True,
                    capture_output=True,
                    text=True,
                )
                is_alive = str(pid) in res.stdout
            else:
                try:
                    os.kill(pid, 0)
                    is_alive = True
                except ProcessLookupError:
                    is_alive = False

            self.assertFalse(
                is_alive,
                f"Child process {pid} remained alive after failed initialization",
            )


if __name__ == "__main__":
    unittest.main()
