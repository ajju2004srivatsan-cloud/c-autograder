"""Sandboxed C compiler, resource-bounded execution runner, and first-pass sanity sweep."""

from __future__ import annotations

import os
import re
import resource
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class CompileResult:
    """Outcome of compiling a C submission."""

    compiled: bool
    binary_path: Optional[Path]
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    raw_stderr: str = ""
    compiler_version: str = ""


@dataclass
class RunResult:
    """Outcome of running a compiled binary inside the resource-limited sandbox."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    crashed: bool
    elapsed_s: float


@dataclass
class FirstPassReport:
    """Summary of the coordinator's cheap first-pass sanity check."""

    compiled: bool
    smoke_ok: bool
    suspected_infinite_loop: bool
    static_sanity_ok: bool
    warnings_count: int
    notes: List[str] = field(default_factory=list)


def detect_c_compiler() -> str:
    """Return the preferred C compiler executable on the host."""
    for candidate in ("gcc", "clang", "cc"):
        if shutil.which(candidate):
            return candidate
    raise RuntimeError("No C compiler (gcc/clang/cc) found on PATH.")


def get_compiler_version(compiler: Optional[str] = None) -> str:
    """Return a concise version string for the active C compiler."""
    comp = compiler or detect_c_compiler()
    try:
        proc = subprocess.run(
            [comp, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        first_line = (proc.stdout or proc.stderr).splitlines()[0] if (proc.stdout or proc.stderr) else comp
        match = re.search(r"(\d+\.\d+\.\d+)", first_line)
        return match.group(1) if match else first_line.strip()
    except Exception:
        return "unknown"


def compile_submission(
    source_path: str | Path,
    output_binary: Optional[str | Path] = None,
    flags: Optional[List[str]] = None,
) -> CompileResult:
    """Compile a C source file with strict warning flags."""
    src = Path(source_path)
    if not src.is_file():
        raise FileNotFoundError(f"C submission not found: {src}")

    compiler = detect_c_compiler()
    if output_binary is None:
        fd, temp_bin = tempfile.mkstemp(prefix="autograder_bin_")
        os.close(fd)
        bin_path = Path(temp_bin)
    else:
        bin_path = Path(output_binary)

    compile_flags = flags if flags is not None else ["-O2", "-Wall", "-Wextra", "-std=c11"]
    cmd = [compiler, *compile_flags, str(src), "-o", str(bin_path), "-lm"]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    warnings: List[str] = []
    errors: List[str] = []
    for line in proc.stderr.splitlines():
        if "warning:" in line:
            warnings.append(line.strip())
        elif "error:" in line:
            errors.append(line.strip())

    compiled_ok = proc.returncode == 0 and bin_path.is_file()
    return CompileResult(
        compiled=compiled_ok,
        binary_path=bin_path if compiled_ok else None,
        warnings=warnings,
        errors=errors,
        raw_stderr=proc.stderr,
        compiler_version=get_compiler_version(compiler),
    )


def _apply_resource_limits(cpu_seconds: int, memory_mb: int) -> None:
    """Pre-exec hook for child processes to cap CPU time, file size, and memory."""
    try:
        cpu_lim = max(1, int(cpu_seconds) + 1)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_lim, cpu_lim))
    except (ValueError, resource.error):
        pass

    try:
        # Cap output file size to 8 MB to prevent disk-fill attacks
        fsize_bytes = 8 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_bytes, fsize_bytes))
    except (ValueError, resource.error):
        pass

    # On Linux, enforce RLIMIT_AS; on macOS Darwin RLIMIT_AS can break dyld mmap with ASan,
    # so only set RLIMIT_DATA when > 0 and supported.
    if os.uname().sysname == "Linux" and memory_mb > 0:
        try:
            mem_bytes = int(memory_mb) * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except (ValueError, resource.error):
            pass


def run_binary_sandboxed(
    binary_path: str | Path,
    stdin_data: str = "",
    time_limit_s: float = 1.0,
    memory_limit_mb: int = 64,
    env_overrides: Optional[dict] = None,
) -> RunResult:
    """Execute a compiled C binary under fixed wall-clock timeout and resource limits."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)

    start = time.perf_counter()
    try:
        proc = subprocess.run(
            [str(binary_path)],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=time_limit_s,
            env=env,
            preexec_fn=lambda: _apply_resource_limits(int(time_limit_s) + 1, memory_limit_mb),
            check=False,
        )
        elapsed = time.perf_counter() - start
        crashed = proc.returncode < 0 or proc.returncode in (134, 136, 139)
        return RunResult(
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            timed_out=False,
            crashed=crashed,
            elapsed_s=elapsed,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - start
        out = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return RunResult(
            exit_code=-9,
            stdout=out,
            stderr=err,
            timed_out=True,
            crashed=False,
            elapsed_s=elapsed,
        )


def check_static_sanity(source_code: str) -> tuple[bool, List[str]]:
    """Verify basic structural sanity: main() present, input reader, output writer, and return."""
    notes: List[str] = []
    has_main = bool(re.search(r"\bmain\s*\(", source_code))
    has_reader = bool(re.search(r"\b(scanf|fscanf|getchar|fgets|gets|read|cin)\b", source_code))
    has_writer = bool(re.search(r"\b(printf|fprintf|putchar|puts|fputs|write|cout)\b", source_code))
    has_return = bool(re.search(r"\breturn\b", source_code))

    if not has_main:
        notes.append("Missing main() entry point.")
    if not has_reader:
        notes.append("No standard input reader (e.g. scanf/fgets) detected.")
    if not has_writer:
        notes.append("No standard output writer (e.g. printf/puts) detected.")
    if not has_return:
        notes.append("No return statement found in submission.")

    return (has_main and has_writer and has_return), notes


def run_first_pass(
    source_path: str | Path,
    sample_input: str = "7 5\n",
    time_limit_s: float = 1.0,
    memory_limit_mb: int = 64,
) -> tuple[FirstPassReport, CompileResult]:
    """Perform the coordinator's cheap first-pass sanity sweep."""
    src_path = Path(source_path)
    source_text = src_path.read_text(encoding="utf-8", errors="replace")

    static_ok, notes = check_static_sanity(source_text)
    compile_res = compile_submission(src_path)

    if not compile_res.compiled or compile_res.binary_path is None:
        notes.append("Compilation failed during first pass.")
        return (
            FirstPassReport(
                compiled=False,
                smoke_ok=False,
                suspected_infinite_loop=False,
                static_sanity_ok=static_ok,
                warnings_count=len(compile_res.warnings),
                notes=notes,
            ),
            compile_res,
        )

    smoke_res = run_binary_sandboxed(
        compile_res.binary_path,
        stdin_data=sample_input,
        time_limit_s=time_limit_s,
        memory_limit_mb=memory_limit_mb,
    )

    smoke_ok = not smoke_res.timed_out and not smoke_res.crashed and smoke_res.exit_code == 0
    if smoke_res.timed_out:
        notes.append(f"Smoke run timed out after {time_limit_s}s; suspected infinite loop.")
    elif smoke_res.crashed:
        notes.append(f"Smoke run crashed with exit code {smoke_res.exit_code}.")

    return (
        FirstPassReport(
            compiled=True,
            smoke_ok=smoke_ok,
            suspected_infinite_loop=smoke_res.timed_out,
            static_sanity_ok=static_ok,
            warnings_count=len(compile_res.warnings),
            notes=notes,
        ),
        compile_res,
    )
