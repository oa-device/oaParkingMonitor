# oaParkingMonitor MVP Scripts

Simplified scripts for MVP deployment and management.

## Available Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| **`helpers.sh`** | Shared utilities library | `source scripts/helpers.sh` |
| **`setup.sh`** | Initial project setup | `./scripts/setup.sh` |
| **`validate.sh`** | MVP validation | `./scripts/validate.sh` |
| **`start.sh`** | Service startup | `./scripts/start.sh` |
| **`health_check.sh`** | Health monitoring | `./scripts/health_check.sh` |

## MVP Quick Start

```bash
# Initial setup
./scripts/setup.sh

# Validate MVP environment
./scripts/validate.sh

# Start MVP service
./scripts/start.sh

# Check health
./scripts/health_check.sh
```

## Shared Utilities (`helpers.sh`)

The `helpers.sh` library provides consistent functionality across all scripts:

### **Logging Functions**
```bash
log_success "Operation completed"
log_info "Information message"
log_warn "Warning message" 
log_error "Error message"
log_debug "Debug message" (requires DEBUG=1)
log_progress "Progress update"
log_header "Section Header"
```

### **System Detection**
```bash
is_macos                    # Check if running on macOS
is_apple_silicon           # Check for Apple Silicon
get_macos_version          # Get macOS version
command_exists cmd         # Check if command available
check_python_version       # Validate Python 3.12+
```

### **Project Management**
```bash
cd_project_root           # Change to project root
get_environment           # Get current environment
get_config_file           # Get config file for env
check_config_file         # Validate config exists
validate_yaml file        # Check YAML syntax
```

### 🐍 **Virtual Environment**
```bash
check_uv                  # Verify uv available
setup_venv               # Create virtual environment
activate_venv            # Activate venv
check_dependencies       # Validate critical deps
```

### **Service Management**
```bash
is_service_running       # Check if service active
get_service_pid          # Get service process ID
stop_service            # Gracefully stop service
```

### **API Communication**
```bash
api_call "/endpoint" "desc" [host] [port] [timeout]
parse_json "$response" ".path" "default"
check_connectivity [host] [port] [timeout]
```

### 📊 **Utilities**
```bash
format_duration seconds   # Human readable time
timestamp                # Current timestamp
create_runtime_dirs      # Setup runtime directories
check_disk_space [path] [min_gb]
cleanup_temp_files       # Clean temporary files
```

## Script Features

### **Consistent Interface**
- Unified command-line argument parsing
- Standardized help messages (`--help`)
- Common environment variable support
- Professional error handling and logging

### **Environment Awareness**
```bash
export PARKING_MONITOR_ENV=production  # or staging, development
export DEBUG=1                        # Enable debug logging
export LOG_FILE=/path/to/logfile      # Optional file logging
```

### ⚡ **Performance Optimizations**
- Apple Silicon detection with MPS optimization
- Batch operations for efficiency
- Resource monitoring and validation
- Intelligent caching and cleanup

### **Production Readiness**
- Comprehensive validation checks
- Health monitoring with thresholds
- Error tracking and recovery
- Security considerations

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PARKING_MONITOR_ENV` | Environment (production/staging/development) | `production` |
| `DEBUG` | Enable debug logging (0/1) | `0` |
| `LOG_FILE` | Log to file in addition to stdout | (none) |
| `API_URL` | Override API URL for health checks | `http://localhost:9091` |
| `HEALTH_CHECK_TIMEOUT` | Health check timeout in seconds | `10` |

## Script Workflow

### Development Workflow
```bash
1. ./scripts/setup.sh           # Initial setup
2. ./scripts/validate.sh        # Validate environment  
3. ./scripts/start.sh           # Start development server
4. ./scripts/health_check.sh    # Verify operation
```

### Production Deployment
```bash
1. export PARKING_MONITOR_ENV=production
2. ./scripts/validate.sh                    # Pre-deployment validation
3. ./scripts/start.sh -c production.yaml    # Production startup
4. ./scripts/health_check.sh --detailed     # Comprehensive health check
```

### Continuous Integration
```bash
# Validation in CI/CD pipelines
./scripts/validate.sh && echo "Ready for deployment"

# Health monitoring in production
./scripts/health_check.sh --detailed || alert_ops_team
```

## Error Handling

All scripts follow consistent error handling patterns:

- **Exit Code 0**: Success
- **Exit Code 1**: Warning (operation may continue)
- **Exit Code 2**: Error (operation should stop)

### Log Levels
- **SUCCESS** [OK]: Operations completed successfully
- **INFO** [INFO]: Informational messages
- **WARN** [WARN]: Warnings that don't prevent operation
- **ERROR** [FAIL]: Errors that require attention
- **PROGRESS** [PROGRESS]: Progress updates during operations
- **DEBUG** [DEBUG]: Detailed debug information (DEBUG=1 only)

## Integration

### With oaAnsible
Scripts are designed to work seamlessly with Ansible deployment:
```yaml
- name: Setup parking monitor
  command: ./scripts/setup.sh --skip-models
  args:
    chdir: "{{ parking_monitor_path }}"

- name: Validate deployment
  command: ./scripts/validate.sh
  args:
    chdir: "{{ parking_monitor_path }}"
```

### With oaDashboard
Health check endpoints integrate with oaDashboard monitoring:
```bash
# Health data compatible with oaDashboard
curl http://localhost:9091/api/health/detailed | jq '.health_score'
```

### With System Services
Scripts support LaunchAgent integration on macOS:
```bash
# Service management
./scripts/start.sh     # Direct execution
launchctl load com.orangead.parking-monitor.plist  # System service
```

## MVP Simplifications

The MVP removes complex features:
- Permission management scripts (removed)
- Security audit scripts (removed)
- Complex alias configurations (removed)
- Multi-environment management (simplified to single mvp.yaml)

For full production deployment, use the oaAnsible deployment system.