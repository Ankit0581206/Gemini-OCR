#!/usr/bin/env python3
"""
Nepali Document OCR Processor with API Key Rotation
Optimized for Gemini Free Tier (5 RPM, 20 RPD)
"""

import sys
from pathlib import Path
from typing import List, Dict, Any
import time
import json
from datetime import datetime, timedelta
import concurrent.futures
import signal
import atexit
# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.settings import config
from src.ocr_processor import GeminiOCRProcessor
from src.image_preprocessor import ImagePreprocessor
from src.api_key_manager import APIKeyManager
from src.rate_limiter import SmartScheduler
from src.utils import (
    setup_logging, ensure_directory, get_image_files,
    save_annotation, process_single_image
)

class NepaliOCRProcessor:
    """Main processor for Nepali document OCR with key rotation"""
    
    def __init__(self, config):
        self.config = config
        self.logger = setup_logging()
        self.shutdown_flag = False
        
        # Setup signal handling for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        atexit.register(self._cleanup)
        
        # Initialize components
        self.api_key_manager = APIKeyManager(config)
        self.scheduler = SmartScheduler(config)
        self.preprocessor = ImagePreprocessor(config.TARGET_IMAGE_SIZE)
        self.ocr_processor = GeminiOCRProcessor(
            self.api_key_manager,
            config.GEMINI_MODEL
        )
        
        # Setup directories
        self.image_dir = Path(config.INPUT_IMAGE_DIR)
        self.annotation_dir = Path(config.OUTPUT_ANNOTATION_DIR)
        
        ensure_directory(self.image_dir)
        ensure_directory(self.annotation_dir)
        
        # Statistics
        self.stats = {
            "start_time": datetime.now(),
            "total_images": 0,
            "processed": 0,
            "failed": 0,
            "key_rotations": 0,
            "rate_limit_hits": 0,
            "processing_time": 0,
            "keys_used": set()
        }
        
        self.logger.info("Nepali OCR Processor with Key Rotation initialized")
        self._print_config_summary()
    
    def _print_config_summary(self):
        """Print configuration summary"""
        self.logger.info("=" * 60)
        self.logger.info("CONFIGURATION SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Model: {self.config.GEMINI_MODEL}")
        self.logger.info(f"Rate Limits: {self.config.REQUESTS_PER_MINUTE} RPM, "
                        f"{self.config.REQUESTS_PER_DAY} RPD")
        self.logger.info(f"API Keys: {len(self.api_key_manager.keys)} available")
        self.logger.info(f"Rotation Strategy: {self.config.ROTATION_STRATEGY}")
        self.logger.info(f"Request Delay: {self.config.REQUEST_DELAY_SECONDS}s")
        self.logger.info(f"Sleep Hours: {self.config.SLEEP_START_HOUR}:00 - "
                        f"{self.config.SLEEP_END_HOUR}:00")
        self.logger.info("=" * 60)
    
    def process_images(self) -> Dict[str, Any]:
        """
        Process all images with intelligent scheduling and key rotation
        """
        # Get image files
        image_files = get_image_files(
            self.image_dir, 
            self.config.SUPPORTED_EXTENSIONS
        )
        
        if not image_files:
            self.logger.warning(f"No images found in {self.image_dir}")
            return self._finalize_stats()
        
        self.stats["total_images"] = len(image_files)
        self.logger.info(f"Found {len(image_files)} images to process")
        
        # Process images one by one (due to free tier limits)
        for i, image_path in enumerate(image_files):
            if self.shutdown_flag:
                self.logger.info("Shutdown requested, stopping processing...")
                break
            
            self._process_single_image_with_rotation(image_path, i + 1, len(image_files))
            
            # Check if we should continue based on rate limits
            if not self.scheduler.should_process():
                self.logger.warning("Rate limits reached or sleep time activated")
                break
        
        return self._finalize_stats()
    
    def _process_single_image_with_rotation(self, image_path: Path, current: int, total: int):
        """Process a single image with key rotation and rate limiting"""
        self.logger.info(f"Processing image {current}/{total}: {image_path.name}")
        
        try:
            # Check rate limits
            if not self.scheduler.should_process():
                self.stats["rate_limit_hits"] += 1
                self.logger.warning("Rate limit reached, skipping image")
                return
            
            # Validate image
            if not self.preprocessor.validate_image(image_path, self.config.MAX_IMAGE_SIZE_MB):
                self.logger.error(f"Image validation failed: {image_path.name}")
                self.stats["failed"] += 1
                return
            
            # Load and preprocess image
            image = self.preprocessor.load_image(image_path)
            if not image:
                self.stats["failed"] += 1
                return
            
            processed_image = self.preprocessor.preprocess_for_ocr(image)
            image_bytes = self.preprocessor.image_to_bytes(processed_image)
            
            # Extract text with current API key
            start_time = time.time()
            text, key_alias = self.ocr_processor.extract_text_from_image(
                image_bytes,
                self.config.LANGUAGE_HINT
            )
            processing_time = time.time() - start_time
            
            # Record key usage
            self.stats["keys_used"].add(key_alias)
            self.stats["processing_time"] += processing_time
            
            # Validate response
            if not self.ocr_processor.validate_response(text):
                self.logger.warning(f"Low quality OCR for {image_path.name}")
            
            # Save annotation
            annotation_path = save_annotation(
                image_path.name,
                text,
                self.annotation_dir,
                self.config.ENCODING
            )
            
            # Save key-specific metadata
            self._save_key_metadata(annotation_path, key_alias, processing_time)
            
            self.stats["processed"] += 1
            self.logger.info(f"✓ Completed {image_path.name} using key {key_alias} "
                           f"in {processing_time:.2f}s")
            
            # Wait for next slot respecting rate limits
            self.scheduler.wait_for_next_slot()
            
            # Periodic monitoring
            if current % self.config.MONITORING_INTERVAL_MINUTES == 0:
                self._monitor_and_report()
            
        except Exception as e:
            self.logger.error(f"Failed to process {image_path.name}: {str(e)}")
            self.stats["failed"] += 1
    
    def _save_key_metadata(self, annotation_path: Path, key_alias: str, processing_time: float):
        """Save metadata about which key was used"""
        metadata = {
            "api_key_alias": key_alias,
            "processing_time_seconds": processing_time,
            "model_used": self.config.GEMINI_MODEL,
            "processing_date": datetime.now().isoformat()
        }
        
        metadata_path = annotation_path.with_suffix('.key_meta.json')
        try:
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Failed to save key metadata: {e}")
    
    def _monitor_and_report(self):
        """Periodic monitoring and reporting"""
        # Monitor API keys
        key_stats = self.api_key_manager.monitor_keys()
        
        # Monitor rate limits
        scheduler_stats = self.scheduler.get_status()
        
        # Save API key statistics
        self.api_key_manager.save_stats()
        
        # Log summary
        self.logger.info("=" * 50)
        self.logger.info("PROGRESS UPDATE")
        self.logger.info("=" * 50)
        self.logger.info(f"Images processed: {self.stats['processed']}/{self.stats['total_images']}")
        self.logger.info(f"Success rate: {(self.stats['processed']/(self.stats['processed']+self.stats['failed'])*100):.1f}%")
        self.logger.info(f"Keys used today: {len(self.stats['keys_used'])}")
        self.logger.info(f"Active keys: {key_stats['active_keys']}/{key_stats['total_keys']}")
        self.logger.info(f"Total requests today: {key_stats['total_requests_today']}")
        self.logger.info("=" * 50)
    
    def _finalize_stats(self) -> Dict[str, Any]:
        """Finalize and return statistics"""
        end_time = datetime.now()
        duration = (end_time - self.stats["start_time"]).total_seconds()
        
        final_stats = {
            "total_images": self.stats["total_images"],
            "processed": self.stats["processed"],
            "failed": self.stats["failed"],
            "success_rate": (self.stats["processed"] / self.stats["total_images"] * 100 
                           if self.stats["total_images"] > 0 else 0),
            "keys_used": list(self.stats["keys_used"]),
            "total_keys_available": len(self.api_key_manager.keys),
            "total_processing_time_seconds": self.stats["processing_time"],
            "average_processing_time": (self.stats["processing_time"] / self.stats["processed"] 
                                      if self.stats["processed"] > 0 else 0),
            "rate_limit_hits": self.stats["rate_limit_hits"],
            "start_time": self.stats["start_time"].isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "images_per_hour": (self.stats["processed"] / duration * 3600 
                              if duration > 0 else 0)
        }
        
        self._save_final_report(final_stats)
        return final_stats
    
    def _save_final_report(self, stats: Dict[str, Any]) -> None:
        """Save final processing report"""
        report_path = self.annotation_dir / "processing_report.json"
        
        # Add detailed configuration
        stats["config"] = {
            "model": self.config.GEMINI_MODEL,
            "requests_per_minute": self.config.REQUESTS_PER_MINUTE,
            "requests_per_day": self.config.REQUESTS_PER_DAY,
            "rotation_strategy": self.config.ROTATION_STRATEGY,
            "batch_size": self.config.BATCH_SIZE,
            "request_delay": self.config.REQUEST_DELAY_SECONDS
        }
        
        # Add API key statistics
        key_stats = self.api_key_manager.monitor_keys()
        stats["api_key_stats"] = key_stats
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, default=str, ensure_ascii=False)
        
        self.logger.info(f"Processing report saved: {report_path}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_flag = True
    
    def _cleanup(self):
        """Cleanup resources on exit"""
        self.logger.info("Performing cleanup...")
        # api_key_manager may not have been created if init failed during startup.
        if hasattr(self, 'api_key_manager') and self.api_key_manager:
            try:
                self.api_key_manager.save_stats()
            except Exception as e:
                self.logger.error(f"Failed to save API key stats during cleanup: {e}")
        else:
            self.logger.debug("No api_key_manager present during cleanup; skipping save_stats")
        self.logger.info("Cleanup completed")

def main():
    """Main entry point"""
    try:
        processor = NepaliOCRProcessor(config)
        stats = processor.process_images()
        
        # Print final summary
        print("\n" + "="*60)
        print("FINAL PROCESSING SUMMARY")
        print("="*60)
        print(f"Total images: {stats['total_images']}")
        print(f"Successfully processed: {stats['processed']}")
        print(f"Failed: {stats['failed']}")
        print(f"Success rate: {stats['success_rate']:.2f}%")
        print(f"Duration: {stats['duration_seconds']/3600:.2f} hours")
        print(f"Images per hour: {stats['images_per_hour']:.2f}")
        print(f"Keys used: {', '.join(stats['keys_used'])}")
        print(f"Total keys available: {stats['total_keys_available']}")
        print(f"Average processing time: {stats['average_processing_time']:.2f}s")
        print(f"Rate limit hits: {stats['rate_limit_hits']}")
        print(f"Annotations saved in: {config.OUTPUT_ANNOTATION_DIR}")
        print("="*60)
        
        # Save key statistics separately
        processor.api_key_manager.save_stats()
        
        return 0 if stats['failed'] == 0 else 1
        
    except Exception as e:
        logger = setup_logging()
        logger.error(f"Fatal error in main: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())