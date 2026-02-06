#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real-time Cart Ingestion Script (Production Grade)
Polls Fake Store API, detects changes (Create/Update/Delete), publishes events to Pub/Sub.
Features:
- Cold Start Backfill (Snapshot)
- Idempotent Event Generation
- Deletion Detection
- Graceful Shutdown & Error Handling
"""

import json
import time
import signal
import threading
import hashlib
import uuid
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Set

# HTTP requests
import requests

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
# PUB/SUB IMPORTS
# =============================================================================

PUBSUB_AVAILABLE = False
PUBSUB_IMPORT_ERROR = None

try:
    from google.cloud import pubsub_v1
    from google.api_core.exceptions import GoogleAPIError
    
    try:
        from google.api_core.exceptions import DeadlineExceeded as GoogleTimeoutError
    except ImportError:
        GoogleTimeoutError = TimeoutError
    
    PUBSUB_AVAILABLE = True
    
except ImportError as e:
    PUBSUB_AVAILABLE = False
    PUBSUB_IMPORT_ERROR = f"ImportError: {str(e)}"
    
except Exception as e:
    PUBSUB_AVAILABLE = False
    PUBSUB_IMPORT_ERROR = f"{type(e).__name__}: {str(e)}"

# =============================================================================
# GLOBAL CONFIGURATION
# =============================================================================

API_URL = "https://fakestoreapi.com/carts"
POLL_INTERVAL = 60  # seconds
MAX_RETRIES = 3
INITIAL_BACKOFF = 2  # seconds
MAX_PUBLISH_RETRIES = 3

STATE_FILE = Path("./state/carts_state.json")
EVENTS_DIR = Path("./events")
DEAD_LETTER_DIR = Path("./dead_letter")

EVENT_SCHEMA_VERSION = "1.0"
SOURCE_NAME = "fake-store-api"

stop_event = threading.Event()

# =============================================================================
# STEP 1: API POLLING
# =============================================================================

def fetch_carts_from_api() -> Optional[List[dict]]:
    """
    Fetch carts from Fake Store API with retry logic.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Fetching carts from API (attempt {attempt}/{MAX_RETRIES})")
            
            response = requests.get(API_URL, timeout=30)
            response.raise_for_status()
            
            carts = response.json()
            logger.info(f"Successfully fetched {len(carts)} carts")
            
            return carts
            
        except requests.exceptions.RequestException as e:
            backoff_time = INITIAL_BACKOFF * (2 ** (attempt - 1))
            logger.warning(f"API error: {e} (attempt {attempt}/{MAX_RETRIES})")
            
            if attempt < MAX_RETRIES:
                logger.warning(f"Waiting {backoff_time}s before retry")
                time.sleep(backoff_time)
            else:
                logger.error("Max retries reached, skipping this poll")
                return None


# =============================================================================
# STEP 2: STATE MANAGEMENT & CHANGE DETECTION
# =============================================================================

def create_empty_state() -> dict:
    return {
        "carts": {},
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "last_update": None,
            "poll_count": 0,
            "run_id": None
        }
    }


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
            logger.info(f"State loaded: {len(state['carts'])} carts tracked")
            return state
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Corrupted state file: {e}")
            logger.warning("Creating new state")
            return create_empty_state()
    else:
        logger.warning("No state file found (cold start)")
        return create_empty_state()


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    state["metadata"]["last_update"] = datetime.now().isoformat()
    state["metadata"]["poll_count"] += 1
    
    temp_file = STATE_FILE.with_suffix('.json.tmp')
    
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        temp_file.replace(STATE_FILE)
        logger.info(f"State saved: {len(state['carts'])} carts tracked")
    except Exception as e:
        logger.error(f"Failed to save state: {e}")
        if temp_file.exists():
            temp_file.unlink()


def calculate_products_signature(products: List[dict]) -> str:
    sorted_products = sorted(products, key=lambda p: p["productId"])
    return json.dumps(sorted_products, sort_keys=True)


def products_have_changed(old_products: List[dict], new_products: List[dict]) -> bool:
    old_sig = calculate_products_signature(old_products)
    new_sig = calculate_products_signature(new_products)
    return old_sig != new_sig


