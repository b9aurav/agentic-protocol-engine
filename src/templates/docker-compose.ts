import { SetupAnswers } from '../commands/setup';

export interface DockerComposeConfig {
  version: string;
  services: Record<string, any>;
  networks: Record<string, any>;
  volumes?: Record<string, any>;
}

export function generateDockerCompose(config: SetupAnswers): DockerComposeConfig {
  const networkName = `${config.projectName}_network`;
  
  // Dynamic scaling configuration based on user inputs - Requirements 6.1, 6.4
  const agentResourceLimits = calculateAgentResources(config.agentCount);
  const networkSubnet = generateNetworkSubnet(config.projectName);

  return {
    version: '3.8',
    services: {
      // MCP Gateway Service - Optimized for Requirements 6.2, 6.3, 6.4
      mcp_gateway: {
        image: 'ape/mcp-gateway:latest',
        container_name: `${config.projectName}_mcp_gateway`,
        ports: ['3000:3000', '8001:8001'], // Main port and metrics port
        environment: {
          NODE_ENV: 'production',
          LOG_LEVEL: 'info',
          CONFIG_PATH: '/app/config/mcp-gateway.json',
          PROJECT_NAME: config.projectName,
          TARGET_URL: config.targetUrl,
          MAX_CONCURRENT_AGENTS: `${config.agentCount}`,
          RATE_LIMIT_ENABLED: 'true',
          CORS_ENABLED: 'true',
          METRICS_PORT: '8001',
          METRICS_ENABLED: 'true',
          // High-concurrency optimization
          MAX_WORKERS: Math.min(4, Math.max(1, Math.ceil(config.agentCount / 250))),
          CONNECTION_POOL_SIZE: Math.min(100, config.agentCount * 2),
          KEEP_ALIVE_TIMEOUT: '5',
          REQUEST_TIMEOUT: '30',
          // Memory optimization
          MEMORY_LIMIT_MB: config.agentCount > 500 ? '1024' : '512',
          // Graceful shutdown
          GRACEFUL_SHUTDOWN_TIMEOUT: '15'
        },
        volumes: [
          './ape.mcp-gateway.json:/app/config/mcp-gateway.json:ro'
        ],
        networks: [networkName],
        restart: 'unless-stopped',
        // Optimized resource limits based on agent count
        deploy: {
          resources: {
            limits: {
              memory: config.agentCount > 500 ? '1G' : '512M',
              cpus: config.agentCount > 500 ? '2.0' : '1.0'
            },
            reservations: {
              memory: config.agentCount > 500 ? '512M' : '256M',
              cpus: config.agentCount > 500 ? '1.0' : '0.5'
            }
          }
        },
        healthcheck: {
          test: ['CMD', 'curl', '-f', 'http://localhost:3000/health'],
          interval: '15s',
          timeout: '5s',
          retries: 3,
          start_period: '25s'
        },
        depends_on: ['cerebras_proxy'],
        logging: {
          driver: 'json-file',
          options: {
            'max-size': '15m',
            'max-file': '3',
            tag: `${config.projectName}_mcp_gateway`,
            'compress': 'true'
          }
        },
        labels: [
          `ape.project=${config.projectName}`,
          `ape.service=mcp-gateway`,
          `ape.scale=${config.agentCount}`,
          'ape.monitoring=enabled'
        ]
      },

      // Cerebras Proxy Service - Optimized for Requirements 2.1, 2.3, 6.4
      cerebras_proxy: {
        image: 'ape/cerebras-proxy:latest',
        container_name: `${config.projectName}_cerebras_proxy`,
        ports: ['8000:8000', '8002:8002'], // Main port and metrics port
        environment: {
          CEREBRAS_API_KEY: '${CEREBRAS_API_KEY}',
          LOG_LEVEL: 'info',
          METRICS_ENABLED: 'true',
          METRICS_PORT: '8002',
          MAX_CONCURRENT_REQUESTS: `${config.agentCount * 2}`, // Allow 2x agent count for burst
          TTFT_TARGET_MS: '500', // Target Time-to-First-Token in milliseconds
          REQUEST_TIMEOUT: '10000', // 10 second timeout for inference
          RATE_LIMIT_PER_MINUTE: `${config.agentCount * 60}`, // 60 requests per agent per minute
          // High-performance optimization
          CONNECTION_POOL_SIZE: Math.min(50, config.agentCount),
          KEEP_ALIVE_CONNECTIONS: Math.min(20, Math.ceil(config.agentCount / 10)),
          ASYNC_WORKERS: Math.min(4, Math.max(1, Math.ceil(config.agentCount / 100))),
          // Memory optimization
          MEMORY_LIMIT_MB: config.agentCount > 500 ? '768' : '512',
          // Graceful shutdown
          GRACEFUL_SHUTDOWN_TIMEOUT: '10'
        },
        networks: [networkName],
        restart: 'unless-stopped',
        // Optimized resource limits based on agent count
        deploy: {
          resources: {
            limits: {
              memory: config.agentCount > 500 ? '768M' : '512M',
              cpus: config.agentCount > 500 ? '1.5' : '1.0'
            },
            reservations: {
              memory: config.agentCount > 500 ? '384M' : '256M',
              cpus: config.agentCount > 500 ? '0.75' : '0.5'
            }
          }
        },
        healthcheck: {
          test: ['CMD', 'curl', '-f', 'http://localhost:8000/health'],
          interval: '15s',
          timeout: '5s',
          retries: 3,
          start_period: '20s'
        },
        logging: {
          driver: 'json-file',
          options: {
            'max-size': '15m',
            'max-file': '3',
            tag: `${config.projectName}_cerebras_proxy`,
            'compress': 'true'
          }
        },
        labels: [
          `ape.project=${config.projectName}`,
          `ape.service=cerebras-proxy`,
          `ape.scale=${config.agentCount}`,
          'ape.monitoring=enabled'
        ]
      },

      // Llama Agent Service - Optimized for Requirements 1.1, 6.1, 6.4
      llama_agent: {
        image: 'ape/llama-agent:latest',
        ports: ['8000'], // Expose metrics port for Prometheus scraping
        environment: {
          MCP_GATEWAY_URL: 'http://mcp_gateway:3000',
          AGENT_GOAL: config.testGoal,
          TARGET_API_NAME: 'sut_api',
          LOG_LEVEL: 'info',
          SESSION_TIMEOUT: '300',
          AGENT_ID: '${HOSTNAME}', // Dynamic agent identification
          TEST_DURATION: `${config.testDuration}`,
          TARGET_ENDPOINTS: config.endpoints.join(','),
          METRICS_PORT: '8000', // Port for metrics endpoint
          METRICS_ENABLED: 'true',
          // Optimization settings for high-scale deployments
          AGENT_STARTUP_DELAY: Math.floor(Math.random() * 10), // Stagger startup 0-10s
          AGENT_BATCH_SIZE: Math.min(config.agentCount, 50), // Process in batches
          MEMORY_LIMIT_MB: agentResourceLimits.limits.memory.replace('M', ''),
          CPU_LIMIT: agentResourceLimits.limits.cpus,
          // Graceful shutdown configuration
          GRACEFUL_SHUTDOWN_TIMEOUT: '10',
          SHUTDOWN_SIGNAL_TIMEOUT: '5',
          // Connection pooling optimization
          HTTP_POOL_CONNECTIONS: '10',
          HTTP_POOL_MAXSIZE: '20',
          HTTP_RETRIES: '3',
          // Dynamic authentication configuration
          ...(config.authType !== 'none' && {
            AUTH_TYPE: config.authType,
            ...(config.authType === 'bearer' && config.authToken && {
              AUTH_TOKEN: config.authToken
            }),
            ...(config.authType === 'basic' && config.authUsername && config.authPassword && {
              AUTH_USERNAME: config.authUsername,
              AUTH_PASSWORD: config.authPassword
            })
          })
        },
        networks: [networkName],
        restart: 'unless-stopped',
        depends_on: {
          mcp_gateway: {
            condition: 'service_healthy'
          }
        },
        deploy: {
          replicas: config.agentCount,
          resources: agentResourceLimits,
          update_config: agentResourceLimits.update_config,
          restart_policy: agentResourceLimits.restart_policy,
          // Placement constraints for optimal resource distribution
          placement: {
            max_replicas_per_node: Math.max(1, Math.floor(100 / Math.sqrt(config.agentCount)))
          }
        },
        // Optimized logging for high-scale deployments
        logging: {
          driver: 'json-file',
          options: {
            'max-size': config.agentCount > 100 ? '5m' : '10m',
            'max-file': config.agentCount > 100 ? '2' : '3',
            tag: `${config.projectName}_agent_{{.Name}}`,
            'compress': 'true'
          }
        },
        // Health check optimized for faster detection
        healthcheck: {
          test: ['CMD', 'curl', '-f', 'http://localhost:8000/health'],
          interval: '10s',
          timeout: '3s',
          retries: 2,
          start_period: '15s'
        },
        // Resource monitoring labels
        labels: [
          `ape.project=${config.projectName}`,
          `ape.service=llama-agent`,
          `ape.scale=${config.agentCount}`,
          'ape.monitoring=enabled'
        ]
      },

      // Observability Stack - Requirements 4.1, 4.4, 4.5
      
      // Loki for log aggregation
      loki: {
        image: 'grafana/loki:2.9.0',
        container_name: `${config.projectName}_loki`,
        ports: ['3100:3100'],
        command: '-config.file=/etc/loki/local-config.yaml',
        volumes: [
          'loki_data:/loki'
        ],
        networks: [networkName],
        restart: 'unless-stopped',
        environment: {
          LOKI_RETENTION_PERIOD: '168h', // 7 days
          LOKI_MAX_CHUNK_AGE: '1h'
        },
        logging: {
          driver: 'json-file',
          options: {
            'max-size': '10m',
            'max-file': '3',
            tag: `${config.projectName}_loki`
          }
        }
      },

      // Promtail for log collection
      promtail: {
        image: 'grafana/promtail:2.9.0',
        container_name: `${config.projectName}_promtail`,
        volumes: [
          '/var/log:/var/log:ro',
          '/var/lib/docker/containers:/var/lib/docker/containers:ro',
          './config/promtail.yml:/etc/promtail/config.yml:ro'
        ],
        command: '-config.file=/etc/promtail/config.yml',
        networks: [networkName],
        restart: 'unless-stopped',
        depends_on: ['loki'],
        environment: {
          PROJECT_NAME: config.projectName,
          LOKI_URL: 'http://loki:3100'
        },
        logging: {
          driver: 'json-file',
          options: {
            'max-size': '5m',
            'max-file': '2',
            tag: `${config.projectName}_promtail`
          }
        }
      },

      // Prometheus for metrics collection
      prometheus: {
        image: 'prom/prometheus:v2.47.0',
        container_name: `${config.projectName}_prometheus`,
        ports: ['9090:9090'],
        command: [
          '--config.file=/etc/prometheus/prometheus.yml',
          '--storage.tsdb.path=/prometheus',
          '--web.console.libraries=/etc/prometheus/console_libraries',
          '--web.console.templates=/etc/prometheus/consoles',
          '--storage.tsdb.retention.time=200h',
          '--web.enable-lifecycle',
          '--web.enable-admin-api'
        ],
        volumes: [
          './config/prometheus.yml:/etc/prometheus/prometheus.yml:ro',
          'prometheus_data:/prometheus'
        ],
        networks: [networkName],
        restart: 'unless-stopped',
        environment: {
          PROJECT_NAME: config.projectName,
          SCRAPE_INTERVAL: '15s'
        },
        logging: {
          driver: 'json-file',
          options: {
            'max-size': '10m',
            'max-file': '3',
            tag: `${config.projectName}_prometheus`
          }
        }
      },

      // cAdvisor for container metrics
      cadvisor: {
        image: 'gcr.io/cadvisor/cadvisor:v0.47.0',
        container_name: `${config.projectName}_cadvisor`,
        ports: ['8080:8080'],
        volumes: [
          '/:/rootfs:ro',
          '/var/run:/var/run:ro',
          '/sys:/sys:ro',
          '/var/lib/docker/:/var/lib/docker:ro',
          '/dev/disk/:/dev/disk:ro'
        ],
        privileged: true,
        devices: ['/dev/kmsg'],
        networks: [networkName],
        restart: 'unless-stopped',
        command: [
          '--housekeeping_interval=10s',
          '--docker_only=true',
          '--disable_metrics=percpu,sched,tcp,udp,disk,diskIO,accelerator,hugetlb,referenced_memory,cpu_topology,resctrl'
        ],
        logging: {
          driver: 'json-file',
          options: {
            'max-size': '5m',
            'max-file': '2',
            tag: `${config.projectName}_cadvisor`
          }
        }
      },

      // Node Exporter for host metrics
      node_exporter: {
        image: 'prom/node-exporter:v1.6.1',
        container_name: `${config.projectName}_node_exporter`,
        ports: ['9100:9100'],
        command: [
          '--path.procfs=/host/proc',
          '--path.rootfs=/rootfs',
          '--path.sysfs=/host/sys',
          '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
        ],
        volumes: [
          '/proc:/host/proc:ro',
          '/sys:/host/sys:ro',
          '/:/rootfs:ro'
        ],
        networks: [networkName],
        restart: 'unless-stopped',
        logging: {
          driver: 'json-file',
          options: {
            'max-size': '5m',
            'max-file': '2',
            tag: `${config.projectName}_node_exporter`
          }
        }
      },

      // Grafana for visualization - Requirements 4.3, 4.6
      grafana: {
        image: 'grafana/grafana:10.1.0',
        container_name: `${config.projectName}_grafana`,
        ports: ['3001:3000'],
        environment: {
          GF_SECURITY_ADMIN_USER: 'admin',
          GF_SECURITY_ADMIN_PASSWORD: 'ape-admin',
          GF_USERS_ALLOW_SIGN_UP: 'false',
          GF_INSTALL_PLUGINS: 'grafana-piechart-panel,grafana-worldmap-panel',
          GF_FEATURE_TOGGLES_ENABLE: 'traceqlEditor',
          PROJECT_NAME: config.projectName
        },
        volumes: [
          'grafana_data:/var/lib/grafana',
          './config/grafana/provisioning:/etc/grafana/provisioning:ro',
          './config/grafana/dashboards:/var/lib/grafana/dashboards:ro'
        ],
        networks: [networkName],
        restart: 'unless-stopped',
        depends_on: ['prometheus', 'loki'],
        logging: {
          driver: 'json-file',
          options: {
            'max-size': '10m',
            'max-file': '3',
            tag: `${config.projectName}_grafana`
          }
        }
      }
    },

    // Network configuration for inter-service communication - Requirements 6.3
    networks: {
      [networkName]: {
        driver: 'bridge',
        name: `${config.projectName}_ape_network`,
        ipam: {
          driver: 'default',
          config: [
            {
              subnet: networkSubnet,
              gateway: networkSubnet.replace('0.0/16', '0.1')
            }
          ]
        },
        driver_opts: {
          'com.docker.network.bridge.name': `br-${config.projectName}`,
          'com.docker.network.driver.mtu': '1500'
        }
      }
    },

    // Persistent volumes for data storage
    volumes: {
      prometheus_data: {},
      grafana_data: {},
      loki_data: {}
    }
  };
}

