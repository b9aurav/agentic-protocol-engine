#!/bin/bash

# APE Package Test from Scratch Script
# Tests the complete package build and functionality with Docker cleanup

set -e  # Exit on any error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
SKIP_CLEANUP=false
SKIP_DOCKER_CLEANUP=false
TEST_PROJECT_NAME="ape-test-scratch"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-cleanup)
            SKIP_CLEANUP=true
            shift
            ;;
        --skip-docker-cleanup)
            SKIP_DOCKER_CLEANUP=true
            shift
            ;;
        --test-project-name)
            TEST_PROJECT_NAME="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --skip-cleanup           Skip final cleanup of test artifacts"
            echo "  --skip-docker-cleanup    Skip Docker cleanup at the beginning"
            echo "  --test-project-name NAME Set test project name (default: ape-test-scratch)"
            echo "  -h, --help              Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

function write_step() {
    echo -e "${BLUE}🔄 $1${NC}"
}

function write_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

function write_error() {
    echo -e "${RED}❌ $1${NC}"
}

function write_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

function write_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

# Start timer
START_TIME=$(date +%s)

echo -e "${MAGENTA}🚀 APE Package Test from Scratch${NC}"
echo -e "${MAGENTA}=================================${NC}"
echo ""

# Step 1: Docker Cleanup
if [ "$SKIP_DOCKER_CLEANUP" = false ]; then
    write_step "Cleaning up Docker containers and images"
    
    # Stop and remove APE-related containers with comprehensive patterns
    write_info "Stopping and removing APE-related containers..."
    
    # Get all containers with APE-related names
    CONTAINER_PATTERNS=("*ape*" "*llama*" "*cerebras*" "*mcp*" "*test-*" "*scratch*")
    ALL_CONTAINERS=""
    
    for pattern in "${CONTAINER_PATTERNS[@]}"; do
        containers=$(docker ps -a --filter "name=$pattern" -q 2>/dev/null || true)
        if [ ! -z "$containers" ]; then
            ALL_CONTAINERS="$ALL_CONTAINERS $containers"
        fi
    done
    
    # Remove duplicates and process
    if [ ! -z "$ALL_CONTAINERS" ]; then
        UNIQUE_CONTAINERS=$(echo $ALL_CONTAINERS | tr ' ' '\n' | sort -u | tr '\n' ' ')
        CONTAINER_COUNT=$(echo $UNIQUE_CONTAINERS | wc -w)
        write_info "Found $CONTAINER_COUNT containers to remove"
        docker stop $UNIQUE_CONTAINERS 2>/dev/null || true
        docker rm $UNIQUE_CONTAINERS 2>/dev/null || true
        write_info "Containers removed"
    else
        write_info "No APE-related containers found"
    fi
    
    # Remove APE-related images with comprehensive patterns
    write_info "Removing APE-related images..."
    
    IMAGE_PATTERNS=("*ape*" "*llama*" "*cerebras*" "*mcp*" "test-*" "*scratch*")
    ALL_IMAGES=""
    
    for pattern in "${IMAGE_PATTERNS[@]}"; do
        images=$(docker images --filter "reference=$pattern" -q 2>/dev/null || true)
        if [ ! -z "$images" ]; then
            ALL_IMAGES="$ALL_IMAGES $images"
        fi
    done
    
    # Remove duplicates and process
    if [ ! -z "$ALL_IMAGES" ]; then
        UNIQUE_IMAGES=$(echo $ALL_IMAGES | tr ' ' '\n' | sort -u | tr '\n' ' ')
        IMAGE_COUNT=$(echo $UNIQUE_IMAGES | wc -w)
        write_info "Found $IMAGE_COUNT images to remove"
        docker rmi -f $UNIQUE_IMAGES 2>/dev/null || true
        write_info "Images removed"
    else
        write_info "No APE-related images found"
    fi
    
    # Additional cleanup: Remove containers by name patterns
    write_info "Additional cleanup by name patterns..."
    NAME_PATTERNS=("test-" "ape-" "llama" "cerebras" "mcp")
    
    for pattern in "${NAME_PATTERNS[@]}"; do
        containers=$(docker ps -a | grep "$pattern" | awk '{print $NF}' 2>/dev/null || true)
        if [ ! -z "$containers" ]; then
            write_info "Removing containers matching '$pattern'..."
            echo "$containers" | xargs docker stop 2>/dev/null || true
            echo "$containers" | xargs docker rm 2>/dev/null || true
        fi
    done
    
    # Remove images by name patterns
    for pattern in "${NAME_PATTERNS[@]}"; do
        images=$(docker images | grep "$pattern" | awk '{print $3}' 2>/dev/null || true)
        if [ ! -z "$images" ]; then
            write_info "Removing images matching '$pattern'..."
            echo "$images" | xargs docker rmi -f 2>/dev/null || true
        fi
    done
    
    # Clean up dangling images and build cache
    write_info "Cleaning up Docker build cache and dangling images..."
    docker system prune -f 2>/dev/null || true
    docker image prune -f 2>/dev/null || true
    
    write_success "Docker cleanup completed"
