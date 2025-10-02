#!/usr/bin/env node

/**
 * Simple health check script for Demo Test API
 * Usage: node health-check.js [port]
 */

const http = require('http');

const port = process.argv[2] || process.env.PORT || 3000;
const host = 'localhost';

const options = {
  hostname: host,
  port: port,
  path: '/api/health',
  method: 'GET',
  timeout: 5000
};

console.log(`🔍 Checking health of Demo Test API at http://${host}:${port}/api/health`);

const req = http.request(options, (res) => {
  let data = '';
  
  res.on('data', (chunk) => {
    data += chunk;
  });
  
  res.on('end', () => {
    if (res.statusCode === 200) {
      try {
        const response = JSON.parse(data);
        console.log('✅ API is healthy!');
        console.log(`   Status: ${response.status}`);
        console.log(`   Timestamp: ${response.timestamp}`);
        process.exit(0);
      } catch (error) {
        console.log('⚠️  API responded but with invalid JSON');
        console.log(`   Status Code: ${res.statusCode}`);
        console.log(`   Response: ${data}`);
        process.exit(1);
      }
    } else {
      console.log(`❌ API health check failed with status ${res.statusCode}`);
      console.log(`   Response: ${data}`);
      process.exit(1);
    }
  });
});

req.on('error', (error) => {
  console.log(`❌ Failed to connect to API: ${error.message}`);
  console.log('   Make sure the API is running and accessible');
  process.exit(1);
});

req.on('timeout', () => {
  console.log('❌ Health check timed out after 5 seconds');
  console.log('   The API may be overloaded or not responding');
  req.destroy();
  process.exit(1);
});

req.end();