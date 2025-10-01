import { spawn, ChildProcess } from 'child_process';
import * as fs from 'fs-extra';
import * as path from 'path';

export interface DockerComposeOptions {
    file?: string;
    projectName?: string;
    env?: Record<string, string>;
    detach?: boolean;
    scale?: Record<string, number>;
}

export interface ServiceHealth {
    name: string;
    status: 'running' | 'stopped' | 'starting' | 'unhealthy' | 'unknown';
    health?: 'healthy' | 'unhealthy' | 'starting' | 'none';
    ports?: string[];
}

export interface DockerComposeStatus {
    services: ServiceHealth[];
    isRunning: boolean;
    projectName: string;
}

/**
 * Execute Docker Compose commands with proper error handling and logging
 */
export class DockerComposeManager {
    private projectPath: string;
    private composeFile: string;
    private projectName: string;

    constructor(projectPath: string, composeFile: string = 'ape.docker-compose.yml', projectName?: string) {
        this.projectPath = projectPath;
        this.composeFile = composeFile;
        this.projectName = projectName || path.basename(projectPath);
    }

    /**
     * Start services with Docker Compose - Requirements 5.3, 6.1, 6.4
     */
    async start(options: DockerComposeOptions = {}): Promise<void> {
        const composeFilePath = path.join(this.projectPath, this.composeFile);

        if (!await fs.pathExists(composeFilePath)) {
            throw new Error(`Docker Compose file not found: ${composeFilePath}`);
        }

        const args = [
            'compose',
            '-f', composeFilePath,
            '-p', options.projectName || this.projectName
        ];

        // Add scaling configuration if provided
        if (options.scale) {
            args.push('up');
            if (options.detach !== false) {
                args.push('-d');
            }

            // Add scale parameters for each service
            Object.entries(options.scale).forEach(([service, count]) => {
                args.push('--scale', `${service}=${count}`);
            });
        } else {
            args.push('up');
            if (options.detach !== false) {
                args.push('-d');
            }
        }

        await this.executeDockerCommand(args, options.env);
    }

    /**
     * Stop services gracefully - Requirements 5.3
     */
    async stop(force: boolean = false): Promise<void> {
        const composeFilePath = path.join(this.projectPath, this.composeFile);

        if (!await fs.pathExists(composeFilePath)) {
            throw new Error(`Docker Compose file not found: ${composeFilePath}`);
        }

        const args = [
            'compose',
            '-f', composeFilePath,
            '-p', this.projectName
        ];

        if (force) {
            args.push('kill');
        } else {
            args.push('down');
            args.push('--remove-orphans');
        }

        await this.executeDockerCommand(args);
    }

    /**
     * Get status of all services - Requirements 5.3
     */
    async getStatus(): Promise<DockerComposeStatus> {
        const composeFilePath = path.join(this.projectPath, this.composeFile);

        if (!await fs.pathExists(composeFilePath)) {
            throw new Error(`Docker Compose file not found: ${composeFilePath}`);
        }

        const args = [
            'compose',
            '-f', composeFilePath,
            '-p', this.projectName,
            'ps',
            '--format', 'json'
        ];

        try {
            const output = await this.executeDockerCommand(args, undefined, true);
            const services = this.parseDockerComposeStatus(output);

            return {
                services,
                isRunning: services.some(s => s.status === 'running'),
                projectName: this.projectName
            };
        } catch (error) {
            // If compose ps fails, project is likely not running
            return {
                services: [],
                isRunning: false,
                projectName: this.projectName
            };
        }
    }

    /**
     * Get logs from services - Requirements 5.3, 4.2
     */
    async getLogs(options: {
        service?: string;
        follow?: boolean;
        tail?: number;
        grep?: string;
    } = {}): Promise<ChildProcess> {
        const composeFilePath = path.join(this.projectPath, this.composeFile);

        if (!await fs.pathExists(composeFilePath)) {
            throw new Error(`Docker Compose file not found: ${composeFilePath}`);
        }

        const args = [
            'compose',
            '-f', composeFilePath,
            '-p', this.projectName,
            'logs'
        ];

        if (options.follow) {
            args.push('-f');
        }

        if (options.tail) {
            args.push('--tail', options.tail.toString());
        }

        if (options.service) {
            args.push(options.service);
        }

        // Start the process but don't wait for it to complete (for streaming logs)
        const process = spawn('docker', args, {
            cwd: this.projectPath,
            stdio: ['pipe', 'pipe', 'pipe']
        });

        // Apply grep filtering if specified
        if (options.grep) {
            const grepProcess = spawn('grep', [options.grep], {
                stdio: ['pipe', 'inherit', 'inherit']
            });

            process.stdout?.pipe(grepProcess.stdin);
            return grepProcess;
        }

        return process;
    }

    /**
     * Wait for services to be healthy - Requirements 6.1, 6.4
     */
    async waitForHealthy(timeoutMs: number = 120000): Promise<void> {
        const startTime = Date.now();
        const checkInterval = 5000; // Check every 5 seconds

        while (Date.now() - startTime < timeoutMs) {
            const status = await this.getStatus();

            // Check if all services are running and healthy
            const allHealthy = status.services.every(service => {
                return service.status === 'running' &&
                    (service.health === 'healthy' || service.health === 'none');
            });

            if (allHealthy && status.services.length > 0) {
                return;
            }

            // Wait before next check
            await new Promise(resolve => setTimeout(resolve, checkInterval));
        }

        throw new Error(`Services did not become healthy within ${timeoutMs}ms`);
    }

