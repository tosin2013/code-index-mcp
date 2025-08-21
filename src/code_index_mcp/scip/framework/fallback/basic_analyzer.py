"""Fallback basic analyzer implementation."""

from typing import Iterator, Optional, Set, List, Dict, Any
from ..types import SCIPContext
from ..base.language_analyzer import BaseLanguageAnalyzer
from pathlib import Path


class FallbackBasicAnalyzer(BaseLanguageAnalyzer):
    """Fallback analyzer for basic file analysis without parsing."""
    
    def __init__(self):
        """Initialize the fallback basic analyzer."""
        self._processed_files: Set[str] = set()
    
    def parse(self, content: str, filename: str = "<unknown>"):
        """Parse content (no-op for fallback, returns file info)."""
        return {
            'filename': filename,
            'content_length': len(content),
            'line_count': content.count('\n') + 1,
            'type': 'fallback_file'
        }
    
    def walk(self, tree) -> Iterator:
        """Walk tree nodes (returns single file node for fallback)."""
        yield tree  # Return the entire file as a single "node"
    
    def is_symbol_definition(self, node) -> bool:
        """Check if node represents a symbol definition (file-level only)."""
        return isinstance(node, dict) and node.get('type') == 'fallback_file'
    
    def is_symbol_reference(self, node) -> bool:
        """Check if node represents a symbol reference (none for fallback)."""
        return False  # Fallback doesn't analyze references
    
    def get_symbol_name(self, node) -> Optional[str]:
        """Extract symbol name from node (filename for fallback)."""
        if isinstance(node, dict) and 'filename' in node:
            return Path(node['filename']).stem
        return None
    
    def get_node_position(self, node) -> tuple:
        """Get position information from node."""
        if isinstance(node, dict):
            line_count = node.get('line_count', 1)
            return (0, 0, line_count - 1, 0)  # Start to end of file
        return (0, 0, 0, 0)
    
    def extract_file_info(self, content: str, filename: str) -> Dict[str, Any]:
        """Extract basic file information."""
        path = Path(filename)
        
        return {
            'filename': filename,
            'basename': path.name,
            'stem': path.stem,
            'suffix': path.suffix,
            'content_length': len(content),
            'line_count': content.count('\n') + 1,
            'language': self.detect_language_from_extension(path.suffix),
            'is_binary': self._is_likely_binary(content),
            'encoding': 'utf-8'  # Assume UTF-8 for text files
        }
    
    def detect_language_from_extension(self, extension: str) -> str:
        """Detect specific language from file extension."""
        extension_mapping = {
            # Programming languages
            '.c': 'c',
            '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.c++': 'cpp',
            '.h': 'c', '.hpp': 'cpp', '.hh': 'cpp', '.hxx': 'cpp',
            '.js': 'javascript', '.mjs': 'javascript', '.jsx': 'javascript',
            '.ts': 'typescript', '.tsx': 'typescript',
            '.py': 'python', '.pyi': 'python', '.pyx': 'python',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.rb': 'ruby',
            '.cs': 'csharp',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin', '.kts': 'kotlin',
            '.scala': 'scala',
            '.r': 'r',
            '.lua': 'lua',
            '.perl': 'perl', '.pl': 'perl',
            '.zig': 'zig',
            '.dart': 'dart',
            '.m': 'objective-c', '.mm': 'objective-c',

            # Web and markup
            '.html': 'html', '.htm': 'html',
            '.css': 'css',
            '.scss': 'scss', '.sass': 'sass',
            '.less': 'less',
            '.vue': 'vue',
            '.svelte': 'svelte',
            '.astro': 'astro',

            # Data and config
            '.json': 'json',
            '.xml': 'xml',
            '.yaml': 'yaml', '.yml': 'yaml',
            '.toml': 'toml',
            '.ini': 'ini',
            '.cfg': 'ini',
            '.conf': 'ini',

            # Documentation
            '.md': 'markdown', '.markdown': 'markdown',
            '.mdx': 'mdx',
            '.tex': 'latex',
            '.rst': 'rst',

            # Database and query
            '.sql': 'sql',
            '.cql': 'cql',
            '.cypher': 'cypher',
            '.sparql': 'sparql',
            '.graphql': 'graphql', '.gql': 'graphql',

            # Shell and scripts
            '.sh': 'shell', '.bash': 'bash',
            '.zsh': 'zsh', '.fish': 'fish',
            '.ps1': 'powershell',
            '.bat': 'batch', '.cmd': 'batch',

            # Template languages
            '.handlebars': 'handlebars', '.hbs': 'handlebars',
            '.ejs': 'ejs',
            '.pug': 'pug',
            '.mustache': 'mustache',

            # Other
            '.dockerfile': 'dockerfile',
            '.gitignore': 'gitignore',
            '.env': 'dotenv',
        }

        return extension_mapping.get(extension.lower(), 'text')
    
    def get_file_statistics(self, content: str) -> Dict[str, int]:
        """Get basic file statistics."""
        return {
            'total_characters': len(content),
            'total_lines': content.count('\n') + 1,
            'non_empty_lines': len([line for line in content.split('\n') if line.strip()]),
            'blank_lines': content.count('\n') + 1 - len([line for line in content.split('\n') if line.strip()]),
            'estimated_words': len(content.split()) if content.strip() else 0
        }
    
    def _is_likely_binary(self, content: str, sample_size: int = 1024) -> bool:
        """Check if content is likely binary based on null bytes."""
        sample = content[:sample_size]
        return '\x00' in sample or any(ord(c) > 127 for c in sample[:100])