"""
OpenCode headless HTTP API client for the ZeptoCode prompt optimization harness.
"""
import json
import logging
import os
import queue
import socket
import subprocess
import threading
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class OpenCodeClient:
    """HTTP client for OpenCode headless API."""

    def __init__(self, repo_root: Path, scenario_dir: Path, port: int = 4096):
        self.repo_root = Path(repo_root)
        self.scenario_dir = Path(scenario_dir)
        self.port = port
        self.base_url = f"http://localhost:{port}"

    def start_server(self) -> subprocess.Popen:
        """
        Start the OpenCode server with cwd set to the scenario project directory.
        Correct invocation: ocx opencode -p <profile> serve --port <N>
        """
        env = os.environ.copy()
        env["OPENCODE_OLLAMA_PORT"] = "8000"

        proc = subprocess.Popen(
            ["ocx", "opencode", "-p", "naga-ollama", "serve", "--port", str(self.port)],
            cwd=str(self.scenario_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        # Poll until port accepts connections (up to 30s)
        start_time = time.time()
        while time.time() - start_time < 30:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("localhost", self.port))
            sock.close()
            if result == 0:
                time.sleep(2)  # let HTTP layer fully initialise after TCP bind
                return proc
            time.sleep(0.2)

        proc.kill()
        proc.wait()
        raise RuntimeError(f"OpenCode server did not become ready on port {self.port} within 30s")

    def stop_server(self, proc: subprocess.Popen) -> None:
        """Gracefully stop the OpenCode server, force-killing if needed."""
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    def create_session(self) -> str:
        """Create a new session scoped to the scenario directory."""
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{self.base_url}/session",
                json={},
                params={"directory": str(self.scenario_dir)},
            )
            response.raise_for_status()
            return response.json()["id"]

    def send_prompt_async(self, session_id: str, text: str) -> None:
        """
        Fire a prompt and return immediately (HTTP 204).

        Uses POST /session/{id}/prompt_async so the call returns before the
        model starts generating. Completion is detected via the SSE stream.
        Slash commands (/activate-plan, /plan-session) expand correctly from
        prompt text via this endpoint.
        """
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{self.base_url}/session/{session_id}/prompt_async",
                json={"parts": [{"type": "text", "text": text}]},
                params={"directory": str(self.scenario_dir)},
            )
            response.raise_for_status()

    def wait_for_completion(self, session_id: str, idle_timeout: int = 300) -> list[dict]:
        """
        Collect SSE events until session.idle, session.error, or idle timeout.

        Runs the SSE consumer in a background thread so we can cleanly stop it
        without leaving the httpx stream connection hanging.

        Args:
            session_id: Session to monitor
            idle_timeout: Seconds of silence before declaring hung (default 300)

        Returns:
            List of message.part.updated event property dicts
        """
        result_queue: queue.Queue = queue.Queue()
        stop_event = threading.Event()

        def _consume():
            collected = []
            last_content = time.time()
            try:
                timeout = httpx.Timeout(
                    idle_timeout + 60.0,
                    connect=10.0,
                    read=idle_timeout + 60.0,
                    write=10.0,
                    pool=10.0,
                )
                with httpx.Client(timeout=timeout) as client:
                    with client.stream("GET", f"{self.base_url}/event") as response:
                        for line in response.iter_lines():
                            if stop_event.is_set():
                                break

                            if not line or not line.startswith("data:"):
                                if time.time() - last_content > idle_timeout:
                                    logger.warning(f"Idle timeout ({idle_timeout}s)")
                                    break
                                continue

                            try:
                                d = json.loads(line[5:].strip())
                            except json.JSONDecodeError:
                                continue

                            t = d.get("type")
                            props = d.get("properties", {})

                            if props.get("sessionID") != session_id:
                                if time.time() - last_content > idle_timeout:
                                    logger.warning(f"Idle timeout ({idle_timeout}s)")
                                    break
                                continue

                            if t == "message.part.updated":
                                collected.append(props)
                                last_content = time.time()
                            elif t == "session.idle":
                                # The plugin may inject another prompt on session.idle
                                # (next DAG node). Reset the timer and keep listening —
                                # true completion is silence for idle_timeout seconds.
                                logger.info(f"session.idle for {session_id} — resetting idle timer")
                                last_content = time.time()
                            elif t == "session.error":
                                logger.warning(f"session.error for {session_id}: {props}")
                                break
            except Exception as e:
                logger.warning(f"SSE consumer error: {e}")
            finally:
                result_queue.put(collected)

        thread = threading.Thread(target=_consume, daemon=True)
        thread.start()
        thread.join(timeout=idle_timeout + 120)

        if thread.is_alive():
            stop_event.set()
            logger.warning("SSE thread did not exit cleanly — forcing stop")

        try:
            return result_queue.get_nowait()
        except queue.Empty:
            return []

    def get_transcript(self, session_id: str, events: list[dict]) -> str:
        """Concatenate text from message.part.updated events into a transcript."""
        parts = []
        for event in events:
            part = event.get("part", {})
            if isinstance(part, dict):
                text = part.get("text") or part.get("content")
                if text and isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)

    def delete_session(self, session_id: str) -> None:
        """Delete a session (best-effort)."""
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.delete(f"{self.base_url}/session/{session_id}")
                if not (200 <= response.status_code < 300):
                    logger.warning(f"DELETE /session/{session_id} returned {response.status_code}")
        except Exception as e:
            logger.warning(f"Failed to delete session {session_id}: {e}")

    def reset_baseline(self) -> None:
        """
        Restore the scenario project directory to its committed baseline.

        Two steps, both scoped to the scenario subpath within the repo:
        1. git checkout -- <rel_path>  — restores all tracked files to HEAD
        2. git clean -fdx <rel_path>   — removes untracked files (build artifacts,
           CPM cache, .pixi envs, etc.)

        Both commands run from repo root with the scenario dir as a path argument,
        so they only touch that subdirectory and nothing else in the repo.
        """
        rel = str(self.scenario_dir.relative_to(self.repo_root))

        subprocess.run(
            ["git", "checkout", "--", rel],
            cwd=str(self.repo_root),
            check=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "clean", "-fdx", rel],
            cwd=str(self.repo_root),
            check=True,
            timeout=60,
        )
        logger.info(f"Baseline restored for {rel}")

    def run_scenario_session(
        self,
        scenario_name: str,
        kickoff_command: str,
        kickoff_arguments: str,
    ) -> str:
        """
        Run a complete scenario session end-to-end.

        1. Start server (cwd = scenario_dir)
        2. Create session (directory = scenario_dir)
        3. Fire prompt_async with the kickoff text
        4. Stream SSE until session.idle / error / timeout
        5. Extract transcript
        6. Cleanup: delete session → stop server → restore baseline
        """
        logger.info(f"Starting scenario: {scenario_name}")
        proc = self.start_server()
        try:
            session_id = self.create_session()
            logger.info(f"Session created: {session_id}")

            kickoff_text = f"/{kickoff_command} {kickoff_arguments}"
            self.send_prompt_async(session_id, kickoff_text)
            logger.info(f"Prompt fired: {kickoff_text[:80]}")

            events = self.wait_for_completion(session_id)
            logger.info(f"Collected {len(events)} events for {scenario_name}")

            transcript = self.get_transcript(session_id, events)
            self.delete_session(session_id)
            return transcript
        finally:
            self.stop_server(proc)
            self.reset_baseline()
