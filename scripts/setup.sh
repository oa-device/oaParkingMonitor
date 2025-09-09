#!/bin/bash
# oaParkingMonitor Setup Script
# Initial project setup and dependency installation

# Load shared utilities
# shellcheck source=helpers.sh
source "$(dirname "$0")/helpers.sh"

# Script configuration
readonly SCRIPT_VERSION="2.0.0"

# Setup operations
setup_system_requirements() {
    log_header "System Requirements"
    
    # macOS check
    if is_macos; then
        log_success "Running on macOS $(get_macos_version)"
        
        if is_apple_silicon; then
            log_success "Apple Silicon detected - optimal performance expected"
        else
            log_info "Intel processor detected - CPU/CUDA fallback available"
        fi
    else
        log_warn "Not running on macOS - setup will continue but performance may be limited"
    fi
    
    # Python version check
    if ! check_python_version; then
        log_error "Python requirements not met"
        return 1
    fi
    
    # Install uv if not present
    if ! command_exists uv; then
        log_progress "Installing uv package manager..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        
        # Source cargo environment
        if [[ -f "$HOME/.cargo/env" ]]; then
            # shellcheck source=/dev/null
            source "$HOME/.cargo/env"
        fi
        
        # Verify installation
        if check_uv; then
            log_success "uv installed successfully"
        else
            log_error "uv installation failed"
            return 1
        fi
    else
        log_success "uv already available"
    fi
    
    return 0
}

setup_project_dependencies() {
    log_header "Dependencies Installation"
    
    cd_project_root
    
    # Install Python dependencies
    log_progress "Installing Python dependencies with uv..."
    
    if uv sync; then
        log_success "Dependencies installed successfully"
    else
        log_error "Dependencies installation failed"
        return 1
    fi
    
    # Verify critical dependencies
    if check_dependencies; then
        log_success "All critical dependencies verified"
    else
        log_error "Dependency verification failed"
        return 1
    fi
    
    return 0
}

setup_project_structure() {
    log_header "Project Structure"
    
    cd_project_root
    
    # Create project directories
    log_progress "Creating project directories..."
    
    local directories=(
        "logs"
        "models/downloads"
        "models/exports"
        "models/custom"
        "assets/sample_images"
        "assets/overlay_templates"
        "assets/logos"
    )
    
    for dir in "${directories[@]}"; do
        if mkdir -p "$dir"; then
            log_success "Created: $dir"
        else
            log_error "Failed to create: $dir"
            return 1
        fi
    done
    
    # Create runtime directories
    create_runtime_dirs
    
    # Set appropriate permissions
    chmod 755 logs 2>/dev/null || true
    
    return 0
}

setup_configuration() {
    log_header "Configuration Setup"
    
    cd_project_root
    
    # Copy configuration template
    if [[ ! -f "config.yaml" ]]; then
        if [[ -f "config/default.yaml" ]]; then
            log_progress "Creating configuration file..."
            
            if cp config/default.yaml config.yaml; then
                log_success "Configuration created at config.yaml"
                log_info "Please edit config.yaml to match your environment"
            else
                log_error "Failed to create configuration file"
                return 1
            fi
        else
            log_error "Default configuration template not found"
            return 1
        fi
    else
        log_success "Configuration file already exists"
        
        # Validate existing configuration
        if validate_yaml "config.yaml"; then
            log_success "Configuration syntax valid"
        else
            log_warn "Configuration syntax issues detected"
        fi
    fi
    
    # Show available environment configurations
    log_info "Available environment configurations:"
    if find config/ -name "*.yaml" -type f >/dev/null 2>&1; then
        find config/ -name "*.yaml" -type f | sed 's/^/  /'
    else
        log_warn "No environment configurations found"
    fi
    
    return 0
}

setup_model_testing() {
    log_header "Model Testing"
    
    cd_project_root
    activate_venv
    
    # Test model download and basic functionality
    if [[ -f "test_model.py" ]]; then
        log_progress "Testing YOLOv11m model download and performance..."
        
        if uv run python test_model.py; then
            log_success "Model testing completed successfully"
        else
            log_warn "Model testing failed - may impact performance"
        fi
    else
        log_info "Model test script not found - skipping model testing"
    fi
    
    return 0
}

show_setup_summary() {
    log_header "Setup Summary"
    
    log_success "🎉 ${SERVICE_NAME} setup completed successfully!"
    
    echo
    log_info "Next steps:"
    log_info "1. Configure your environment:"
    log_info "   - Edit config.yaml for your camera and parking zones"
    log_info "   - Set PARKING_MONITOR_ENV environment variable if needed"
    log_info ""
    log_info "2. Validate deployment readiness:"
    log_info "   ./scripts/validate.sh"
    log_info ""
    log_info "3. Start the service:"
    log_info "   ./scripts/start.sh"
    log_info ""
    log_info "4. Verify service health:"
    log_info "   ./scripts/health_check.sh --detailed"
    log_info ""
    log_info "5. Access the dashboard:"
    log_info "   http://localhost:${DEFAULT_PORT}/dashboard"
    
    echo
    log_info "For more information:"
    log_info "- README.md - Project overview and usage"
    log_info "- DEPLOYMENT.md - Production deployment guide"
    log_info "- ./scripts/helpers.sh - Available utility functions"
}

show_usage() {
    cat << EOF
${SERVICE_NAME} Setup Script v${SCRIPT_VERSION}

Usage: $0 [OPTIONS]

Options:
  --skip-models    Skip model testing (faster setup)
  -h, --help       Show this help message

This script performs:
  - System requirements validation
  - uv package manager installation (if needed)
  - Python dependencies installation
  - Project directory structure creation
  - Configuration file setup
  - Model download and testing

Environment Variables:
  PARKING_MONITOR_ENV  Environment (production, staging, development)
  DEBUG               Enable debug output (0/1)

EOF
}

# Main execution
main() {
    local skip_models=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-models)
                skip_models=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    log_info "${SERVICE_NAME} Setup Script v${SCRIPT_VERSION}"
    log_info "Project root: $PROJECT_ROOT"
    echo
    
    # Execute setup sequence
    if ! setup_system_requirements; then
        log_error "System requirements setup failed"
        exit 1
    fi
    
    if ! setup_project_dependencies; then
        log_error "Dependencies setup failed"
        exit 1
    fi
    
    if ! setup_project_structure; then
        log_error "Project structure setup failed"
        exit 1
    fi
    
    if ! setup_configuration; then
        log_error "Configuration setup failed"
        exit 1
    fi
    
    if [[ "$skip_models" != "true" ]]; then
        setup_model_testing || log_warn "Model testing failed but setup continues"
    else
        log_info "Skipping model testing as requested"
    fi
    
    show_setup_summary
}

# Execute main function
main "$@"