export function generatePrometheusConfig(config: SetupAnswers): any {
  return {
    global: {
      scrape_interval: '15s',
      evaluation_interval: '15s',
      external_labels: {
        cluster: 'ape-load-test',
        environment: 'production',
        project: config.projectName
      }
    },
    rule_files: ['rules.yml'],
    scrape_configs: [
      // Prometheus self-monitoring
      {
        job_name: 'prometheus',
        static_configs: [
          {
            targets: ['localhost:9090']
          }
        ],
        scrape_interval: '30s'
      },
      
      // cAdvisor for container metrics
      {
        job_name: 'cadvisor',
        static_configs: [
          {
            targets: ['cadvisor:8080']
          }
        ],
        scrape_interval: '15s',
        relabel_configs: [
          {
            source_labels: ['container_label_com_docker_compose_service'],
            target_label: 'ape_service'
          },
          {
            source_labels: ['container_label_com_docker_compose_project'],
            target_label: 'ape_project'
          },
          {
            source_labels: ['name'],
            regex: '/(.*)',
            target_label: 'container_name'
          }
        ]
      },
      
      // Node Exporter for host system metrics
      {
        job_name: 'node-exporter',
        static_configs: [
          {
            targets: ['node_exporter:9100']
          }
        ],
        scrape_interval: '15s'
      },
      
      // MCP Gateway metrics
      {
        job_name: 'mcp-gateway',
        static_configs: [
          {
            targets: ['mcp_gateway:8001']
          }
        ],
        metrics_path: '/metrics',
        scrape_interval: '5s',
        scrape_timeout: '10s'
      },
      
      // Cerebras Proxy metrics
      {
        job_name: 'cerebras-proxy',
        static_configs: [
          {
            targets: ['cerebras_proxy:8002']
          }
        ],
        metrics_path: '/metrics',
        scrape_interval: '5s',
        scrape_timeout: '10s'
      },
      
      // APE Agent metrics (dynamic discovery)
      {
        job_name: 'ape-agents',
        docker_sd_configs: [
          {
            host: 'unix:///var/run/docker.sock',
            port: 8000,
            refresh_interval: '15s',
            filters: [
              {
                name: 'label',
                values: ['com.docker.compose.service=llama-agent']
              }
            ]
          }
        ],
        relabel_configs: [
          {
            source_labels: ['__meta_docker_port_public'],
            regex: '8000',
            action: 'keep'
          },
          {
            target_label: 'job',
            replacement: 'ape-agent'
          },
          {
            source_labels: ['__meta_docker_container_name'],
            regex: '.*_llama-agent_([0-9]+)',
            target_label: 'agent_id',
            replacement: 'agent-${1}'
          },
          {
            source_labels: ['__meta_docker_container_label_com_docker_compose_service'],
            target_label: 'service_name'
          },
          {
            source_labels: ['__meta_docker_container_id'],
            target_label: 'container_id',
            regex: '(.{12}).*',
            replacement: '${1}'
          }
        ],
        scrape_interval: '5s',
        metrics_path: '/metrics',
        scrape_timeout: '10s'
      }
    ]
  };
}

