#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Batch Ingestion Script for Fake Store API
Extracts products and users data, stores in GCS, and loads to BigQuery
Supports both local-only mode (testing) and production mode (GCS + BigQuery)
"""

import requests
import json
import logging
import argparse
import uuid
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, List

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# =============================================================================
# GCP IMPORTS WITH AVAILABILITY CHECK
# =============================================================================
GCS_AVAILABLE = False
BIGQUERY_AVAILABLE = False
GCP_IMPORT_ERROR = None

try:
    from google.cloud import storage
    GCS_AVAILABLE = True
except ImportError as e:
    GCP_IMPORT_ERROR = f"google-cloud-storage: {str(e)}"

try:
    from google.cloud import bigquery
    BIGQUERY_AVAILABLE = True
except ImportError as e:
    if GCP_IMPORT_ERROR:
        GCP_IMPORT_ERROR += f" | google-cloud-bigquery: {str(e)}"
    else:
        GCP_IMPORT_ERROR = f"google-cloud-bigquery: {str(e)}"

# =============================================================================
# GLOBAL CONFIGURATION
# =============================================================================
API_SOURCES = [
    {"name": "products", "url": "https://fakestoreapi.com/products"},
    {"name": "users", "url": "https://fakestoreapi.com/users"}
]

REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
INITIAL_BACKOFF = 2  # seconds
LOCAL_RAW_DIR = Path("./raw")

# Generate unique run identifier and extraction timestamp
RUN_ID = str(uuid.uuid4())[:8]
EXTRACTED_AT = datetime.now(timezone.utc).isoformat()

# =============================================================================
# API EXTRACTION
# =============================================================================
def fetch_from_api(url: str, entity_type: str) -> Optional[List[dict]]:
    """
    Fetch data from REST API with exponential backoff retry logic.

    Args:
        url: API endpoint URL
        entity_type: Type of entity being fetched (for logging)

    Returns:
        List of records if successful, None otherwise
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"Fetching {entity_type} from API (attempt {attempt}/{MAX_RETRIES})"
            )

            with requests.Session() as session:
                response = session.get(url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                data = response.json()

            logger.info(
                f"Successfully fetched {len(data)} {entity_type} records"
            )
            return data

        except requests.exceptions.RequestException as e:
            backoff_time = INITIAL_BACKOFF * (2 ** (attempt - 1))
            logger.warning(
                f"API request failed for {entity_type}: {e} "
                f"(attempt {attempt}/{MAX_RETRIES})"
            )

            if attempt < MAX_RETRIES:
                logger.warning(f"Retrying in {backoff_time} seconds")
                import time
                time.sleep(backoff_time)
            else:
                logger.error(
                    f"Max retries reached for {entity_type}, extraction failed"
                )
                return None

# =============================================================================
# LOCAL STORAGE (BACKUP & TESTING)
# =============================================================================
def save_to_local_storage(
    data: List[dict],
    entity_type: str,
    date_partition: str,
    run_id: str
) -> Path:
    """
    Save extracted data to local filesystem with idempotent structure.
    Structure: raw/{entity_type}/date={yyyy-mm-dd}/run_id={run_id}/data.json

    Args:
        data: List of records to save
        entity_type: Type of entity (products, users)
        date_partition: Date partition (yyyy-mm-dd format)
        run_id: Unique run identifier

    Returns:
        Path to saved file
    """
    file_path = LOCAL_RAW_DIR / entity_type / f"date={date_partition}" / f"run_id={run_id}" / "data.json"
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Prepare payload with metadata for BigQuery compatibility
    payload = {
        "extracted_at": EXTRACTED_AT,
        "run_id": run_id,
        "entity_type": entity_type,
        "record_count": len(data),
        "data": data
    }

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            
            json.dump(payload, f, ensure_ascii=False) 

        logger.info(f"Saved {entity_type} locally: {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"Failed to save {entity_type} locally: {e}")
        raise

# =============================================================================
# GOOGLE CLOUD STORAGE
# =============================================================================
def upload_to_gcs(
    local_path: Path,
    bucket_name: str,
    entity_type: str,
    date_partition: str,
    run_id: str,
    project_id: str  
) -> Optional[str]:
    """
    Upload JSON file to Google Cloud Storage with immutable structure.
    """
    if not GCS_AVAILABLE:
        logger.warning("Google Cloud Storage library not available, skipping GCS upload")
        return None

    try:
        client = storage.Client(project=project_id) 
        bucket = client.bucket(bucket_name)

        blob_path = f"raw/{entity_type}/date={date_partition}/run_id={run_id}/data.json"
        blob = bucket.blob(blob_path)

        blob.metadata = {
            "extracted_at": EXTRACTED_AT,
            "run_id": run_id,
            "entity_type": entity_type,
            "source": "fake-store-api"
        }

        blob.upload_from_filename(str(local_path))
        gcs_uri = f"gs://{bucket_name}/{blob_path}"
        logger.info(f"Uploaded {entity_type} to GCS: {gcs_uri}")

        return gcs_uri

    except Exception as e:
        logger.error(f"Failed to upload {entity_type} to GCS: {e}")
        logger.warning(f"Data preserved locally at: {local_path}")
        return None

# =============================================================================
# BIGQUERY LOADING
# =============================================================================
def create_bigquery_schema() -> List:
    """
    Define BigQuery schema for raw tables.

    Returns:
        List of SchemaField objects
    """
    return [
        bigquery.SchemaField("extracted_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("entity_type", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("record_count", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("data", "JSON", mode="REQUIRED")
    ]

def load_to_bigquery(
    gcs_uri: str,
    project_id: str,
    dataset_id: str,
    entity_type: str
) -> bool:
    """
    Load JSON data from GCS to BigQuery raw table using load job.

    Args:
        gcs_uri: Full GCS URI (gs://bucket/path)
        project_id: GCP project ID
        dataset_id: BigQuery dataset name
        entity_type: Type of entity (determines table name)

    Returns:
        True if load successful, False otherwise
    """
    if not BIGQUERY_AVAILABLE:
        logger.warning(
            "Google BigQuery library not available, skipping BigQuery load"
        )
        return False

    try:
        client = bigquery.Client(project=project_id)

        # Define target table
        table_id = f"{entity_type}_raw"
        table_ref = f"{project_id}.{dataset_id}.{table_id}"

        # Configure load job
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            autodetect=False,
            schema=create_bigquery_schema()
        )

        logger.info(f"Starting BigQuery load job for {entity_type}")
        logger.info(f"Source: {gcs_uri}")
        logger.info(f"Destination: {table_ref}")

        # Start load job
        load_job = client.load_table_from_uri(
            gcs_uri,
            table_ref,
            job_config=job_config
        )

        # Wait for job completion
        load_job.result()

        # Log results
        destination_table = client.get_table(table_ref)
        logger.info(
            f"Loaded {load_job.output_rows} rows to {table_ref} "
            f"(total rows: {destination_table.num_rows})"
        )

        return True

    except Exception as e:
        logger.error(f"Failed to load {entity_type} to BigQuery: {e}")
        return False

# =============================================================================
# ORCHESTRATION
# =============================================================================
def ingest_entity(
    source: Dict[str, str],
    bucket_name: Optional[str],
    project_id: Optional[str],
    dataset_id: str,
    local_only: bool
) -> Dict:
    """
    Complete ingestion pipeline for a single entity.
    Pipeline: API -> Local Storage -> GCS -> BigQuery

    Args:
        source: Dictionary with 'name' and 'url' keys
        bucket_name: GCS bucket name (None if local_only)
        project_id: GCP project ID (None if local_only)
        dataset_id: BigQuery dataset name
        local_only: If True, skip GCS and BigQuery steps

    Returns:
        Dictionary with ingestion results and statistics
    """
    entity_type = source["name"]
    api_url = source["url"]
    date_partition = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    result = {
        "entity": entity_type,
        "status": "failed",
        "record_count": 0,
        "local_saved": False,
        "gcs_uploaded": False,
        "bigquery_loaded": False,
        "error": None
    }

    try:
        logger.info(f"Starting ingestion pipeline for {entity_type}")

        # Step 1: Extract from API
        data = fetch_from_api(api_url, entity_type)
        if data is None:
            result["error"] = "API extraction failed"
            return result

        result["record_count"] = len(data)

        # Step 2: Save to local storage (always done for backup)
        local_path = save_to_local_storage(
            data, entity_type, date_partition, RUN_ID
        )
        result["local_saved"] = True
        result["local_path"] = str(local_path)

        # Step 3: Upload to GCS (if not local_only)
        if local_only:
            logger.info(
                f"Local-only mode enabled, skipping cloud upload for {entity_type}"
            )
            result["status"] = "success"
            return result

        if not bucket_name:
            logger.warning(
                f"No bucket name provided, skipping GCS upload for {entity_type}"
            )
            result["status"] = "partial"
            return result

        gcs_uri = upload_to_gcs(
            local_path, bucket_name, entity_type, date_partition, RUN_ID,project_id
        )

        if gcs_uri is None:
            logger.warning(f"GCS upload failed for {entity_type}, data saved locally")
            result["status"] = "partial"
            return result

        result["gcs_uploaded"] = True
        result["gcs_uri"] = gcs_uri

        # Step 4: Load to BigQuery (if GCS upload succeeded)
        if not project_id:
            logger.warning(
                f"No project ID provided, skipping BigQuery load for {entity_type}"
            )
            result["status"] = "partial"
            return result

        bq_success = load_to_bigquery(
            gcs_uri, project_id, dataset_id, entity_type
        )

        result["bigquery_loaded"] = bq_success
        result["status"] = "success" if bq_success else "partial"

        logger.info(f"Completed ingestion pipeline for {entity_type}")
        return result

    except Exception as e:
        logger.error(f"Unexpected error during {entity_type} ingestion: {e}")
        result["error"] = str(e)
        return result

def print_summary(results: List[Dict], mode: str):
    """
    Print detailed summary of ingestion results.

    Args:
        results: List of result dictionaries from ingestion
        mode: Operating mode (LOCAL or GCP)
    """
    logger.info("=" * 70)
    logger.info("INGESTION SUMMARY")
    logger.info("=" * 70)

    for result in results:
        entity = result["entity"]
        status = result["status"]

        if status == "success":
            logger.info(f"SUCCESS: {entity}")
            logger.info(f"  Records: {result['record_count']}")
            logger.info(f"  Local: {result.get('local_path', 'N/A')}")

            if mode == "GCP":
                logger.info(
                    f"  GCS: {'Yes' if result.get('gcs_uploaded') else 'No'}"
                )
                logger.info(
                    f"  BigQuery: {'Yes' if result.get('bigquery_loaded') else 'No'}"
                )

        elif status == "partial":
            logger.warning(f"PARTIAL: {entity}")
            logger.warning(f"  Records: {result['record_count']}")
            logger.warning(f"  Local: {result.get('local_path', 'N/A')}")
            logger.warning(
                f"  GCS: {'Yes' if result.get('gcs_uploaded') else 'No'}"
            )
            logger.warning(
                f"  BigQuery: {'Yes' if result.get('bigquery_loaded') else 'No'}"
            )

        else:
            logger.error(f"FAILED: {entity}")
            if result.get("error"):
                logger.error(f"  Error: {result['error']}")

    # Statistics
    success_count = sum(1 for r in results if r["status"] == "success")
    partial_count = sum(1 for r in results if r["status"] == "partial")
    failed_count = sum(1 for r in results if r["status"] == "failed")
    total_records = sum(r["record_count"] for r in results)

    logger.info("-" * 70)
    logger.info(f"Total entities: {len(results)}")
    logger.info(f"Success: {success_count} | Partial: {partial_count} | Failed: {failed_count}")
    logger.info(f"Total records extracted: {total_records}")
    logger.info("=" * 70)

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
def main():
    """Main entry point for batch ingestion script."""

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Batch ingestion from Fake Store API to GCS and BigQuery',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Local-only mode (testing):
    python batch_ingestion.py --local-only

  Production mode:
    python batch_ingestion.py \
      --project-id my-gcp-project \
      --bucket-name my-raw-data-bucket \
      --dataset-id raw
        """
    )

    parser.add_argument(
        '--project-id',
        type=str,
        help='GCP project ID (required for production mode)'
    )

    parser.add_argument(
        '--bucket-name',
        type=str,
        help='GCS bucket name for raw data storage (required for production mode)'
    )

    parser.add_argument(
        '--dataset-id',
        type=str,
        default='raw',
        help='BigQuery dataset for raw tables (default: raw)'
    )

    parser.add_argument(
        '--local-only',
        action='store_true',
        help='Run in local-only mode without GCS/BigQuery (for testing)'
    )

    parser.add_argument(
        '--max-workers',
        type=int,
        default=2,
        help='Maximum number of parallel workers (default: 2)'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.local_only:
        if not args.project_id or not args.bucket_name:
            logger.error(
                "Error: --project-id and --bucket-name are required for production mode"
            )
            logger.info("Use --local-only flag to run without GCP dependencies")
            parser.print_help()
            return 1

        # Check GCP library availability
        if not GCS_AVAILABLE or not BIGQUERY_AVAILABLE:
            logger.error("Error: GCP libraries not available")
            if GCP_IMPORT_ERROR:
                logger.error(f"Import error: {GCP_IMPORT_ERROR}")
            logger.error("Install with: pip install google-cloud-storage google-cloud-bigquery")
            logger.info("Or use --local-only flag to run without GCP dependencies")
            return 1

    # Determine operating mode
    mode = "LOCAL" if args.local_only else "GCP"

    # Print header
    logger.info("=" * 70)
    logger.info("BATCH INGESTION STARTED")
    logger.info("=" * 70)
    logger.info(f"Run ID: {RUN_ID}")
    logger.info(f"Timestamp: {EXTRACTED_AT}")
    logger.info(f"Mode: {mode}")
    logger.info(f"Entities: {', '.join(s['name'] for s in API_SOURCES)}")
    if not args.local_only:
        logger.info(f"Project: {args.project_id}")
        logger.info(f"Bucket: {args.bucket_name}")
        logger.info(f"Dataset: {args.dataset_id}")
    logger.info("=" * 70)

    # Execute ingestion in parallel
    results = []

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        future_to_source = {
            executor.submit(
                ingest_entity,
                source,
                args.bucket_name,
                args.project_id,
                args.dataset_id,
                args.local_only
            ): source for source in API_SOURCES
        }

        for future in as_completed(future_to_source):
            result = future.result()
            results.append(result)

    # Print summary
    print_summary(results, mode)

    # Determine exit code
    if all(r["status"] == "success" for r in results):
        logger.info("Batch ingestion completed successfully")
        return 0
    elif any(r["status"] == "failed" for r in results):
        logger.error("Batch ingestion completed with failures")
        return 1
    else:
        logger.warning("Batch ingestion completed with partial results")
        return 0

if __name__ == '__main__':
    exit(main())