#!/usr/bin/env node

/**
 * Cross-platform wrapper for APE package testing
 * Automatically detects the platform and runs the appropriate test script
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// Parse command line arguments
const args = process.argv.slice(2);
const isWindows = process.platform === 'win32';

// Determine which script to run
const scriptName = isWindows ? 'test-package-from-scratch.ps1' : 'test-package-from-scratch.sh';
const scriptPath = path.join(__dirname, scriptName);

// Check if script exists
if (!fs.existsSync(scriptPath)) {
    console.error(`❌ Test script not found: ${scriptPath}`);
    process.exit(1);
}

console.log(`🔄 Running APE package test on ${process.platform}...`);
console.log(`📄 Using script: ${scriptName}`);
console.log('');

// Prepare command and arguments
let command, commandArgs;

if (isWindows) {
    // Use PowerShell on Windows
    command = 'powershell';
    commandArgs = ['-ExecutionPolicy', 'Bypass', '-File', scriptPath, ...args];
} else {
    // Use bash on Unix-like systems
    command = 'bash';
    commandArgs = [scriptPath, ...args];
    
    // Make script executable if needed
    try {
        fs.chmodSync(scriptPath, '755');
    } catch (error) {
        console.warn(`⚠️  Could not make script executable: ${error.message}`);
    }
}

// Run the test script
const child = spawn(command, commandArgs, {
    stdio: 'inherit',
    shell: isWindows
});

child.on('error', (error) => {
    console.error(`❌ Failed to start test script: ${error.message}`);
    process.exit(1);
});

child.on('close', (code) => {
    if (code === 0) {
        console.log('');
        console.log('🎉 Test script completed successfully!');
    } else {
        console.log('');
        console.log(`💥 Test script failed with exit code: ${code}`);
    }
    process.exit(code);
});

// Handle Ctrl+C gracefully
process.on('SIGINT', () => {
    console.log('\n🛑 Test interrupted by user');
    child.kill('SIGINT');
    process.exit(130);
});

process.on('SIGTERM', () => {
    console.log('\n🛑 Test terminated');
    child.kill('SIGTERM');
    process.exit(143);
});