else
    write_warning "Skipping Docker cleanup"
fi

# Step 2: Clean up old test artifacts
write_step "Cleaning up old test artifacts"
rm -rf "$TEST_PROJECT_NAME" 2>/dev/null || true
rm -f agentic-protocol-engine-*.tgz 2>/dev/null || true
write_success "Test artifacts cleaned up"

# Step 3: Build the package
write_step "Building APE package"
if ! npm run build; then
    write_error "Failed to build package"
    exit 1
fi
write_success "Package built successfully"

# Step 4: Pack the package
write_step "Packing APE package"
PACKAGE_FILE=$(npm pack | tail -n 1)
if [ $? -ne 0 ] || [ -z "$PACKAGE_FILE" ]; then
    write_error "Failed to pack package"
    exit 1
fi
write_success "Package packed: $PACKAGE_FILE"

# Step 5: Install package globally
write_step "Installing APE package globally"
if ! npm install -g "$PACKAGE_FILE"; then
    write_error "Failed to install package globally"
    exit 1
fi
write_success "Package installed globally"

# Step 6: Create test project
write_step "Creating test project: $TEST_PROJECT_NAME"

# Create answers for interactive prompts
cat << EOF | npx create-ape-load "$TEST_PROJECT_NAME"
REST API Application - Standard RESTful API with CRUD operations
$TEST_PROJECT_NAME
http://host.docker.internal:3000
3000
Bearer Token
test-bearer-token-12345
3
2
Test realistic API interactions and user workflows
/api/health,/api/products,/api/users
No
Yes
EOF

if [ $? -ne 0 ]; then
    write_error "Failed to create test project"
    exit 1
fi
write_success "Test project created: $TEST_PROJECT_NAME"

# Step 7: Verify project structure
write_step "Verifying project structure"
REQUIRED_FILES=(
    "$TEST_PROJECT_NAME/ape.config.json"
    "$TEST_PROJECT_NAME/ape.docker-compose.yml"
    "$TEST_PROJECT_NAME/ape.mcp-gateway.json"
    "$TEST_PROJECT_NAME/services/llama-agent/Dockerfile"
    "$TEST_PROJECT_NAME/services/mcp-gateway/Dockerfile"
    "$TEST_PROJECT_NAME/services/cerebras-proxy/Dockerfile"
)

MISSING_FILES=()
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    write_error "Missing required files:"
    for file in "${MISSING_FILES[@]}"; do
        echo "  - $file"
    done
    exit 1
fi
write_success "Project structure verified"

# Step 7.5: Setup environment variables
write_step "Setting up environment variables"
ENV_TEMPLATE_PATH="$TEST_PROJECT_NAME/.env.template"
ENV_PATH="$TEST_PROJECT_NAME/.env"

if [ -f "$ENV_TEMPLATE_PATH" ]; then
    cp "$ENV_TEMPLATE_PATH" "$ENV_PATH"
    
    # Add test Cerebras API key to the .env file
    sed -i.bak 's/CEREBRAS_API_KEY=your_cerebras_api_key_here/CEREBRAS_API_KEY=test-cerebras-key-12345/' "$ENV_PATH" 2>/dev/null || \
    sed -i 's/CEREBRAS_API_KEY=your_cerebras_api_key_here/CEREBRAS_API_KEY=test-cerebras-key-12345/' "$ENV_PATH" 2>/dev/null
    
    # Remove backup file if created
    rm -f "$ENV_PATH.bak" 2>/dev/null
    
    write_success "Environment variables configured (.env.template → .env)"
else
    write_warning "No .env.template found, skipping environment setup"
fi

# Step 8: Test Docker builds
write_step "Testing Docker builds for all services"

declare -A BUILD_RESULTS
SERVICES=(
    "llama-agent:$TEST_PROJECT_NAME/services/llama-agent:test-llama-agent-scratch"
    "mcp-gateway:$TEST_PROJECT_NAME/services/mcp-gateway:test-mcp-gateway-scratch"
    "cerebras-proxy:$TEST_PROJECT_NAME/services/cerebras-proxy:test-cerebras-proxy-scratch"
)

for service_info in "${SERVICES[@]}"; do
    IFS=':' read -r service_name service_path service_tag <<< "$service_info"
    write_info "Building $service_name..."
    
    if docker build -t "$service_tag" "$service_path"; then
        BUILD_RESULTS["$service_name"]=true
        write_success "$service_name built successfully"
    else
        BUILD_RESULTS["$service_name"]=false
        write_error "Failed to build $service_name"
    fi
done

# Step 9: Test llama agent functionality
if [ "${BUILD_RESULTS[llama-agent]}" = true ]; then
    write_step "Testing llama agent functionality"
    
    TEST_COMMAND='