export function generatePromtailConfig(_config: SetupAnswers): any {
  return {
    server: {
      http_listen_port: 9080,
      grpc_listen_port: 0
    },
    positions: {
      filename: '/tmp/positions.yaml'
    },
    clients: [
      {
        url: 'http://loki:3100/loki/api/v1/push'
      }
    ],
    scrape_configs: [
      {
        job_name: 'containers',
        static_configs: [
          {
            targets: ['localhost'],
            labels: {
              job: 'containerlogs',
              __path__: '/var/lib/docker/containers/*/*log'
            }
          }
        ],
        pipeline_stages: [
          {
            json: {
              expressions: {
                output: 'log',
                stream: 'stream',
                attrs: 'attrs'
              }
            }
          },
          {
            json: {
              expressions: {
                tag: 'attrs.tag'
              },
              source: 'attrs'
            }
          },
          {
            regex: {
              expression: '^(?P<container_name>(?:[^|]*))',
              source: 'tag'
            }
          },
          {
            timestamp: {
              format: 'RFC3339Nano',
              source: 'time'
            }
          },
          {
            labels: {
              stream: '',
              container_name: ''
            }
          },
          {
            output: {
              source: 'output'
            }
          }
        ]
      }
    ]
  };
}

// Optimized resource calculation for Requirements 6.1, 6.4 - scaling to 1000+ agents
function calculateAgentResources(agentCount: number): any {
  // Dynamic resource allocation based on agent count and system capacity
  let memoryLimit = '512M';
  let cpuLimit = '0.5';
  let memoryReservation = '256M';
  let cpuReservation = '0.25';
  
  // Optimized resource scaling for high-density deployments
  if (agentCount > 500) {
    // Ultra-high scale: minimal per-agent resources for 1000+ agents
    memoryLimit = '128M';
    cpuLimit = '0.1';
    memoryReservation = '64M';
    cpuReservation = '0.05';
  } else if (agentCount > 200) {
    // High scale: reduced resources for 200-500 agents
    memoryLimit = '192M';
    cpuLimit = '0.15';
    memoryReservation = '96M';
    cpuReservation = '0.08';
  } else if (agentCount > 100) {
    // Medium-high scale: balanced resources for 100-200 agents
    memoryLimit = '256M';
    cpuLimit = '0.25';
    memoryReservation = '128M';
    cpuReservation = '0.1';
  } else if (agentCount > 50) {
    // Medium scale: standard resources for 50-100 agents
    memoryLimit = '384M';
    cpuLimit = '0.35';
    memoryReservation = '192M';
    cpuReservation = '0.15';
  }
  // Default resources for <= 50 agents remain unchanged

  return {
    limits: {
      memory: memoryLimit,
      cpus: cpuLimit
    },
    reservations: {
      memory: memoryReservation,
      cpus: cpuReservation
    },
    // Additional optimization settings
    update_config: {
      parallelism: Math.min(agentCount, 10), // Update max 10 agents at once
      delay: '2s',
      failure_action: 'rollback',
      monitor: '10s'
    },
    restart_policy: {
      condition: 'on-failure',
      delay: '3s',
      max_attempts: 3,
      window: '60s'
    }
  };
}

