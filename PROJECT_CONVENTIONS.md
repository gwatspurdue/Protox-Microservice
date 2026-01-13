# Project Conventions and Structure

This document outlines the code conventions and architectural patterns used in this project. Follow these guidelines to maintain consistency across all components.

## Project Architecture

### Directory Structure
```
project-root/
├── main.py                 # FastAPI application and route handlers
├── module_handler.py       # Business logic and core functionality
├── requirements.txt        # Python dependencies
├── README.md              # Project documentation
└── env.yml                # Environment configuration
```

### Separation of Concerns
- **main.py**: API routes, request/response models, and HTTP layer
- **_handler.py**: Core business logic, data processing, and external service interactions

## Code Style Conventions

### Module Organization

#### Imports
```python
# Order imports as:
# 1. Standard library
# 2. Third-party packages
# 3. Local application imports
import io
from pathlib import Path
from typing import List, Dict, Any, Optional

import torch
import pandas as pd
from chemprop import data, featurizers, models
from lightning import pytorch as pl

from admetica_handler import AdmeticaHandler
```

### Type Hints
- **Always use type hints** for function parameters and return types
- Use `Optional[Type]` for optional values instead of `Union[Type, None]`
- Import types from `typing` module for complex types

```python
def get_model_path(self, property_name: str) -> Optional[Path]:
    """Retrieve the path for a given property model."""
    model_path = self.MODEL_PATHS.get(property_name.lower())
    if model_path and model_path.exists():
        return model_path
    return None
```

### Docstrings
- Use Google-style docstrings for all public methods
- Include Args, Returns, and optional Raises sections
- Add module-level docstring describing the file's purpose

```python
def process_smiles(self, smiles: str, property_name: str = 'solubility') -> Dict[str, Any]:
    """
    Process a single SMILES string for a given property.

    Args:
        smiles: A SMILES string to process
        property_name: The molecular property to predict

    Returns:
        Dictionary containing processed information
    """
```

### Class Structure
- Use `__init__` for initialization
- Private/internal methods should be named with underscore prefix
- Group related methods together
- Include class-level constants/configuration before methods

```python
class AdmeticaHandler:
    """Handle interactions with ChemProp models for SMILES processing."""

    # Class-level configuration
    BASE_DIRS = {...}
    MODEL_PATHS = {...}

    def __init__(self):
        """Initialize the handler."""
        self.model_cache = {}

    def public_method(self):
        """Public method description."""
        pass

    def _private_method(self):
        """Private method description."""
        pass
```

## FastAPI Conventions

### Request/Response Models
- Use Pydantic `BaseModel` for all request/response schemas
- Include default values where appropriate
- Add docstrings explaining the purpose

```python
class SMILESRequest(BaseModel):
    """Request model for single SMILES string."""
    smiles: str
    property: str = "solubility"  # Default property


class SMILESResponse(BaseModel):
    """Response model for SMILES processing."""
    smiles: str
    property: str
    status: str
    prediction: float = None
    error: str = None
```

### Route Definition
- Use descriptive endpoint names
- Include request/response model types in decorator
- Add comprehensive docstrings to route handlers
- Validate input at the beginning of the function
- Return consistent response structures

```python
@app.post("/endpoint-name/", response_model=ResponseModel)
async def handler_name(request: RequestModel) -> ResponseModel:
    """
    Brief description of what the endpoint does.

    Args:
        request: RequestModel description

    Returns:
        ResponseModel with results
    """
    # Input validation
    if not request.field or request.field.strip() == "":
        raise HTTPException(status_code=400, detail="Error message")

    # Process request
    result = handler.process(request.field)
    
    # Check for errors
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result
```

### Error Handling
- Use `HTTPException` with appropriate status codes
- Provide clear, actionable error messages
- Handle errors consistently across all routes

```python
# Validation errors: 400
raise HTTPException(status_code=400, detail="Invalid input")

# Not found: 404
raise HTTPException(status_code=404, detail="Resource not found")

# Server errors: 500
raise HTTPException(status_code=500, detail="Internal server error")
```

## Handler Class Conventions

### Initialization
- Initialize any caches or state in `__init__`
- Load static configuration (paths, constants) as class variables

```python
class SpecializedHandler:
    """Handle specific domain logic."""
    
    # Static configuration
    CONFIG = {...}
    PATHS = {...}
    
    def __init__(self):
        """Initialize the handler."""
        self.cache = {}
```

