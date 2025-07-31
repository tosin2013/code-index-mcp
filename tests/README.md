# Test Files Overview

## Core Tests Retained

### 1. `test_duplicate_names.py`
**Purpose**: Test duplicate name handling functionality
- **15 test cases** - All passing ✅
- **Coverage**:
  - Qualified names generation and parsing
  - Duplicate handling in lookup tables
  - Duplicate names in relationship tracking
  - End-to-end integration testing

### 2. `test_indexing_system.py`  
**Purpose**: Test core indexing system functionality
- **6 test cases** - All passing ✅
- **Coverage**:
  - Project scanning functionality
  - File categorization
  - Language analyzers
  - Index building and serialization

## Removed Obsolete Tests

### Root Level Legacy Tests (Deleted)
- `test_duplicate_detection.py` - API changed, functionality integrated into new tests
- `test_qualified_names.py` - Import errors, functionality covered in test_duplicate_names.py
- `test_qualified_relationship_tracking.py` - Functionality integrated
- `test_reverse_lookups.py` - Module doesn't exist

### tests/ Directory Obsolete Tests (Deleted)
- `test_auto_refresh_decorator.py` - Module doesn't exist
- `test_find_files_operation.py` - Module doesn't exist
- `test_integration_auto_refresh.py` - Depends on non-existent modules
- `test_integration_simple.py` - Depends on non-existent modules
- `test_performance_refresh.py` - Depends on non-existent modules
- `test_refresh_manager.py` - Module doesn't exist
- `test_refreshable_operation.py` - Module doesn't exist
- `test_search_code_operation.py` - Module doesn't exist

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific tests
python -m pytest tests/test_duplicate_names.py -v
python -m pytest tests/test_indexing_system.py -v
```

## Testing Principles

1. **Supported File Types Only**: Only test files in `SUPPORTED_EXTENSIONS`
2. **API Compatibility**: Tests reflect current API design
3. **Functional Completeness**: Cover core indexing and duplicate handling features
4. **Maintainability**: Keep tests concise and maintainable