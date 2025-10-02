import chalk from 'chalk';
import * as fs from 'fs-extra';
import * as path from 'path';
import { DockerComposeManager } from '../utils/docker';

interface StatusOptions {
  watch?: boolean;
}

interface TestMetrics {
  activeAgents: number;
  totalServices: number;
  runningServices: number;
  uptime: string;
  projectName: string;
  configPath?: string;
}

export async function statusCommand(options: StatusOptions): Promise<void> {
  try {
    if (options.watch) {
      await watchStatus();
    } else {
      await displayStatus();
    }
  } catch (error) {
    console.error(chalk.red(`Failed to get status: ${error instanceof Error ? error.message : 'Unknown error'}`));
    process.exit(1);
  }
}

async function displayStatus(): Promise<void> {
  console.log(chalk.blue('📊 APE Load Test Status\n'));
  
  // Find the project directory
  const projectDir = await findProjectDirectory();
  if (!projectDir) {
    console.log(chalk.yellow('⚠️  No APE project found in current directory or parent directories.'));
    console.log(chalk.yellow('💡 Run this command from within an APE project directory.'));
    console.log(chalk.yellow('💡 Or run "npx create-ape-load" to create a new project.'));
    return;
  }

  const dockerManager = new DockerComposeManager(
    projectDir,
    'ape.docker-compose.yml',
    path.basename(projectDir)
  );

  // Get service status - Requirements 5.3
  const status = await dockerManager.getStatus();
  const metrics = await calculateMetrics(status, projectDir);
  
  // Display overall status
  const overallStatus = status.isRunning ? '🟢 Running' : '🔴 Stopped';
  console.log(chalk.bold(`Status: ${overallStatus}`));
  console.log(chalk.blue(`📁 Project: ${metrics.projectName}`));
  console.log(chalk.blue(`🐳 Services: ${metrics.runningServices}/${metrics.totalServices} running`));
  console.log(chalk.blue(`🤖 Active Agents: ${metrics.activeAgents}`));
  
  if (status.isRunning) {
    console.log(chalk.blue(`⏱️  Uptime: ${metrics.uptime}`));
  }
  
  // Display service details
  console.log(chalk.cyan('\n📋 Service Details:'));
  
  if (status.services.length === 0) {
    console.log(chalk.gray('  No services found'));
  } else {
    // Group services by type for better organization
    const serviceGroups = groupServicesByType(status.services);
    
    Object.entries(serviceGroups).forEach(([type, services]) => {
      console.log(chalk.cyan(`\n  ${type}:`));
      services.forEach(service => {
        const statusIcon = getStatusIcon(service.status, service.health);
        const healthInfo = service.health !== 'none' ? ` (${service.health})` : '';
        const portsInfo = service.ports && service.ports.length > 0 ? 
          ` - Ports: ${service.ports.join(', ')}` : '';
        
        console.log(`    ${statusIcon} ${service.name} - ${service.status}${healthInfo}${portsInfo}`);
      });
    });
  }
  
  // Display configuration info
  if (metrics.configPath) {
    console.log(chalk.cyan('\n⚙️  Configuration:'));
    console.log(chalk.cyan(`  📄 Config: ${path.relative(process.cwd(), metrics.configPath)}`));
    console.log(chalk.cyan(`  🐳 Compose: ${path.relative(process.cwd(), path.join(projectDir, 'ape.docker-compose.yml'))}`));
  }
  
  // Display access points if running
  if (status.isRunning) {
    console.log(chalk.yellow('\n🔗 Access Points:'));
    console.log(chalk.yellow('  📊 Grafana Dashboard: http://localhost:3001 (admin/ape-admin)'));
    console.log(chalk.yellow('  📈 Prometheus Metrics: http://localhost:9090'));
    console.log(chalk.yellow('  🔍 MCP Gateway: http://localhost:3000'));
    
    console.log(chalk.cyan('\n📋 Management Commands:'));
    console.log(chalk.cyan('  📋 View logs: ape-load logs'));
    console.log(chalk.cyan('  📊 Watch status: ape-load status --watch'));
    console.log(chalk.cyan('  ⏹️  Stop test: ape-load stop'));
  } else {
    console.log(chalk.yellow('\n💡 Management Commands:'));
    console.log(chalk.yellow('  🚀 Start test: ape-load start'));
    console.log(chalk.yellow('  📋 View logs: ape-load logs'));
  }
}

