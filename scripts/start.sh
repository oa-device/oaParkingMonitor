#!/bin/bash
# oaParkingMonitor Service Startup Script
# Production-ready startup with Metal/MPS optimization for macOS

# Load shared utilities
# shellcheck source=helpers.sh
source "$(dirname "$0")/helpers.sh"

# Script-specific configuration
readonly SCRIPT_VERSION="2.0.0"
readonly DEFAULT_CONFIG_FILE="config/mvp.yaml"

# Command line argument parsing
parse_arguments() {
    local config_file="$DEFAULT_CONFIG_FILE"
    local port=""
    local log_level="INFO"
    local show_help=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -c|--config)
                config_file="$2"
                shift 2
                ;;
            -p|--port)
                port="$2"
                shift 2
                ;;
            --log-level)
                log_level="$2"
                shift 2
                ;;
            -h|--help)
                show_help=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_help=true
                break
                ;;
        esac
    done
    
    if [[ "$show_help" == "true" ]]; then
        show_usage
        exit 0
    fi
    
    # Export parsed arguments
    export CONFIG_FILE="$config_file"
    export PORT="$port"
    export LOG_LEVEL="$log_level"
}

show_usage() {
    cat << EOF
${SERVICE_NAME} Startup Script v${SCRIPT_VERSION}

Usage: $0 [OPTIONS]

Options:
  -c, --config FILE    Configuration file (default: $DEFAULT_CONFIG_FILE)
  -p, --port PORT      Port to run on (overrides config)
  --log-level LEVEL    Log level (DEBUG, INFO, WARNING, ERROR)
  -h, --help           Show this help message

Environment Variables:
  PARKING_MONITOR_ENV  Environment (production, staging, development)
  DEBUG               Enable debug output (0/1)

Examples:
  $0                                    # Start with default settings
  $0 -c staging.yaml --log-level DEBUG # Start with custom config and debug logging
  $0 -p 8091                           # Start on custom port

EOF
}

# System requirements validation
validate_system_requirements() {
    log_header "System Requirements"
    
    # macOS and Apple Silicon detection
    if is_macos; then
        log_success "Running on macOS $(get_macos_version)"
        
        if is_apple_silicon; then
            log_success "Apple Silicon detected - Metal Performance Shaders available"
            export PYTORCH_ENABLE_MPS_FALLBACK=1
        else
            log_info "Intel processor detected - using CPU/CUDA if available"
        fi
    else
        log_warn "Not running on macOS - Metal/MPS optimizations will be disabled"
    fi
    
    # Python version check
    check_python_version || return 1
    
    # Package manager check
    check_uv || return 1
    
    return 0
}

# Configuration validation
validate_configuration() {
    log_header "Configuration Validation"
    
    cd_project_root
    
    # Check if configuration file exists
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_error "Configuration file not found: $CONFIG_FILE"
        log_info "Available configurations:"
        find config/ -name "*.yaml" -type f | sed 's/^/  /' || true
        log_info "Run ./scripts/setup.sh first - using bundled config/mvp.yaml"
        return 1
    fi
    
    log_success "Configuration file: $CONFIG_FILE"
    
    # Validate YAML syntax
    validate_yaml "$CONFIG_FILE" || return 1
    
    return 0
}

# Dependencies setup and validation
setup_dependencies() {
    log_header "Dependencies Setup"
    
    cd_project_root
    
    # Setup virtual environment
    setup_venv || return 1
    
    # Check critical dependencies
    check_dependencies || return 1
    
    return 0
}

# Runtime environment preparation
prepare_runtime() {
    log_header "Runtime Preparation"
    
    # Create necessary directories
    create_runtime_dirs
    
    # Check system resources
    check_system_resources
    
    # Check disk space
    check_disk_space "$HOME" 1 || log_warn "Low disk space detected"
    
    return 0
}

# Service startup with monitoring
start_service() {
    log_header "Service Startup"
    
    cd_project_root
    activate_venv
    
    # Check if already running
    if is_service_running; then
        local pid
        pid=$(get_service_pid)
        log_warn "Service may already be running (PID: $pid)"
        
        echo
        log_info "Existing processes:"
        ps -p "$pid" -o pid,ppid,etime,command 2>/dev/null || true
        
        echo
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Startup cancelled by user"
            exit 0
        fi
    fi
    
    # Set environment variables for optimization
    export PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0
    export PYTORCH_MPS_LOW_WATERMARK_RATIO=0.0
    export OMP_NUM_THREADS=4
    export ENVIRONMENT=$(get_environment)
    
    # Build command arguments
    local args="--config $CONFIG_FILE --log-level $LOG_LEVEL"
    if [[ -n "$PORT" ]]; then
        args="$args --port $PORT"
        log_success "Custom port: $PORT"
    fi
    
    log_success "Log level: $LOG_LEVEL"
    log_success "Environment: $(get_environment)"
    
    echo
    log_progress "Starting ${SERVICE_NAME} service..."
    log_info "API will be available at http://localhost:${PORT:-$DEFAULT_PORT}"
    log_info "Health check: curl http://localhost:${PORT:-$DEFAULT_PORT}/health"
    log_info "Documentation: http://localhost:${PORT:-$DEFAULT_PORT}/docs"
    log_info "Dashboard: http://localhost:${PORT:-$DEFAULT_PORT}/dashboard"
    
    echo
    log_info "Press Ctrl+C to stop the service"
    echo
    
    # Start the service
    if [[ "$(get_environment)" == "development" ]]; then
        log_info "Starting in development mode with auto-reload"
        exec uv run python -m uvicorn src.main:app \
            --host 0.0.0.0 \
            --port "${PORT:-$DEFAULT_PORT}" \
            --reload \
            --log-level "$(echo "$LOG_LEVEL" | tr '[:upper:]' '[:lower:]')"
    else
        log_info "Starting in production mode"
        exec uv run python -m src.main $args
    fi
}

# Main execution flow
main() {
    log_info "${SERVICE_NAME} Startup Script v${SCRIPT_VERSION}"
    log_info "Project root: $PROJECT_ROOT"
    echo
    
    # Parse command line arguments
    parse_arguments "$@"
    
    # Execute startup sequence
    validate_system_requirements || {
        log_error "System requirements validation failed"
        exit 1
    }
    
    validate_configuration || {
        log_error "Configuration validation failed"
        exit 1
    }
    
    setup_dependencies || {
        log_error "Dependencies setup failed"
        exit 1
    }
    
    prepare_runtime || {
        log_error "Runtime preparation failed"
        exit 1
    }
    
    start_service
}

# Execute main function with all arguments
main "$@"