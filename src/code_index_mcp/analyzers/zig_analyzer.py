"""Zig language analyzer."""

import os
from typing import Dict, Any
from .base_analyzer import LanguageAnalyzer
from .analysis_result import AnalysisResult


class ZigAnalyzer(LanguageAnalyzer):
    """Analyzer for Zig files."""

    def analyze(self, content: str, file_path: str, full_path: str = None) -> AnalysisResult:
        """Analyze Zig file content."""
        lines = content.splitlines()

        # Create result object
        _, ext = os.path.splitext(file_path)
        result = AnalysisResult(
            file_path=file_path,
            line_count=self._count_lines(content),
            size_bytes=self._get_file_size(content, full_path),
            extension=ext,
            analysis_type="zig"
        )

        # Zig-specific analysis
        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Skip empty lines and comments
            if not line_stripped or line_stripped.startswith('//'):
                continue

            # Check for imports
            if '@import(' in line_stripped:
                # Extract module name from @import("module") or @import("module.zig")
                import_match = line_stripped.split('@import(')
                if len(import_match) > 1:
                    import_name = import_match[1].split(')')[0].strip('"\'')
                    result.add_symbol("import", f"@import({import_name})", i + 1)
            
            if '@cImport(' in line_stripped:
                result.add_symbol("import", "@cImport", i + 1)

            # Check for function definitions
            if ' fn ' in line_stripped or line_stripped.startswith('fn '):
                # Handle both 'pub fn' and 'fn' declarations
                if 'fn ' in line_stripped:
                    fn_part = line_stripped.split('fn ', 1)[1]
                    func_name = fn_part.split('(')[0].strip()
                    if func_name:
                        symbol_type = "function"
                        if 'pub fn' in line_stripped:
                            symbol_type = "function_public"
                        result.add_symbol(symbol_type, func_name, i + 1)

            # Check for struct definitions
            if ' struct ' in line_stripped or ' struct{' in line_stripped:
                # Look for const Name = struct pattern
                if 'const ' in line_stripped and '=' in line_stripped:
                    const_part = line_stripped.split('const ', 1)[1]
                    struct_name = const_part.split('=')[0].strip()
                    if struct_name:
                        result.add_symbol("struct", struct_name, i + 1)

            # Check for enum definitions
            if ' enum ' in line_stripped or ' enum{' in line_stripped or ' enum(' in line_stripped:
                # Look for const Name = enum pattern
                if 'const ' in line_stripped and '=' in line_stripped:
                    const_part = line_stripped.split('const ', 1)[1]
                    enum_name = const_part.split('=')[0].strip()
                    if enum_name:
                        result.add_symbol("enum", enum_name, i + 1)

            # Check for error set definitions
            if ' error{' in line_stripped or '= error{' in line_stripped:
                # Look for const Name = error pattern
                if 'const ' in line_stripped and '=' in line_stripped:
                    const_part = line_stripped.split('const ', 1)[1]
                    error_name = const_part.split('=')[0].strip()
                    if error_name:
                        result.add_symbol("error_set", error_name, i + 1)

            # Check for test blocks
            if line_stripped.startswith('test '):
                test_name = line_stripped[5:].split('{')[0].strip().strip('"')
                if test_name:
                    result.add_symbol("test", test_name, i + 1)

            # Check for const/var declarations at module level
            if line_stripped.startswith('pub const ') or line_stripped.startswith('const '):
                # Skip struct/enum/error definitions already handled
                if not any(keyword in line_stripped for keyword in [' struct', ' enum', ' error{']):
                    const_part = line_stripped.replace('pub const ', '').replace('const ', '')
                    if ':' in const_part or '=' in const_part:
                        const_name = const_part.split(':')[0].split('=')[0].strip()
                        if const_name:
                            symbol_type = "const_public" if line_stripped.startswith('pub const') else "const"
                            result.add_symbol(symbol_type, const_name, i + 1)

            if line_stripped.startswith('pub var ') or line_stripped.startswith('var '):
                var_part = line_stripped.replace('pub var ', '').replace('var ', '')
                if ':' in var_part or '=' in var_part:
                    var_name = var_part.split(':')[0].split('=')[0].strip()
                    if var_name:
                        symbol_type = "var_public" if line_stripped.startswith('pub var') else "var"
                        result.add_symbol(symbol_type, var_name, i + 1)

        return result