"""Objective-C language analyzer."""

import os
import re
from typing import Dict, Any
from .base_analyzer import LanguageAnalyzer
from .analysis_result import AnalysisResult


class ObjectiveCAnalyzer(LanguageAnalyzer):
    """Analyzer for Objective-C files."""
    
    def __init__(self):
        """Initialize with compiled regex patterns for performance."""
        self.import_pattern = re.compile(r'^#import\s+["<]([^">]+)[">]')
        self.interface_pattern = re.compile(r'^@interface\s+(\w+)(?:\s*:\s*(\w+))?')
        self.implementation_pattern = re.compile(r'^@implementation\s+(\w+)')
        self.method_pattern = re.compile(r'^[-+]\s*\([^)]+\)\s*(\w+)')
        self.property_pattern = re.compile(r'^@property\s*\([^)]*\)\s*[\w\s*]+\s*(\w+)')

    def analyze(self, content: str, file_path: str, full_path: str = None) -> AnalysisResult:
        """Analyze Objective-C file content."""
        lines = content.splitlines()

        # Create result object
        _, ext = os.path.splitext(file_path)
        result = AnalysisResult(
            file_path=file_path,
            line_count=self._count_lines(content),
            size_bytes=self._get_file_size(content, full_path),
            extension=ext,
            analysis_type="objective-c"
        )

        # Objective-C specific analysis using pre-compiled patterns

        in_interface = False
        in_implementation = False

        for i, line in enumerate(lines):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('//'):
                continue

            # Check for imports
            import_match = self.import_pattern.match(line)
            if import_match:
                result.add_symbol("import", import_match.group(1), i + 1)

            # Check for interface definitions
            interface_match = self.interface_pattern.match(line)
            if interface_match:
                superclass = interface_match.group(2) if interface_match.group(2) else None
                result.add_symbol("interface", interface_match.group(1), i + 1,
                                {"superclass": superclass})
                in_interface = True
                in_implementation = False

            # Check for implementation definitions
            implementation_match = self.implementation_pattern.match(line)
            if implementation_match:
                result.add_symbol("implementation", implementation_match.group(1), i + 1)
                in_interface = False
                in_implementation = True

            # Check for method definitions
            method_match = self.method_pattern.match(line)
            if method_match and (in_interface or in_implementation):
                method_type = "instance" if line.startswith('-') else "class"
                result.add_symbol("function", method_match.group(1), i + 1,
                                {"type": method_type})

            # Check for property definitions
            property_match = self.property_pattern.match(line)
            if property_match and in_interface:
                result.add_symbol("property", property_match.group(1), i + 1)

            # Reset context on @end
            if line == '@end':
                in_interface = False
                in_implementation = False

        return result

