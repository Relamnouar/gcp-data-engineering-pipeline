# GCP Data Engineering Pipeline

## Overview

This project implements a production-ready data pipeline on Google Cloud Platform (GCP), featuring batch and near-real-time ingestion from the Fake Store API, with data transformation using dbt and infrastructure provisioning via Terraform.

---

## Architecture & Design Decisions

### Batch Ingestion Pipeline

The `batch_ingestion.py` script extracts static reference data (products and users) from REST API endpoints and loads them into BigQuery through Google Cloud Storage.

**Key Features:**
- **Resilient API Extraction**: Implements exponential backoff retry logic (max 3 attempts) to handle transient network failures
- **Parallel Processing**: Uses ThreadPoolExecutor to fetch multiple entity types concurrently, reducing total execution time
- **Idempotent Storage**: Data is partitioned by date and run_id (`raw/{entity}/date={yyyy-mm-dd}/run_id={uuid}/data.json`) to prevent accidental overwrites
- **Graceful Degradation**: Falls back to local storage if GCS/BigQuery services are unavailable, ensuring data preservation

**Test Scenarios:**
- **Local-only mode** (`--local-only`): Validates API extraction and JSON serialization without GCP dependencies
- **Production mode**: Tests end-to-end pipeline including GCS upload and BigQuery load jobs
- **Failure recovery**: Simulates API timeouts and validates retry behavior with backoff delays

---

### Near-Real-Time Streaming Pipeline

The `near_realtime_ingestion_2.py` script continuously monitors the shopping carts endpoint, detects changes, and publishes events to Pub/Sub for downstream processing.

**Change Detection Algorithm:**
1. **State Management**: Maintains a persistent snapshot of cart data (cart_id, date, products) in `./state/carts_state.json`
2. **Cold Start Backfill**: On first execution, treats all existing carts as `cart_created` events to initialize the system
3. **Delta Detection**: Compares current API response with stored state to identify:
   - **New carts**: IDs present in API but not in state
   - **Modified carts**: Changes in date field or product list (detected via JSON signature comparison)
   - **Deleted carts**: IDs present in state but missing from API response
4. **Event Publishing**: Generates CloudEvents-compliant messages with deterministic event IDs for idempotency

**Key Features:**
- **Exactly-Once Semantics**: Event IDs are hashed from cart content, preventing duplicate processing
- **Message Ordering**: Uses Pub/Sub ordering keys (`cart_{id}`) to guarantee chronological event processing per cart
- **Graceful Shutdown**: Listens for SIGINT/SIGTERM signals to complete ongoing operations before exit
- **Dead Letter Queue**: Failed publish attempts are saved locally for manual recovery

**Test Scenarios:**
- **Cold start**: Verify snapshot creation and bulk event generation for existing data
- **Incremental updates**: Add/modify/delete carts via API mock and validate event types
- **Failure handling**: Test Pub/Sub unavailability and confirm local event persistence
- **Polling interval**: Configurable via `--poll-interval` flag for testing different latency requirements

---

### ELT Architecture

This project adopts an **Extract, Load, Transform (ELT)** approach rather than traditional ETL:

- **Extract**: Raw JSON data is extracted from APIs with minimal processing
- **Load**: Data is immediately loaded into BigQuery as-is (Bronze layer)
- **Transform**: All business logic and data quality rules are applied in BigQuery using dbt

**Benefits:**
- **Scalability**: Leverages BigQuery's massively parallel processing for transformations
- **Auditability**: Raw data is preserved for reprocessing if business rules change
- **Flexibility**: Analysts can access Bronze layer for ad-hoc exploration
- **Cost Efficiency**: Compute resources are only used during transformation, not during extraction

---

### dbt Medallion Architecture

The dbt project implements a **Medallion Architecture** with three data quality tiers:

#### Bronze Layer (Raw)
- Direct ingestion from GCS and Pub/Sub
- No transformations applied
- Serves as immutable source of truth

#### Silver Layer (Staging)
- Data type casting and standardization
- Null handling and deduplication
- Incremental models for streaming data
- Data quality tests (uniqueness, not-null constraints)

#### Gold Layer (Business-Ready)
- **Star Schema Design** for analytical workloads:
  - **Fact Tables**: `fact_cart_items` (granular transaction-level data)
  - **Dimension Tables**: `dim_products`, `dim_users`, `dim_dates`
- Pre-aggregated metrics and KPIs
- Optimized for BI tool consumption (Looker, Tableau, Power BI)

**Benefits:**
- **Performance**: Star schema enables fast JOIN operations for OLAP queries
- **Simplicity**: Business users can query denormalized fact tables without complex SQL
- **Governance**: Certified datasets with documented lineage and ownership

---

### Infrastructure as Code (Terraform)

Terraform automates the provisioning of all GCP resources, ensuring:

- **Reproducibility**: Entire environment can be recreated in minutes
- **Version Control**: Infrastructure changes are tracked in Git
- **Consistency**: Development, staging, and production environments use identical configurations

**Provisioned Resources:**
- BigQuery datasets (bronze, silver, gold)
- GCS buckets with lifecycle policies
- Pub/Sub topics and subscriptions
- IAM roles and service accounts

---

### Containerization (Docker)

Docker provides a consistent execution environment across different operating systems, eliminating "works on my machine" issues.

**Benefits:**
- **Dependency Isolation**: All Python packages, Terraform, and dbt versions are pinned
- **Credential Management**: Service account keys are mounted securely via volumes
- **Tester-Friendly**: Reviewers can run the entire pipeline without installing dependencies locally

