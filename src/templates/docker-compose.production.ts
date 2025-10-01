import { SetupAnswers } from '../commands/setup';

/**
 * Production-optimized Docker Compose configuration
 * Implements optimizations for Requirements 6.1, 6.4
 */
export function generateProductionOverride(config: SetupAnswers): any {
  const isHighScale = config.agentCount > 500;
  const isMediumScale = config.agentCount > 100;
  
  return {
    version: '3.8',
    services: {
      // Production-optimized Llama Agent configuration
      llama_agent: {
        // Production resource limits and optimizations
        deploy: {
          resources: {
            limits: {
              memory: isHighScale ? '128M' : isMediumScale ? '256M' : '512M',
              cpus: isHighScale ? '0.1' : isMediumScale ? '0.25' : '0.5'
            },
            reservations: {
              memory: isHighScale ? '64M' : isMediumScale ? '128M' : '256M',
              cpus: isHighScale ? '0.05' : isMediumScale ? '0.1' : '0.25'
            }
          },
          // Rolling update configuration for zero-downtime scaling
          update_config: {
            parallelism: Math.min(10, Math.ceil(config.agentCount / 20)),
            delay: '3s',
            failure_action: 'rollback',
            monitor: '15s',
            max_failure_ratio: 0.1,
            order: 'start-first'
          },
          // Restart policy optimized for production
          restart_policy: {
            condition: 'on-failure',
            delay: '5s',
            max_attempts: 3,
            window: '120s'
          },
          // Placement constraints for optimal distribution
          placement: {
            constraints: ['node.role==worker'],
            preferences: [
              {
                spread: 'node.id'
              }
            ],
            max_replicas_per_node: Math.max(1, Math.floor(50 / Math.sqrt(config.agentCount)))
          }
        },
        // Production environment variables
        environment: {
          // Memory optimization
          PYTHONOPTIMIZE: '2',
          PYTHONDONTWRITEBYTECODE: '1',
          PYTHONUNBUFFERED: '1',
          MALLOC_ARENA_MAX: '2',
          
          // Agent-specific production settings
          AGENT_PRODUCTION_MODE: 'true',
          AGENT_BATCH_SIZE: Math.min(config.agentCount, 50),
          AGENT_STARTUP_DELAY: '${RANDOM_DELAY:-0}', // Will be set by startup script
          
          // Connection pooling optimization
          HTTP_POOL_CONNECTIONS: isHighScale ? '5' : '10',
          HTTP_POOL_MAXSIZE: isHighScale ? '10' : '20',
          HTTP_RETRIES: '3',
          HTTP_TIMEOUT: '30',
          
          // Resource monitoring
          MEMORY_MONITORING_ENABLED: 'true',
          CPU_MONITORING_ENABLED: 'true',
          METRICS_COLLECTION_INTERVAL: '30',
          
          // Graceful shutdown
          GRACEFUL_SHUTDOWN_TIMEOUT: '15',
          SHUTDOWN_SIGNAL_TIMEOUT: '5'
        },
        // Production logging configuration
        logging: {
          driver: 'json-file',
          options: {
            'max-size': isHighScale ? '5m' : '10m',
            'max-file': isHighScale ? '2' : '3',
            'compress': 'true',
            'labels': 'ape.project,ape.service,ape.scale'
          }
        },
        // Production health check
        healthcheck: {
          test: ['CMD', 'python', '-c', 'import requests; requests.get("http://localhost:8000/health", timeout=3)'],
          interval: '15s',
          timeout: '5s',
          retries: 2,
          start_period: '30s'
        },
        // Security settings
        security_opt: ['no-new-privileges:true'],
        read_only: true,
        tmpfs: ['/tmp', '/app/tmp'],
        
        // Production labels
        labels: [
          `ape.project=${config.projectName}`,
          `ape.service=llama-agent`,
          `ape.scale=${config.agentCount}`,
          'ape.environment=production',
          'ape.monitoring=enabled',
          'ape.backup=false'
        ]
      },

      // Production-optimized MCP Gateway
      mcp_gateway: {
        deploy: {
          resources: {
            limits: {
              memory: isHighScale ? '1G' : '512M',
              cpus: isHighScale ? '2.0' : '1.0'
            },
            reservations: {
              memory: isHighScale ? '512M' : '256M',
              cpus: isHighScale ? '1.0' : '0.5'
            }
          },
          // Single replica with high availability
          replicas: 1,
          placement: {
            constraints: ['node.role==manager']
          }
        },
        environment: {
          // Production optimization
          NODE_ENV: 'production',
          PYTHONOPTIMIZE: '2',
          
          // High-concurrency settings
          MAX_WORKERS: Math.min(4, Math.max(1, Math.ceil(config.agentCount / 250))),
          WORKER_CLASS: 'uvicorn.workers.UvicornWorker',
          CONNECTION_POOL_SIZE: Math.min(200, config.agentCount * 2),
          KEEP_ALIVE_TIMEOUT: '5',
          REQUEST_TIMEOUT: '30',
          
          // Rate limiting for production
          RATE_LIMIT_ENABLED: 'true',
          RATE_LIMIT_PER_MINUTE: `${config.agentCount * 120}`, // 2 requests per agent per second
          BURST_LIMIT: `${config.agentCount * 10}`,
          
          // Security settings
          CORS_ENABLED: 'false', // Disable CORS in production
          SECURITY_HEADERS: 'true',
          
          // Monitoring
          METRICS_ENABLED: 'true',
          DETAILED_METRICS: isHighScale ? 'false' : 'true', // Reduce metrics overhead for high scale
          
          // Memory management
          MEMORY_LIMIT_MB: isHighScale ? '1024' : '512',
          GC_THRESHOLD: '100'
        },
        // Production security
        security_opt: ['no-new-privileges:true'],
        read_only: true,
        tmpfs: ['/tmp', '/app/tmp'],
        
        labels: [
          `ape.project=${config.projectName}`,
          'ape.service=mcp-gateway',
          'ape.environment=production',
          'ape.monitoring=enabled',
          'ape.backup=false'
        ]
      },

      // Production-optimized Cerebras Proxy
      cerebras_proxy: {
        deploy: {
          resources: {
            limits: {
              memory: isHighScale ? '1G' : '512M',
              cpus: isHighScale ? '2.0' : '1.0'
            },
            reservations: {
              memory: isHighScale ? '512M' : '256M',
              cpus: isHighScale ? '1.0' : '0.5'
            }
          },
          replicas: 1,
          placement: {
            constraints: ['node.role==manager']
          }
        },
        environment: {
          // Production optimization
          PYTHONOPTIMIZE: '2',
          
          // High-performance settings
          CONNECTION_POOL_SIZE: Math.min(100, config.agentCount),
          KEEP_ALIVE_CONNECTIONS: Math.min(50, Math.ceil(config.agentCount / 10)),
          ASYNC_WORKERS: Math.min(8, Math.max(1, Math.ceil(config.agentCount / 100))),
          
          // Inference optimization
          BATCH_SIZE: isHighScale ? '10' : '5',
          INFERENCE_TIMEOUT: '10',
          RETRY_ATTEMPTS: '3',
          RETRY_BACKOFF: '1.5',
          
          // Memory management
          MEMORY_LIMIT_MB: isHighScale ? '1024' : '512',
          CACHE_SIZE_MB: isHighScale ? '256' : '128',
          
          // Monitoring
          METRICS_ENABLED: 'true',
          PERFORMANCE_TRACKING: 'true'
        },
        // Production security
        security_opt: ['no-new-privileges:true'],
        read_only: true,
        tmpfs: ['/tmp', '/app/tmp'],
        
        labels: [
          `ape.project=${config.projectName}`,
          'ape.service=cerebras-proxy',
          'ape.environment=production',
          'ape.monitoring=enabled',
          'ape.backup=false'
        ]
      },

      // Production observability stack optimizations
      prometheus: {
        deploy: {
          resources: {
            limits: {
              memory: isHighScale ? '2G' : '1G',
              cpus: '1.0'
            },
            reservations: {
              memory: isHighScale ? '1G' : '512M',
              cpus: '0.5'
            }
          },
          placement: {
            constraints: ['node.role==manager']
          }
        },
        command: [
          '--config.file=/etc/prometheus/prometheus.yml',
          '--storage.tsdb.path=/prometheus',
          '--web.console.libraries=/etc/prometheus/console_libraries',
          '--web.console.templates=/etc/prometheus/consoles',
          '--storage.tsdb.retention.time=7d', // Reduced retention for high scale
          '--storage.tsdb.retention.size=10GB',
          '--web.enable-lifecycle',
          '--web.enable-admin-api',
          // Performance optimizations
          '--query.max-concurrency=20',
          '--query.max-samples=50000000',
          '--storage.tsdb.min-block-duration=2h',
          '--storage.tsdb.max-block-duration=25h'
        ]
      },

      grafana: {
        deploy: {
          resources: {
            limits: {
              memory: '512M',
              cpus: '0.5'
            },
            reservations: {
              memory: '256M',
              cpus: '0.25'
            }
          },
          placement: {
            constraints: ['node.role==manager']
          }
        },
        environment: {
          // Production Grafana settings
          GF_SECURITY_ADMIN_PASSWORD: '${GRAFANA_ADMIN_PASSWORD:-ape-admin}',
          GF_USERS_ALLOW_SIGN_UP: 'false',
          GF_USERS_ALLOW_ORG_CREATE: 'false',
          GF_AUTH_ANONYMOUS_ENABLED: 'false',
          
          // Performance optimization
          GF_DATABASE_MAX_IDLE_CONN: '2',
          GF_DATABASE_MAX_OPEN_CONN: '10',
          GF_DATABASE_CONN_MAX_LIFETIME: '14400',
          
          // Security
          GF_SECURITY_DISABLE_GRAVATAR: 'true',
          GF_SECURITY_COOKIE_SECURE: 'true',
          GF_SECURITY_COOKIE_SAMESITE: 'strict',
          
          // Alerting optimization
          GF_ALERTING_EXECUTE_ALERTS: 'true',
          GF_ALERTING_MAX_ATTEMPTS: '3',
          GF_UNIFIED_ALERTING_ENABLED: 'true'
        }
      },

      // Optimized log collection for high scale
      promtail: {
        deploy: {
          resources: {
            limits: {
              memory: '256M',
              cpus: '0.25'
            },
            reservations: {
              memory: '128M',
              cpus: '0.1'
            }
          }
        },
        environment: {
          // Log processing optimization
          PROMTAIL_BATCH_SIZE: isHighScale ? '1048576' : '102400', // 1MB vs 100KB
          PROMTAIL_BATCH_WAIT: isHighScale ? '5s' : '1s',
          PROMTAIL_MAX_RETRIES: '3',
          
          // Memory optimization
          PROMTAIL_MEMORY_LIMIT: '256M'
        }
      },

      loki: {
        deploy: {
          resources: {
            limits: {
              memory: isHighScale ? '2G' : '1G',
              cpus: '1.0'
            },
            reservations: {
              memory: isHighScale ? '1G' : '512M',
              cpus: '0.5'
            }
          },
          placement: {
            constraints: ['node.role==manager']
          }
        },
        environment: {
          // Loki optimization for high scale
          LOKI_RETENTION_PERIOD: isHighScale ? '72h' : '168h', // Reduced retention for high scale
          LOKI_MAX_CHUNK_AGE: '2h',
          LOKI_CHUNK_TARGET_SIZE: isHighScale ? '2097152' : '1048576', // 2MB vs 1MB
          LOKI_MAX_TRANSFER_RETRIES: '3'
        }
      }
    },

    // Production network optimization
    networks: {
      [`${config.projectName}_network`]: {
        driver: 'bridge',
        driver_opts: {
          'com.docker.network.bridge.name': `br-${config.projectName}`,
          'com.docker.network.driver.mtu': '1500',
          // Production network optimizations
          'com.docker.network.bridge.enable_icc': 'true',
          'com.docker.network.bridge.enable_ip_masquerade': 'true',
          'com.docker.network.bridge.host_binding_ipv4': '0.0.0.0'
        }
      }
    }
  };
}

