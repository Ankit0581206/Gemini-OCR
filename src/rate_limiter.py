import time
import threading
from datetime import datetime, timedelta
from collections import deque
import logging
from typing import Optional
from dataclasses import dataclass
import queue

logger = logging.getLogger(__name__)

@dataclass
class RateLimit:
    """Rate limit configuration"""
    requests: int
    window_seconds: int
    name: str = ""

class RateLimiter:
    """Token bucket rate limiter implementation"""
    
    def __init__(self, limits: list, max_burst: int = 1):
        """
        Args:
            limits: List of RateLimit objects
            max_burst: Maximum burst capacity
        """
        self.limits = limits
        self.max_burst = max_burst
        self.requests = deque()
        self.lock = threading.Lock()
        self.last_check = datetime.now()
        
        logger.info(f"Rate limiter initialized with {len(limits)} limits")
    
    def acquire(self, wait: bool = True) -> bool:
        """
        Acquire a token for making a request
        
        Args:
            wait: If True, wait until token is available
            
        Returns:
            True if token acquired, False if not available
        """
        with self.lock:
            now = datetime.now()
            
            # Clean old requests
            self._clean_old_requests(now)
            
            # Check all rate limits
            for limit in self.limits:
                window_start = now - timedelta(seconds=limit.window_seconds)
                
                # Count requests in window
                requests_in_window = sum(1 for req_time in self.requests 
                                       if req_time > window_start)
                
                if requests_in_window >= limit.requests:
                    if wait:
                        # Calculate wait time
                        oldest_request = self.requests[0]
                        wait_until = oldest_request + timedelta(seconds=limit.window_seconds)
                        wait_seconds = (wait_until - now).total_seconds()
                        
                        if wait_seconds > 0:
                            logger.warning(f"Rate limit '{limit.name}' exceeded. "
                                         f"Waiting {wait_seconds:.1f} seconds")
                            time.sleep(wait_seconds)
                            return self.acquire(wait=False)
                    else:
                        logger.warning(f"Rate limit '{limit.name}' exceeded")
                        return False
            
            # Add current request
            self.requests.append(now)
            return True
    
    def _clean_old_requests(self, now: datetime) -> None:
        """Remove requests older than the longest window"""
        if not self.limits:
            return
        
        max_window = max(limit.window_seconds for limit in self.limits)
        cutoff = now - timedelta(seconds=max_window)
        
        # Remove old requests
        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()
    
    def get_status(self) -> dict:
        """Get current rate limit status"""
        with self.lock:
            now = datetime.now()
            self._clean_old_requests(now)
            
            status = {
                "total_requests_in_memory": len(self.requests),
                "limits": []
            }
            
            for limit in self.limits:
                window_start = now - timedelta(seconds=limit.window_seconds)
                requests_in_window = sum(1 for req_time in self.requests 
                                       if req_time > window_start)
                
                status["limits"].append({
                    "name": limit.name,
                    "limit": limit.requests,
                    "used": requests_in_window,
                    "remaining": limit.requests - requests_in_window,
                    "window_seconds": limit.window_seconds
                })
            
            return status

class SmartScheduler:
    """Smart scheduling to optimize free tier usage"""
    
    def __init__(self, config):
        self.config = config
        self.is_sleep_time = False
        self.last_check = datetime.now()
        
        # Create rate limiters for different time windows
        self.minute_limiter = RateLimiter([
            RateLimit(
                requests=config.REQUESTS_PER_MINUTE,
                window_seconds=60,
                name="requests_per_minute"
            )
        ])
        
        self.daily_limiter = RateLimiter([
            RateLimit(
                requests=config.REQUESTS_PER_DAY,
                window_seconds=86400,  # 24 hours
                name="requests_per_day"
            )
        ])
        
        logger.info(f"Smart scheduler initialized: {config.REQUESTS_PER_MINUTE} RPM, "
                   f"{config.REQUESTS_PER_DAY} RPD")
    
    def should_process(self) -> bool:
        """Check if processing should continue"""
        now = datetime.now()
        
        # Check sleep schedule
        if not self.config.PROCESS_DURING_SLEEP:
            current_hour = now.hour
            if self.config.SLEEP_START_HOUR <= current_hour < self.config.SLEEP_END_HOUR:
                if not self.is_sleep_time:
                    logger.info(f"Entering sleep time ({self.config.SLEEP_START_HOUR}:00"
                              f" to {self.config.SLEEP_END_HOUR}:00)")
                    self.is_sleep_time = True
                return False
            elif self.is_sleep_time:
                logger.info("Exiting sleep time")
                self.is_sleep_time = False
        
        # Check rate limits
        if not self.minute_limiter.acquire(wait=False):
            logger.info("Minute rate limit reached, waiting...")
            time.sleep(60)  # Wait a minute
            return self.should_process()
        
        if not self.daily_limiter.acquire(wait=False):
            logger.warning("Daily rate limit reached. Stopping processing.")
            return False
        
        return True
    
    def wait_for_next_slot(self) -> None:
        """Wait for next available processing slot"""
        # Wait between requests to respect rate limits
        time.sleep(self.config.REQUEST_DELAY_SECONDS)
        
        # Ensure we don't exceed minute limit
        while not self.minute_limiter.acquire(wait=False):
            logger.info("Waiting for minute rate limit reset...")
            time.sleep(10)
    
    def get_status(self) -> dict:
        """Get scheduler status"""
        return {
            "is_sleep_time": self.is_sleep_time,
            "sleep_hours": f"{self.config.SLEEP_START_HOUR}:00-{self.config.SLEEP_END_HOUR}:00",
            "minute_limit": self.minute_limiter.get_status(),
            "daily_limit": self.daily_limiter.get_status(),
            "request_delay": self.config.REQUEST_DELAY_SECONDS
        }