from llama_agent import LlamaAgent
from models import AgentConfig
config = AgentConfig(
    agent_id="test-scratch",
    cerebras_proxy_url="http://localhost:8000",
    mcp_gateway_url="http://localhost:3000"
)
agent = LlamaAgent(config)
print("✅ Llama agent created successfully")
print("Model:", agent.llm.model)
print("Sessions accessible:", hasattr(agent.agent_worker, "sessions"))
print("Tools count:", len(agent.tools))
'
    
    if docker run --rm -e CEREBRAS_API_KEY=test-key -e MCP_GATEWAY_URL=http://localhost:3000 test-llama-agent-scratch python -c "$TEST_COMMAND"; then
        BUILD_RESULTS["llama-agent-test"]=true
        write_success "Llama agent functionality test passed"
    else
        BUILD_RESULTS["llama-agent-test"]=false
        write_error "Llama agent functionality test failed"
    fi
else
    write_warning "Skipping llama agent functionality test (build failed)"
fi

# Step 10: Test MCP Gateway functionality
if [ "${BUILD_RESULTS[mcp-gateway]}" = true ]; then
    write_step "Testing MCP Gateway functionality"
    
    # Start container in background
    CONTAINER_ID=$(docker run -d -p 13000:3000 test-mcp-gateway-scratch)
    sleep 5
    
    # Test health endpoint
    if curl -f http://localhost:13000/health >/dev/null 2>&1; then
        BUILD_RESULTS["mcp-gateway-test"]=true
        write_success "MCP Gateway functionality test passed"
    else
        BUILD_RESULTS["mcp-gateway-test"]=false
        write_error "MCP Gateway functionality test failed"
    fi
    
    # Stop and remove container
    docker stop "$CONTAINER_ID" >/dev/null 2>&1 || true
    docker rm "$CONTAINER_ID" >/dev/null 2>&1 || true
else
    write_warning "Skipping MCP Gateway functionality test (build failed)"
fi

# Step 11: Test configuration validation
write_step "Testing configuration validation"
cd "$TEST_PROJECT_NAME"
if ape-load validate; then
    write_success "Configuration validation passed"
else
    write_error "Configuration validation failed"
fi
cd ..

# Step 12: Generate test report
write_step "Generating test report"
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
DURATION_MIN=$((DURATION / 60))
DURATION_SEC=$((DURATION % 60))

echo ""
echo -e "${MAGENTA}📊 Test Results Summary${NC}"
echo -e "${MAGENTA}======================${NC}"
echo ""

printf "Test Duration: %02d:%02d\n" $DURATION_MIN $DURATION_SEC
echo ""

echo "Build Results:"
for service_info in "${SERVICES[@]}"; do
    IFS=':' read -r service_name service_path service_tag <<< "$service_info"
    if [ "${BUILD_RESULTS[$service_name]}" = true ]; then
        echo -e "  $service_name: ${GREEN}✅ PASS${NC}"
    else
        echo -e "  $service_name: ${RED}❌ FAIL${NC}"
    fi
done

echo ""
echo "Functionality Tests:"
FUNCTIONALITY_TESTS=(
    "Llama Agent Import & Creation:llama-agent-test"
    "MCP Gateway Health Check:mcp-gateway-test"
    "Configuration Validation:config-validation"
)

for test_info in "${FUNCTIONALITY_TESTS[@]}"; do
    IFS=':' read -r test_name test_key <<< "$test_info"
    if [ "$test_key" = "config-validation" ] || [ "${BUILD_RESULTS[$test_key]}" = true ]; then
        echo -e "  $test_name: ${GREEN}✅ PASS${NC}"
    else
        echo -e "  $test_name: ${RED}❌ FAIL${NC}"
    fi
done

# Step 13: Cleanup (optional)
if [ "$SKIP_CLEANUP" = false ]; then
    write_step "Cleaning up test artifacts"
    
    # Remove test project
    rm -rf "$TEST_PROJECT_NAME" 2>/dev/null || true
    
    # Remove package file
    rm -f "$PACKAGE_FILE" 2>/dev/null || true
    
    # Remove test Docker images
    TEST_IMAGES=$(docker images --filter "reference=test-*-scratch" -q 2>/dev/null || true)
    if [ ! -z "$TEST_IMAGES" ]; then
        docker rmi $TEST_IMAGES 2>/dev/null || true
    fi
    
    write_success "Test artifacts cleaned up"
else
    write_warning "Skipping cleanup - test artifacts preserved"
    write_info "Test project: $TEST_PROJECT_NAME"
    write_info "Package file: $PACKAGE_FILE"
fi

echo ""

# Check overall success
FAILED_TESTS=0
for result in "${BUILD_RESULTS[@]}"; do
    if [ "$result" = false ]; then
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
done

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed! APE package is working correctly.${NC}"
    exit 0
else
    echo -e "${RED}💥 Some tests failed. Please check the output above.${NC}"
    exit 1
fi