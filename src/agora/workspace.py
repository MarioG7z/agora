import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

from agora.errors import PermanentError


def read_file(path: str | Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise PermanentError(f"Cannot read {path}: {error}") from error


@dataclass
class PytestRun:
    passed: bool
    output: str


class Workspace:
    """The only folder where agents may write files and run tests."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def write_file(self, relative_path: str, content: str) -> Path:
        # resolve() collapses "..", and joining an absolute path replaces the root,
        # so both ways of escaping end up outside the root and are rejected here.
        target = (self.root / relative_path).resolve()
        if not target.is_relative_to(self.root):
            raise PermanentError(f"Path outside the workspace: {relative_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    async def run_pytest(self, time_limit: float = 60.0) -> PytestRun:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "pytest",
            "-q",
            cwd=self.root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), time_limit)
        except TimeoutError:
            # A hanging test must not hang the whole run: stop it and report a failure.
            process.kill()
            await process.wait()
            return PytestRun(passed=False, output=f"pytest stopped after {time_limit} seconds")
        return PytestRun(passed=process.returncode == 0, output=output.decode(errors="replace"))
