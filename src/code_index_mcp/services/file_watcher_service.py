"""
File Watcher Service for automatic index rebuilds.

This module provides file system monitoring capabilities that automatically
trigger index rebuilds when relevant files are modified, created, or deleted.
It uses the watchdog library for cross-platform file system event monitoring.
"""

import logging
from threading import Timer
from typing import Optional, Callable
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    # Fallback classes for when watchdog is not available
    class Observer:
        def __init__(self): pass
        def schedule(self, *args, **kwargs): pass
        def start(self): pass
        def stop(self): pass
        def join(self, *args, **kwargs): pass
        def is_alive(self): return False

    class FileSystemEventHandler:
        def __init__(self): pass

    class FileSystemEvent:
        def __init__(self):
            self.is_directory = False
            self.src_path = ""
            self.event_type = ""

    WATCHDOG_AVAILABLE = False

from .base_service import BaseService
from ..constants import SUPPORTED_EXTENSIONS


class FileWatcherService(BaseService):
    """
    Service for monitoring file system changes and triggering index rebuilds.

    This service uses the watchdog library to monitor file system events and
    automatically triggers background index rebuilds when relevant files change.
    It includes intelligent debouncing to batch rapid changes and filtering
    to only monitor relevant file types.
    """
    MAX_RESTART_ATTEMPTS = 3

    def __init__(self, ctx):
        """
        Initialize the file watcher service.

        Args:
            ctx: The MCP Context object
        """
        super().__init__(ctx)
        self.logger = logging.getLogger(__name__)
        self.observer: Optional[Observer] = None
        self.event_handler: Optional[DebounceEventHandler] = None
        self.is_monitoring = False
        self.restart_attempts = 0
        self.rebuild_callback: Optional[Callable] = None

        # Check if watchdog is available
        if not WATCHDOG_AVAILABLE:
            self.logger.warning("Watchdog library not available - file watcher disabled")

    def start_monitoring(self, rebuild_callback: Callable) -> bool:
        """
        Start file system monitoring.

        Args:
            rebuild_callback: Function to call when rebuild is needed

        Returns:
            True if monitoring started successfully, False otherwise
        """
        if not WATCHDOG_AVAILABLE:
            self.logger.warning("Cannot start file watcher - watchdog library not available")
            return False

        if self.is_monitoring:
            self.logger.debug("File watcher already monitoring")
            return True

        # Validate project setup
        error = self._validate_project_setup()
        if error:
            self.logger.error("Cannot start file watcher: %s", error)
            return False

        self.rebuild_callback = rebuild_callback

        # Get debounce seconds from config
        config = self.settings.get_file_watcher_config()
        debounce_seconds = config.get('debounce_seconds', 6.0)

        try:
            self.observer = Observer()
            self.event_handler = DebounceEventHandler(
                debounce_seconds=debounce_seconds,
                rebuild_callback=self.rebuild_callback,
                base_path=Path(self.base_path),
                logger=self.logger
            )

            # Log detailed Observer setup
            watch_path = str(self.base_path)
            self.logger.debug(f"Scheduling Observer for path: {watch_path}")
            
            self.observer.schedule(
                self.event_handler,
                watch_path,
                recursive=True
            )

            # Log Observer start
            self.logger.debug("Starting Observer...")
            self.observer.start()
            self.is_monitoring = True
            self.restart_attempts = 0
            
            # Log Observer thread info
            if hasattr(self.observer, '_thread'):
                thread_info = f"Observer thread: {self.observer._thread}"
                self.logger.debug(thread_info)

            # Verify observer is actually running
            if self.observer.is_alive():
                self.logger.info(
                    "File watcher started successfully",
                    extra={
                        "debounce_seconds": debounce_seconds,
                        "monitored_path": str(self.base_path),
                        "supported_extensions": len(SUPPORTED_EXTENSIONS)
                    }
                )
                
                # Add diagnostic test - create a test event to verify Observer works
                import os
                self.logger.debug(f"Observer thread is alive: {self.observer.is_alive()}")
                self.logger.debug(f"Monitored path exists: {os.path.exists(str(self.base_path))}")
                self.logger.debug(f"Event handler is set: {self.event_handler is not None}")
                
                # Log current directory for comparison
                current_dir = os.getcwd()
                self.logger.debug(f"Current working directory: {current_dir}")
                self.logger.debug(f"Are paths same: {os.path.normpath(current_dir) == os.path.normpath(str(self.base_path))}")
                
                return True
            else:
                self.logger.error("File watcher failed to start - Observer not alive")
                return False

        except Exception as e:
            self.logger.warning("Failed to start file watcher: %s", e)
            self.logger.info("Falling back to reactive index refresh")
            return False

    def stop_monitoring(self) -> None:
        """
        Stop file system monitoring and cleanup all resources.
        
        This method ensures complete cleanup of:
        - Observer thread
        - Event handler
        - Debounce timers
        - Monitoring state
        """
        if not self.observer and not self.is_monitoring:
            # Already stopped or never started
            return
            
        self.logger.info("Stopping file watcher monitoring...")
        
        try:
            # Step 1: Stop the observer first
            if self.observer:
                self.logger.debug("Stopping observer...")
                self.observer.stop()
                
                # Step 2: Cancel any active debounce timer
                if self.event_handler and self.event_handler.debounce_timer:
                    self.logger.debug("Cancelling debounce timer...")
                    self.event_handler.debounce_timer.cancel()
                
                # Step 3: Wait for observer thread to finish (with timeout)
                self.logger.debug("Waiting for observer thread to finish...")
                self.observer.join(timeout=5.0)
                
                # Step 4: Check if thread actually finished
                if self.observer.is_alive():
                    self.logger.warning("Observer thread did not stop within timeout")
                else:
                    self.logger.debug("Observer thread stopped successfully")
            
            # Step 5: Clear all references
            self.observer = None
            self.event_handler = None
            self.rebuild_callback = None
            self.is_monitoring = False
            
            self.logger.info("File watcher stopped and cleaned up successfully")
            print("STOPPED: File watcher stopped")
            
        except Exception as e:
            self.logger.error("Error stopping file watcher: %s", e)
            print(f"WARNING: Error stopping file watcher: {e}")
            
            # Force cleanup even if there were errors
            self.observer = None
            self.event_handler = None
            self.rebuild_callback = None
            self.is_monitoring = False

    def is_active(self) -> bool:
        """
        Check if file watcher is actively monitoring.

        Returns:
            True if actively monitoring, False otherwise
        """
        return (self.is_monitoring and
                self.observer and
                self.observer.is_alive())

    def restart_observer(self) -> bool:
        """
        Attempt to restart the file system observer.

        Returns:
            True if restart successful, False otherwise
        """
        if self.restart_attempts >= self.MAX_RESTART_ATTEMPTS:
            self.logger.error("Max restart attempts reached, file watcher disabled")
            return False

        self.logger.info("Attempting to restart file watcher (attempt %d)",
                         self.restart_attempts + 1)
        self.restart_attempts += 1

        # Stop current observer if running
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join(timeout=2.0)
            except Exception as e:
                self.logger.warning("Error stopping observer during restart: %s", e)

        # Start new observer
        try:
            self.observer = Observer()
            self.observer.schedule(
                self.event_handler,
                str(self.base_path),
                recursive=True
            )
            self.observer.start()
            self.is_monitoring = True

            self.logger.info("File watcher restarted successfully")
            return True

        except Exception as e:
            self.logger.error("Failed to restart file watcher: %s", e)
            return False

    def get_status(self) -> dict:
        """
        Get current file watcher status information.

        Returns:
            Dictionary containing status information
        """
        # Get current debounce seconds from config
        config = self.settings.get_file_watcher_config()
        debounce_seconds = config.get('debounce_seconds', 6.0)

        return {
            "available": WATCHDOG_AVAILABLE,
            "active": self.is_active(),
            "monitoring": self.is_monitoring,
            "restart_attempts": self.restart_attempts,
            "debounce_seconds": debounce_seconds,
            "base_path": self.base_path if self.base_path else None,
            "observer_alive": self.observer.is_alive() if self.observer else False
        }


