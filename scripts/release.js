#!/usr/bin/env node

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const releaseType = process.argv[2] || 'patch';

if (!['patch', 'minor', 'major'].includes(releaseType)) {
  console.error('Usage: node scripts/release.js [patch|minor|major]');
  process.exit(1);
}

try {
  console.log(`🚀 Starting ${releaseType} release...`);
  
  // Ensure we're on main branch
  const currentBranch = execSync('git branch --show-current', { encoding: 'utf8' }).trim();
  if (currentBranch !== 'main') {
    console.warn(`⚠️  Warning: You're on branch '${currentBranch}', not 'main'`);
  }
  
  // Ensure working directory is clean
  try {
    execSync('git diff-index --quiet HEAD --', { stdio: 'ignore' });
  } catch (error) {
    console.error('❌ Working directory is not clean. Please commit or stash changes.');
    process.exit(1);
  }
  
  // Run tests
  console.log('🧪 Running tests...');
  execSync('npm run test:ci', { stdio: 'inherit' });
  
  // Run linting
  console.log('🔍 Running linter...');
  execSync('npm run lint', { stdio: 'inherit' });
  
  // Build the project
  console.log('🔨 Building project...');
  execSync('npm run build', { stdio: 'inherit' });
  
  // Bump version
  console.log(`📦 Bumping ${releaseType} version...`);
  const versionOutput = execSync(`npm version ${releaseType}`, { encoding: 'utf8' });
  const newVersion = versionOutput.trim();
  
  console.log(`✅ Version bumped to ${newVersion}`);
  
  // Push changes and tags
  console.log('📤 Pushing changes and tags...');
  execSync('git push', { stdio: 'inherit' });
  execSync('git push --tags', { stdio: 'inherit' });
  
  console.log(`🎉 Release ${newVersion} completed successfully!`);
  console.log('📋 Next steps:');
  console.log('   - GitHub Actions will automatically build and publish to npm');
  console.log('   - Docker images will be built and pushed to registry');
  console.log('   - Check the Actions tab for build status');
  
} catch (error) {
  console.error('❌ Release failed:', error.message);
  process.exit(1);
}