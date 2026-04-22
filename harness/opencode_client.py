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

    def __init__(self, repo_root: Path, port: int = 4096):
        """
        Initialize OpenCode client.

        Args:
            repo_root: Root directory of the repository
            port: Port to run OpenCode server on (default: 4096)
        """
        self.repo_root = repo_root
        self.port = port
        self.base_url = f"http://localhost:{port}"

    def start_server(self) -> subprocess.Popen:
        """
        Start the OpenCode server.

        Returns:
            Popen object for the server process

        Raises:
            RuntimeError: If server port is not available after 10 seconds
        """
        env = os.environ.copy()
        env["OPENCODE_OLLAMA_PORT"] = "8000"

        proc = subprocess.Popen(
            ["ocx", "opencode", "serve", "-p", "naga-ollama", "--port", str(self.port)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )

        # Wait for port to be available
        start_time = time.time()
        while time.time() - start_time < 10:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("localhost", self.port))
            sock.close()
            if result == 0:
                # Port is open, but give server more time to be fully ready
                time.sleep(3)
                return proc
            time.sleep(0.2)

        raise RuntimeError(f"Server port {self.port} did not become available within 10 seconds")

    def stop_server(self, proc: subprocess.Popen) -> None:
        """
        Stop the OpenCode server.

        Args:
            proc: Popen object for the server process
        """
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    def create_session(self) -> str:
        """
        Create a new session in OpenCode.

        Returns:
            Session ID
        """
        with httpx.Client(timeout=10.0) as client:
            response = client.post(f"{self.base_url}/session", json={})
            return response.json()["id"]

    def send_message(self, session_id: str, text: str) -> dict:
        """
        Send a message to an OpenCode session.

        Args:
            session_id: Session ID
            text: Message text

        Returns:
            Response JSON dict
        """
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{self.base_url}/session/{session_id}/message",
                json={"parts": [{"type": "text", "text": text}]}
            )
            return response.json()

    def wait_for_completion(self, session_id: str) -> list[dict]:
        """
        Wait for session to complete by streaming events.

        Uses Server-Sent Events (SSE) to receive updates. Stops when:
        - A "session.idle" or "session.error" event is received, OR
        - 15 seconds of no content-bearing events (message.part.updated) have elapsed

        Args:
            session_id: Session ID

        Returns:
            List of "message.part.updated" event data dicts
        """
        collected_events = []
        last_content_event_time = time.time()

        with httpx.Client(timeout=httpx.Timeout(10.0, connect=10.0, read=90.0, write=10.0, pool=10.0)) as client:
            with client.stream("GET", f"{self.base_url}/event") as response:
                for line in response.iter_lines():
                    # Skip empty lines
                    if not line:
                        continue
                    
                    # Check if content-bearing event has been silent for too long
                    current_time = time.time()
                    if current_time - last_content_event_time > 15:
                        logger.warning("No content events for 15 seconds, assuming completion")
                        break

                    # Parse SSE data line (format: "data: {...}")
                    if line.startswith("data:"):
                        try:
                            data_json = line[5:].strip()
                            event_data = json.loads(data_json)
                            
                            # Extract type and properties
                            event_type = event_data.get("type")
                            properties = event_data.get("properties", {})
                            
                            # Only process events for this session
                            if properties.get("sessionID") == session_id:
                                # Collect message.part.updated events
                                if event_type == "message.part.updated":
                                    collected_events.append(properties)
                                    last_content_event_time = current_time
                                
                                # Stop on session completion
                                elif event_type == "session.idle":
                                    logger.info("Session entered idle state")
                                    return collected_events
                                elif event_type == "session.error":
                                    logger.warning(f"Session error event received: {properties}")
                                    return collected_events
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse event data: {line[:100]}: {e}")

        return collected_events

    def get_transcript(self, session_id: str, events: list[dict]) -> str:
        """
        Extract transcript from session events.

        Extracts text content from message.part.updated events.
        Looks for part.text or part.content fields.

        Args:
            session_id: Session ID (for consistency)
            events: List of event properties dicts from wait_for_completion()

        Returns:
            Concatenated transcript string
        """
        transcript_parts = []

        for event in events:
            # Events are message.part.updated properties with 'part' key
            content = None
            
            if "part" in event and isinstance(event["part"], dict):
                # Try 'text' field first (new format)
                content = event["part"].get("text")
                
                # Fallback to 'content' field (legacy format)
                if content is None:
                    content = event["part"].get("content")

            # Extract and append non-empty strings
            if isinstance(content, str) and content:
                transcript_parts.append(content)

        return "\n".join(transcript_parts)

    def delete_session(self, session_id: str) -> None:
        """
        Delete a session.

        Args:
            session_id: Session ID
        """
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.delete(f"{self.base_url}/session/{session_id}")
                if not (200 <= response.status_code < 300):
                    logger.warning(f"Delete session returned status {response.status_code}")
        except Exception as e:
            logger.warning(f"Failed to delete session {session_id}: {e}")

    def reset_baseline(self, scenario_dir: Path) -> None:
        """
        Reset the repository to a clean state using git.

        Note: scenario_dir parameter is accepted for API compatibility but
        the reset is performed on self.repo_root.

        Args:
            scenario_dir: Scenario directory (not used, for API compatibility)
        """
        subprocess.run(
            ["git", "reset", "--hard"],
            cwd=self.repo_root,
            check=True,
            timeout=30
        )

    def run_scenario_session(self, scenario_name: str, kickoff_message: str) -> str:
        """
        Run a complete scenario session: start server, create session, send message,
        wait for completion, extract transcript, clean up.

        Args:
            scenario_name: Name of the scenario (for logging)
            kickoff_message: Initial message to send to the session

        Returns:
            Transcript from the session
        """
        proc = self.start_server()
        try:
            session_id = self.create_session()
            self.send_message(session_id, kickoff_message)
            events = self.wait_for_completion(session_id)
            transcript = self.get_transcript(session_id, events)
            try:
                self.delete_session(session_id)
            except Exception as e:
                logger.warning(f"Failed to delete session during cleanup: {e}")
            return transcript
        finally:
            self.stop_server(proc)
            self.reset_baseline(Path(self.repo_root) / "optimization-scenarios" / "cpp-greenfield-project")
