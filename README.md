# Protox Microservice

A FastAPI microservice for molecular property predictions using the Protox API.

## Overview

This microservice provides HTTP endpoints for predicting molecular properties from SMILES strings via the Protox API. It implements an asynchronous workflow with task submission and polling for results. Both synchronous (with polling) and asynchronous (manual polling) interfaces are available.

## Features

- **Asynchronous Predictions**: Submit tasks and poll for results
- **Synchronous Interface**: Submit and wait for results in one endpoint
- **Batch Processing**: Handle multiple SMILES strings efficiently
- **Task Tracking**: Track prediction tasks by ID
- **Result Caching**: Cache completed results to avoid re-downloading
- **Error Handling**: Comprehensive validation and error responses
- **Health Checks**: Monitor service availability
- **Administrative Endpoints**: Cache and task management

## Architecture

The service implements Protox's asynchronous prediction workflow:

1. **Submit**: Send SMILES string to Protox and receive a task ID
2. **Poll**: Check task status periodically (30-second intervals)
3. **Retrieve**: Download results CSV once task completes
4. **Parse**: Extract prediction values from results

This approach allows the microservice to handle long-running predictions without blocking HTTP connections.

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd Protox-Microservice
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables (optional):
```bash
cp env.yml.example env.yml
# Edit env.yml with your Protox API configuration
```

## Running the Service

### Development Mode

Start the service with auto-reload:
```bash
uvicorn main:app --reload
```

### Production Mode

Start the service without auto-reload:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

The service will be available at `http://localhost:8000`

## API Documentation

### Interactive API Docs

Once running, access the interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Endpoints

#### Health Check
```
GET /health
```

Returns service status.

**Response:**
```json
{
  "status": "healthy",
  "service": "protox-microservice"
}
```

#### Get Available Properties
```
GET /properties
```

Returns list of supported molecular properties.

**Response:**
```json
{
  "properties": ["toxicity"],
  "count": 1
}
```

#### Get Available Models
```
GET /models
```

Returns list of available toxicity models with descriptions.

**Response:**
```json
{
  "models": {
    "bbb": "Blood-brain barrier permeability",
    "hia": "Human intestinal absorption",
    "pgp": "P-glycoprotein inhibitor",
    "cyp2d6": "CYP2D6 inhibitor",
    "cyp3a4": "CYP3A4 inhibitor",
    "ames": "Ames mutagenicity",
    "skin_sens": "Skin sensitization",
    "acute_tox": "Acute toxicity"
  },
  "count": 8
}
```

#### Submit Prediction (Asynchronous)
```
POST /submit
Content-Type: application/json

{
  "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
  "property": "toxicity",
  "models": ["bbb", "hia", "pgp"]
}
```

Submit a prediction task and receive a task ID for polling. Optionally specify which models to request. Use this for long-running predictions where you don't want to block the HTTP connection.

**Response:**
```json
{
  "status": "submitted",
  "task_id": "task_12345",
  "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
  "property": "toxicity"
}
```

#### Check Task Status
```
GET /status/{task_id}
```

Check the status of a submitted task.

**Response (Pending):**
```json
{
  "task_id": "task_12345",
  "status": "pending"
}
```

**Response (Completed):**
```json
{
  "task_id": "task_12345",
  "status": "completed"
}
```

#### Single Prediction (Synchronous with Polling)
```
POST /predict
Content-Type: application/json

{
  "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
  "property": "toxicity",
  "models": ["bbb", "hia"],
  "max_polls": null
}
```

Submit a prediction task and automatically poll for results. This endpoint blocks until the task completes (or times out). Optionally specify which models to request.

**Response (Success):**
```json
{
  "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
  "property": "toxicity",
  "task_id": "task_12345",
  "status": "success",
  "prediction": 0.75,
  "error": null
}
```

**Response (Timeout):**
```json
{
  "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
  "property": "toxicity",
  "task_id": "task_12345",
  "status": "timeout",
  "prediction": null,
  "error": "Task did not complete after 10 polls"
}
```

