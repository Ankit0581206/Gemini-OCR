import logging
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import concurrent.futures
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__) 

def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('ocr_processing.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def ensure_directory(path: Path) -> None:
    """Ensure directory exists"""
    path.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(__name__)
    logger.debug(f"Ensured directory exists: {path}")

def get_image_files(image_dir: Path, extensions: List[str]) -> List[Path]:
    """Get all image files from directory"""
    image_files = []
    for ext in extensions:
        image_files.extend(image_dir.glob(f"*{ext}"))
        image_files.extend(image_dir.glob(f"*{ext.upper()}"))
    
    # Sort files for consistent processing
    image_files.sort()
    logger = logging.getLogger(__name__)
    logger.info(f"Found {len(image_files)} image files in {image_dir}")
    
    return image_files

def save_annotation(image_name: str, text: str, output_dir: Path, 
                   encoding: str = "utf-8") -> Path:
    """
    Save extracted text to annotation file
    
    Args:
        image_name: Original image filename
        text: Extracted text
        output_dir: Output directory for annotations
        encoding: File encoding
    
    Returns:
        Path to saved annotation file
    """
    # Create annotation filename
    annotation_name = f"{Path(image_name).stem}.txt"
    annotation_path = output_dir / annotation_name
    
    # Save text
    try:
        with open(annotation_path, 'w', encoding=encoding) as f:
            f.write(text)
        
        logger = logging.getLogger(__name__)
        logger.info(f"Saved annotation: {annotation_path}")
        
        # Save metadata
        save_metadata(annotation_path, image_name, len(text))
        
        return annotation_path
    except Exception as e:
        logger.error(f"Failed to save annotation {annotation_path}: {str(e)}")
        raise

def save_metadata(annotation_path: Path, image_name: str, text_length: int) -> None:
    """Save processing metadata"""
    metadata = {
        "image_file": image_name,
        "annotation_file": annotation_path.name,
        "text_length": text_length,
        "processing_date": datetime.now().isoformat(),
        "checksum": hashlib.md5(annotation_path.read_bytes()).hexdigest()
    }
    
    metadata_path = annotation_path.with_suffix('.meta.json')
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

def process_single_image(image_path: Path, processor, preprocessor, 
                        config) -> Dict[str, Any]:
    """Process a single image and return results"""
    logger = logging.getLogger(__name__)
    
    try:
        # Validate image
        if not preprocessor.validate_image(image_path, config.MAX_IMAGE_SIZE_MB):
            return {"success": False, "error": "Image validation failed"}
        
        # Load and preprocess image
        image = preprocessor.load_image(image_path)
        if not image:
            return {"success": False, "error": "Failed to load image"}
        
        processed_image = preprocessor.preprocess_for_ocr(image)
        image_bytes = preprocessor.image_to_bytes(processed_image)
        
        # Extract text
        text = processor.extract_text_from_image(
            image_bytes, 
            config.LANGUAGE_HINT
        )
        
        # Validate response
        if not processor.validate_response(text):
            logger.warning(f"Low quality OCR for {image_path.name}")
        
        return {
            "success": True,
            "image_name": image_path.name,
            "text": text,
            "text_length": len(text)
        }
        
    except Exception as e:
        logger.error(f"Error processing {image_path.name}: {str(e)}")
        return {
            "success": False,
            "image_name": image_path.name,
            "error": str(e)
        }