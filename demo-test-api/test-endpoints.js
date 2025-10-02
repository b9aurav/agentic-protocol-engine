#!/usr/bin/env node

/**
 * Simple endpoint testing script for Demo Test API
 * Tests all major endpoints to ensure they're working correctly
 * Usage: node test-endpoints.js [port]
 */

const http = require('http');

const port = process.argv[2] || process.env.PORT || 3000;
const host = 'localhost';

let testsPassed = 0;
let testsFailed = 0;

// Session storage for maintaining cookies across requests
let sessionCookies = '';

function makeRequest(path, method = 'GET', data = null, retries = 3) {
  return new Promise((resolve, reject) => {
    const attemptRequest = (attemptsLeft) => {
      const options = {
        hostname: host,
        port: port,
        path: path,
        method: method,
        headers: {
          'Content-Type': 'application/json',
          'User-Agent': 'Demo-Test-API-Tester/1.0'
        },
        timeout: 10000
      };

      // Add session cookies if we have them
      if (sessionCookies) {
        options.headers['Cookie'] = sessionCookies;
      }

      const req = http.request(options, (res) => {
        let responseData = '';
        
        // Capture session cookies from response
        if (res.headers['set-cookie']) {
          sessionCookies = res.headers['set-cookie'].map(cookie => cookie.split(';')[0]).join('; ');
        }
        
        res.on('data', (chunk) => {
          responseData += chunk;
        });
        
        res.on('end', () => {
          // Retry on 500/503 errors (likely from error simulation) but only if we have retries left
          if ((res.statusCode === 500 || res.statusCode === 503) && attemptsLeft > 0) {
            console.log(`    Retrying due to ${res.statusCode} error (${attemptsLeft} attempts left)`);
            setTimeout(() => attemptRequest(attemptsLeft - 1), 100);
            return;
          }

          try {
            const parsedData = responseData ? JSON.parse(responseData) : null;
            resolve({
              statusCode: res.statusCode,
              headers: res.headers,
              data: parsedData,
              rawData: responseData
            });
          } catch (error) {
            resolve({
              statusCode: res.statusCode,
              headers: res.headers,
              data: null,
              rawData: responseData,
              parseError: error.message
            });
          }
        });
      });

      req.on('error', (error) => {
        if (attemptsLeft > 0) {
          console.log(`    Retrying due to network error (${attemptsLeft} attempts left)`);
          setTimeout(() => attemptRequest(attemptsLeft - 1), 100);
        } else {
          reject(error);
        }
      });

      req.on('timeout', () => {
        req.destroy();
        if (attemptsLeft > 0) {
          console.log(`    Retrying due to timeout (${attemptsLeft} attempts left)`);
          setTimeout(() => attemptRequest(attemptsLeft - 1), 100);
        } else {
          reject(new Error('Request timeout'));
        }
      });

      if (data) {
        req.write(JSON.stringify(data));
      }

      req.end();
    };

    attemptRequest(retries);
  });
}

async function runTest(name, testFn) {
  try {
    console.log(`🧪 Testing: ${name}`);
    await testFn();
    console.log(`✅ PASS: ${name}`);
    testsPassed++;
  } catch (error) {
    console.log(`❌ FAIL: ${name} - ${error.message}`);
    testsFailed++;
  }
}