---

## Execution Guide

### Prerequisites

- **Docker Desktop** installed and running
- **GCP Project** with billing enabled

---

### Step 1: Configure Environment Variables

Edit the `.env` file with your GCP project details:

```env
GCP_PROJECT_ID=your-project-id
GCP_REGION=europe-west9
BQ_DATASET=bronze_data
GCS_BUCKET_NAME=your-project-id-raw-data-2026-xyz
```

**Bucket Naming Best Practices:**
- Must be globally unique across all GCP customers
- Use format: `{project-id}-{purpose}-{year}-{random-suffix}`
- Example: `my-ecommerce-raw-data-2026-abc123`

---

### Step 2: Add GCP Service Account Key

Place your downloaded service account JSON key into the `credentials/` directory:

```bash
./credentials/gcp-key.json
```

See [How to Obtain GCP Service Account Key](#how-to-obtain-gcp-service-account-key) section below.

---

### Step 3: Launch Docker Environment

**On Windows:**
```cmd
Start-project.bat
```

**On macOS/Linux:**
```bash
make run
```

This command:
1. Builds the Docker image with all dependencies
2. Starts the container in interactive mode
3. Mounts your project directory and credentials
4. Opens a bash shell inside the container

---

### Step 4: Enable GCP APIs

Inside the Docker container, run the API enablement script:

```bash
python start_apis_GCP.py --project-id $GCP_PROJECT_ID
```

**APIs Enabled:**
- BigQuery API
- Cloud Storage API
- Pub/Sub API

---

### Step 5: Provision Infrastructure with Terraform

Navigate to the Terraform directory and deploy resources:

```bash
cd terraform
terraform init
terraform apply -auto-approve
```

**Expected Output:**
- 3 BigQuery datasets created (bronze_data, silver_data, gold_data)
- 1 GCS bucket created
- 1 Pub/Sub topic created (carts-events)

---

### Step 6: Execute Ingestion Scripts

Run the batch ingestion for static data:

```bash
python batch_ingestion.py \
  --project-id $GCP_PROJECT_ID \
  --bucket-name $GCS_BUCKET_NAME \
  --dataset-id bronze_data
```

**Expected Output:**
- Products and users data saved to GCS
- Raw tables created in BigQuery (products_raw, users_raw)

Start the near-real-time ingestion for streaming data:

```bash
python near_realtime_ingestion_2.py \
  --project-id $GCP_PROJECT_ID
```

**Expected Output:**
- Initial snapshot events published (cold start backfill)
- Continuous polling every 60 seconds
- Change events (created/modified/deleted) published to Pub/Sub

*Press Ctrl+C to stop the streaming process gracefully.*

---

### Step 7: Transform Data with dbt

Navigate to the dbt project directory and execute transformations:

```bash
cd ey_test_tech

# Install dbt dependencies (packages)
dbt deps

# Run all transformations (Bronze → Silver → Gold)
dbt build

# Execute data quality tests
dbt test

```

**Expected Output:**
- Silver layer tables created with cleaned data
- Gold layer star schema deployed (fact_cart_items, dim_products, dim_users, dim_dates)
- All data quality tests passed

---

## How to Obtain GCP Service Account Key

### Option 1: GCP Console (Web UI)

1. Navigate to [Google Cloud Console](https://console.cloud.google.com)
2. Select your project from the dropdown
3. Go to **IAM & Admin > Service Accounts**
4. Click **Create Service Account**:
   - **Name**: `data-pipeline-sa`
   - **Description**: Service account for data engineering pipeline
5. Click **Create and Continue**
6. Grant the following roles:
   - BigQuery Admin
   - Storage Admin
   - Pub/Sub Admin
7. Click **Continue > Done**
8. Click on the newly created service account
9. Go to **Keys** tab > **Add Key > Create New Key**
10. Select **JSON** format and click **Create**
11. Save the downloaded file as `gcp-key.json` in the `credentials/` directory

### Option 2: gcloud CLI

```bash
# Set your project ID
export PROJECT_ID="your-project-id"

# Create service account
gcloud iam service-accounts create data-pipeline-sa \
  --display-name="Data Pipeline Service Account" \
  --project=$PROJECT_ID

# Grant required roles
for ROLE in roles/bigquery.admin roles/storage.admin roles/pubsub.admin; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:data-pipeline-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="$ROLE"
done

# Create and download key
gcloud iam service-accounts keys create credentials/gcp-key.json \
  --iam-account=data-pipeline-sa@$PROJECT_ID.iam.gserviceaccount.com
```

---



## Monitoring & Observability

- **BigQuery Console**: Monitor table row counts and query execution
- **GCS Console**: Verify raw data uploads and partitioning
- **Pub/Sub Console**: Check message throughput and subscription lag
- **dbt Logs**: Review transformation results in `ey_test_tech/logs/`
- **Local Event Store**: Inspect `./events/` directory for published messages

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Docker build fails | Ensure Docker Desktop is running and has sufficient resources (4GB+ RAM) |
| GCP authentication error | Verify `gcp-key.json` exists in `credentials/` and has correct permissions |
| Terraform apply fails | Run `gcloud auth application-default login` and ensure APIs are enabled |
| dbt connection error | Check `profiles.yml` references correct project ID and dataset names |
| Pub/Sub publish timeout | Verify service account has `roles/pubsub.publisher` permission |
