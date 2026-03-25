"""tmux split-screen manager for Conductor.

Creates and manages tmux layout:
  - Left 60%: Main window (user interaction / Conductor output)
  - Right 40%: 2×2 grid (4 Actor instance outputs)
"""

from __future__ import annotations

import subprocess
import shutil
from dataclasses import dataclass, field


@dataclass
class PaneInfo:
    """Information about a tmux pane assigned to an actor."""

    pane_id: str
    pane_index: int
    actor_instance_id: str | None = None
    status: str = "idle"  # idle | working | done | failed


@dataclass
class TmuxManager:
    """Manages tmux session with Conductor layout."""

    session_name: str = "conductor"
    main_pane_id: str = ""
    actor_panes: list[PaneInfo] = field(default_factory=list)
    _created: bool = False

    @staticmethod
    def is_available() -> bool:
        """Check if tmux is installed and available."""
        return shutil.which("tmux") is not None

    @staticmethod
    def is_inside_tmux() -> bool:
        """Check if we're running inside a tmux session."""
        import os
        return "TMUX" in os.environ

    def _run(self, *args: str, capture: bool = True) -> str:
        """Run a tmux command."""
        cmd = ["tmux"] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 and capture:
            raise RuntimeError(f"tmux command failed: {' '.join(cmd)}\n{result.stderr}")
        return result.stdout.strip() if capture else ""

    def create_session(self) -> None:
        """Create tmux session with Conductor layout.

        Layout:
        ┌────────────────────┬──────────────┐
        │                    │  Actor 0     │
        │   Main Window      ├──────────────┤
        │   (Conductor)      │  Actor 1     │
        │   60% width        ├──────────────┤
        │                    │  Actor 2     │
        │                    ├──────────────┤
        │                    │  Actor 3     │
        └────────────────────┴──────────────┘
        """
        if self._created:
            return

        # Kill existing session if any
        try:
            self._run("kill-session", "-t", self.session_name)
        except RuntimeError:
            pass

        # Create new session with main window
        self._run(
            "new-session", "-d", "-s", self.session_name,
            "-x", "200", "-y", "50",
        )

        # Get main pane ID
        self.main_pane_id = self._run(
            "display-message", "-t", self.session_name, "-p", "#{pane_id}"
        )

        # Set main pane title
        self._run(
            "select-pane", "-t", self.main_pane_id,
            "-T", "🎼 Conductor"
        )

        # Split right 40% for actor panes
        right_pane = self._run(
            "split-window", "-t", self.session_name,
            "-h", "-p", "40", "-P", "-F", "#{pane_id}",
        )

        # Split the right pane into 4 rows
        # right_pane is pane 0 of the right side
        pane_ids = [right_pane]

        # Split into 2 (top and bottom)
        bottom_pane = self._run(
            "split-window", "-t", right_pane,
            "-v", "-p", "75", "-P", "-F", "#{pane_id}",
        )
        pane_ids.append(bottom_pane)

        # Split bottom into 2
        bottom_2 = self._run(
            "split-window", "-t", bottom_pane,
            "-v", "-p", "66", "-P", "-F", "#{pane_id}",
        )
        pane_ids.append(bottom_2)

        # Split the last one
        bottom_3 = self._run(
            "split-window", "-t", bottom_2,
            "-v", "-p", "50", "-P", "-F", "#{pane_id}",
        )
        pane_ids.append(bottom_3)

        # Create PaneInfo for each actor pane
        self.actor_panes = [
            PaneInfo(pane_id=pid, pane_index=i)
            for i, pid in enumerate(pane_ids)
        ]

        # Set initial titles
        for i, pane in enumerate(self.actor_panes):
            self._run(
                "select-pane", "-t", pane.pane_id,
                "-T", f"Actor {i} (idle)"
            )

        # Focus on main pane
        self._run("select-pane", "-t", self.main_pane_id)

        # Enable pane titles
        self._run(
            "set-option", "-t", self.session_name,
            "pane-border-status", "top",
        )
        self._run(
            "set-option", "-t", self.session_name,
            "pane-border-format",
            " #{pane_title} ",
        )

        self._created = True

    def assign_actor(self, actor_instance_id: str, persona_name: str, specialty: str) -> PaneInfo | None:
        """Assign an actor to an available pane.

        Returns the PaneInfo if a pane was available, None otherwise.
        """
        for pane in self.actor_panes:
            if pane.actor_instance_id is None:
                pane.actor_instance_id = actor_instance_id
                pane.status = "working"
                title = f"🔨 {persona_name} ({specialty})"
                try:
                    self._run("select-pane", "-t", pane.pane_id, "-T", title)
                except RuntimeError:
                    pass
                return pane
        return None

    def update_pane_status(self, actor_instance_id: str, status: str, label: str = "") -> None:
        """Update pane title with actor status."""
        for pane in self.actor_panes:
            if pane.actor_instance_id == actor_instance_id:
                pane.status = status
                icons = {"working": "🔨", "done": "✅", "failed": "❌"}
                icon = icons.get(status, "❓")
                title = f"{icon} {label}" if label else f"{icon} {actor_instance_id}"
                try:
                    self._run("select-pane", "-t", pane.pane_id, "-T", title)
                except RuntimeError:
                    pass
                break

    def release_pane(self, actor_instance_id: str) -> None:
        """Release a pane back to idle state."""
        for pane in self.actor_panes:
            if pane.actor_instance_id == actor_instance_id:
                pane.actor_instance_id = None
                pane.status = "idle"
                try:
                    self._run(
                        "select-pane", "-t", pane.pane_id,
                        "-T", f"Actor {pane.pane_index} (idle)"
                    )
                except RuntimeError:
                    pass
                break

    def send_to_pane(self, actor_instance_id: str, text: str) -> None:
        """Send text to an actor's pane (for displaying output)."""
        for pane in self.actor_panes:
            if pane.actor_instance_id == actor_instance_id:
                try:
                    # Clear pane and send text
                    self._run("send-keys", "-t", pane.pane_id, f"echo '{text}'", "Enter")
                except RuntimeError:
                    pass
                break

    def send_to_main(self, text: str) -> None:
        """Send text to the main Conductor pane."""
        if self.main_pane_id:
            try:
                self._run("send-keys", "-t", self.main_pane_id, text, "Enter")
            except RuntimeError:
                pass

    def attach(self) -> None:
        """Attach to the tmux session (blocks until detached)."""
        if self._created:
            subprocess.run(["tmux", "attach-session", "-t", self.session_name])

    def kill(self) -> None:
        """Kill the tmux session."""
        try:
            self._run("kill-session", "-t", self.session_name)
        except RuntimeError:
            pass
        self._created = False
