#!/bin/bash
# Test script to verify Docker Compose setup
# Designed to run in CI/CD pipelines (e.g., GitHub Actions)

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo "==== Docker Compose Test Script ===="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed.${NC}"
    exit 1
fi

# Check if docker-compose.yml exists in current directory
if [ ! -f "docker-compose.yaml" ]; then
    echo -e "${RED}Error: docker-compose.yaml not found in current directory.${NC}"
    exit 1
fi

echo -e "${YELLOW}Starting Docker Compose...${NC}"
docker-compose down -v &> /dev/null # Clean up any existing containers
docker-compose up -d

# Wait for containers to start (adjust timeout as needed for your services)
echo -e "${YELLOW}Waiting for containers to initialize...${NC}"
sleep 10

# Get list of services from docker-compose.yml
SERVICES=$(docker-compose config --services)

# Check if all services are running
ALL_RUNNING=true
for SERVICE in $SERVICES; do
    STATUS=$(docker-compose ps -q $SERVICE)
    if [ -z "$STATUS" ]; then
        echo -e "${RED}❌ Service $SERVICE is not running${NC}"
        ALL_RUNNING=false
    else
        CONTAINER_STATUS=$(docker inspect --format='{{.State.Status}}' $STATUS)
        if [ "$CONTAINER_STATUS" != "running" ]; then
            echo -e "${RED}❌ Service $SERVICE is not running (status: $CONTAINER_STATUS)${NC}"
            ALL_RUNNING=false
        else
            echo -e "${GREEN}✓ Service $SERVICE is running${NC}"

            # Check logs for errors
            ERROR_LOGS=$(docker-compose logs $SERVICE | grep -i "error\|exception\|fatal" | wc -l)
            if [ $ERROR_LOGS -gt 0 ]; then
                echo -e "${YELLOW}  ⚠ Found $ERROR_LOGS potential errors in logs${NC}"
            else
                echo -e "${GREEN}  ✓ No errors found in logs${NC}"
            fi
        fi
    fi
done

# Cleanup - tear down containers after test
echo -e "${YELLOW}Cleaning up...${NC}"
docker-compose down

if [ "$ALL_RUNNING" = true ]; then
    echo -e "${GREEN}==== All services are running successfully! ====${NC}"
    exit 0
else
    echo -e "${RED}==== Some services failed to start properly. ====${NC}"
    exit 1
fi