def compare_and_detect_changes(state: dict, api_carts: List[dict]) -> dict:
    """
    Compare current state with API data to detect Created, Modified, and Deleted carts.
    """
    is_cold_start = (state["metadata"]["last_update"] is None)
    
    api_ids = set(str(c["id"]) for c in api_carts)
    state_ids = set(state["carts"].keys())
    
    new_carts = []
    modified_carts = []
    deleted_carts = []
    unchanged_carts = []

    # --- 1. COLD START STRATEGY: SNAPSHOT ---
    if is_cold_start:
        logger.info(">>> COLD START DETECTED: Initializing Snapshot/Backfill strategy")
        logger.info("All existing carts will be treated as 'cart_created' events.")
        
        for cart in api_carts:
            cart_id = str(cart["id"])
            # Update State
            state["carts"][cart_id] = {
                "date": cart["date"],
                "userId": cart["userId"],
                "products": cart.get("products", [])
            }
            # Treat as NEW for event generation
            new_carts.append(cart)
        
        logger.info(f"Snapshot prepared: {len(new_carts)} carts to ingest")
        
        return {
            "new": new_carts,
            "modified": [],
            "deleted": [],
            "unchanged": [],
            "is_cold_start": True
        }
    
    # --- 2. DELETION DETECTION (State - API) ---
    missing_ids = state_ids - api_ids
    
    for cart_id in missing_ids:
        logger.info(f"Deleted cart detected: id={cart_id}")
        
        # Retrieve last known data to enrich the deletion event
        last_known_data = state["carts"][cart_id]
        
        deleted_cart_obj = {
            "id": cart_id,
            "userId": last_known_data["userId"],
            "date": datetime.now().isoformat(), # Timestamp of deletion detection
            "products": last_known_data["products"]
        }
        deleted_carts.append(deleted_cart_obj)
        
        # Remove from state
        del state["carts"][cart_id]

    # --- 3. NORMAL UPSERT LOGIC (API - State) ---
    for cart in api_carts:
        cart_id = str(cart["id"])
        cart_date = cart["date"]
        cart_products = cart.get("products", [])
        
        if cart_id not in state["carts"]:
            # New cart
            logger.info(f"New cart detected: id={cart_id}")
            new_carts.append(cart)
            
            state["carts"][cart_id] = {
                "date": cart_date,
                "userId": cart["userId"],
                "products": cart_products
            }
        else:
            # Check for changes
            old_state = state["carts"][cart_id]
            old_date = old_state["date"]
            old_products = old_state.get("products", [])
            
            date_changed = (old_date != cart_date)
            products_changed = products_have_changed(old_products, cart_products)
            
            if date_changed or products_changed:
                logger.info(f"Modified cart detected: id={cart_id}")
                modified_carts.append(cart)
                
                state["carts"][cart_id]["date"] = cart_date
                state["carts"][cart_id]["products"] = cart_products
            else:
                unchanged_carts.append(cart)
    
    logger.info(
        f"Analysis: {len(new_carts)} new | "
        f"{len(modified_carts)} modified | "
        f"{len(deleted_carts)} deleted | "
        f"{len(unchanged_carts)} unchanged"
    )
    
    return {
        "new": new_carts,
        "modified": modified_carts,
        "deleted": deleted_carts,
        "unchanged": unchanged_carts,
        "is_cold_start": False
    }


# =============================================================================
# STEP 3: EVENT GENERATION
# =============================================================================

def generate_event_id(cart: dict) -> str:
    """
    Generate deterministic unique event ID based on content.
    Crucial for Idempotency: Same content = Same ID.
    """
    cart_id = str(cart["id"])
    cart_date = cart["date"]
    products_sig = calculate_products_signature(cart.get("products", []))
    
    # Create hash input
    hash_input = f"{cart_id}_{cart_date}_{products_sig}"
    
    # Generate MD5 hash (first 12 characters)
    event_hash = hashlib.md5(hash_input.encode('utf-8')).hexdigest()[:12]
    
    return f"cart_{cart_id}_{event_hash}"


