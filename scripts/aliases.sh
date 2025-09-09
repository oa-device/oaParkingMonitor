#!/bin/bash
# Native aliases for oaParkingMonitor service management
# Provides convenient shortcuts for common operations

# Service management aliases
alias parking-start='./scripts/start.sh'
alias parking-stop='./scripts/stop.sh'
alias parking-restart='./scripts/restart.sh'
alias parking-status='./scripts/health_check.sh'
alias parking-logs='./scripts/logs.sh'

# Development aliases  
alias parking-setup='./scripts/setup.sh'
alias parking-validate='./scripts/validate.sh'
alias parking-test='./scripts/test.sh'

# Configuration aliases
alias parking-config='nano config.yaml'
alias parking-config-staging='cp config/staging.yaml config.yaml'
alias parking-config-preprod='cp config/preprod.yaml config.yaml'  
alias parking-config-prod='cp config/production.yaml config.yaml'

# Monitoring aliases
alias parking-dashboard='open http://localhost:9091/dashboard'
alias parking-api='open http://localhost:9091/docs'
alias parking-health='curl -s http://localhost:9091/health | jq .'
alias parking-stats='curl -s http://localhost:9091/api/stats | jq .'

# Utility aliases
alias parking-dir='cd ~/orangead/parking-monitor'
alias parking-help='echo "Available parking monitor commands:" && grep "alias parking" ~/.bashrc || grep "alias parking" ~/orangead/parking-monitor/scripts/aliases.sh'

echo "Parking monitor aliases loaded. Type 'parking-help' to see available commands."