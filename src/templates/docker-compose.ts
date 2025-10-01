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
          CONFIG_PATH: '/app/config/mcp-gateway.json'
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
        depends_on: ['cerebras_proxy']
      },

      // Cerebras Proxy Service - Requirements 2.1, 2.3
      cerebras_proxy: {
        image: 'ape/cerebras-proxy:latest',
        container_name: `${config.projectName}_cerebras_proxy`,
        ports: ['8000:8000'],
        environment: {
          CEREBRAS_API_KEY: '${CEREBRAS_API_KEY}',
          LOG_LEVEL: 'info',
          METRICS_ENABLED: 'true'
        },
        networks: [networkName],
        restart: 'unless-stopped',
        healthcheck: {
          test: ['CMD', 'curl', '-f', 'http://localhost:8000/health'],
          interval: '30s',
          timeout: '10s',
          retries: 3,
          start_period: '30s'
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
          SESSION_TIMEOUT: '300'
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
          resources: {
            limits: {
              memory: '512M',
              cpus: '0.5'
            },
            reservations: {
              memory: '256M',
              cpus: '0.25'
            }
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
        restart: 'unless-stopped'
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
        depends_on: ['loki']
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
          '--web.enable-lifecycle'
        ],
        volumes: [
          './config/prometheus.yml:/etc/prometheus/prometheus.yml:ro',
          'prometheus_data:/prometheus'
        ],
        networks: [networkName],
        restart: 'unless-stopped'
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
        restart: 'unless-stopped'
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
        restart: 'unless-stopped'
      },

      // Grafana for visualization - Requirements 4.3, 4.6
      grafana: {
        image: 'grafana/grafana:10.1.0',
        container_name: `${config.projectName}_grafana`,
        ports: ['3001:3000'],
        environment: {
          GF_SECURITY_ADMIN_USER: 'admin',
          GF_SECURITY_ADMIN_PASSWORD: 'ape-admin',
          GF_USERS_ALLOW_SIGN_UP: 'false'
        },
        volumes: [
          'grafana_data:/var/lib/grafana',
          './config/grafana/provisioning:/etc/grafana/provisioning:ro',
          './config/grafana/dashboards:/var/lib/grafana/dashboards:ro'
        ],
        networks: [networkName],
        restart: 'unless-stopped',
        depends_on: ['prometheus', 'loki']
      }
    },

    // Network configuration for inter-service communication - Requirements 6.3
    networks: {
      [networkName]: {
        driver: 'bridge',
        ipam: {
          config: [
            {
              subnet: '172.20.0.0/16'
            }
          ]
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