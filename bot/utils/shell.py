"""Async subprocess runner for bot shell commands.

Used by the /shell handler (Wave 2) to execute arbitrary commands in
the bot container or on the host via Docker socket.

Telegram messages are capped at ~4096 chars; output is truncated to
the last 3000 characters to preserve the most relevant tail.
"""
import asyncio


async def run_command(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    """Run a subprocess asynchronously and return (returncode, output).

    Args:
        cmd: Command and arguments as a list, e.g. ["docker", "ps"].
        timeout: Maximum seconds to wait before killing the process.

    Returns:
        (returncode, output) — output is stderr+stdout combined,
        truncated to 3000 chars from the tail if longer.
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode(errors="replace")
        # Keep tail — more relevant for long build/deploy output
        return proc.returncode, output[-3000:] if len(output) > 3000 else output
    except asyncio.TimeoutError:
        proc.kill()
        return 1, f"Timeout: command did not complete within {timeout}s"
