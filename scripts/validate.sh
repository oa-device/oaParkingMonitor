#!/bin/bash
# oaParkingMonitor Deployment Validation Script
# Comprehensive pre-deployment checks using shared utilities

# Load shared utilities
# shellcheck source=helpers.sh
source "$(dirname "$0")/helpers.sh"

# Script configuration
readonly SCRIPT_VERSION="2.0.0"

# Validation tracking
VALIDATION_ERRORS=0
VALIDATION_WARNINGS=0

# Helper functions for validation tracking
validation_error() {
    log_error "$1"
    ((VALIDATION_ERRORS++))
}

validation_warning() {
    log_warn "$1" 
    ((VALIDATION_WARNINGS++))
}

validation_success() {
    log_success "$1"
}

# Comprehensive system validation
validate_system_environment() {
    log_header "System Environment"
    
    # Operating system check
    if is_macos; then
        validation_success "Running on macOS $(get_macos_version)"
        
        if is_apple_silicon; then
            validation_success "Apple Silicon detected - Metal/MPS optimizations available"
        else
            validation_warning "Intel processor - Metal/MPS optimizations unavailable"
        fi
    else
        validation_warning "Not running on macOS - Metal optimizations disabled"
    fi
    
    # Python version validation
    if check_python_version; then
        validation_success "Python version compatible"
    else
        validation_error "Python version incompatible"
    fi
    
    # Package manager validation
    if check_uv; then
        validation_success "uv package manager available"
    else
        validation_error "uv package manager not found"
    fi
}

# Project structure validation
validate_project_structure() {
    log_header "Project Structure"
    
    cd_project_root
    
    if validate_project_structure; then
        validation_success "Project structure valid"
    else
        validation_error "Project structure incomplete"
    fi
    
    # Check configuration files
    local env
    env=$(get_environment)
    
    if check_config_file; then
        validation_success "Configuration file found"
        
        local config_file
        config_file=$(get_config_file)
        if validate_yaml "$config_file"; then
            validation_success "Configuration syntax valid"
        else
            validation_error "Configuration syntax invalid"
        fi
    else
        validation_error "Configuration file missing"
    fi
}

# Dependencies validation
validate_dependencies() {
    log_header "Dependencies"
    
    # Virtual environment check
    cd_project_root
    
    if [[ -d ".venv" && -f "uv.lock" ]]; then
        validation_success "Virtual environment exists"
        
        if check_dependencies; then
            validation_success "All critical dependencies available"
        else
            validation_error "Missing critical dependencies"
        fi
    else
        validation_error "Virtual environment not found - run 'uv sync'"
    fi
}

# Runtime environment validation
validate_runtime_environment() {
    log_header "Runtime Environment"
    
    # Create and validate runtime directories
    create_runtime_dirs
    validation_success "Runtime directories ready"
    
    # System resources check
    check_system_resources
    
    # Disk space validation
    if check_disk_space "$HOME" 2; then
        validation_success "Sufficient disk space available"
    else
        validation_warning "Low disk space detected"
    fi
}

# Scripts and permissions validation
validate_scripts() {
    log_header "Scripts and Permissions"
    
    local scripts=(
        "scripts/start.sh"
        "scripts/health_check.sh"
        "scripts/setup.sh"
        "scripts/helpers.sh"
    )
    
    for script in "${scripts[@]}"; do
        if [[ -f "$script" ]]; then
            if [[ -x "$script" ]]; then
                validation_success "Script executable: $script"
            else
                validation_warning "Script not executable: $script"
            fi
        else
            validation_error "Missing script: $script"
        fi
    done
}