#### Batch Prediction
```
POST /predict-batch
Content-Type: application/json

{
  "smiles_list": [
    "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
    "CC(=O)Oc1ccccc1C(=O)O"
  ],
  "property": "toxicity",
  "models": ["bbb", "hia"]
}
```

Submit multiple SMILES strings for prediction. Submits all tasks, then polls for all results. Optionally specify which models to request.

**Response:**
```json
{
  "count": 2,
  "property": "toxicity",
  "status": "partial",
  "results": [
    {
      "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
      "property": "toxicity",
      "task_id": "task_12345",
      "status": "success",
      "prediction": 0.75,
      "error": null
    },
    {
      "smiles": "CC(=O)Oc1ccccc1C(=O)O",
      "property": "toxicity",
      "task_id": "task_12346",
      "status": "success",
      "prediction": 0.82,
      "error": null
    }
  ]
}
```

#### Get Cache Statistics
```
GET /cache-stats
```

Returns current cache size of retrieved results.

**Response:**
```json
{
  "cache_size": 2
}
```

#### Clear Cache
```
POST /cache/clear
```

Clears the internal result cache.

**Response:**
```json
{
  "status": "cache cleared"
}
```

## Usage Patterns

### Pattern 1: Synchronous Predictions (Simple)

For quick predictions, use the `/predict` endpoint which handles submission and polling automatically:

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O", "property": "toxicity"}'
```

### Pattern 2: Asynchronous Predictions (Advanced)

For handling many predictions or avoiding blocking calls, use `/submit` and then `/status/{task_id}`:

```bash
# Submit task
RESPONSE=$(curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d '{"smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O", "property": "toxicity"}')

TASK_ID=$(echo $RESPONSE | jq -r '.task_id')

# Poll for status
while true; do
  curl -X GET "http://localhost:8000/status/$TASK_ID"
  sleep 30
done
```

### Pattern 3: Batch Predictions

Submit multiple SMILES at once:

```bash
curl -X POST http://localhost:8000/predict-batch \
  -H "Content-Type: application/json" \
  -d '{
    "smiles_list": ["CC(C)Cc1ccc(cc1)C(C)C(=O)O", "CC(=O)Oc1ccccc1C(=O)O"],
    "property": "toxicity"
  }'
