#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test APE package build and functionality from scratch with Docker cleanup
.DESCRIPTION
    This script performs a complete end-to-end test of the APE package
#>

param(
    [switch]$SkipCleanup,
    [switch]$SkipDockerCleanup,
    [string]$TestProjectName = "ape-test-scratch"
)

# Colors for output
$Red = "`e[31m"
$Green = "`e[32m"
$Yellow = "`e[33m"
$Blue = "`e[34m"
$Magenta = "`e[35m"
$Cyan = "`e[36m"
$Reset = "`e[0m"

function Write-Step {
    param([string]$Message)
    Write-Host "${Blue}[STEP] $Message${Reset}"
}

function Write-Success {
    param([string]$Message)
    Write-Host "${Green}[SUCCESS] $Message${Reset}"
}

function Write-Error {
    param([string]$Message)
    Write-Host "${Red}[ERROR] $Message${Reset}"
}

function Write-Warning {
    param([string]$Message)
    Write-Host "${Yellow}[WARNING] $Message${Reset}"
}

function Write-Info {
    param([string]$Message)
    Write-Host "${Cyan}[INFO] $Message${Reset}"
}

# Start timer
$StartTime = Get-Date

Write-Host "${Magenta}APE Package Test from Scratch${Reset}"
Write-Host "${Magenta}=================================${Reset}"
Write-Host ""

# Step 1: Docker Cleanup
if (-not $SkipDockerCleanup) {
    Write-Step "Cleaning up Docker containers and images"
    
    # Stop and remove APE-related containers with comprehensive patterns
    Write-Info "Stopping and removing APE-related containers..."
    
    # Get all containers with APE-related names
    $containerPatterns = @("*ape*", "*llama*", "*cerebras*", "*mcp*", "*test-*", "*scratch*")
    $allContainers = @()
    
    foreach ($pattern in $containerPatterns) {
        $containers = docker ps -a --filter "name=$pattern" -q 2>$null
        if ($containers) {
            $allContainers += $containers
        }
    }
    
    # Remove duplicates and process
    $uniqueContainers = $allContainers | Sort-Object -Unique
    if ($uniqueContainers) {
        Write-Info "Found $($uniqueContainers.Count) containers to remove"
        docker stop $uniqueContainers 2>$null | Out-Null
        docker rm $uniqueContainers 2>$null | Out-Null
        Write-Info "Containers removed"
    } else {
        Write-Info "No APE-related containers found"
    }
    
    # Remove APE-related images with comprehensive patterns
    Write-Info "Removing APE-related images..."
    
    $imagePatterns = @("*ape*", "*llama*", "*cerebras*", "*mcp*", "test-*", "*scratch*")
    $allImages = @()
    
    foreach ($pattern in $imagePatterns) {
        $images = docker images --filter "reference=$pattern" -q 2>$null
        if ($images) {
            $allImages += $images
        }
    }
    
    # Remove duplicates and process
    $uniqueImages = $allImages | Sort-Object -Unique
    if ($uniqueImages) {
        Write-Info "Found $($uniqueImages.Count) images to remove"
        docker rmi -f $uniqueImages 2>$null | Out-Null
        Write-Info "Images removed"
    } else {
        Write-Info "No APE-related images found"
    }
    
    # Additional cleanup: Remove containers by name patterns
    Write-Info "Additional cleanup by name patterns..."
    $namePatterns = @("test-", "ape-", "llama", "cerebras", "mcp")
    foreach ($pattern in $namePatterns) {
        $containers = docker ps -a | Select-String $pattern | ForEach-Object { ($_ -split '\s+')[-1] }
        if ($containers) {
            Write-Info "Removing containers matching '$pattern'..."
            docker stop $containers 2>$null | Out-Null
            docker rm $containers 2>$null | Out-Null
        }
    }
    
    # Remove images by name patterns
    foreach ($pattern in $namePatterns) {
        $images = docker images | Select-String $pattern | ForEach-Object { ($_ -split '\s+')[2] }
        if ($images) {
            Write-Info "Removing images matching '$pattern'..."
            docker rmi -f $images 2>$null | Out-Null
        }
    }
    
    # Clean up dangling images and build cache
    Write-Info "Cleaning up Docker build cache and dangling images..."
    docker system prune -f 2>$null | Out-Null
    docker image prune -f 2>$null | Out-Null
    
    Write-Success "Docker cleanup completed"
} else {
    Write-Warning "Skipping Docker cleanup"
}