### Error Handling Pattern
- Always return structured results with status indication
- Include both success and error response formats
- Use try-except for external service calls

```python
def process_item(self, item: str) -> Dict[str, Any]:
    """Process a single item."""
    try:
        # Main logic
        result = self._process(item)
        return {
            "item": item,
            "status": "success",
            "data": result
        }
    except Exception as e:
        return {
            "item": item,
            "status": "error",
            "error": str(e)
        }
```

### Batch Processing
- Always provide both single and batch processing methods
- Use list comprehension or map for batch operations
- Maintain consistent return types

```python
def process_item(self, item: str) -> Dict[str, Any]:
    """Process single item."""
    # Implementation
    pass

def process_items(self, items: List[str]) -> List[Dict[str, Any]]:
    """Process list of items."""
    return [self.process_item(item) for item in items]
```

### Public Interface Methods
- Provide a method to list available options/properties
- Include validation methods for inputs
- Return clear status information

```python
def get_available_properties(self) -> List[str]:
    """Return list of available properties for prediction."""
    return list(self.MODEL_PATHS.keys())

def validate_property(self, property_name: str) -> bool:
    """Check if property is supported."""
    return property_name.lower() in self.MODEL_PATHS
```

## Naming Conventions

### Files
- Use lowercase with underscores: `my_module.py`
- Suffix handler/service files with `_handler.py` or `_service.py`
- Match class name to file content

### Variables and Functions
- Use snake_case for variables and functions
- Use UPPER_CASE for constants
- Use descriptive, clear names

```python
# Good
processed_data = handler.process_item(input_smiles)
available_models = handler.get_available_properties()

# Avoid
pd = handler.process(smi)  # Unclear abbreviations
results = handler.p(x)     # Non-descriptive names
```

### Classes
- Use PascalCase for class names
- Be descriptive: `AdmeticaHandler` not `Handler`

## Configuration Management

### Environment Variables
- Store in `env.yml` or `.env` files
- Never commit sensitive data
- Document all required environment variables

### Class-Level Configuration
- Use dictionaries for mappings
- Use Path objects for file paths
- Keep configuration near the top of the class

```python
BASE_DIRS = {
    'absorption': Path('..', 'absorption'),
    'distribution': Path('..', 'distribution'),
}

MODEL_PATHS = {
    'caco2': BASE_DIRS['absorption'] / 'caco2' / 'caco2.ckpt',
    'solubility': BASE_DIRS['absorption'] / 'solubility' / 'solubility.ckpt',
}
```

## Testing Conventions

### Test File Organization
```
tests/
├── test_main.py           # API route tests
├── test_module_handler.py # Handler logic tests
└── conftest.py           # Shared fixtures
```

### Test Naming
- Test files: `test_<module>.py`
- Test functions: `test_<what_is_being_tested>`
- Test classes: `Test<ClassName>`

```python
def test_process_single_smiles_success():
    """Test successful SMILES processing."""
    pass

def test_process_single_smiles_invalid_input():
    """Test error handling for invalid input."""
    pass
```

## Documentation Standards

### Code Comments
- Use comments to explain *why*, not *what*
- Keep comments up-to-date with code changes
- Use clear, concise language

```python
# Why: We cache models to avoid reloading on each request
self.model_cache = {}

# What (avoid): Load the model
model = self.load_model(path)
```

### README Contents
- Project description
- Installation instructions
- API documentation with examples
- Configuration requirements
- Contributing guidelines

## Python Version and Dependencies

- Target Python 3.8+
- List all dependencies in `requirements.txt` or `env.yml`
- Pin major version numbers for stability
- Include development dependencies separately

## Async/Await Conventions

- Use `async def` for FastAPI route handlers
- Mark I/O-bound operations as `async`
- Use `await` for async function calls
- Avoid blocking operations in async contexts

```python
@app.post("/endpoint/")
async def handler(request: RequestModel):
    """Async handler for HTTP request."""
    contents = await file.read()  # I/O operation
    return await handler.process_async(contents)
```

## Summary Checklist

When creating new files in this project:
- ✅ Add module-level docstring
- ✅ Use type hints for all functions
- ✅ Write Google-style docstrings
- ✅ Organize imports properly
- ✅ Use meaningful variable names
- ✅ Handle errors with HTTPException or structured returns
- ✅ Separate API logic from business logic
- ✅ Include both single and batch processing methods
- ✅ Add configuration at class level
- ✅ Test and validate user input