class DebounceEventHandler(FileSystemEventHandler):
    """
    File system event handler with debouncing capability.

    This handler filters file system events to only relevant files and
    implements a debounce mechanism to batch rapid changes into single
    rebuild operations.
    """

    def __init__(self, debounce_seconds: float, rebuild_callback: Callable,
                 base_path: Path, logger: logging.Logger):
        """
        Initialize the debounce event handler.

        Args:
            debounce_seconds: Number of seconds to wait before triggering rebuild
            rebuild_callback: Function to call when rebuild is needed
            base_path: Base project path for filtering
            logger: Logger instance for debug messages
        """
        super().__init__()
        self.debounce_seconds = debounce_seconds
        self.rebuild_callback = rebuild_callback
        self.base_path = base_path
        self.debounce_timer: Optional[Timer] = None
        self.logger = logger

        # Exclusion patterns for directories and files to ignore
        self.exclude_patterns = {
            '.git', '.svn', '.hg',
            'node_modules', '__pycache__', '.venv', 'venv',
            '.DS_Store', 'Thumbs.db',
            'dist', 'build', 'target', '.idea', '.vscode',
            '.pytest_cache', '.coverage', '.tox',
            'bin', 'obj'  # Additional build directories
        }

        # Convert supported extensions to set for faster lookup
        self.supported_extensions = set(SUPPORTED_EXTENSIONS)

    def on_any_event(self, event: FileSystemEvent) -> None:
        """
        Handle any file system event.

        Args:
            event: The file system event
        """
        # Always log events for debugging
        event_info = f"Raw event: {event.event_type} - {event.src_path} (is_directory: {event.is_directory})"
        self.logger.debug(event_info)
        
        # Test event processing
        should_process = self.should_process_event(event)
        process_info = f"Should process: {should_process}"
        self.logger.debug(process_info)
        
        if should_process:
            process_msg = f"Processing file system event: {event.event_type} - {event.src_path}"
            self.logger.debug(process_msg)
            self.reset_debounce_timer()
        else:
            filter_msg = f"Event filtered out: {event.event_type} - {event.src_path}"
            self.logger.debug(filter_msg)

    def should_process_event(self, event: FileSystemEvent) -> bool:
        """
        Determine if event should trigger index rebuild.

        Args:
            event: The file system event to evaluate

        Returns:
            True if event should trigger rebuild, False otherwise
        """
        # Skip directory events
        if event.is_directory:
            self.logger.debug(f"Skipping directory event: {event.src_path}")
            return False

        try:
            path = Path(event.src_path)
        except Exception as e:
            # Handle any path conversion issues
            self.logger.debug(f"Path conversion failed for {event.src_path}: {e}")
            return False

        # Log detailed filtering steps
        self.logger.debug(f"Checking path: {path}")
        
        # Skip excluded paths
        is_excluded = self.is_excluded_path(path)
        self.logger.debug(f"Is excluded path: {is_excluded}")
        if is_excluded:
            return False

        # Only process supported file types
        is_supported = self.is_supported_file_type(path)
        self.logger.debug(f"Is supported file type: {is_supported} (extension: {path.suffix})")
        if not is_supported:
            return False

        # Skip temporary files
        is_temp = self.is_temporary_file(path)
        self.logger.debug(f"Is temporary file: {is_temp}")
        if is_temp:
            return False

        self.logger.debug(f"Event will be processed: {event.src_path}")
        return True

    def is_excluded_path(self, path: Path) -> bool:
        """
        Check if path should be excluded from monitoring.

        Args:
            path: The file path to check

        Returns:
            True if path should be excluded, False otherwise
        """
        try:
            relative_path = path.relative_to(self.base_path)
            parts = relative_path.parts

            # Check if any part of the path matches exclusion patterns
            return any(part in self.exclude_patterns for part in parts)
        except ValueError:
            # Path is not relative to base_path - exclude it
            return True
        except Exception:
            # Handle any other path processing issues
            return True

    def is_supported_file_type(self, path: Path) -> bool:
        """
        Check if file type is supported for indexing.

        Args:
            path: The file path to check

        Returns:
            True if file type is supported, False otherwise
        """
        return path.suffix.lower() in self.supported_extensions

    def is_temporary_file(self, path: Path) -> bool:
        """
        Check if file is a temporary file.

        Args:
            path: The file path to check

        Returns:
            True if file appears to be temporary, False otherwise
        """
        name = path.name.lower()

        # Common temporary file patterns
        temp_patterns = ['.tmp', '.swp', '.swo', '~', '.bak', '.orig']

        # Check for temporary file extensions
        if any(name.endswith(pattern) for pattern in temp_patterns):
            return True

        # Check for vim/editor temporary files
        if name.startswith('.') and (name.endswith('.swp') or name.endswith('.swo')):
            return True

        # Check for backup files (e.g., file.py~, file.py.bak)
        if '~' in name or '.bak' in name:
            return True

        return False

    def reset_debounce_timer(self) -> None:
        """Reset the debounce timer, canceling any existing timer."""
        if self.debounce_timer:
            self.debounce_timer.cancel()
            self.logger.debug("Previous debounce timer cancelled")

        timer_msg = f"Starting debounce timer for {self.debounce_seconds} seconds"
        self.logger.debug(timer_msg)
        
        self.debounce_timer = Timer(
            self.debounce_seconds,
            self.trigger_rebuild
        )
        self.debounce_timer.start()
        
        self.logger.debug("Debounce timer started successfully")

    def trigger_rebuild(self) -> None:
        """Trigger index rebuild after debounce period."""
        trigger_msg = "File changes detected, triggering background rebuild"
        self.logger.info(trigger_msg)

        if self.rebuild_callback:
            try:
                callback_msg = "Calling rebuild callback..."
                self.logger.debug(callback_msg)
                
                result = self.rebuild_callback()
                
                result_msg = f"Rebuild callback completed with result: {result}"
                self.logger.debug(result_msg)
            except Exception as e:
                error_msg = f"Rebuild callback failed: {e}"
                self.logger.error(error_msg)
                import traceback
                traceback_msg = traceback.format_exc()
                self.logger.error("Traceback: %s", traceback_msg)
        else:
            no_callback_msg = "No rebuild callback configured"
            self.logger.warning(no_callback_msg)
