"""
Zone Analysis Adapter
Orchestrates zone analysis with data format conversion and fallback handling
"""

from typing import List, Dict, Any
import logging

from .data_converters import DetectionConverter, ZoneConverter, ResultConverter, FallbackAnalyzer


class ZoneAnalysisAdapter:
    """
    High-level adapter that orchestrates zone analysis with proper data conversion
    """
    
    def __init__(self, zone_analyzer, logger: logging.Logger = None):
        self.zone_analyzer = zone_analyzer
        self.logger = logger or logging.getLogger(__name__)
        
        # Initialize converters
        self.detection_converter = DetectionConverter()
        self.zone_converter = ZoneConverter()
        self.result_converter = ResultConverter(self.logger)
        self.fallback_analyzer = FallbackAnalyzer(self.logger)
    
    def analyze_parking_zones(self, detections, config) -> List[Dict[str, Any]]:
        """
        Analyze parking zones using modular zone analyzer with enhanced detection
        
        Args:
            detections: List of VehicleDetection objects
            config: ParkingConfig object with zone configuration
            
        Returns:
            List of zone status dictionaries in legacy format
        """
        try:
            # Convert legacy VehicleDetection objects to new format for zone analyzer
            detection_data = self.detection_converter.to_analysis_format(detections)
            
            # Convert parking zones to analyzer format
            zones_data = self.zone_converter.to_analysis_format(config.parking_zones)
            
            # Analyze zones with enhanced detection methods
            zone_results = self.zone_analyzer.analyze_zones(
                zones_data, 
                detection_data,
                enhanced_detection=True
            )
            
            # Convert results back to legacy format and update config
            zones_status = self.result_converter.to_legacy_format(
                zone_results, zones_data, detections, config
            )
            
            return zones_status
            
        except Exception as e:
            self.logger.error(f"Zone analysis failed: {e}")
            # Fallback to original logic on error
            return self.fallback_analyzer.analyze_zones(
                config.parking_zones, detections, config
            )