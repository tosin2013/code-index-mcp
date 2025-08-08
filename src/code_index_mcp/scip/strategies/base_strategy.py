"""Base strategy interface for SCIP indexing."""
# pylint: disable=no-member  # Protobuf classes are dynamically generated

from abc import ABC, abstractmethod
from typing import List
from ..proto import scip_pb2


class SCIPIndexerStrategy(ABC):
    """Base class for all SCIP indexing strategies."""

    def __init__(self, priority: int = 50):
        """
        Initialize the strategy with a priority level.

        Args:
            priority: Strategy priority (higher = more preferred)
                     100 = Official tools (highest)
                     75 = Custom analyzers as backup
                     50 = Custom analyzers (primary)
                     25 = Language-specialized defaults
                     10 = Generic defaults
                     1 = Fallback (lowest)
        """
        self.priority = priority

    @abstractmethod
    def can_handle(self, extension: str, file_path: str) -> bool:
        """
        Check if this strategy can handle the given file type.

        Args:
            extension: File extension (e.g., '.py')
            file_path: Full path to the file

        Returns:
            True if this strategy can handle the file
        """

    @abstractmethod
    def generate_scip_documents(self, files: List[str], project_path: str) -> List[scip_pb2.Document]:
        """
        Generate SCIP documents for the given files.

        Args:
            files: List of file paths to index
            project_path: Root path of the project

        Returns:
            List of SCIP Document objects

        Raises:
            StrategyError: If the strategy cannot process the files
        """

    def get_priority(self) -> int:
        """Return the strategy priority."""
        return self.priority

    def get_strategy_name(self) -> str:
        """Return a human-readable name for this strategy."""
        return self.__class__.__name__

    def is_available(self) -> bool:
        """
        Check if this strategy is available and ready to use.

        Returns:
            True if the strategy can be used
        """
        return True


class StrategyError(Exception):
    """Base exception for strategy-related errors."""


class ToolUnavailableError(StrategyError):
    """Raised when a required tool is not available."""


class ConversionError(StrategyError):
    """Raised when conversion to SCIP format fails."""
