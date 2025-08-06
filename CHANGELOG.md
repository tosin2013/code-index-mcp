# Changelog

All notable changes to this project will be documented in this file.

## [1.2.1] - 2024-08-06

### Fixed
- **File Watcher**: Enhanced move event handling for modern editors (VS Code, etc.)
  - Fixed issue where files created via temp-then-move pattern weren't being detected
  - Improved event processing logic to exclusively check destination path for move events
  - Eliminated ambiguous fallback behavior that could cause inconsistent results

### Improved
- **Code Quality**: Comprehensive Pylint compliance improvements
  - Fixed all f-string logging warnings using lazy % formatting
  - Added proper docstrings to fallback classes
  - Fixed multiple-statements warnings
  - Moved imports to top-level following PEP 8 conventions
  - Added appropriate pylint disables for stub methods

### Technical Details
- Unified path checking logic across all event types
- Reduced code complexity in `should_process_event()` method
- Better error handling with consistent exception management
- Enhanced debugging capabilities with improved logging

## [1.2.0] - Previous Release

### Added
- Enhanced find_files functionality with filename search
- Performance improvements to file discovery
- Auto-refresh troubleshooting documentation

## [1.1.1] - Previous Release

### Fixed
- Various bug fixes and stability improvements

## [1.1.0] - Previous Release

### Added
- Initial file watcher functionality
- Cross-platform file system monitoring

## [1.0.0] - Initial Release

### Added
- Core MCP server implementation
- Code indexing and analysis capabilities
- Multi-language support