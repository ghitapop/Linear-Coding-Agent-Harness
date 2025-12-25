"""Keyboard handler for interrupt signals.

Listens for ESC key and CTRL+C to interrupt running operations.
"""

import asyncio
import sys
import threading
from typing import Callable, Optional

# Windows-specific imports
if sys.platform == "win32":
    import msvcrt
else:
    import select
    import termios
    import tty


class KeyboardHandler:
    """Handles keyboard input for interrupt signals.

    Listens for:
    - ESC key: Interrupt current operation
    - CTRL+C: Interrupt current operation (not exit)
    """

    ESC_KEY = 27  # ASCII code for ESC

    def __init__(self) -> None:
        """Initialize keyboard handler."""
        self._interrupt_requested = asyncio.Event()
        self._quit_requested = asyncio.Event()
        self._listener_thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False  # When paused, don't consume keyboard input
        self._callback: Optional[Callable[[], None]] = None

    @property
    def interrupt_requested(self) -> bool:
        """Check if interrupt was requested."""
        return self._interrupt_requested.is_set()

    @property
    def quit_requested(self) -> bool:
        """Check if quit was requested."""
        return self._quit_requested.is_set()

    def clear_interrupt(self) -> None:
        """Clear the interrupt flag."""
        self._interrupt_requested.clear()

    def request_interrupt(self) -> None:
        """Request an interrupt (can be called externally)."""
        self._interrupt_requested.set()
        if self._callback:
            self._callback()

    def request_quit(self) -> None:
        """Request app quit."""
        self._quit_requested.set()
        self._interrupt_requested.set()

    def set_interrupt_callback(self, callback: Callable[[], None]) -> None:
        """Set callback to be called when interrupt is requested."""
        self._callback = callback

    def pause(self) -> None:
        """Pause keyboard listening to allow normal input() to work."""
        self._paused = True

    def resume(self) -> None:
        """Resume keyboard listening after user input is complete."""
        self._paused = False

    def start(self) -> None:
        """Start listening for keyboard input."""
        if self._running:
            return

        self._running = True
        self._listener_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="keyboard-listener"
        )
        self._listener_thread.start()

    def stop(self) -> None:
        """Stop listening for keyboard input."""
        self._running = False
        if self._listener_thread:
            self._listener_thread.join(timeout=0.5)
            self._listener_thread = None

    def _listen_loop(self) -> None:
        """Main keyboard listening loop."""
        if sys.platform == "win32":
            self._listen_windows()
        else:
            self._listen_unix()

    def _listen_windows(self) -> None:
        """Listen for keyboard input on Windows."""
        while self._running:
            try:
                # When paused, don't consume keyboard input (let input() work)
                if self._paused:
                    threading.Event().wait(0.1)
                    continue

                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b'\x1b':  # ESC
                        print("\n[ESC pressed - interrupting current operation...]")
                        self._interrupt_requested.set()
                        if self._callback:
                            self._callback()
                    elif key == b'\x03':  # CTRL+C
                        print("\n[CTRL+C pressed - interrupting current operation...]")
                        self._interrupt_requested.set()
                        if self._callback:
                            self._callback()
                else:
                    # Small sleep to avoid busy waiting
                    threading.Event().wait(0.1)
            except Exception:
                # Ignore errors in keyboard handling
                threading.Event().wait(0.1)

    def _listen_unix(self) -> None:
        """Listen for keyboard input on Unix."""
        old_settings = None
        try:
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())

            while self._running:
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    char = sys.stdin.read(1)
                    if ord(char) == self.ESC_KEY:
                        print("\n[ESC pressed - interrupting current operation...]")
                        self._interrupt_requested.set()
                        if self._callback:
                            self._callback()
        except Exception:
            pass
        finally:
            if old_settings:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


# Global instance
_keyboard_handler: Optional[KeyboardHandler] = None


def get_keyboard_handler() -> KeyboardHandler:
    """Get the global keyboard handler instance."""
    global _keyboard_handler
    if _keyboard_handler is None:
        _keyboard_handler = KeyboardHandler()
    return _keyboard_handler


def is_interrupt_requested() -> bool:
    """Check if an interrupt was requested."""
    handler = get_keyboard_handler()
    return handler.interrupt_requested


def clear_interrupt() -> None:
    """Clear the interrupt flag."""
    handler = get_keyboard_handler()
    handler.clear_interrupt()


def request_interrupt() -> None:
    """Request an interrupt."""
    handler = get_keyboard_handler()
    handler.request_interrupt()


def pause_keyboard() -> None:
    """Pause keyboard listening to allow normal input() to work."""
    handler = get_keyboard_handler()
    handler.pause()


def resume_keyboard() -> None:
    """Resume keyboard listening after user input is complete."""
    handler = get_keyboard_handler()
    handler.resume()