/**
 * Generate production environment file
 */
export function generateProductionEnv(config: SetupAnswers): string {
  const isHighScale = config.agentCount > 500;
  
  return `# APE Production Environment Configuration
# Generated for ${config.agentCount} agents

# Docker Compose
COMPOSE_PROJECT_NAME=${config.projectName}
COMPOSE_FILE=ape.docker-compose.yml:ape.docker-compose.production.yml

# Resource Optimization
APE_SCALE_MODE=${isHighScale ? 'high' : 'standard'}
APE_AGENT_COUNT=${config.agentCount}
APE_MEMORY_PER_AGENT=${isHighScale ? '128M' : '256M'}
APE_CPU_PER_AGENT=${isHighScale ? '0.1' : '0.25'}

# Performance Tuning
APE_BATCH_SIZE=${Math.min(config.agentCount, 50)}
APE_STARTUP_STAGGER=${Math.min(10, Math.ceil(config.agentCount / 50))}
APE_HEALTH_CHECK_INTERVAL=${isHighScale ? '30s' : '15s'}

# Monitoring
APE_METRICS_ENABLED=true
APE_DETAILED_METRICS=${isHighScale ? 'false' : 'true'}
APE_LOG_LEVEL=info
APE_LOG_COMPRESSION=${isHighScale ? 'true' : 'false'}

# Security
APE_SECURITY_MODE=production
APE_READ_ONLY_CONTAINERS=true
APE_NO_NEW_PRIVILEGES=true

# Grafana (Change in production!)
GRAFANA_ADMIN_PASSWORD=ape-admin-${Math.random().toString(36).substring(7)}

# Cerebras API
CEREBRAS_API_KEY=\${CEREBRAS_API_KEY}

# Resource Limits
DOCKER_DEFAULT_ULIMIT_NOFILE=65536:65536
DOCKER_DEFAULT_ULIMIT_NPROC=8192:8192
`;
}