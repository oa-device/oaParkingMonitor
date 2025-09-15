"""
Edge Device Configuration Manager
Handles configuration loading and updating for simplified edge device
"""

import os
import yaml
import socket
from pathlib import Path
from typing import Optional
from datetime import datetime

from .manager import ConfigManager as BaseConfigManager
from ..models.edge import EdgeConfig, DeploymentConfig, DeviceConfig, VersionInfo, CentralApiConfig


class EdgeConfigManager(BaseConfigManager):
    """
    Configuration manager for edge device
    Extends base ConfigManager with edge-specific functionality
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize edge configuration manager

        Args:
            config_path: Path to configuration file (default: config/edge.yaml)
        """
        super().__init__(config_path)
        self.edge_config_path = config_path or "config/edge.yaml"

    async def load_edge_config(self) -> EdgeConfig:
        """
        Load edge device configuration from file and environment variables

        Returns:
            EdgeConfig: Complete edge device configuration
        """
        try:
            # Try to load from file first
            config_data = {}
            config_file = Path(self.edge_config_path)

            if config_file.exists():
                with open(config_file, 'r') as f:
                    config_data = yaml.safe_load(f) or {}
                self.logger.info(f"Loaded configuration from {config_file}")
            else:
                self.logger.info("No configuration file found, using defaults and environment")

            # Build configuration with environment variable overrides
            edge_config = EdgeConfig(
                deployment=self._build_deployment_config(config_data.get('deployment', {})),
                device=self._build_device_config(config_data.get('device', {})),
                version=self._build_version_info(config_data.get('version', {})),
                centralApi=self._build_central_api_config(config_data.get('centralApi'))
            )

            self.logger.info("Edge configuration loaded successfully")
            return edge_config

        except Exception as e:
            self.logger.error(f"Failed to load edge configuration: {e}")
            raise

    def _build_deployment_config(self, config_data: dict) -> DeploymentConfig:
        """Build deployment configuration with environment variable overrides"""
        return DeploymentConfig(
            customerId=os.getenv("CUSTOMER_ID", config_data.get('customerId', '')),
            siteId=os.getenv("SITE_ID", config_data.get('siteId', '')),
            zoneId=os.getenv("ZONE_ID", config_data.get('zoneId', '')),
            cameraId=os.getenv("CAMERA_ID", config_data.get('cameraId', ''))
        )

    def _build_device_config(self, config_data: dict) -> DeviceConfig:
        """Build device configuration with environment variable overrides"""
        return DeviceConfig(
            physicalCameraId=os.getenv("PHYSICAL_CAMERA_ID", config_data.get('physicalCameraId', '/dev/video0')),
            modelPath=os.getenv("MODEL_PATH", config_data.get('modelPath', 'models/yolo11m.pt')),
            modelVersion=config_data.get('modelVersion', '1.2.3'),
            snapshotInterval=int(os.getenv("SNAPSHOT_INTERVAL", config_data.get('snapshotInterval', 5))),
            totalSpaces=int(os.getenv("TOTAL_SPACES", config_data.get('totalSpaces', 50)))
        )

    def _build_version_info(self, config_data: dict) -> VersionInfo:
        """Build version information"""
        return VersionInfo(
            software=config_data.get('software', '2.0.0'),
            deployed=config_data.get('deployed', datetime.now().isoformat()),
            hostname=socket.gethostname()
        )

    def _build_central_api_config(self, config_data: Optional[dict]) -> Optional[CentralApiConfig]:
        """Build central API configuration if enabled"""
        if not config_data:
            config_data = {}

        # Check if central API is enabled
        enabled = os.getenv("CENTRAL_API_ENABLED", "false").lower() == "true"
        if not enabled and not config_data.get('enabled', False):
            return None

        return CentralApiConfig(
            enabled=enabled,
            endpoint=os.getenv("CENTRAL_API_URL", config_data.get('endpoint', '')),
            apiKey=os.getenv("API_KEY", config_data.get('apiKey', '')),
            secretKey=os.getenv("SECRET_KEY", config_data.get('secretKey', '')),
            batchSize=int(os.getenv("BATCH_SIZE", config_data.get('batchSize', 100))),
            submissionInterval=int(os.getenv("SUBMISSION_INTERVAL", config_data.get('submissionInterval', 60)))
        )

    async def update_deployment_config(self, new_config: DeploymentConfig) -> bool:
        """
        Update deployment configuration

        Args:
            new_config: New deployment configuration

        Returns:
            Success status
        """
        try:
            # Load current configuration
            current_config = {}
            config_file = Path(self.edge_config_path)

            if config_file.exists():
                with open(config_file, 'r') as f:
                    current_config = yaml.safe_load(f) or {}

            # Update deployment section
            current_config['deployment'] = {
                'customerId': new_config.customerId,
                'siteId': new_config.siteId,
                'zoneId': new_config.zoneId,
                'cameraId': new_config.cameraId
            }

            # Ensure directory exists
            config_file.parent.mkdir(parents=True, exist_ok=True)

            # Write updated configuration
            with open(config_file, 'w') as f:
                yaml.dump(current_config, f, default_flow_style=False, indent=2)

            self.logger.info("Deployment configuration updated successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to update deployment configuration: {e}")
            return False

    async def save_runtime_config(self, edge_config: EdgeConfig) -> bool:
        """
        Save runtime configuration copy to data directory

        Args:
            edge_config: Edge configuration to save

        Returns:
            Success status
        """
        try:
            # Get data directory
            data_dir = Path.home() / "orangead" / "data" / "oaParkingMonitor"
            data_dir.mkdir(parents=True, exist_ok=True)

            config_copy_path = data_dir / "config.yaml"

            # Build configuration data
            config_data = {
                'deployment': {
                    'customerId': edge_config.deployment.customerId,
                    'siteId': edge_config.deployment.siteId,
                    'zoneId': edge_config.deployment.zoneId,
                    'cameraId': edge_config.deployment.cameraId
                },
                'device': {
                    'physicalCameraId': edge_config.device.physicalCameraId,
                    'modelPath': edge_config.device.modelPath,
                    'modelVersion': edge_config.device.modelVersion,
                    'snapshotInterval': edge_config.device.snapshotInterval,
                    'totalSpaces': edge_config.device.totalSpaces
                },
                'version': {
                    'software': edge_config.version.software,
                    'deployed': edge_config.version.deployed,
                    'hostname': edge_config.version.hostname
                }
            }

            if edge_config.centralApi:
                config_data['centralApi'] = {
                    'enabled': edge_config.centralApi.enabled,
                    'endpoint': edge_config.centralApi.endpoint,
                    'batchSize': edge_config.centralApi.batchSize,
                    'submissionInterval': edge_config.centralApi.submissionInterval
                    # Note: API keys not saved to runtime copy for security
                }

            # Save runtime copy
            with open(config_copy_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)

            self.logger.info(f"Runtime configuration saved to {config_copy_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save runtime configuration: {e}")
            return False