"""
OpenCode headless HTTP API client for the ZeptoCode prompt optimization harness.
"""
import json
import logging
import os
import socket
import subprocess
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class OpenCodeClient:
    """HTTP client for OpenCode headless API."""

    def __init__(self, repo_root: Path, scenario_dir: Path, port: int = 4096):
        """
        Initialize OpenCode client.

        Args:
            repo_root: Root of the ZeptoCode git repository (used for git reset --hard)
            scenario_dir: Working directory for the scenario project (server cwd + session directory)
            port: Port to run OpenCode server on (default: 4096)
        """
        self.repo_root = Path(repo_root)
        self.scenario_dir = Path(scenario_dir)
        self.port = port
        self.base_url = f"http://localhost:{port}"

    def start_server(self) -> subprocess.Popen:
        """
        Start the OpenCode server with cwd set to the scenario project directory.

        The server must run from the scenario dir so that agents resolve files,
        pixi environments, and .opencode/ session plans relative to the project.

        Returns:
            Popen object for the server process

        Raises:
            RuntimeError: If server port is not available after 30 seconds
        """
        env = os.environ.copy()
        env["OPENCODE_OLLAMA_PORT"] = "8000"

        proc = subprocess.Popen(
            ["ocx", "opencode", "-p", "naga-ollama", "--dangerously-skip-permissions", "--port", str(self.port)],
            cwd=str(self.scenario_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        # Poll until port accepts connections (up to 30s — ocx can be slow to start)
        start_time = time.time()
        while time.time() - start_time < 30:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("localhost", self.port))
            sock.close()
            if result == 0:
                # Give the HTTP layer a moment to fully initialise after TCP bind
                time.sleep(2)
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
        """
        Create a new session scoped to the scenario directory.

        The `directory` query parameter tells OpenCode which project this session
        belongs to, so agents find the right .opencode/ plans and Qdrant data.

        Returns:
            Session ID string
        """
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{self.base_url}/session",
                json={},
                params={"directory": str(self.scenario_dir)},
            )
            response.raise_for_status()
            return response.json()["id"]

    def send_command(self, session_id: str, command: str, arguments: str) -> dict:
        """
        Invoke a slash command via the dedicated command endpoint.

        This is the correct way to trigger slash commands like /activate-plan
        and /plan-session — they expand properly via this endpoint rather than
        being treated as raw text by the prompt endpoint.

        Args:
            session_id: Session ID
            command: Command name without the leading slash (e.g. "activate-plan")
            arguments: Everything after the command name (e.g. "cpp-demo-fmt-argparse-extension")

        Returns:
            Response JSON dict
        """
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.base_url}/session/{session_id}/command",
                json={"command": command, "arguments": arguments},
                params={"directory": str(self.scenario_dir)},
            )
            response.raise_for_status()
            return response.json()

    def send_message(self, session_id: str, text: str) -> dict:
        """
        Send a plain text prompt to an OpenCode session.

        Use send_command() for slash commands. Use this for free-form text
        (e.g. the /plan-session body, or any non-command prompt).

        Args:
            session_id: Session ID
            text: Message text

        Returns:
            Response JSON dict
        """
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.base_url}/session/{session_id}/prompt",
                json={"parts": [{"type": "text", "text": text}]},
                params={"directory": str(self.scenario_dir)},
            )
            response.raise_for_status()
            return response.json()

    def wait_for_completion(self, session_id: str, idle_timeout: int = 300) -> list[dict]:
        """
        Stream SSE events until the session goes idle or errors.

        Args:
            session_id: Session ID to monitor
            idle_timeout: Seconds of no content events before declaring completion (default 300)

        Returns:
            List of message.part.updated event property dicts
        """
        collected_events = []
        last_content_time = time.time()

        with httpx.Client(timeout=httpx.Timeout(connect=10.0, read=idle_timeout + 30.0)) as client:
            with client.stream("GET", f"{self.base_url}/event") as response:
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        # Check idle timeout on non-data lines too
                        if time.time() - last_content_time > idle_timeout:
                            logger.warning(f"No content events for {idle_timeout}s — declaring completion")
                            break
                        continue

                    try:
                        event_data = json.loads(line[5:].strip())
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse SSE data: {line[:120]}: {e}")
                        continue

                    event_type = event_data.get("type")
                    props = event_data.get("properties", {})

                    # Filter to this session only
                    if props.get("sessionID") != session_id:
                        if time.time() - last_content_time > idle_timeout:
                            logger.warning(f"No content events for {idle_timeout}s — declaring completion")
                            break
                        continue

                    if event_type == "message.part.updated":
                        collected_events.append(props)
                        last_content_time = time.time()
                    elif event_type == "session.idle":
                        logger.info(f"session.idle received for {session_id}")
                        return collected_events
                    elif event_type == "session.error":
                        logger.warning(f"session.error received: {props}")
                        return collected_events

        return collected_events

    def get_transcript(self, session_id: str, events: list[dict]) -> str:
        """
        Concatenate text content from collected message.part.updated events.

        Args:
            session_id: Unused; kept for API compatibility
            events: Event property dicts from wait_for_completion()

        Returns:
            Full transcript as a single string
        """
        parts = []
        for event in events:
            part = event.get("part", {})
            if isinstance(part, dict):
                text = part.get("text") or part.get("content")
                if text and isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)

    def delete_session(self, session_id: str) -> None:
        """Delete a session (best-effort; logs on failure)."""
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.delete(f"{self.base_url}/session/{session_id}")
                if not (200 <= response.status_code < 300):
                    logger.warning(f"DELETE /session/{session_id} returned {response.status_code}")
        except Exception as e:
            logger.warning(f"Failed to delete session {session_id}: {e}")

    def reset_baseline(self) -> None:
        """
        Run git reset --hard from the repo root to restore all tracked files
        (prompt files, agents, .opencode/qdrant SQLite baseline).

        Server must be stopped before calling this to avoid SQLite file locks.
        """
        subprocess.run(
            ["git", "checkout", "--", "."],
            cwd=str(self.repo_root),
            check=True,
            timeout=30,
        )
        logger.info("Baseline restored via git checkout -- .")

    def run_scenario_session(
        self,
        scenario_name: str,
        kickoff_command: str,
        kickoff_arguments: str,
    ) -> str:
        """
        Run a complete scenario session end-to-end.

        Sequence:
          1. Start server (cwd = scenario_dir)
          2. Create session (directory = scenario_dir)
          3. Send slash command via /command endpoint
          4. Stream events until idle/error/timeout
          5. Extract transcript
          6. Cleanup: delete session → stop server → git reset

        Args:
            scenario_name: Human-readable name for logging
            kickoff_command: Slash command name without leading slash (e.g. "activate-plan")
            kickoff_arguments: Arguments string (e.g. "cpp-demo-fmt-argparse-extension")

        Returns:
            Full session transcript string
        """
        logger.info(f"Starting scenario: {scenario_name}")
        proc = self.start_server()
        try:
            session_id = self.create_session()
            logger.info(f"Session created: {session_id}")

            self.send_command(session_id, kickoff_command, kickoff_arguments)
            logger.info(f"Command sent: /{kickoff_command} {kickoff_arguments}")

            events = self.wait_for_completion(session_id)
            logger.info(f"Collected {len(events)} events for {scenario_name}")

            transcript = self.get_transcript(session_id, events)
            self.delete_session(session_id)
            return transcript
        finally:
            self.stop_server(proc)
            self.reset_baseline()