// Helper function to generate unique network subnet for each project - Requirements 6.3
function generateNetworkSubnet(projectName: string): string {
  // Generate a deterministic subnet based on project name hash
  let hash = 0;
  for (let i = 0; i < projectName.length; i++) {
    const char = projectName.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  
  // Use hash to generate a subnet in the 172.20-30.x.x range
  const subnetBase = 20 + (Math.abs(hash) % 11); // 172.20.0.0 to 172.30.0.0
  return `172.${subnetBase}.0.0/16`;
}
// Enhanced Docker Compose generation with environment specific configurations
export function generateDockerComposeWithEnvironment(config: SetupAnswers, environment: 'development' | 'staging' | 'production' = 'production'): DockerComposeConfig {
  const baseConfig = generateDockerCompose(config);
  
  // Apply environment-specific optimizations
  switch (environment) {
    case 'development':
      return applyDevelopmentConfig(baseConfig, config);
    case 'staging':
      return applyStagingConfig(baseConfig, config);
    case 'production':
    default:
      return applyProductionConfig(baseConfig, config);
  }
}

function applyDevelopmentConfig(config: DockerComposeConfig, _setupConfig: SetupAnswers): DockerComposeConfig {
  // Development optimizations: faster startup, more verbose logging, hot reload
  const devConfig = { ...config };
  
  // Enable debug logging for all services
  Object.keys(devConfig.services).forEach(serviceName => {
    const service = devConfig.services[serviceName];
    if (service.environment) {
      service.environment.LOG_LEVEL = 'debug';
    }
  });
  
  // Add development-specific volumes for hot reload
  if (devConfig.services.mcp_gateway) {
    devConfig.services.mcp_gateway.volumes = [
      ...devConfig.services.mcp_gateway.volumes,
      './src:/app/src:ro' // Hot reload for development
    ];
  }
  
  return devConfig;
}

function applyStagingConfig(config: DockerComposeConfig, _setupConfig: SetupAnswers): DockerComposeConfig {
  // Staging optimizations: production-like but with enhanced monitoring
  const stagingConfig = { ...config };
  
  // Add staging-specific environment variables
  Object.keys(stagingConfig.services).forEach(serviceName => {
    const service = stagingConfig.services[serviceName];
    if (service.environment) {
      service.environment.ENVIRONMENT = 'staging';
      service.environment.METRICS_DETAILED = 'true';
    }
  });
  
  return stagingConfig;
}

function applyProductionConfig(config: DockerComposeConfig, _setupConfig: SetupAnswers): DockerComposeConfig {
  // Production optimizations: security, performance, reliability
  const prodConfig = { ...config };
  
  // Add production security headers and optimizations
  Object.keys(prodConfig.services).forEach(serviceName => {
    const service = prodConfig.services[serviceName];
    if (service.environment) {
      service.environment.ENVIRONMENT = 'production';
      service.environment.SECURITY_HEADERS = 'true';
    }
    
    // Add security options for production
    service.security_opt = ['no-new-privileges:true'];
    service.read_only = serviceName !== 'prometheus' && serviceName !== 'grafana' && serviceName !== 'loki'; // Allow writes only for data services
  });
  
  return prodConfig;
}

// Utility function to validate Docker Compose configuration
export function validateDockerComposeConfig(config: DockerComposeConfig): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  
  // Validate required services
  const requiredServices = ['mcp_gateway', 'cerebras_proxy', 'llama_agent', 'prometheus', 'grafana'];
  for (const service of requiredServices) {
    if (!config.services[service]) {
      errors.push(`Missing required service: ${service}`);
    }
  }
  
  // Validate network configuration
  if (!config.networks || Object.keys(config.networks).length === 0) {
    errors.push('No networks defined');
  }
  
  // Validate volumes for data persistence
  if (!config.volumes || !config.volumes.prometheus_data || !config.volumes.grafana_data) {
    errors.push('Missing required persistent volumes');
  }
  
  // Validate service dependencies
  if (config.services.llama_agent && !config.services.llama_agent.depends_on) {
    errors.push('llama_agent service missing required dependencies');
  }
  
  return {
    valid: errors.length === 0,
    errors
  };
}

