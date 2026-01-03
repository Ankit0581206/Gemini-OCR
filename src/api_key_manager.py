import json
import os
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
from pathlib import Path
import random

logger = logging.getLogger(__name__)

class KeyStatus(Enum):
    ACTIVE = "active"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    ERROR = "error"
    INACTIVE = "inactive"

class RotationStrategy(Enum):
    ROUND_ROBIN = "round_robin"
    LOAD_BALANCE = "load_balance"
    SMART_ROTATE = "smart_rotate"

@dataclass
class APIKey:
    """Represents an API key with usage tracking"""
    key: str
    alias: str
    status: KeyStatus = KeyStatus.ACTIVE
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limit_hits: int = 0
    last_used: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0
    cooldown_until: Optional[datetime] = None
    daily_requests: int = 0
    daily_reset: datetime = field(default_factory=lambda: datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
    request_timestamps: List[datetime] = field(default_factory=list)
    
    @property
    def key_hash(self) -> str:
        """Return hashed version of key for logging"""
        return hashlib.sha256(self.key.encode()).hexdigest()[:8]
    
    @property
    def is_active(self) -> bool:
        """Check if key is currently active"""
        if self.status != KeyStatus.ACTIVE:
            return False
        
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return False
        
        # Check daily reset
        if datetime.now().date() > self.daily_reset.date():
            self.daily_requests = 0
            self.daily_reset = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        return True
    
    def record_request(self, success: bool, error_message: str = None):
        """Record a request attempt"""
        self.total_requests += 1
        self.daily_requests += 1
        self.last_used = datetime.now()
        self.request_timestamps.append(self.last_used)
        
        # Keep only last hour of timestamps
        cutoff = datetime.now() - timedelta(hours=1)
        self.request_timestamps = [ts for ts in self.request_timestamps if ts > cutoff]
        
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            self.error_count += 1
            self.last_error = error_message
            
            # Check for rate limiting
            if "429" in str(error_message) or "rate limit" in str(error_message).lower():
                self.rate_limit_hits += 1
                self.status = KeyStatus.RATE_LIMITED
                self.cooldown_until = datetime.now() + timedelta(minutes=60)
                logger.warning(f"Key {self.alias} rate limited. Cooldown until {self.cooldown_until}")
    
    def get_stats(self) -> Dict:
        """Get key statistics"""
        return {
            "alias": self.alias,
            "key_hash": self.key_hash,
            "status": self.status.value,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0,
            "daily_requests": self.daily_requests,
            "rate_limit_hits": self.rate_limit_hits,
            "error_count": self.error_count,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "is_active": self.is_active
        }

class APIKeyManager:
    """Manages rotation and load balancing of multiple API keys"""
    
    def __init__(self, config):
        self.config = config
        self.keys: List[APIKey] = []
        self.current_index = 0
        self.rotation_strategy = RotationStrategy(config.ROTATION_STRATEGY)
        self.key_file = Path(config.API_KEY_FILE)
        self.load_keys()
        self.start_time = datetime.now()
        logger.info(f"API Key Manager initialized with {len(self.keys)} keys")
    
    def load_keys(self) -> None:
        """Load API keys from file or environment"""
        # Try loading from JSON file
        if self.key_file.exists():
            try:
                with open(self.key_file, 'r') as f:
                    key_data = json.load(f)

                # Support several shapes for api_keys.json:
                # 1) List of dicts: [{"key": "...", "alias": "..."}, ...]
                # 2) Dict mapping alias->key: {"alias1": "key1", ...}
                # 3) List of strings: ["key1", "key2", ...]
                if isinstance(key_data, dict):
                    for alias, key in key_data.items():
                        key_obj = APIKey(key=key, alias=alias)
                        self.keys.append(key_obj)
                elif isinstance(key_data, list):
                    for item in key_data:
                        # Support nested single-item lists [[{...}], [{...}]]
                        if isinstance(item, list) and item:
                            inner = item[0]
                        else:
                            inner = item

                        if isinstance(inner, dict):
                            k = inner.get('key') or inner.get('api_key') or inner.get('value')
                            alias = inner.get('alias') or f"key_{len(self.keys)}"
                            if k:
                                key_obj = APIKey(key=k, alias=alias)
                                self.keys.append(key_obj)
                        elif isinstance(inner, str):
                            key_obj = APIKey(key=inner, alias=f"key_{len(self.keys)}")
                            self.keys.append(key_obj)
                else:
                    logger.error(f"Unrecognized key file format: {type(key_data)}")

                logger.info(f"Loaded {len(self.keys)} keys from {self.key_file}")
            except Exception as e:
                logger.error(f"Failed to load keys from file: {e}")
        
        # Load from environment variables
        if not self.keys:
            env_keys = self._load_keys_from_env()
            for alias, key in env_keys.items():
                key_obj = APIKey(key=key, alias=alias)
                self.keys.append(key_obj)
            
            if self.keys:
                self.save_keys()
        
        if not self.keys:
            # Don't raise here to allow the application to start and perform a graceful
            # shutdown or present the user-friendly error later. Raising caused the
            # whole process to crash during initialization which prevented cleanup.
            logger.error("No API keys found. Please add keys to api_keys.json or environment variables.")
            return

        logger.info(f"Total keys available: {len(self.keys)}")
    
    def _load_keys_from_env(self) -> Dict[str, str]:
        """Load keys from environment variables"""
        env_keys = {}
        prefix = self.config.API_KEY_ENV_PREFIX
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                alias = key[len(prefix):].lower()
                env_keys[alias] = value
        
        logger.info(f"Loaded {len(env_keys)} keys from environment")
        return env_keys
    
    def save_keys(self) -> None:
        """Save API keys to file (without statistics)"""
        key_data = []
        for key_obj in self.keys:
            key_data.append({
                'key': key_obj.key,
                'alias': key_obj.alias
            })
        
        try:
            with open(self.key_file, 'w') as f:
                json.dump(key_data, f, indent=2)
            logger.info(f"Saved {len(key_data)} keys to {self.key_file}")
        except Exception as e:
            logger.error(f"Failed to save keys: {e}")
    
    def save_stats(self) -> None:
        """Save key statistics to file"""
        stats_file = Path("api_key_stats.json")
        stats = {
            "last_updated": datetime.now().isoformat(),
            "total_keys": len(self.keys),
            "keys": [key.get_stats() for key in self.keys],
            "total_requests": sum(k.total_requests for k in self.keys),
            "successful_requests": sum(k.successful_requests for k in self.keys),
            "uptime_hours": (datetime.now() - self.start_time).total_seconds() / 3600
        }
        
        try:
            with open(stats_file, 'w') as f:
                json.dump(stats, f, indent=2, default=str)
            logger.debug(f"Saved key statistics to {stats_file}")
        except Exception as e:
            logger.error(f"Failed to save statistics: {e}")
    
    def get_next_key(self) -> Optional[APIKey]:
        """Get next available API key based on rotation strategy"""
        if not self.keys:
            return None
        
        active_keys = [k for k in self.keys if k.is_active]
        
        if not active_keys:
            logger.warning("No active API keys available")
            self._reset_cooldowns()
            active_keys = [k for k in self.keys if k.is_active]
            
            if not active_keys:
                return None
        
        if self.rotation_strategy == RotationStrategy.ROUND_ROBIN:
            return self._round_robin(active_keys)
        elif self.rotation_strategy == RotationStrategy.LOAD_BALANCE:
            return self._load_balance(active_keys)
        elif self.rotation_strategy == RotationStrategy.SMART_ROTATE:
            return self._smart_rotate(active_keys)
        else:
            return self._round_robin(active_keys)
    
    def _round_robin(self, active_keys: List[APIKey]) -> APIKey:
        """Round robin rotation strategy"""
        for i in range(len(active_keys)):
            idx = (self.current_index + i) % len(active_keys)
            key = active_keys[idx]
            if key.is_active and key.daily_requests < self.config.REQUESTS_PER_DAY:
                self.current_index = (idx + 1) % len(active_keys)
                return key
        return active_keys[0]
    
    def _load_balance(self, active_keys: List[APIKey]) -> APIKey:
        """Load balancing strategy based on request count"""
        # Filter keys that haven't reached daily limit
        available_keys = [k for k in active_keys if k.daily_requests < self.config.REQUESTS_PER_DAY]
        
        if not available_keys:
            # All keys reached daily limit, use the one with least requests today
            return min(active_keys, key=lambda k: k.daily_requests)
        
        # Use key with least requests in current minute
        current_minute = datetime.now().replace(second=0, microsecond=0)
        recent_requests = {}
        
        for key in available_keys:
            requests_this_minute = sum(1 for ts in key.request_timestamps 
                                     if ts.replace(second=0, microsecond=0) == current_minute)
            recent_requests[key] = requests_this_minute
        
        # Find key with least requests this minute
        return min(recent_requests.items(), key=lambda x: x[1])[0]
    
    def _smart_rotate(self, active_keys: List[APIKey]) -> APIKey:
        """Smart rotation considering multiple factors"""
        scored_keys = []
        
        for key in active_keys:
            if key.daily_requests >= self.config.REQUESTS_PER_DAY:
                continue
            
            score = 0
            
            # Factor 1: Recent usage (prefer less used)
            current_minute = datetime.now().replace(second=0, microsecond=0)
            requests_this_minute = sum(1 for ts in key.request_timestamps 
                                     if ts.replace(second=0, microsecond=0) == current_minute)
            score -= requests_this_minute * 10  # Penalize recent usage
            
            # Factor 2: Success rate
            success_rate = (key.successful_requests / key.total_requests * 100) if key.total_requests > 0 else 100
            score += success_rate * 0.1
            
            # Factor 3: Time since last use (prefer unused)
            if key.last_used:
                minutes_since_last_use = (datetime.now() - key.last_used).total_seconds() / 60
                score += min(minutes_since_last_use, 60) * 0.5
            
            # Factor 4: Error count (penalize)
            score -= key.error_count * 5
            
            scored_keys.append((score, key))
        
        if not scored_keys:
            return active_keys[0]
        
        # Return key with highest score. Sort only by score to avoid comparing
        # APIKey instances (which are not orderable) when scores tie.
        scored_keys.sort(key=lambda t: t[0], reverse=True)
        return scored_keys[0][1]
    
    def _reset_cooldowns(self) -> None:
        """Reset cooldowns for rate-limited keys"""
        reset_count = 0
        for key in self.keys:
            if key.cooldown_until and datetime.now() > key.cooldown_until:
                if key.status == KeyStatus.RATE_LIMITED:
                    key.status = KeyStatus.ACTIVE
                    key.cooldown_until = None
                    reset_count += 1
                    logger.info(f"Reset cooldown for key {key.alias}")
        
        if reset_count > 0:
            logger.info(f"Reset cooldowns for {reset_count} keys")
    
    def monitor_keys(self) -> Dict:
        """Monitor and report key status"""
        stats = {
            "total_keys": len(self.keys),
            "active_keys": sum(1 for k in self.keys if k.is_active),
            "rate_limited_keys": sum(1 for k in self.keys if k.status == KeyStatus.RATE_LIMITED),
            "total_requests_today": sum(k.daily_requests for k in self.keys),
            "keys": [k.get_stats() for k in self.keys]
        }
        
        logger.info(f"Key Status: {stats['active_keys']}/{stats['total_keys']} active, "
                   f"{stats['total_requests_today']} requests today")
        
        # Auto-recovery for inactive keys
        if self.config.AUTO_RECOVERY:
            self._reset_cooldowns()
        
        return stats
    
    def add_key(self, key: str, alias: str = None) -> bool:
        """Add a new API key"""
        if not alias:
            alias = f"key_{len(self.keys)}"
        
        # Check if key already exists
        for existing in self.keys:
            if existing.key == key:
                logger.warning(f"Key already exists with alias {existing.alias}")
                return False
        
        new_key = APIKey(key=key, alias=alias)
        self.keys.append(new_key)
        self.save_keys()
        logger.info(f"Added new key: {alias}")
        return True
    
    def remove_key(self, alias: str) -> bool:
        """Remove an API key"""
        for i, key in enumerate(self.keys):
            if key.alias == alias:
                self.keys.pop(i)
                self.save_keys()
                logger.info(f"Removed key: {alias}")
                return True
        return False