# APE Package Testing Scripts

This directory contains comprehensive testing scripts for the Agentic Protocol Engine (APE) package.

## Scripts Overview

### `test-package.js` (Recommended)
Cross-platform Node.js wrapper that automatically detects your operating system and runs the appropriate test script.

**Usage:**
```bash
node scripts/test-package.js [options]
```

### `test-package-from-scratch.ps1` (Windows)
PowerShell script for Windows systems with comprehensive Docker cleanup and testing.

**Usage:**
```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-package-from-scratch.ps1 [options]
```

### `test-package-from-scratch.sh` (Unix/Linux/macOS)
Bash script for Unix-like systems with the same functionality as the PowerShell version.

**Usage:**
```bash
bash scripts/test-package-from-scratch.sh [options]
```

## Available Options

All scripts support the following options:

- `--skip-cleanup` / `-SkipCleanup`: Skip final cleanup of test artifacts
- `--skip-docker-cleanup` / `-SkipDockerCleanup`: Skip Docker cleanup at the beginning
- `--test-project-name NAME` / `-TestProjectName NAME`: Set custom test project name (default: `ape-test-scratch`)
- `--help` / `-h`: Show help message

## What the Tests Do

The test scripts perform a comprehensive end-to-end validation:

### 1. **Environment Cleanup**
- Stops and removes APE-related Docker containers
- Removes APE-related Docker images
- Cleans up Docker build cache
- Removes old test artifacts

### 2. **Package Build & Installation**
- Builds the APE package from source
- Packs the package into a tarball
- Installs the package globally via npm

### 3. **Project Creation**
- Creates a test project using `npx create-ape-load`
- Uses automated responses for interactive prompts
- Verifies all required files are generated
- Sets up environment variables (copies `.env.template` to `.env`)
- Configures test Cerebras API key for testing

### 4. **Docker Build Tests**
- Builds Docker images for all three services:
  - Llama Agent
  - MCP Gateway
  - Cerebras Proxy
- Validates that all builds complete successfully

### 5. **Functionality Tests**
- **Llama Agent**: Tests import, initialization, and core functionality
- **MCP Gateway**: Tests container startup and health endpoint
- **Configuration**: Validates generated configuration files

### 6. **Environment Setup**
- Copies `.env.template` to `.env` in the test project
- Configures test Cerebras API key for container testing
- Ensures proper environment variable setup for services

### 7. **Reporting**
- Generates a comprehensive test report
- Shows build results for each service
- Reports functionality test results
- Displays total test duration

### 8. **Cleanup (Optional)**
- Removes test project directory
- Removes package tarball
- Removes test Docker images

## Example Usage

### Quick Test (Recommended)
```bash
# Run full test suite with automatic cleanup
node scripts/test-package.js
```

### Development Testing
```bash
# Run tests but keep artifacts for debugging
node scripts/test-package.js --skip-cleanup
```

### Custom Project Name
```bash
# Use a custom test project name
node scripts/test-package.js --test-project-name my-custom-test
```

### Skip Docker Cleanup
```bash
# Skip initial Docker cleanup (faster for repeated runs)
node scripts/test-package.js --skip-docker-cleanup
```

## Test Output

The scripts provide colored output with clear indicators:

- 🔄 **Blue**: Current step being executed
- ✅ **Green**: Successful completion
- ❌ **Red**: Errors or failures
- ⚠️ **Yellow**: Warnings
- ℹ️ **Cyan**: Informational messages

### Sample Output
```
🚀 APE Package Test from Scratch
=================================

🔄 Cleaning up Docker containers and images
ℹ️  Stopping APE-related containers...
ℹ️  Removing APE-related images...
✅ Docker cleanup completed

🔄 Building APE package
✅ Package built successfully

🔄 Packing APE package
✅ Package packed: agentic-protocol-engine-1.0.0.tgz

...

📊 Test Results Summary
======================

Test Duration: 02:34

Build Results:
  llama-agent: ✅ PASS
  mcp-gateway: ✅ PASS
  cerebras-proxy: ✅ PASS

Functionality Tests:
  Llama Agent Import & Creation: ✅ PASS
  MCP Gateway Health Check: ✅ PASS
  Configuration Validation: ✅ PASS

🎉 All tests passed! APE package is working correctly.
```

## Integration with CI/CD

These scripts are designed to be CI/CD friendly:

- Exit codes: `0` for success, `1` for failure
- Structured output for parsing
- Configurable cleanup behavior
- Cross-platform compatibility

### GitHub Actions Example
```yaml
- name: Test APE Package
  run: node scripts/test-package.js --skip-cleanup
```

### Docker-based CI Example
```yaml
- name: Test APE Package in Docker
  run: |
    docker run --rm -v $(pwd):/workspace -w /workspace \
      -v /var/run/docker.sock:/var/run/docker.sock \
      node:18 node scripts/test-package.js
```

## Troubleshooting

### Common Issues

1. **Docker Permission Errors**
   - Ensure Docker daemon is running
   - Check Docker permissions for your user

2. **Port Conflicts**
   - The scripts use ports 13000 for testing
   - Ensure these ports are available

3. **npm Global Install Issues**
   - May require `sudo` on some systems
   - Check npm global directory permissions

4. **PowerShell Execution Policy (Windows)**
   - Run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### Debug Mode

For debugging, use the `--skip-cleanup` option to preserve test artifacts:

```bash
node scripts/test-package.js --skip-cleanup
```

This allows you to:
- Inspect the generated test project
- Examine Docker images and containers
- Debug configuration issues
- Test individual components manually

## Requirements

- Node.js 16+ (for the wrapper script)
- Docker and Docker Compose
- npm with global install permissions
- PowerShell 5+ (Windows) or Bash (Unix/Linux/macOS)

## Contributing

When modifying these scripts:

1. Test on both Windows and Unix-like systems
2. Ensure error handling is robust
3. Update this README with any new options or behavior
4. Maintain colored output consistency
5. Keep exit codes meaningful for CI/CD integration