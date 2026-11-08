"""A failed install must not leave a started sandbox for the next reclaim."""

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _stub(name: str, **attrs: object) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


class CreateSandboxParams:
    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


class Daytona:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass


_stub("daytona_sdk", CreateSandboxParams=CreateSandboxParams, Daytona=Daytona)


class AsyncAnthropic:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass


anthropic = _stub("anthropic", AsyncAnthropic=AsyncAnthropic)
_stub("anthropic.types")
_stub("anthropic.types.beta", BetaWebhookEvent=object)
sys.modules["anthropic"].types = sys.modules["anthropic.types"]


class HTTPException(Exception):
    def __init__(self, status_code: int = 0, detail: str = "") -> None:
        super().__init__(detail)
        self.status_code = status_code


class FastAPI:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def post(self, *args: object, **kwargs: object):
        def decorate(fn):
            return fn

        return decorate


_stub(
    "fastapi",
    FastAPI=FastAPI,
    HTTPException=HTTPException,
    Request=object,
    Response=object,
)

import daytona_webhook as wh


class FakeProcess:
    def __init__(self, fail: str) -> None:
        self.fail = fail
        self.commands: list[str] = []

    def exec(self, command: str, timeout: int | None = None):
        self.commands.append(command)
        if self.fail == "raise" and command.startswith("pip "):
            raise RuntimeError("registry down")
        if self.fail == "exit" and command.startswith("pip "):
            return types.SimpleNamespace(exit_code=1, result="no network")
        return types.SimpleNamespace(exit_code=0, result="")


class FakeSandbox:
    def __init__(self, sandbox_id: str, process: FakeProcess) -> None:
        self.id = sandbox_id
        self.process = process
        self.fs = self

    def upload_file(self, *_args: object, **_kwargs: object) -> None:
        return None


def test_pip_exception_deletes_the_sandbox(monkeypatch) -> None:
    deleted: list[str] = []
    process = FakeProcess("raise")
    sandbox = FakeSandbox("sb-1", process)

    class Client:
        def create(self, _params: object) -> FakeSandbox:
            return sandbox

        def delete(self, sb: FakeSandbox) -> None:
            deleted.append(sb.id)

    monkeypatch.setattr(wh, "daytona", Client())
    try:
        wh._spawn("sesn_a", environment_id="env_a", work_id="work_a", credentials={"ANTHROPIC_WORK_SECRET": "s"})
    except RuntimeError:
        pass
    else:
        raise AssertionError("pip failure must not look like a started runner")
    assert deleted == ["sb-1"]
    assert not any(cmd.startswith("nohup ") for cmd in process.commands)


def test_pip_nonzero_exit_deletes_the_sandbox(monkeypatch) -> None:
    deleted: list[str] = []
    process = FakeProcess("exit")

    class Client:
        def create(self, _params: object) -> FakeSandbox:
            return FakeSandbox("sb-2", process)

        def delete(self, sb: FakeSandbox) -> None:
            deleted.append(sb.id)

    monkeypatch.setattr(wh, "daytona", Client())
    try:
        wh._spawn("sesn_b", environment_id="env_b", work_id="work_b", credentials={"ANTHROPIC_WORK_SECRET": "s"})
    except RuntimeError:
        pass
    else:
        raise AssertionError("a failed pip exit must not leave the sandbox running")
    assert deleted == ["sb-2"]


def test_successful_spawn_keeps_the_sandbox(monkeypatch) -> None:
    deleted: list[str] = []
    process = FakeProcess("ok")

    class Client:
        def create(self, _params: object) -> FakeSandbox:
            return FakeSandbox("sb-3", process)

        def delete(self, sb: FakeSandbox) -> None:
            deleted.append(sb.id)

    monkeypatch.setattr(wh, "daytona", Client())
    sandbox_id = wh._spawn(
        "sesn_c", environment_id="env_c", work_id="work_c", credentials={"ANTHROPIC_WORK_SECRET": "s"}
    )
    assert sandbox_id == "sb-3"
    assert deleted == []
    assert any(cmd.startswith("nohup ") for cmd in process.commands)
