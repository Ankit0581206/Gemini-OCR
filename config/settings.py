import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

@dataclass
class OCRConfig:
    """Configuration for Nepali OCR processing"""
    # Paths
    INPUT_IMAGE_DIR: str = "images"
    OUTPUT_ANNOTATION_DIR: str = "annotations"
    
    # API Key Management
    API_KEY_FILE: str = "api_keys.json"
    API_KEY_ENV_PREFIX: str = "GEMINI_API_KEY_"  # For multiple keys in .env
    
    # Gemini API settings
    GEMINI_MODEL: str = "gemini-2.5-flash"  # Free tier compatible
    
    # Rate limiting (Free tier: 5 RPM, 20 RPD)
    REQUESTS_PER_MINUTE: int = 5
    REQUESTS_PER_DAY: int = 1000
    RATE_LIMIT_WINDOW_MINUTES: int = 1
    RATE_LIMIT_WINDOW_DAYS: int = 1
    
    # Processing settings
    BATCH_SIZE: int = 1  # Reduced for free tier
    MAX_RETRIES: int = 3
    TIMEOUT_SECONDS: int = 120
    REQUEST_DELAY_SECONDS: float = 15.0  # Increased delay for free tier
    
    # API Key rotation
    ROTATION_STRATEGY: str = "smart_rotate"  # Options: round_robin, load_balance, smart_rotate
    MIN_REQUESTS_PER_KEY: int = 5  # Switch after N requests
    COOLDOWN_PERIOD_MINUTES: int = 60  # Cooldown for rate-limited keys
    
    # Image settings
    SUPPORTED_EXTENSIONS: List[str] = field(default_factory=lambda: ['.jpg', '.jpeg', '.png'])
    MAX_IMAGE_SIZE_MB: int = 10
    TARGET_IMAGE_SIZE: tuple = (2048, 2048)
    
    # OCR settings
    LANGUAGE_HINT: str = "nepali"
    INCLUDE_CONFIDENCE: bool = False
    
    # Output settings
    ENCODING: str = "utf-8"
    SAVE_INTERMEDIATE_RESULTS: bool = True
    
    # Sleep schedule (process during off-peak hours)
    SLEEP_START_HOUR: int = 0  # Midnight
    SLEEP_END_HOUR: int = 6    # 6 AM
    PROCESS_DURING_SLEEP: bool = True
    
    # Monitoring
    MONITORING_INTERVAL_MINUTES: int = 5
    AUTO_RECOVERY: bool = True

config = OCRConfig()