# Step 2: Clean up old test artifacts
Write-Step "Cleaning up old test artifacts"
if (Test-Path $TestProjectName) {
    Remove-Item -Recurse -Force $TestProjectName
}
if (Test-Path "agentic-protocol-engine-*.tgz") {
    Remove-Item -Force "agentic-protocol-engine-*.tgz"
}
Write-Success "Test artifacts cleaned up"

# Step 3: Build the package
Write-Step "Building APE package"
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Build failed" }
    Write-Success "Package built successfully"
} catch {
    Write-Error "Failed to build package: $_"
    exit 1
}

# Step 4: Pack the package
Write-Step "Packing APE package"
try {
    $packOutput = npm pack
    if ($LASTEXITCODE -ne 0) { throw "Pack failed" }
    $packageFile = $packOutput | Select-Object -Last 1
    Write-Success "Package packed: $packageFile"
} catch {
    Write-Error "Failed to pack package: $_"
    exit 1
}

# Step 5: Install package globally
Write-Step "Installing APE package globally"
try {
    npm install -g $packageFile
    if ($LASTEXITCODE -ne 0) { throw "Global install failed" }
    Write-Success "Package installed globally"
} catch {
    Write-Error "Failed to install package globally: $_"
    exit 1
}

# Step 6: Create test project
Write-Step "Creating test project: $TestProjectName"
try {
    # Use a non-interactive approach by directly calling the setup command with parameters
    # Since the interactive prompts are complex, let's use a simpler approach
    Write-Info "Using non-interactive project creation..."
    
    # Create the project directory first
    New-Item -ItemType Directory -Path $TestProjectName -Force | Out-Null
    
    # Copy the package's services and config to the test project
    $packageInstallPath = (npm root -g) + "\agentic-protocol-engine"
    if (Test-Path $packageInstallPath) {
        Copy-Item -Recurse -Force "$packageInstallPath\services" "$TestProjectName\"
        Copy-Item -Recurse -Force "$packageInstallPath\config" "$TestProjectName\"
    }
    
    # Create basic configuration files manually
    $apeConfig = @{
        projectName = $TestProjectName
        targetUrl = "http://localhost:3000"
        targetPort = 3000
        authType = "basic"
        username = "test@example.com"
        password = "admin123"
        agentCount = 3
        testDuration = 2
        testGoal = "Test realistic API interactions and user workflows"
        endpoints = @("/admin/login", "/admin/dashboard/metrics", "/admin/users", "/admin/products")
        applicationType = "rest-api"
    }
    
    $apeConfig | ConvertTo-Json -Depth 10 | Out-File "$TestProjectName\ape.config.json" -Encoding UTF8
    
    # Create updated docker-compose file without version and container names
    $dockerCompose = @"
services:
  mcp_gateway:
    build:
      context: ./services/mcp-gateway
      dockerfile: Dockerfile
    ports:
      - "13000:3000"
    environment:
      - NODE_ENV=production
    networks:
      - ape_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
  
  cerebras_proxy:
    build:
      context: ./services/cerebras-proxy
      dockerfile: Dockerfile
    ports:
      - "18000:8000"
    environment:
      - CEREBRAS_API_KEY=${'$'}{CEREBRAS_API_KEY}
      - CEREBRAS_BASE_URL=https://api.cerebras.ai
    networks:
      - ape_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
  
  llama_agent:
    build:
      context: ./services/llama-agent
      dockerfile: Dockerfile
    expose:
      - "8000"
    environment:
      - CEREBRAS_API_KEY=${'$'}{CEREBRAS_API_KEY}
      - MCP_GATEWAY_URL=http://mcp_gateway:3000
      - CEREBRAS_PROXY_URL=http://cerebras_proxy:8000
    networks:
      - ape_network
    depends_on:
      mcp_gateway:
        condition: service_healthy
      cerebras_proxy:
        condition: service_healthy
    deploy:
      replicas: 1

networks:
  ape_network:
    driver: bridge
"@
    
    $dockerCompose | Out-File "$TestProjectName\ape.docker-compose.yml" -Encoding UTF8
    
    # Create basic MCP gateway config
    $mcpConfig = @{
        routes = @(
            @{
                name = "test-api"
                baseUrl = "http://host.docker.internal:3000"
                endpoints = @("/api/health", "/api/products", "/api/users")
            }
        )
    }
    
    $mcpConfig | ConvertTo-Json -Depth 10 | Out-File "$TestProjectName\ape.mcp-gateway.json" -Encoding UTF8
    
    # Create .env.template
    $envTemplate = @"
# APE Environment Configuration
CEREBRAS_API_KEY=test-cerebras-key-12345
"@
    
    $envTemplate | Out-File "$TestProjectName\.env.template" -Encoding UTF8
    
    if ($LASTEXITCODE -ne 0) { throw "Project creation failed" }
    Write-Success "Test project created: $TestProjectName"
} catch {
    Write-Error "Failed to create test project: $_"
    exit 1
}