```


## Project Structure

```
Protox-Microservice/
├── main.py                    # FastAPI application and route handlers
├── protox_handler.py          # Handler for Protox API interactions
├── requirements.txt           # Python dependencies
├── env.yml                    # Environment configuration
├── PROJECT_CONVENTIONS.md     # Project coding standards
└── README.md                  # This file
```

## Architecture

### Asynchronous Workflow

The microservice implements Protox's asynchronous prediction workflow:

1. **Enqueue** (`_submit_task`): Send SMILES to `api_enqueue.php` with requested models, receive task ID
2. **Rate Limiting**: Respect `Retry-After` headers and automatic sleep between requests
3. **Poll** (`_retrieve_task_status`): Check if task completed at `api_retrieve.php` (30-second intervals)
4. **Download** (`_get_results`): Retrieve TSV results file from Protox server
5. **Parse**: Extract prediction values from DataFrame

### Request Format

The `api_enqueue.php` endpoint accepts:
- `input_type`: Type of input (default: "smiles")
- `input`: The SMILES string to predict
- `requested_data`: JSON-encoded list of toxicity models to request

### Rate Limiting and Quota Management

- **429 (Too Many Requests)**: Automatically respects `Retry-After` header
- **403 (Forbidden)**: Raises `QuotaExceededException` when daily quota exceeded
- **Sleep on Success**: Automatically sleeps for `Retry-After` seconds after successful submissions

### Separation of Concerns

- **main.py**: HTTP request/response handling, input validation, route definitions
- **protox_handler.py**: Protox API interactions, task submission, polling, result retrieval, data processing, rate limiting

### Key Components

#### ProtoxHandler (protox_handler.py)
- Submits SMILES strings via `api_enqueue.php` with configurable models
- Handles rate limiting with `Retry-After` headers
- Detects and raises exceptions for quota exceeded (403) and rate limiting (429)
- Polls task status at configurable intervals (default: 30 seconds)
- Retrieves and parses TSV result files from Protox
- Caches completed results to avoid re-downloading
- Supports per-request model selection or uses default models
- Provides both synchronous (with polling) and asynchronous (task ID only) interfaces
- Comprehensive logging for debugging

#### FastAPI Application (main.py)
- Exposes REST endpoints for submission and polling
- Implements Pydantic request/response models
- Validates user input at HTTP layer
- Provides both synchronous and asynchronous interfaces with model selection
- Converts handler results to HTTP responses with proper status codes

## Error Handling

The service returns appropriate HTTP status codes:

- **200 OK**: Successful prediction(s)
- **400 Bad Request**: Invalid input (empty SMILES, unsupported property, etc.)
- **404 Not Found**: Resource not found
- **500 Internal Server Error**: Server-side errors

Error responses include a `detail` field with actionable messages:

```json
{
  "detail": "Property 'invalid_property' not supported. Available properties: toxicity"
}
```

## Configuration

### Environment Variables

Configure the service using environment variables in `env.yml`:

- `PROTOX_ENQUEUE_URL`: Protox enqueue endpoint (default: https://tox.charite.de/protox3/src/api_enqueue.php)
- `PROTOX_RETRIEVE_URL`: Protox task status endpoint (default: https://tox.charite.de/protox3/src/api_retrieve.php)
- `PROTOX_RESULT_BASE_URL`: Protox results file base URL (default: https://tox.charite.de/protox3/csv)
- `PROTOX_TIMEOUT`: HTTP request timeout in seconds (default: 30)
- `PROTOX_POLL_INTERVAL`: Polling interval in seconds (default: 30)
- `PROTOX_INPUT_TYPE`: Type of input data (default: "smiles")
- `PROTOX_MODELS`: Comma-separated list of default models to request

### Available Toxicity Models

The following toxicity models are available for prediction:
- **bbb**: Blood-brain barrier permeability
- **hia**: Human intestinal absorption
- **pgp**: P-glycoprotein inhibitor
- **cyp2d6**: CYP2D6 inhibitor
- **cyp3a4**: CYP3A4 inhibitor
- **ames**: Ames mutagenicity
- **skin_sens**: Skin sensitization
- **acute_tox**: Acute toxicity

Request specific models via the `models` parameter or leave unset to use defaults.

### Result Caching

The handler maintains an internal cache of retrieved results to avoid re-downloading from Protox. Use the `/cache/clear` endpoint to clear the cache if needed.

## Contributing

When adding new features, follow the [PROJECT_CONVENTIONS.md](PROJECT_CONVENTIONS.md) guidelines:

- Use type hints for all functions
- Write Google-style docstrings
- Separate API logic from business logic
- Include comprehensive error handling
- Add both single and batch processing methods
- Validate all user input

## Testing

To test the API, you can use:

### cURL - Synchronous Prediction
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O", "property": "toxicity"}'
```

### cURL - Submit Task
```bash
curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d '{"smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O", "property": "toxicity"}'
```

### cURL - Check Task Status
```bash
curl -X GET "http://localhost:8000/status/task_12345"
```

### Python
```python
import httpx

# Synchronous prediction
response = httpx.post(
    "http://localhost:8000/predict",
    json={
        "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
        "property": "toxicity"
    }
)
print(response.json())
```

### Docker (Optional)

Build a Docker image:
```bash
docker build -t protox-microservice .
docker run -p 8000:8000 protox-microservice
```

## License

[Add your license information here]

## Support

For issues or questions, please contact the development team or open an issue in the repository.