async function runAllTests() {
  console.log(`🚀 Starting endpoint tests for Demo Test API at http://${host}:${port}`);
  console.log('');

  // Test 1: Root endpoint
  await runTest('Root endpoint (/)', async () => {
    const response = await makeRequest('/');
    if (response.statusCode !== 200) {
      throw new Error(`Expected status 200, got ${response.statusCode}`);
    }
    if (!response.data || !response.data.message) {
      throw new Error('Missing expected response structure');
    }
  });

  // Test 2: Health endpoint
  await runTest('Health endpoint (/api/health)', async () => {
    const response = await makeRequest('/api/health');
    if (response.statusCode !== 200) {
      throw new Error(`Expected status 200, got ${response.statusCode}`);
    }
    if (!response.data || response.data.status !== 'healthy') {
      throw new Error('Health check failed');
    }
  });

  // Test 3: Status endpoint
  await runTest('Status endpoint (/api/status)', async () => {
    const response = await makeRequest('/api/status');
    if (response.statusCode !== 200) {
      throw new Error(`Expected status 200, got ${response.statusCode}`);
    }
    if (!response.data || response.data.status !== 'running') {
      throw new Error('Status check failed');
    }
  });

  // Test 4: Products list
  await runTest('Products list (/api/products)', async () => {
    const response = await makeRequest('/api/products');
    if (response.statusCode !== 200) {
      throw new Error(`Expected status 200, got ${response.statusCode}`);
    }
    if (!response.data || !response.data.products || !Array.isArray(response.data.products)) {
      throw new Error('Products list not found or invalid');
    }
    if (response.data.products.length === 0) {
      throw new Error('No products found');
    }
  });

  // Test 5: Categories list
  await runTest('Categories list (/api/categories)', async () => {
    const response = await makeRequest('/api/categories');
    if (response.statusCode !== 200) {
      throw new Error(`Expected status 200, got ${response.statusCode}`);
    }
    if (!response.data || !response.data.categories || !Array.isArray(response.data.categories)) {
      throw new Error('Categories list not found or invalid');
    }
  });

  // Test 6: Single product
  await runTest('Single product (/api/products/1)', async () => {
    const response = await makeRequest('/api/products/1');
    if (response.statusCode !== 200) {
      throw new Error(`Expected status 200, got ${response.statusCode}`);
    }
    if (!response.data || !response.data.product || !response.data.product.id) {
      throw new Error('Product details not found');
    }
  });

  // Test 7: Non-existent product (should return 404)
  await runTest('Non-existent product (/api/products/999)', async () => {
    const response = await makeRequest('/api/products/999');
    if (response.statusCode !== 404) {
      throw new Error(`Expected status 404, got ${response.statusCode}`);
    }
  });

  // Test 8: Cart operations
  await runTest('Cart operations', async () => {
    // Get empty cart
    let response = await makeRequest('/api/cart');
    if (response.statusCode !== 200) {
      throw new Error(`Expected status 200 for empty cart, got ${response.statusCode}`);
    }

    // Add item to cart
    response = await makeRequest('/api/cart', 'POST', { productId: '1', quantity: 2 });
    if (response.statusCode !== 200) {
      throw new Error(`Expected status 200 for add to cart, got ${response.statusCode}`);
    }
    if (!response.data || !response.data.cart || !response.data.cart.items) {
      throw new Error('Cart response invalid after adding item');
    }

    // Get cart with items
    response = await makeRequest('/api/cart');
    if (response.statusCode !== 200) {
      throw new Error(`Expected status 200 for cart with items, got ${response.statusCode}`);
    }
    if (!response.data || !response.data.cart || response.data.cart.items.length === 0) {
      throw new Error('Cart should contain items');
    }
  });

  console.log('');
  console.log('📊 Test Results:');
  console.log(`   ✅ Passed: ${testsPassed}`);
  console.log(`   ❌ Failed: ${testsFailed}`);
  console.log(`   📈 Success Rate: ${Math.round((testsPassed / (testsPassed + testsFailed)) * 100)}%`);

  if (testsFailed === 0) {
    console.log('');
    console.log('🎉 All tests passed! The Demo Test API is working correctly.');
    process.exit(0);
  } else {
    console.log('');
    console.log('⚠️  Some tests failed. Please check the API implementation.');
    process.exit(1);
  }
}

// Run the tests
runAllTests().catch((error) => {
  console.log(`💥 Test runner failed: ${error.message}`);
  process.exit(1);
});