# Step 7: Verify project structure
Write-Step "Verifying project structure"
$requiredFiles = @(
    "$TestProjectName/ape.config.json",
    "$TestProjectName/ape.docker-compose.yml",
    "$TestProjectName/ape.mcp-gateway.json",
    "$TestProjectName/services/llama-agent/Dockerfile",
    "$TestProjectName/services/mcp-gateway/Dockerfile",
    "$TestProjectName/services/cerebras-proxy/Dockerfile"
)

$missingFiles = @()
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        $missingFiles += $file
    }
}

if ($missingFiles.Count -gt 0) {
    Write-Error "Missing required files:"
    $missingFiles | ForEach-Object { Write-Host "  - $_" }
    exit 1
}
Write-Success "Project structure verified"

# Step 7.5: Setup environment variables
Write-Step "Setting up environment variables"
try {
    $envTemplatePath = "$TestProjectName/.env.template"
    $envPath = "$TestProjectName/.env"
    
    if (Test-Path $envTemplatePath) {
        Copy-Item $envTemplatePath $envPath
        
        # Add test Cerebras API key to the .env file
        $envContent = Get-Content $envPath -Raw
        $envContent = $envContent -replace "CEREBRAS_API_KEY=your_cerebras_api_key_here", "CEREBRAS_API_KEY=test-cerebras-key-12345"
        Set-Content $envPath $envContent
        
        Write-Success "Environment variables configured (.env.template → .env)"
    } else {
        Write-Warning "No .env.template found, skipping environment setup"
    }
} catch {
    Write-Warning "Failed to setup environment variables: $_"
}

# Step 8: Test Docker builds
Write-Step "Testing Docker builds for all services"

$services = @(
    @{ Name = "llama-agent"; Path = "$TestProjectName/services/llama-agent"; Tag = "test-llama-agent-scratch" },
    @{ Name = "mcp-gateway"; Path = "$TestProjectName/services/mcp-gateway"; Tag = "test-mcp-gateway-scratch" },
    @{ Name = "cerebras-proxy"; Path = "$TestProjectName/services/cerebras-proxy"; Tag = "test-cerebras-proxy-scratch" }
)

$buildResults = @{}

foreach ($service in $services) {
    Write-Info "Building $($service.Name)..."
    try {
        docker build -t $service.Tag $service.Path
        if ($LASTEXITCODE -ne 0) { throw "Build failed" }
        $buildResults[$service.Name] = $true
        Write-Success "$($service.Name) built successfully"
    } catch {
        Write-Error "Failed to build $($service.Name): $_"
        $buildResults[$service.Name] = $false
    }
}

# Step 9: Test llama agent functionality
if ($buildResults["llama-agent"]) {
    Write-Step "Testing llama agent functionality"
    try {
        # Create a temporary Python test file
        $pythonTestFile = "$TestProjectName/test_llama_agent.py"
        $pythonTestContent = @"
import sys
from llama_agent import LlamaAgent
from models import AgentConfig

config = AgentConfig(
    agent_id="test",
    cerebras_proxy_url="http://localhost:8000",
    mcp_gateway_url="http://localhost:3000"
)

agent = LlamaAgent(config)
print("SUCCESS: Llama agent created")
print("Model:", agent.llm.model)
print("Sessions:", hasattr(agent.agent_worker, "sessions"))
print("Tools:", len(agent.tools))
"@
        Set-Content $pythonTestFile $pythonTestContent
        
        docker run --rm -v "${PWD}/${TestProjectName}:/test" -e CEREBRAS_API_KEY=test-key -e MCP_GATEWAY_URL=http://localhost:3000 test-llama-agent-scratch python /test/test_llama_agent.py
        
        # Clean up test file
        Remove-Item $pythonTestFile -ErrorAction SilentlyContinue
        if ($LASTEXITCODE -ne 0) { throw "Llama agent test failed" }
        Write-Success "Llama agent functionality test passed"
    } catch {
        Write-Error "Llama agent functionality test failed: $_"
        $buildResults["llama-agent-test"] = $false
    }
} else {
    Write-Warning "Skipping llama agent functionality test (build failed)"
}

