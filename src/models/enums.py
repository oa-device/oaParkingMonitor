"""
Model Enumerations
Common enum types used throughout the parking monitor system
"""

from enum import Enum


class DetectionDifficulty(str, Enum):
    """Enumeration for parking zone detection difficulty levels"""
    EASY = "easy"
    NORMAL = "normal" 
    HARD = "hard"


class LogLevel(str, Enum):
    """Enumeration for logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"