// Graceful scaling and shutdown utilities for Requirements 6.1, 6.4
export interface ScalingConfig {
  currentAgents: number;
  targetAgents: number;
  maxConcurrentUpdates: number;
  updateDelay: number;
  healthCheckTimeout: number;
}

export function generateScalingStrategy(config: ScalingConfig): any {
  const isScalingUp = config.targetAgents > config.currentAgents;
  const agentDifference = Math.abs(config.targetAgents - config.currentAgents);
  
  // Calculate optimal batch size for scaling operations
  const batchSize = Math.min(
    config.maxConcurrentUpdates,
    Math.max(1, Math.ceil(agentDifference / 10)) // Scale in 10% increments
  );
  
  return {
    strategy: isScalingUp ? 'scale-up' : 'scale-down',
    batchSize,
    totalBatches: Math.ceil(agentDifference / batchSize),
    updateDelay: `${config.updateDelay}s`,
    healthCheckTimeout: `${config.healthCheckTimeout}s`,
    rollbackOnFailure: true,
    // Scaling-specific configurations
    ...(isScalingUp && {
      // Scale up: start new containers gradually
      parallelism: batchSize,
      order: 'start-first'
    }),
    ...(!isScalingUp && {
      // Scale down: stop containers gracefully
      parallelism: Math.min(batchSize, 5), // Slower scale-down to prevent service disruption
      order: 'stop-first',
      gracefulShutdownTimeout: '15s'
    })
  };
}

