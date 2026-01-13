"""Handler for Protox predictions via HTTP requests.

This module manages all interactions with the Protox external service,
handling asynchronous SMILES predictions through task submission and polling.
Implements proper rate limiting and quota management.
"""

from typing import Dict, List, Any, Optional
import httpx
import logging
import time
import json
import pandas as pd
from io import StringIO

logger = logging.getLogger(__name__)


class QuotaExceededException(Exception):
    """Raised when daily quota has been exceeded."""
    pass


class RateLimitedException(Exception):
    """Raised when rate limit is hit and must wait."""
    pass


class ProtoxHandler:
    """Handle interactions with Protox API for molecular property predictions."""

    # Protox API configuration
    ENQUEUE_URL: str = "https://tox.charite.de/protox3/src/api_enqueue.php"
    RETRIEVE_URL: str = "https://tox.charite.de/protox3/src/api_retrieve.php"
    RESULT_BASE_URL: str = "https://tox.charite.de/protox3/csv"
    TIMEOUT: int = 30
    POLL_INTERVAL: int = 30  # seconds between status checks

    # Available toxicity models
    AVAILABLE_MODELS: Dict[str, str] = {
        "bbb": "Blood-brain barrier permeability",
        "hia": "Human intestinal absorption",
        "pgp": "P-glycoprotein inhibitor",
        "cyp2d6": "CYP2D6 inhibitor",
        "cyp3a4": "CYP3A4 inhibitor",
        "ames": "Ames mutagenicity",
        "skin_sens": "Skin sensitization",
        "acute_tox": "Acute toxicity",
    }

    # Available properties for predictions
    AVAILABLE_PROPERTIES: List[str] = [
        "toxicity",
    ]

    def __init__(
        self,
        enqueue_url: Optional[str] = None,
        retrieve_url: Optional[str] = None,
        result_base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        poll_interval: Optional[int] = None,
        models: Optional[List[str]] = None,
        input_type: str = "smiles",
    ):
        """Initialize the Protox handler.

        Args:
            enqueue_url: Optional custom enqueue endpoint
            retrieve_url: Optional custom retrieval endpoint
            result_base_url: Optional custom results base URL
            timeout: Optional custom request timeout in seconds
            poll_interval: Optional custom polling interval in seconds
            models: List of toxicity models to request (default: all available)
            input_type: Type of input data, e.g., 'smiles' (default: 'smiles')
        """
        self.enqueue_url = enqueue_url or self.ENQUEUE_URL
        self.retrieve_url = retrieve_url or self.RETRIEVE_URL
        self.result_base_url = result_base_url or self.RESULT_BASE_URL
        self.timeout = timeout or self.TIMEOUT
        self.poll_interval = poll_interval or self.POLL_INTERVAL
        self.input_type = input_type
        self.models = models or list(self.AVAILABLE_MODELS.keys())
        self._task_cache: Dict[str, Any] = {}  # Maps task_id to results

    def submit_prediction(
        self, smiles: str, property_name: str = "toxicity", models: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Submit a prediction task to Protox API.

        Args:
            smiles: A SMILES string to process
            property_name: The molecular property to predict
            models: Optional list of specific models to request (None = use default)

        Returns:
            Dictionary with task_id or error information
        """
        if not smiles or smiles.strip() == "":
            return {
                "status": "error",
                "error": "SMILES string cannot be empty",
            }

        if not self.validate_property(property_name):
            return {
                "status": "error",
                "error": f"Property '{property_name}' not supported",
            }

        # Use provided models or default
        request_models = models or self.models

        try:
            task_id = self._submit_task(smiles, request_models)
            logger.info(f"Successfully submitted SMILES: {smiles}, Task ID: {task_id}")
            return {
                "status": "submitted",
                "task_id": task_id,
                "smiles": smiles,
                "property": property_name,
            }
        except QuotaExceededException as e:
            logger.error(f"Daily quota exceeded: {str(e)}")
            return {
                "status": "error",
                "error": "Daily quota exceeded",
            }
        except RateLimitedException as e:
            logger.error(f"Rate limited: {str(e)}")
            return {
                "status": "error",
                "error": "Rate limited, please retry later",
            }
        except Exception as e:
            logger.error(f"Error submitting prediction for SMILES {smiles}: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
            }

    def predict_single(
        self, smiles: str, property_name: str = "toxicity", max_polls: Optional[int] = None, models: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Predict a molecular property for a single SMILES string with polling.

        Submits the task and polls for completion up to max_polls times.

        Args:
            smiles: A SMILES string to process
            property_name: The molecular property to predict
            max_polls: Maximum number of polls before timing out (None = unlimited)
            models: Optional list of specific models to request (None = use default)

        Returns:
            Dictionary containing prediction results with status field
        """
        if not smiles or smiles.strip() == "":
            return {
                "smiles": smiles,
                "property": property_name,
                "status": "error",
                "error": "SMILES string cannot be empty",
            }

        if not self.validate_property(property_name):
            return {
                "smiles": smiles,
                "property": property_name,
                "status": "error",
                "error": f"Property '{property_name}' not supported",
            }

        # Use provided models or default
        request_models = models or self.models

        try:
            # Submit task
            task_id = self._submit_task(smiles, request_models)
            
            # Poll for results
            result = self._poll_for_results(task_id, smiles, property_name, max_polls)
            return result

        except Exception as e:
            logger.error(f"Error predicting for SMILES {smiles}: {str(e)}")
            return {
                "smiles": smiles,
                "property": property_name,
                "status": "error",
                "error": str(e),
            }

    def predict_batch(
        self, smiles_list: List[str], property_name: str = "toxicity", max_polls: Optional[int] = None, models: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Predict molecular properties for a batch of SMILES strings.

        Submits all tasks first, then polls for results.

        Args:
            smiles_list: List of SMILES strings to process
            property_name: The molecular property to predict
            max_polls: Maximum number of polls before timing out (None = unlimited)
            models: Optional list of specific models to request (None = use default)

        Returns:
            List of dictionaries containing prediction results
        """
        # Use provided models or default
        request_models = models or self.models

        # Submit all tasks
        task_list = []
        for smiles in smiles_list:
            if not smiles or smiles.strip() == "":
                continue
            try:
                task_id = self._submit_task(smiles, request_models)
                task_list.append({"task_id": task_id, "smiles": smiles})
            except Exception as e:
                logger.error(f"Error submitting SMILES {smiles}: {str(e)}")

        # Poll for all results
        results = []
        for task_info in task_list:
            result = self._poll_for_results(
                task_info["task_id"],
                task_info["smiles"],
                property_name,
                max_polls,
            )
            results.append(result)

        return results

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Check the status of a submitted task.

        Args:
            task_id: The task ID to check

        Returns:
            Dictionary with task status information
        """
        try:
            response = self._retrieve_task_status(task_id)
            if response.status_code == 200 and response.text:
                return {
                    "status": "completed",
                    "task_id": task_id,
                }
            else:
                return {
                    "status": "pending",
                    "task_id": task_id,
                }
        except Exception as e:
            logger.error(f"Error checking task status {task_id}: {str(e)}")
            return {
                "status": "error",
                "task_id": task_id,
                "error": str(e),
            }

    def validate_property(self, property_name: str) -> bool:
        """Check if property is supported by Protox.

        Args:
            property_name: Property name to validate

        Returns:
            True if property is supported, False otherwise
        """
        return property_name.lower() in [p.lower() for p in self.AVAILABLE_PROPERTIES]

    def get_available_properties(self) -> List[str]:
        """Return list of available properties for prediction.

        Returns:
            List of supported property names
        """
        return self.AVAILABLE_PROPERTIES.copy()

    def get_available_models(self) -> Dict[str, str]:
        """Return available toxicity models.

        Returns:
            Dictionary mapping model names to descriptions
        """
        return self.AVAILABLE_MODELS.copy()

    def clear_cache(self) -> None:
        """Clear the internal task cache."""
        self._task_cache.clear()

    def get_cache_size(self) -> int:
        """Get the current size of the task cache.

        Returns:
            Number of cached tasks
        """
        return len(self._task_cache)

    def _submit_task(self, smiles: str, models: Optional[List[str]] = None) -> str:
        """Submit a SMILES string to Protox API for prediction.

        Args:
            smiles: SMILES string to predict
            models: Optional list of models to request (None = use default)

        Returns:
            Task ID for tracking the prediction

        Raises:
            httpx.RequestError: If HTTP request fails
            QuotaExceededException: If daily quota exceeded (403)
            RateLimitedException: If rate limited (429)
            ValueError: If API returns unexpected response
        """
        request_models = models or self.models
        
        payload = {
            "input_type": self.input_type,
            "input": smiles,
            "requested_data": json.dumps(request_models),
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self.enqueue_url, data=payload)

            # Handle success
            if response.status_code == 200:
                task_id = response.text.strip()
                if not task_id:
                    raise ValueError("No task ID returned from submission")

                # Respect Retry-After header
                retry_after = int(response.headers.get("Retry-After", 5)) + 1
                logger.info(f"Task submitted successfully. Waiting {retry_after}s before next request...")
                time.sleep(retry_after)
                return task_id

            # Handle rate limiting
            elif response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 5)) + 1
                error_msg = f"Rate limited by Protox. Retry-After: {retry_after}s"
                logger.warning(error_msg)
                raise RateLimitedException(error_msg)

            # Handle quota exceeded
            elif response.status_code == 403:
                error_msg = "Daily quota exceeded for Protox API"
                logger.error(error_msg)
                raise QuotaExceededException(error_msg)

            # Handle other errors
            else:
                error_msg = f"Protox API error {response.status_code}: {response.reason}"
                logger.error(error_msg)
                raise httpx.RequestError(error_msg)

    def _retrieve_task_status(self, task_id: str) -> httpx.Response:
        """Check the status of a submitted task.

        Args:
            task_id: Task ID to check

        Returns:
            HTTP response object

        Raises:
            httpx.RequestError: If HTTP request fails
        """
        with httpx.Client(timeout=self.timeout) as client:
            payload = {"id": task_id}
            response = client.post(self.retrieve_url, data=payload)
            response.raise_for_status()
            return response

    def _get_results(self, task_id: str) -> pd.DataFrame:
        """Retrieve results from completed task.

        Args:
            task_id: Completed task ID

        Returns:
            DataFrame containing prediction results

        Raises:
            httpx.RequestError: If download fails
            ValueError: If CSV cannot be parsed
        """
        if task_id in self._task_cache:
            return self._task_cache[task_id]

        result_url = f"{self.result_base_url}/{task_id}_result.csv"
        
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(result_url)
            response.raise_for_status()

            # Parse TSV format
            df = pd.read_csv(StringIO(response.text), sep='\t')
            
            # Cache the results
            self._task_cache[task_id] = df
            return df

    def _poll_for_results(
        self,
        task_id: str,
        smiles: str,
        property_name: str,
        max_polls: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Poll for task completion and return results.

        Args:
            task_id: Task ID to poll
            smiles: Original SMILES string
            property_name: Property that was predicted
            max_polls: Maximum number of polls (None = unlimited)

        Returns:
            Dictionary with prediction results
        """
        poll_count = 0
        
        while True:
            if max_polls is not None and poll_count >= max_polls:
                return {
                    "smiles": smiles,
                    "property": property_name,
                    "status": "timeout",
                    "error": f"Task did not complete after {max_polls} polls",
                }

            try:
                # Check task status
                response = self._retrieve_task_status(task_id)
                
                if response.status_code == 200 and response.text:
                    # Task completed, retrieve results
                    try:
                        df = self._get_results(task_id)
                        
                        # Extract first prediction value
                        if not df.empty and len(df.columns) > 0:
                            # Get first non-index column
                            first_col = df.columns[0]
                            prediction = float(df[first_col].iloc[0])
                            
                            return {
                                "smiles": smiles,
                                "property": property_name,
                                "task_id": task_id,
                                "status": "success",
                                "prediction": prediction,
                            }
                        else:
                            return {
                                "smiles": smiles,
                                "property": property_name,
                                "task_id": task_id,
                                "status": "error",
                                "error": "Empty results from Protox",
                            }
                    except Exception as e:
                        logger.error(f"Failed to parse result for task {task_id}: {e}")
                        return {
                            "smiles": smiles,
                            "property": property_name,
                            "task_id": task_id,
                            "status": "error",
                            "error": f"Failed to parse results: {str(e)}",
                        }
                else:
                    # Task still pending
                    poll_count += 1
                    if poll_count == 1:
                        logger.info(f"Task {task_id} pending, starting poll cycle...")
                    time.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Error polling task {task_id}: {str(e)}")
                return {
                    "smiles": smiles,
                    "property": property_name,
                    "task_id": task_id,
                    "status": "error",
                    "error": str(e),
                }

