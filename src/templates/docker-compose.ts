import { SetupAnswers } from '../commands/setup';

export interface DockerComposeConfig {
  version: string;
  services: Record<string, any>;
  networks: Record<string, any>;
  volumes?: Record<string, any>;
}

export function generateDockerCompose(config: SetupAnswers): DockerComposeConfig {
  const targetUrl = new URL(config.targetUrl);
  const networkName = `${config.projectName}_network`;
  
  // Dynamic scaling configuration based on user inputs - Requirements 6.1, 6.4
  const agentResourceLimits = calculateAgentResources(config.agentCount);
  const networkSubnet = generateNetworkSubnet(config.projectName);

  return {
    version: '3.8',
    services: {
      // MCP Gateway Service - Requirements 6.2, 6.3
      mcp_gateway: {
        image: 'ape/mcp-gateway:latest',
        container_name: `${config.projectName}_mcp_gateway`,
        ports: ['3000:3000'],
        environment: {
          NODE_ENV: 'production',
          LOG_LEVEL: 'info',
          CONFIG_PATH: '/app/config/mcp-gateway.json',
          PROJECT_NAME: config.projectName,
          TARGET_URL: config.targetUrl,
          MAX_CONCURRENT_AGENTS: `${config.agentCount}`,
          RATE_LIMIT_ENABLED: 'true',
          CORS_ENABLED: 'true'
        },
        volumes: [
          './ape.mcp-gateway.json:/app/config/mcp-gateway.json:ro'
        ],
        networks: [networkName],
        restart: 'unless-stopped',
        healthcheck: {
          test: ['CMD', 'curl', '-f', 'http://localhost:3000/health'],
          interval: '30s',
          timeout: '10s',
          retries: 3,
          start_period: '40s'
        },
        depends_on: ['cerebras_proxy'],
        logging: {
          driver: 'json-file',
          options: {
            'max-size': '10m',
            'max-file': '3',
            tag: `${config.projectName}_mcp_gateway`
          }
        }
      },

      // Cerebras Proxy Service - Requirements 2.1, 2.3
      cerebras_proxy: {
        image: 'ape/cerebras-proxy:latest',
        container_name: `${config.projectName}_cerebras_proxy`,
        ports: ['8000:8000'],
        environment: {
          CEREBRAS_API_KEY: '${CEREBRAS_API_KEY}',
          LOG_LEVEL: 'info',
          METRICS_ENABLED: 'true',
          MAX_CONCURRENT_REQUESTS: `${config.agentCount * 2}`, // Allow 2x agent count for burst
          TTFT_TARGET_MS: '500', // Target Time-to-First-Token in milliseconds
          REQUEST_TIMEOUT: '10000', // 10 second timeout for inference
          RATE_LIMIT_PER_MINUTE: `${config.agentCount * 60}` // 60 requests per agent per minute
        },
        networks: [networkName],
        restart: 'unless-stopped',
        healthcheck: {
          test: ['CMD', 'curl', '-f', 'http://localhost:8000/health'],
          interval: '30s',
          timeout: '10s',
          retries: 3,
          start_period: '30s'
        },
        logging: {
          driver: 'json-file',
          options: {
            'max-size': '10m',
            'max-file': '3',
            tag: `${config.projectName}_cerebras_proxy`
          }
        }
      },

      // Llama Agent Service - Requirements 1.1, 6.1, 6.4
      llama_agent: {
        image: 'ape/llama-agent:latest',
        environment: {
          MCP_GATEWAY_URL: 'http://mcp_gateway:3000',
          AGENT_GOAL: config.testGoal,
          TARGET_API_NAME: 'sut_api',
          LOG_LEVEL: 'info',
          SESSION_TIMEOUT: '300',
          AGENT_ID: '${HOSTNAME}', // Dynamic agent identification
          TEST_DURATION: `${config.testDuration}`,
          TARGET_ENDPOINTS: config.endpoints.join(','),
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
          restart_policy: {
            condition: 'on-failure',
            delay: '5s',
            max_attempts: 3,
            window: '120s'
          }
        },
        logging: {
          driver: 'json-file',
          options: {
            'max-size': '10m',
            'max-file': '3',
            tag: `${config.projectName}_agent_{{.Name}}`
          }
        }
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
      evaluation_interval: '15s'
    },
    rule_files: [],
    scrape_configs: [
      {
        job_name: 'prometheus',
        static_configs: [
          {
            targets: ['localhost:9090']
          }
        ]
      },
      {
        job_name: 'cadvisor',
        static_configs: [
          {
            targets: ['cadvisor:8080']
          }
        ]
      },
      {
        job_name: 'node-exporter',
        static_configs: [
          {
            targets: ['node_exporter:9100']
          }
        ]
      },
      {
        job_name: 'mcp-gateway',
        static_configs: [
          {
            targets: ['mcp_gateway:3000']
          }
        ],
        metrics_path: '/metrics'
      },
      {
        job_name: 'cerebras-proxy',
        static_configs: [
          {
            targets: ['cerebras_proxy:8000']
          }
        ],
        metrics_path: '/metrics'
      }
    ]
  };
}

export function generatePromtailConfig(config: SetupAnswers): any {
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

// Helper function to calculate agent resource limits based on agent count - Requirements 6.1, 6.4
function calculateAgentResources(agentCount: number): any {
  // Scale resources based on agent count for optimal performance
  let memoryLimit = '512M';
  let cpuLimit = '0.5';
  let memoryReservation = '256M';
  let cpuReservation = '0.25';

  if (agentCount > 100) {
    // For high-scale deployments, reduce per-agent resources
    memoryLimit = '256M';
    cpuLimit = '0.25';
    memoryReservation = '128M';
    cpuReservation = '0.1';
  } else if (agentCount > 50) {
    // Medium scale
    memoryLimit = '384M';
    cpuLimit = '0.35';
    memoryReservation = '192M';
    cpuReservation = '0.15';
  }

  return {
    limits: {
      memory: memoryLimit,
      cpus: cpuLimit
    },
    reservations: {
      memory: memoryReservation,
      cpus: cpuReservation
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

function applyDevelopmentConfig(config: DockerComposeConfig, setupConfig: SetupAnswers): DockerComposeConfig {
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

function applyStagingConfig(config: DockerComposeConfig, setupConfig: SetupAnswers): DockerComposeConfig {
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

function applyProductionConfig(config: DockerComposeConfig, setupConfig: SetupAnswers): DockerComposeConfig {
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