def create_event(cart: dict, event_type: str, extracted_at: str, run_id: str) -> dict:
    event_id = generate_event_id(cart)
    published_at = datetime.now().isoformat() + "Z"
    
    event = {
        "event_id": event_id,
        "event_type": event_type,
        "event_schema_version": EVENT_SCHEMA_VERSION,
        "source": SOURCE_NAME,
        "extracted_at": extracted_at,
        "published_at": published_at,
        "run_id": run_id,
        "data": json.dumps({  
            "id": cart["id"],
            "userId": cart["userId"],
            "date": cart["date"],
            "products": cart.get("products", []),
            "__v": cart.get("__v", 0)
        })
    }
    
    return event


def save_event_locally(event: dict):
    event_date = event["published_at"][:10]
    date_dir = EVENTS_DIR / event_date
    date_dir.mkdir(parents=True, exist_ok=True)
    event_file = date_dir / f"{event['event_id']}.json"
    
    try:
        with open(event_file, 'w', encoding='utf-8') as f:
            json.dump(event, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save event locally: {e}")


def process_carts_and_generate_events(
    new_carts: List[dict],
    modified_carts: List[dict],
    deleted_carts: List[dict],
    extracted_at: str,
    run_id: str
) -> List[dict]:
    
    events = []
    
    logger.info("=" * 60)
    logger.info("EVENT GENERATION")
    logger.info("=" * 60)
    
    # Process new carts (includes Snapshot items)
    if new_carts:
        logger.info(f"Processing {len(new_carts)} NEW carts (Created)")
        for cart in new_carts:
            event = create_event(cart, "cart_created", extracted_at, run_id)
            save_event_locally(event)
            events.append(event)
    
    # Process modified carts
    if modified_carts:
        logger.info(f"Processing {len(modified_carts)} MODIFIED carts (Updated)")
        for cart in modified_carts:
            event = create_event(cart, "cart_modified", extracted_at, run_id)
            save_event_locally(event)
            events.append(event)
            
    # Process deleted carts
    if deleted_carts:
        logger.info(f"Processing {len(deleted_carts)} DELETED carts (Removed)")
        for cart in deleted_carts:
            event = create_event(cart, "cart_deleted", extracted_at, run_id)
            save_event_locally(event)
            events.append(event)
    
    logger.info(f"Total events generated: {len(events)}")
    logger.info("=" * 60)
    
    return events


# =============================================================================
# STEP 4: PUB/SUB PUBLISHING
# =============================================================================

def init_pubsub_publisher(
    project_id: str,
    topic_name: str,
    local_mode: bool = False
) -> Optional[Tuple]:
    if local_mode:
        logger.warning("LOCAL MODE - Pub/Sub disabled (--local-mode flag)")
        return None
    
    if not PUBSUB_AVAILABLE:
        logger.error("Failed to import google-cloud-pubsub")
        return None

    try:
        logger.info("Initializing Pub/Sub publisher (ADC)...")
        publisher = pubsub_v1.PublisherClient(
            publisher_options=pubsub_v1.types.PublisherOptions(
                enable_message_ordering=True
            )
        )
        topic_path = publisher.topic_path(project_id, topic_name)
        
        logger.info(f"Pub/Sub initialized. Target: {topic_path}")
        return (publisher, topic_path)
    
    except Exception as e:
        logger.error(f"Failed to initialize Pub/Sub: {e}")
        return None


def publish_event_to_pubsub(
    publisher,
    topic_path: str,
    event: dict,
    retry_count: int = 0
) -> bool:
    event_id = event["event_id"]
    
    try:
        data_obj = json.loads(event["data"])
        cart_id = str(data_obj["id"])
    except Exception:
        cart_id = event_id
    
    try:
        data = json.dumps(event, ensure_ascii=False).encode('utf-8')
        attributes = {
            "event_id": event_id,
            "event_type": event["event_type"],
            "source": event["source"],
            "cart_id": cart_id
        }
        
        future = publisher.publish(
            topic_path,
            data=data,
            ordering_key=f"cart_{cart_id}",
            **attributes
        )
        future.result(timeout=10)
        logger.info(f"Published: {event_id}")
        return True
    
    except (GoogleAPIError, GoogleTimeoutError, Exception) as e:
        retry_count += 1
        if retry_count <= MAX_PUBLISH_RETRIES:
            time.sleep(2 ** retry_count)
            return publish_event_to_pubsub(publisher, topic_path, event, retry_count)
        else:
            logger.error(f"Failed to publish {event_id}: {e}")
            return False


def save_to_dead_letter(event: dict):
    DEAD_LETTER_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{event['event_id']}_{timestamp}.json"
    filepath = DEAD_LETTER_DIR / filename
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(event, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def publish_events(publisher_config: Optional[Tuple], events: List[dict]) -> dict:
    if not events:
        return {"success": 0, "failed": 0, "dead_letter": 0}
    
    if publisher_config is None:
        logger.info(f"LOCAL MODE: {len(events)} events saved locally (not published)")
        return {"success": len(events), "failed": 0, "dead_letter": 0}
    
    publisher, topic_path = publisher_config
    
    logger.info(f"PUBLISHING {len(events)} EVENTS TO PUB/SUB")
    
    stats = {"success": 0, "failed": 0, "dead_letter": 0}
    
    for event in events:
        if publish_event_to_pubsub(publisher, topic_path, event):
            stats["success"] += 1
        else:
            stats["failed"] += 1
            save_to_dead_letter(event)
            stats["dead_letter"] += 1
            
    return stats


# =============================================================================
# MAIN POLLING LOOP
# =============================================================================

def polling_loop(publisher_config: Optional[Tuple]):
    run_id = str(uuid.uuid4())[:8]
    state = load_state()
    state["metadata"]["run_id"] = run_id
    
    mode = "PUB/SUB" if publisher_config else "LOCAL"
    
    logger.info("=" * 60)
    logger.info(f"REAL-TIME INGESTION STARTED | Run ID: {run_id} | Mode: {mode}")
    logger.info("=" * 60)
    
    poll_count = 0
    
    while not stop_event.is_set():
        poll_count += 1
        extracted_at = datetime.now().isoformat() + "Z"
        
        logger.info(f"\nPoll #{poll_count} - Fetching API...")
        
        carts = fetch_carts_from_api()
        if carts is None:
            if not stop_event.is_set():
                stop_event.wait(POLL_INTERVAL)
            continue
        
        # STEP 2: State comparison (Handles Snapshot & Deletions)
        changes = compare_and_detect_changes(state, carts)
        
        carts_to_process = changes["new"] + changes["modified"] + changes["deleted"]
        
        if len(carts_to_process) > 0:
            if changes["is_cold_start"]:
                logger.info(">>> BACKFILL: Processing initial snapshot events...")
            
            # STEP 3: Generate events
            events = process_carts_and_generate_events(
                changes["new"],
                changes["modified"],
                changes["deleted"],
                extracted_at,
                run_id
            )
            
            # STEP 4: Publish
            stats = publish_events(publisher_config, events)
            logger.info(f"Batch Result: {stats['success']} published / {stats['failed']} failed")
        else:
            logger.info("No changes detected.")
        
        # STEP 5: Save state
        save_state(state)
        
        if not stop_event.is_set():
            logger.info(f"Sleeping {POLL_INTERVAL}s...")
            stop_event.wait(POLL_INTERVAL)
    
    logger.info("\nSTOPPED GRACEFULLY")


def signal_handler(sig, frame):
    logger.info("Interrupt signal received. Stopping...")
    stop_event.set()


def main():
    parser = argparse.ArgumentParser(description='Real-time cart ingestion to Pub/Sub')
    parser.add_argument('--project-id', help='GCP Project ID')
    parser.add_argument('--topic-name', default='carts-events', help='Pub/Sub topic name')
    parser.add_argument('--local-mode', action='store_true', help='Run in local mode')
    parser.add_argument('--poll-interval', type=int, default=60, help='Polling interval (sec)')
    
    args = parser.parse_args()
    
    global POLL_INTERVAL
    POLL_INTERVAL = args.poll_interval
    
    if not args.local_mode and not args.project_id:
        logger.error("--project-id is required for Pub/Sub mode")
        exit(1)
    
    publisher_config = None
    if not args.local_mode:
        publisher_config = init_pubsub_publisher(args.project_id, args.topic_name)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        polling_loop(publisher_config)
    except KeyboardInterrupt:
        stop_event.set()


if __name__ == '__main__':
    main()