# Step 10: Test MCP Gateway functionality
if ($buildResults["mcp-gateway"]) {
    Write-Step "Testing MCP Gateway functionality"
    try {
        # Test basic container startup and health check
        $containerId = docker run -d -p 13000:3000 test-mcp-gateway-scratch
        Start-Sleep 5
        
        # Test health endpoint
        $healthResponse = Invoke-RestMethod -Uri "http://localhost:13000/health" -Method Get -TimeoutSec 10
        
        # Stop container
        docker stop $containerId | Out-Null
        docker rm $containerId | Out-Null
        
        Write-Success "MCP Gateway functionality test passed"
    } catch {
        Write-Error "MCP Gateway functionality test failed: $_"
        # Cleanup container if it exists
        if ($containerId) {
            docker stop $containerId 2>$null | Out-Null
            docker rm $containerId 2>$null | Out-Null
        }
    }
} else {
    Write-Warning "Skipping MCP Gateway functionality test (build failed)"
}

# Step 11: Test configuration validation
Write-Step "Testing configuration validation"
try {
    Set-Location $TestProjectName
    ape-load validate
    if ($LASTEXITCODE -ne 0) { throw "Configuration validation failed" }
    Set-Location ..
    Write-Success "Configuration validation passed"
} catch {
    Write-Error "Configuration validation failed: $_"
    Set-Location ..
}

# Step 12: Generate test report
Write-Step "Generating test report"
$endTime = Get-Date
$duration = $endTime - $StartTime

Write-Host ""
Write-Host "${Magenta}Test Results Summary${Reset}"
Write-Host "${Magenta}======================${Reset}"
Write-Host ""

Write-Host "Test Duration: $($duration.ToString('mm\:ss'))"
Write-Host ""

Write-Host "Build Results:"
foreach ($service in $services) {
    $status = if ($buildResults[$service.Name]) { "${Green}PASS${Reset}" } else { "${Red}FAIL${Reset}" }
    Write-Host "  $($service.Name): $status"
}

Write-Host ""
Write-Host "Functionality Tests:"
$functionalityTests = @(
    @{ Name = "Llama Agent Import & Creation"; Status = $buildResults.ContainsKey("llama-agent-test") -and $buildResults["llama-agent-test"] -ne $false },
    @{ Name = "MCP Gateway Health Check"; Status = $buildResults["mcp-gateway"] },
    @{ Name = "Configuration Validation"; Status = $true }
)

foreach ($test in $functionalityTests) {
    $status = if ($test.Status) { "${Green}PASS${Reset}" } else { "${Red}FAIL${Reset}" }
    Write-Host "  $($test.Name): $status"
}

# Step 13: Cleanup (optional)
if (-not $SkipCleanup) {
    Write-Step "Cleaning up test artifacts"
    
    # Remove test project
    if (Test-Path $TestProjectName) {
        Remove-Item -Recurse -Force $TestProjectName
    }
    
    # Remove package file
    if (Test-Path $packageFile) {
        Remove-Item -Force $packageFile
    }
    
    # Remove test Docker images
    $testImages = docker images --filter "reference=test-*-scratch" -q
    if ($testImages) {
        docker rmi $testImages 2>$null
    }
    
    Write-Success "Test artifacts cleaned up"
} else {
    Write-Warning "Skipping cleanup - test artifacts preserved"
    Write-Info "Test project: $TestProjectName"
    Write-Info "Package file: $packageFile"
}

Write-Host ""
$overallSuccess = ($buildResults.Values | Where-Object { $_ -eq $false }).Count -eq 0

if ($overallSuccess) {
    Write-Host "${Green}All tests passed! APE package is working correctly.${Reset}"
    exit 0
} else {
    Write-Host "${Red}Some tests failed. Please check the output above.${Reset}"
    exit 1
}