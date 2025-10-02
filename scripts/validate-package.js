#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

console.log('🔍 Validating package configuration...\n');

// Check package.json
const packageJson = JSON.parse(fs.readFileSync('package.json', 'utf8'));

console.log('📦 Package Information:');
console.log(`   Name: ${packageJson.name}`);
console.log(`   Version: ${packageJson.version}`);
console.log(`   Description: ${packageJson.description}`);
console.log(`   Main: ${packageJson.main}`);
console.log(`   Types: ${packageJson.types}`);

// Check bin files
console.log('\n🔧 Binary Commands:');
Object.entries(packageJson.bin).forEach(([cmd, file]) => {
  const exists = fs.existsSync(file);
  const executable = exists ? (fs.statSync(file).mode & parseInt('111', 8)) !== 0 : false;
  console.log(`   ${cmd}: ${file} ${exists ? '✅' : '❌'} ${executable ? '(executable)' : '(not executable)'}`);
});

// Check files array
console.log('\n📁 Included Files:');
packageJson.files.forEach(pattern => {
  console.log(`   ${pattern}`);
});

// Check required files exist
const requiredFiles = [
  'dist/index.js',
  'dist/index.d.ts',
  'dist/cli.js',
  'dist/create.js',
  'README.md'
];

console.log('\n📋 Required Files:');
requiredFiles.forEach(file => {
  const exists = fs.existsSync(file);
  console.log(`   ${file}: ${exists ? '✅' : '❌'}`);
});

// Check scripts
console.log('\n⚙️  Available Scripts:');
Object.keys(packageJson.scripts).forEach(script => {
  console.log(`   npm run ${script}`);
});

// Validate npm pack (dry run)
console.log('\n📦 NPM Pack Validation:');
try {
  const packOutput = execSync('npm pack --dry-run', { encoding: 'utf8' });
  const lines = packOutput.split('\n').filter(line => line.trim());
  const fileCount = lines.length - 2; // Exclude header and summary lines
  console.log(`   Would include ${fileCount} files in package`);
  
  // Show first few files
  console.log('   Sample files:');
  lines.slice(1, 6).forEach(line => {
    if (line.trim()) console.log(`     ${line.trim()}`);
  });
  
} catch (error) {
  console.log(`   ❌ Pack validation failed: ${error.message}`);
}

// Check for common issues
console.log('\n🔍 Common Issues Check:');

// Check for missing shebang in CLI files
['dist/cli.js', 'dist/create.js'].forEach(file => {
  if (fs.existsSync(file)) {
    const content = fs.readFileSync(file, 'utf8');
    const hasShebang = content.startsWith('#!/usr/bin/env node');
    console.log(`   ${file} shebang: ${hasShebang ? '✅' : '❌'}`);
  }
});

// Check TypeScript declarations
const hasTypes = fs.existsSync('dist/index.d.ts');
console.log(`   TypeScript declarations: ${hasTypes ? '✅' : '❌'}`);

// Check dependencies
const hasAllDeps = packageJson.dependencies && Object.keys(packageJson.dependencies).length > 0;
console.log(`   Has dependencies: ${hasAllDeps ? '✅' : '❌'}`);

console.log('\n✅ Package validation completed!');
console.log('\n💡 To test locally:');
console.log('   npm pack');
console.log('   npm install -g agentic-protocol-engine-1.0.0.tgz');
console.log('   npx create-ape-test --help');