async function watchStatus(): Promise<void> {
  console.log(chalk.blue('📊 APE Load Test Status - Watch Mode\n'));
  console.log(chalk.yellow('👀 Watching for updates... (Press Ctrl+C to exit)\n'));
  
  let lastStatusHash = '';
  
  const updateStatus = async () => {
    try {
      // Clear screen and move cursor to top
      process.stdout.write('\x1B[2J\x1B[0f');
      
      console.log(chalk.blue('📊 APE Load Test Status - Watch Mode'));
      console.log(chalk.gray(`🕐 Last updated: ${new Date().toLocaleTimeString()}`));
      console.log(chalk.yellow('👀 Press Ctrl+C to exit\n'));
      
      const projectDir = await findProjectDirectory();
      if (!projectDir) {
        console.log(chalk.yellow('⚠️  No APE project found'));
        return;
      }

      const dockerManager = new DockerComposeManager(
        projectDir,
        'ape.docker-compose.yml',
        path.basename(projectDir)
      );

      const status = await dockerManager.getStatus();
      const metrics = await calculateMetrics(status, projectDir);
      
      // Create a hash of the current status to detect changes
      const currentStatusHash = JSON.stringify({
        services: status.services.map(s => ({ name: s.name, status: s.status, health: s.health })),
        isRunning: status.isRunning
      });
      
      // Display status with change indicator
      const changeIndicator = currentStatusHash !== lastStatusHash ? '🔄' : '✅';
      lastStatusHash = currentStatusHash;
      
      const overallStatus = status.isRunning ? '🟢 Running' : '🔴 Stopped';
      console.log(chalk.bold(`${changeIndicator} Status: ${overallStatus}`));
      console.log(chalk.blue(`📁 Project: ${metrics.projectName}`));
      console.log(chalk.blue(`🐳 Services: ${metrics.runningServices}/${metrics.totalServices} running`));
      console.log(chalk.blue(`🤖 Active Agents: ${metrics.activeAgents}`));
      
      if (status.isRunning) {
        console.log(chalk.blue(`⏱️  Uptime: ${metrics.uptime}`));
      }
      
      // Compact service status display for watch mode
      console.log(chalk.cyan('\n📋 Services:'));
      status.services.forEach(service => {
        const statusIcon = getStatusIcon(service.status, service.health);
        console.log(`  ${statusIcon} ${service.name.padEnd(20)} ${service.status}`);
      });
      
    } catch (error) {
      console.error(chalk.red(`Error updating status: ${error instanceof Error ? error.message : 'Unknown error'}`));
    }
  };
  
  // Initial display
  await updateStatus();
  
  // Update every 5 seconds
  const interval = setInterval(updateStatus, 5000);
  
  // Handle Ctrl+C gracefully
  process.on('SIGINT', () => {
    clearInterval(interval);
    console.log(chalk.yellow('\n\n📊 Status monitoring stopped.'));
    process.exit(0);
  });
}

async function calculateMetrics(status: any, projectDir: string): Promise<TestMetrics> {
  const activeAgents = status.services.filter((s: any) => 
    s.name.includes('llama_agent') && s.status === 'running'
  ).length;
  
  const runningServices = status.services.filter((s: any) => s.status === 'running').length;
  
  // Calculate uptime by checking container start time (simplified)
  const uptime = status.isRunning ? 'Running' : 'Stopped';
  
  // Look for config file
  const configPath = await findConfigFile(projectDir);
  
  return {
    activeAgents,
    totalServices: status.services.length,
    runningServices,
    uptime,
    projectName: status.projectName,
    configPath
  };
}

function groupServicesByType(services: any[]): Record<string, any[]> {
  const groups: Record<string, any[]> = {
    'AI Agents': [],
    'Core Services': [],
    'Observability': [],
    'Other': []
  };
  
  services.forEach(service => {
    if (service.name.includes('llama_agent') || service.name.includes('agent')) {
      groups['AI Agents'].push(service);
    } else if (service.name.includes('mcp_gateway') || service.name.includes('cerebras_proxy')) {
      groups['Core Services'].push(service);
    } else if (service.name.includes('prometheus') || service.name.includes('grafana') || 
               service.name.includes('loki') || service.name.includes('promtail') ||
               service.name.includes('cadvisor') || service.name.includes('node_exporter')) {
      groups['Observability'].push(service);
    } else {
      groups['Other'].push(service);
    }
  });
  
  // Remove empty groups
  Object.keys(groups).forEach(key => {
    if (groups[key].length === 0) {
      delete groups[key];
    }
  });
  
  return groups;
}

function getStatusIcon(status: string, health?: string): string {
  if (status === 'running') {
    if (health === 'healthy') return '✅';
    if (health === 'unhealthy') return '❌';
    if (health === 'starting') return '🟡';
    return '🟢';
  } else if (status === 'starting') {
    return '🔄';
  } else if (status === 'stopped' || status === 'exited') {
    return '⏹️';
  } else {
    return '❓';
  }
}

async function findProjectDirectory(): Promise<string | null> {
  let currentDir = process.cwd();
  const maxDepth = 5;
  let depth = 0;
  
  while (depth < maxDepth) {
    const composeFile = path.join(currentDir, 'ape.docker-compose.yml');
    
    if (await fs.pathExists(composeFile)) {
      return currentDir;
    }
    
    const parentDir = path.dirname(currentDir);
    if (parentDir === currentDir) {
      break;
    }
    
    currentDir = parentDir;
    depth++;
  }
  
  return null;
}

async function findConfigFile(projectDir: string): Promise<string | undefined> {
  const configFile = path.join(projectDir, 'ape.config.json');
  
  if (await fs.pathExists(configFile)) {
    return configFile;
  }
  
  return undefined;
}