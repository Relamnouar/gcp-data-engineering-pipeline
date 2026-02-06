# =============================================================================
# DATA ENGINEERING PIPELINE - MAKEFILE
# =============================================================================
# This Makefile orchestrates the Docker environment for Linux and macOS users.
# It ensures a reproducible execution environment for Terraform, Python, and dbt.
# =============================================================================

.PHONY: help check-docker start shell stop run clean

# Configuration
# Must match the service name in docker-compose.yml
CONTAINER_SERVICE = data-pipeline

# -----------------------------------------------------------------------------
# Default Target
# -----------------------------------------------------------------------------
help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  run         Full sequence: Start environment, enter shell, stop on exit."
	@echo "  start       Build and start the container in background mode."
	@echo "  shell       Enter the running container (bash)."
	@echo "  stop        Stop and remove containers."
	@echo "  clean       Stop containers and remove local artifacts (terraform state, etc)."

# -----------------------------------------------------------------------------
# System Checks
# -----------------------------------------------------------------------------
check-docker:
	@docker info > /dev/null 2>&1 || (echo "ERROR: Docker is not running. Please start Docker Desktop and try again."; exit 1)

# -----------------------------------------------------------------------------
# Lifecycle Management
# -----------------------------------------------------------------------------
start: check-docker
	@echo "[INFO] Cleaning up existing processes..."
	@docker-compose down --remove-orphans > /dev/null 2>&1
	
	@echo "[INFO] Building and starting the environment..."
	@docker-compose up -d --build
	
	@echo "[INFO] Verifying container status..."
	@sleep 2
	@docker-compose ps --services --filter "status=running" | grep -q $(CONTAINER_SERVICE) || \
		(echo "CRITICAL ERROR: Container failed to start. Run 'docker-compose logs' for diagnostics."; exit 1)
	@echo "[SUCCESS] Environment is ready."

shell:
	@echo "[INFO] Connecting to the container..."
	@docker-compose exec $(CONTAINER_SERVICE) bash

stop:
	@echo "[INFO] Stopping environment..."
	@docker-compose down

# -----------------------------------------------------------------------------
# Main Entry Point (Equivalent to start_project.bat)
# -----------------------------------------------------------------------------
# 1. Starts the environment
# 2. Opens the shell
# 3. Automatically stops the environment when the user exits the shell
run: start shell stop

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------
clean: stop
	@echo "[INFO] Cleaning temporary files..."
	@rm -rf terraform/.terraform \
		terraform/*.tfstate \
		terraform/*.tfstate.backup \
		terraform/.terraform.lock.hcl \
		ey_test_tech/target \
		ey_test_tech/dbt_packages \
		ey_test_tech/logs
	@echo "[INFO] Cleanup complete."