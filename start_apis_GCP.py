import os
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

def enable_required_apis():
    """Enable required GCP APIs for Terraform deployment."""

    # Verify service account key path
    key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not key_path or not os.path.exists(key_path):
        print(f"CRITICAL: Service account key not found at {key_path}")
        return

    print(f"Authenticating with service account key: {key_path}")

    # Load credentials with cloud platform scope
    scopes = ['https://www.googleapis.com/auth/cloud-platform']
    creds = service_account.Credentials.from_service_account_file(key_path, scopes=scopes)

    # Generate access token
    try:
        creds.refresh(Request())
        token = creds.token
        project_id = creds.project_id
    except Exception as e:
        print(f"AUTHENTICATION ERROR: {e}")
        print("Verify that your JSON key is valid and matches the project.")
        return

    print(f"Enabling APIs for project: {project_id}")

    # Required APIs for Terraform infrastructure
    apis = [
        "serviceusage.googleapis.com",          # Service Usage API
        "cloudresourcemanager.googleapis.com",  # Cloud Resource Manager API
        "iam.googleapis.com",                   # Identity and Access Management API
        "storage-component.googleapis.com",     # Cloud Storage API
        "bigquery.googleapis.com",              # BigQuery API
        "pubsub.googleapis.com"                 # Pub/Sub API
    ]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Enable each API
    for api in apis:
        url = f"https://serviceusage.googleapis.com/v1/projects/{project_id}/services/{api}:enable"
        print(f" -> Enabling {api}...")
        resp = requests.post(url, headers=headers)

        if resp.status_code < 400:
            print(f"    SUCCESS")
        else:
            if "ALREADY_EXISTS" in resp.text:
                print(f"    ALREADY ENABLED")
            else:
                print(f"    FAILED ({resp.status_code}): {resp.text}")

if __name__ == "__main__":
    enable_required_apis()