    /**
     * Scale a specific service - Requirements 6.1, 6.4
     */
    async scale(service: string, replicas: number): Promise<void> {
        const composeFilePath = path.join(this.projectPath, this.composeFile);

        if (!await fs.pathExists(composeFilePath)) {
            throw new Error(`Docker Compose file not found: ${composeFilePath}`);
        }

        const args = [
            'compose',
            '-f', composeFilePath,
            '-p', this.projectName,
            'up',
            '-d',
            '--scale', `${service}=${replicas}`,
            '--no-recreate'
        ];

        await this.executeDockerCommand(args);
    }

    /**
     * Execute Docker command with proper error handling
     */
    private async executeDockerCommand(
        args: string[],
        env?: Record<string, string>,
        captureOutput: boolean = false
    ): Promise<string> {
        return new Promise((resolve, reject) => {
            const childProcess = spawn('docker', args, {
                cwd: this.projectPath,
                env: { ...process.env, ...env },
                stdio: captureOutput ? ['pipe', 'pipe', 'pipe'] : ['inherit', 'inherit', 'inherit']
            });

            let output = '';
            let errorOutput = '';

            if (captureOutput) {
                childProcess.stdout?.on('data', (data: Buffer) => {
                    output += data.toString();
                });

                childProcess.stderr?.on('data', (data: Buffer) => {
                    errorOutput += data.toString();
                });
            }

            childProcess.on('close', (code: number | null) => {
                if (code === 0) {
                    resolve(output);
                } else {
                    reject(new Error(`Docker command failed with code ${code}: ${errorOutput || 'Unknown error'}`));
                }
            });

            childProcess.on('error', (error: Error) => {
                reject(new Error(`Failed to execute Docker command: ${error.message}`));
            });
        });
    }

    /**
     * Parse Docker Compose status output
     */
    private parseDockerComposeStatus(output: string): ServiceHealth[] {
        if (!output.trim()) {
            return [];
        }

        try {
            const lines = output.trim().split('\n');
            return lines.map(line => {
                const service = JSON.parse(line);
                return {
                    name: service.Service || service.Name,
                    status: this.mapDockerStatus(service.State),
                    health: service.Health || 'none',
                    ports: service.Publishers ? service.Publishers.map((p: any) => `${p.PublishedPort}:${p.TargetPort}`) : []
                };
            });
        } catch (error) {
            // Fallback to simple parsing if JSON parsing fails
            return this.parseDockerComposeStatusFallback(output);
        }
    }

    /**
     * Fallback parser for Docker Compose status
     */
    private parseDockerComposeStatusFallback(output: string): ServiceHealth[] {
        const lines = output.trim().split('\n');
        const services: ServiceHealth[] = [];

        for (const line of lines) {
            if (line.includes('Up') || line.includes('Exit')) {
                const parts = line.split(/\s+/);
                const name = parts[0];
                const status = line.includes('Up') ? 'running' : 'stopped';

                services.push({
                    name,
                    status,
                    health: 'none',
                    ports: []
                });
            }
        }

        return services;
    }

    /**
     * Map Docker status to our status enum
     */
    private mapDockerStatus(dockerStatus: string): ServiceHealth['status'] {
        switch (dockerStatus?.toLowerCase()) {
            case 'running':
                return 'running';
            case 'exited':
            case 'stopped':
                return 'stopped';
            case 'starting':
            case 'created':
                return 'starting';
            case 'unhealthy':
                return 'unhealthy';
            default:
                return 'unknown';
        }
    }
}

/**
 * Check if Docker and Docker Compose are available
 */
export async function checkDockerAvailability(): Promise<{ docker: boolean; compose: boolean }> {
    const checkCommand = async (command: string, args: string[]): Promise<boolean> => {
        try {
            await new Promise<void>((resolve, reject) => {
                const childProcess = spawn(command, args, { stdio: 'pipe' });
                childProcess.on('close', (code: number | null) => {
                    if (code === 0) resolve();
                    else reject();
                });
                childProcess.on('error', reject);
            });
            return true;
        } catch {
            return false;
        }
    };

    const [docker, compose] = await Promise.all([
        checkCommand('docker', ['--version']),
        checkCommand('docker', ['compose', 'version'])
    ]);

    return { docker, compose };
}

/**
 * Validate Docker Compose file exists and is valid
 */
export async function validateComposeFile(filePath: string): Promise<{ valid: boolean; error?: string }> {
    try {
        if (!await fs.pathExists(filePath)) {
            return { valid: false, error: 'Docker Compose file not found' };
        }

        // Basic validation by attempting to parse the file
        const args = ['compose', '-f', filePath, 'config', '--quiet'];

        await new Promise<void>((resolve, reject) => {
            const childProcess = spawn('docker', args, { stdio: 'pipe' });
            childProcess.on('close', (code: number | null) => {
                if (code === 0) resolve();
                else reject(new Error('Invalid Docker Compose configuration'));
            });
            childProcess.on('error', reject);
        });

        return { valid: true };
    } catch (error) {
        return {
            valid: false,
            error: error instanceof Error ? error.message : 'Unknown validation error'
        };
    }
}