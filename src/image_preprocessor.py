import cv2
import numpy as np
from PIL import Image, ImageOps, ImageEnhance
import io
from typing import Optional, Tuple
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class ImagePreprocessor:
    """Preprocess images for better OCR results"""
    
    def __init__(self, target_size: tuple = (2048, 2048)):
        self.target_size = target_size
    
    def load_image(self, image_path: Path) -> Optional[Image.Image]:
        """Load image with error handling"""
        try:
            with Image.open(image_path) as img:
                img = img.convert('RGB')
                logger.info(f"Loaded image: {image_path.name}, Size: {img.size}, Mode: {img.mode}")
                return img
        except Exception as e:
            logger.error(f"Failed to load image {image_path}: {str(e)}")
            return None
    
    def preprocess_for_ocr(self, image: Image.Image) -> Image.Image:
        """
        Apply preprocessing steps to improve OCR accuracy
        """
        # Resize while maintaining aspect ratio
        image = self.resize_image(image)
        
        # Convert to grayscale for better text detection
        if image.mode != 'L':
            image = image.convert('L')
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)
        
        # Enhance sharpness
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.2)
        
        # Apply slight denoising using OpenCV
        image_np = np.array(image)
        image_np = cv2.fastNlMeansDenoising(image_np, h=10)
        image = Image.fromarray(image_np)
        
        # Apply adaptive thresholding
        image_np = np.array(image)
        image_np = cv2.adaptiveThreshold(
            image_np, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        image = Image.fromarray(image_np)
        
        return image
    
    def resize_image(self, image: Image.Image) -> Image.Image:
        """Resize image while maintaining aspect ratio"""
        original_width, original_height = image.size
        target_width, target_height = self.target_size
        
        # Calculate scaling factor
        scale = min(target_width / original_width, target_height / original_height)
        
        if scale < 1:  # Only resize if image is larger than target
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logger.debug(f"Resized image from {original_width}x{original_height} to {new_width}x{new_height}")
        
        return image
    
    def image_to_bytes(self, image: Image.Image, format: str = 'JPEG') -> bytes:
        """Convert PIL Image to bytes"""
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format=format, quality=95)
        return img_byte_arr.getvalue()
    
    def validate_image(self, image_path: Path, max_size_mb: int = 20) -> bool:
        """Validate image before processing"""
        try:
            # Check file size
            file_size_mb = image_path.stat().st_size / (1024 * 1024)
            if file_size_mb > max_size_mb:
                logger.warning(f"Image {image_path.name} is too large: {file_size_mb:.2f}MB")
                return False
            
            # Check if image can be opened
            with Image.open(image_path) as img:
                img.verify()
            
            return True
        except Exception as e:
            logger.error(f"Image validation failed for {image_path}: {str(e)}")
            return False