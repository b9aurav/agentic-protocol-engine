#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

// Make CLI files executable
const cliFiles = [
  'dist/cli.js',
  'dist/create.js'
];

cliFiles.forEach(file => {
  if (fs.existsSync(file)) {
    // Make file executable (Unix/Linux/macOS)
    try {
      fs.chmodSync(file, '755');
      console.log(`Made ${file} executable`);
    } catch (error) {
      console.warn(`Could not make ${file} executable:`, error.message);
    }
  }
});

console.log('Post-build script completed successfully');