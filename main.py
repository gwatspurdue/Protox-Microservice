"""FastAPI application for Protox microservice.

This module defines the HTTP API routes and request/response models
for the Protox prediction service.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from protox_handler import ProtoxHandler

# Initialize FastAPI application
app = FastAPI(
    title="Protox Microservice",
    description="Microservice for molecular property predictions via Protox",
    version="1.0.0",
)

# Initialize handler
handler = ProtoxHandler()


# Request/Response Models
class PredictionRequest(BaseModel):
    """Request model for single SMILES prediction."""

    smiles: str = Field(..., description="SMILES string to process")
    property: str = Field(
        default="toxicity",
        description="Molecular property to predict",
    )
    models: Optional[List[str]] = Field(
        default=None,
        description="Specific toxicity models to request (None = all available)",
    )
    max_polls: Optional[int] = Field(
        default=None,
        description="Maximum number of polls before timing out (None = unlimited)",
    )


class SubmitPredictionResponse(BaseModel):
    """Response model for prediction submission."""

    status: str = Field(description="Status (submitted/error)")
    task_id: Optional[str] = Field(default=None, description="Task ID for tracking")
    smiles: Optional[str] = Field(default=None, description="Submitted SMILES")
    property: Optional[str] = Field(default=None, description="Property to predict")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class PredictionResponse(BaseModel):
    """Response model for single prediction result."""

    smiles: str = Field(description="Input SMILES string")
    property: str = Field(description="Predicted property")
    status: str = Field(description="Status of prediction (success/error/timeout)")
    task_id: Optional[str] = Field(default=None, description="Task ID")
    prediction: Optional[float] = Field(
        default=None, description="Predicted property value"
    )
    error: Optional[str] = Field(default=None, description="Error message if failed")


class BatchPredictionRequest(BaseModel):
    """Request model for batch SMILES predictions."""

    smiles_list: List[str] = Field(
        ..., description="List of SMILES strings to process"
    )
    property: str = Field(
        default="toxicity",
        description="Molecular property to predict",
    )
    models: Optional[List[str]] = Field(
        default=None,
        description="Specific toxicity models to request (None = all available)",
    )
    max_polls: Optional[int] = Field(
        default=None,
        description="Maximum number of polls before timing out (None = unlimited)",
    )


class BatchPredictionResponse(BaseModel):
    """Response model for batch prediction results."""

    count: int = Field(description="Number of predictions")
    property: str = Field(description="Predicted property")
    results: List[PredictionResponse] = Field(
        description="List of individual prediction results"
    )
    status: str = Field(description="Overall batch status")


class TaskStatusResponse(BaseModel):
    """Response model for task status."""

    task_id: str = Field(description="Task ID")
    status: str = Field(description="Task status (pending/completed/error)")
    error: Optional[str] = Field(default=None, description="Error message if any")


# Routes
@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, str]:
    """Health check endpoint to verify service is running.

    Returns:
        Dictionary with service status
    """
    return {"status": "healthy", "service": "protox-microservice"}


@app.get("/properties", tags=["Properties"])
async def get_available_properties() -> Dict[str, Any]:
    """Get list of available molecular properties.

    Returns:
        Dictionary with available property names
    """
    properties = handler.get_available_properties()
    return {"properties": properties, "count": len(properties)}


@app.get("/models", tags=["Properties"])
async def get_available_models() -> Dict[str, Any]:
    """Get list of available toxicity models.

    Returns:
        Dictionary mapping model names to descriptions
    """
    models = handler.get_available_models()
    return {"models": models, "count": len(models)}


@app.post("/submit", response_model=SubmitPredictionResponse, tags=["Predictions"])
async def submit_prediction(request: PredictionRequest) -> SubmitPredictionResponse:
    """Submit a prediction task to Protox API.

    This endpoint submits a SMILES string for prediction and returns a task ID
    that can be used to poll for results. Use /status/{task_id} to check progress.

    Args:
        request: PredictionRequest containing SMILES and property

    Returns:
        SubmitPredictionResponse with task_id or error

    Raises:
        HTTPException: If input validation fails
    """
    # Input validation
    if not request.smiles or request.smiles.strip() == "":
        raise HTTPException(
            status_code=400,
            detail="SMILES string cannot be empty",
        )

    if not handler.validate_property(request.property):
        raise HTTPException(
            status_code=400,
            detail=f"Property '{request.property}' not supported. "
            f"Available properties: {', '.join(handler.get_available_properties())}",
        )

    # Submit prediction
    result = handler.submit_prediction(request.smiles, request.property, request.models)

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["error"])

    return SubmitPredictionResponse(**result)


@app.post(
    "/predict",
    response_model=PredictionResponse,
    tags=["Predictions"],
)
async def predict_single(request: PredictionRequest) -> PredictionResponse:
    """Predict molecular property for a single SMILES string with polling.

    This endpoint submits a prediction task and polls for results.
    For long-running predictions, use /submit followed by /status/{task_id}.

    Args:
        request: PredictionRequest containing SMILES, property, and optional max_polls

    Returns:
        PredictionResponse with prediction result

    Raises:
        HTTPException: If input validation fails
    """
    # Input validation
    if not request.smiles or request.smiles.strip() == "":
        raise HTTPException(
            status_code=400,
            detail="SMILES string cannot be empty",
        )

    if not handler.validate_property(request.property):
        raise HTTPException(
            status_code=400,
            detail=f"Property '{request.property}' not supported. "
            f"Available properties: {', '.join(handler.get_available_properties())}",
        )

    # Process prediction
    result = handler.predict_single(request.smiles, request.property, request.max_polls, request.models)

    # Check for errors
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["error"])

    return PredictionResponse(**result)


@app.post(
    "/predict-batch",
    response_model=BatchPredictionResponse,
    tags=["Predictions"],
)
async def predict_batch(
    request: BatchPredictionRequest,
) -> BatchPredictionResponse:
    """Predict molecular property for a batch of SMILES strings.

    Submits all tasks and polls for results.

    Args:
        request: BatchPredictionRequest containing list of SMILES and property

    Returns:
        BatchPredictionResponse with batch prediction results

    Raises:
        HTTPException: If input validation fails
    """
    # Input validation
    if not request.smiles_list or len(request.smiles_list) == 0:
        raise HTTPException(
            status_code=400,
            detail="SMILES list cannot be empty",
        )

    if len(request.smiles_list) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Batch size cannot exceed 1000 SMILES strings",
        )

    if not handler.validate_property(request.property):
        raise HTTPException(
            status_code=400,
            detail=f"Property '{request.property}' not supported. "
            f"Available properties: {', '.join(handler.get_available_properties())}",
        )

    # Process batch predictions
    results = handler.predict_batch(
        request.smiles_list, request.property, request.max_polls, request.models
    )

    # Check if any predictions succeeded
    has_success = any(r["status"] == "success" for r in results)
    batch_status = "partial" if has_success else "error"

    return BatchPredictionResponse(
        count=len(results),
        property=request.property,
        results=[PredictionResponse(**r) for r in results],
        status=batch_status,
    )


@app.get("/status/{task_id}", response_model=TaskStatusResponse, tags=["Tasks"])
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """Check the status of a submitted task.

    Args:
        task_id: Task ID to check

    Returns:
        TaskStatusResponse with task status

    Raises:
        HTTPException: If task_id is invalid
    """
    if not task_id or task_id.strip() == "":
        raise HTTPException(status_code=400, detail="Task ID cannot be empty")

    result = handler.get_task_status(task_id)

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))

    return TaskStatusResponse(**result)


@app.get("/cache-stats", tags=["Administration"])
async def get_cache_stats() -> Dict[str, int]:
    """Get cache statistics.

    Returns:
        Dictionary with cache size information
    """
    return {"cache_size": handler.get_cache_size()}


@app.post("/cache/clear", tags=["Administration"])
async def clear_cache() -> Dict[str, str]:
    """Clear the request cache.

    Returns:
        Dictionary confirming cache has been cleared
    """
    handler.clear_cache()
    return {"status": "cache cleared"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