export function generateGracefulShutdownConfig(agentCount: number): any {
  // Calculate shutdown timeouts based on agent count
  const baseTimeout = 10;
  const scalingFactor = Math.ceil(agentCount / 100);
  const shutdownTimeout = Math.min(baseTimeout + scalingFactor * 5, 60); // Max 60s
  
  return {
    // Graceful shutdown configuration
    stop_grace_period: `${shutdownTimeout}s`,
    stop_signal: 'SIGTERM',
    
    // Health check during shutdown
    healthcheck_during_shutdown: {
      test: ['CMD', 'curl', '-f', 'http://localhost:8000/health'],
      interval: '5s',
      timeout: '3s',
      retries: 2
    },
    
    // Resource cleanup
    cleanup_config: {
      remove_volumes: false, // Preserve data volumes
      remove_networks: false, // Keep networks for potential restart
      force_kill_timeout: `${shutdownTimeout + 10}s`
    }
  };
}

// Resource monitoring configuration for Requirements 6.4
export function generateResourceMonitoringConfig(agentCount: number): any {
  return {
    // Resource limits monitoring
    resource_monitoring: {
      enabled: true,
      interval: '10s',
      thresholds: {
        memory_usage_percent: 85,
        cpu_usage_percent: 80,
        disk_usage_percent: 90
      },
      alerts: {
        high_memory: agentCount > 100,
        high_cpu: agentCount > 100,
        container_restart: true
      }
    },
    
    // Agent scaling metrics
    scaling_metrics: {
      concurrent_agents: {
        target: agentCount,
        tolerance: 0.05, // 5% tolerance
        measurement_window: '30s'
      },
      resource_utilization: {
        memory_per_agent: agentCount > 500 ? '128M' : '256M',
        cpu_per_agent: agentCount > 500 ? '0.1' : '0.25',
        network_bandwidth: '10Mbps'
      }
    },
    
    // Performance optimization
    performance_tuning: {
      container_startup_stagger: Math.min(10, Math.ceil(agentCount / 50)), // Stagger startup
      health_check_optimization: agentCount > 100,
      log_compression: agentCount > 100,
      metrics_sampling_rate: agentCount > 500 ? 0.1 : 1.0 // Sample 10% of metrics for large deployments
    }
  };
}