# Security validation
validate_security() {
    log_header "Security"
    
    # Check for development artifacts
    local dev_artifacts=()
    while IFS= read -r -d '' file; do
        dev_artifacts+=("$file")
    done < <(find . -name "*.log" -o -name ".env.local" -o -name "debug.*" -o -name "test_*.py" -print0 2>/dev/null)
    
    if [[ ${#dev_artifacts[@]} -eq 0 ]]; then
        validation_success "No development artifacts found"
    else
        validation_warning "Development artifacts found: ${dev_artifacts[*]}"
    fi
    
    # Check for hardcoded secrets
    if grep -r -i "password\|secret\|key\|token" src/ config/ --include="*.py" --include="*.yaml" >/dev/null 2>&1; then
        validation_warning "Potential secrets in configuration - review security"
    else
        validation_success "No obvious hardcoded secrets detected"
    fi
}

# Final validation summary
show_validation_summary() {
    log_header "Validation Summary"
    
    if [[ $VALIDATION_ERRORS -eq 0 ]]; then
        if [[ $VALIDATION_WARNINGS -eq 0 ]]; then
            log_success "🎉 All validation checks passed!"
            log_success "${SERVICE_NAME} is ready for production deployment"
            
            echo
            log_info "Next Steps:"
            log_info "1. Start service: ./scripts/start.sh"
            log_info "2. Verify health: ./scripts/health_check.sh --detailed"
            log_info "3. Monitor logs: tail -f ~/orangead/parking-monitor/logs/parking_monitor.log"
            log_info "4. Access dashboard: http://localhost:${DEFAULT_PORT}/dashboard"
            log_info "5. API documentation: http://localhost:${DEFAULT_PORT}/docs"
            
            return 0
        else
            log_warn "[WARN] Validation completed with $VALIDATION_WARNINGS warning(s)"
            log_warn "Review warnings above - deployment possible but not optimal"
            
            echo
            log_info "Consider addressing warnings before production deployment"
            
            return 1
        fi
    else
        log_error "[FAIL] Validation failed with $VALIDATION_ERRORS error(s) and $VALIDATION_WARNINGS warning(s)"
        log_error "Fix errors above before deployment"
        
        echo
        log_info "Common fixes:"
        log_info "- Install dependencies: uv sync"
        log_info "- Make scripts executable: chmod +x scripts/*.sh"
        log_info "- Configuration is bundled in config/mvp.yaml"
        log_info "- Run setup script: ./scripts/setup.sh"
        
        return 2
    fi
}

# Show usage information
show_usage() {
    cat << EOF
${SERVICE_NAME} Deployment Validation v${SCRIPT_VERSION}

Usage: $0 [OPTIONS]

Options:
  -h, --help       Show this help message
  --version        Show script version

Environment Variables:
  PARKING_MONITOR_ENV  Environment (production, staging, development)
  DEBUG               Enable debug output (0/1)

This script validates:
  - System requirements (macOS, Python, uv)
  - Project structure and configuration
  - Dependencies and virtual environment
  - Runtime directories and permissions
  - Scripts and security considerations

Exit Codes:
  0 - All validations passed
  1 - Warnings present (deployment possible)
  2 - Errors present (deployment not recommended)

EOF
}

# Main execution
main() {
    # Parse arguments
    case "${1:-}" in
        -h|--help)
            show_usage
            exit 0
            ;;
        --version)
            echo "${SERVICE_NAME} Validation Script v${SCRIPT_VERSION}"
            exit 0
            ;;
        *)
            if [[ -n "${1:-}" ]]; then
                log_error "Unknown option: $1"
                show_usage
                exit 1
            fi
            ;;
    esac
    
    log_info "${SERVICE_NAME} Deployment Validation v${SCRIPT_VERSION}"
    log_info "Environment: $(get_environment)"
    log_info "Project root: $PROJECT_ROOT"
    echo
    
    # Execute validation sequence
    validate_system_environment
    validate_project_structure  
    validate_dependencies
    validate_runtime_environment
    validate_scripts
    validate_security
    
    # Show final summary
    echo
    if show_validation_summary; then
        exit 0
    else
        exit $?
    fi
}

# Execute main function
main "$@"