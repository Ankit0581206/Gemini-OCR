import google.generativeai as genai
import time
import logging
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import base64
from datetime import datetime

logger = logging.getLogger(__name__)

class GeminiOCRProcessor:
    """OCR processor using Google's Gemini model with API key rotation"""
    
    def __init__(self, api_key_manager, model_name: str = "gemini-2.5-flash"):
        """
        Initialize Gemini OCR processor
        
        Args:
            api_key_manager: APIKeyManager instance
            model_name: Gemini model to use
        """
        self.api_key_manager = api_key_manager
        self.model_name = model_name
        self.current_key = None
        logger.info(f"Initialized Gemini OCR processor with model: {model_name}")
    
    def _initialize_genai(self, api_key: str) -> None:
        """Initialize Gemini AI with specific API key"""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(self.model_name)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying OCR due to {retry_state.outcome.exception()}. "
            f"Attempt {retry_state.attempt_number}"
        )
    )
    def extract_text_from_image(self, image_bytes: bytes, language_hint: str = "nepali") -> Tuple[str, str]:
        """
        Extract text from image using Gemini
        
        Args:
            image_bytes: Image data in bytes
            language_hint: Language hint for OCR
            
        Returns:
            Tuple of (extracted_text, key_alias_used)
        """
        # Get API key
        key_obj = self.api_key_manager.get_next_key()
        if not key_obj:
            raise ValueError("No available API keys")
        
        self.current_key = key_obj
        self._initialize_genai(key_obj.key)
        
        try:
            # Prepare the prompt
            prompt = self._create_prompt(language_hint)
            
            # Encode image
            image_data = base64.b64encode(image_bytes).decode('utf-8')
            
            # Prepare content parts
            content_parts = [
                prompt,
                {
                    "mime_type": "image/jpeg",
                    "data": image_data
                }
            ]
            
            # Generate content
            start_time = time.time()
            response = self.model.generate_content(content_parts)
            processing_time = time.time() - start_time
            
            if not response.text:
                logger.error(f"Empty response from Gemini API using key {key_obj.alias}")
                key_obj.record_request(success=False, error_message="Empty response")
                raise ValueError("Empty response from API")
            
            extracted_text = response.text.strip()
            
            # Record successful request
            key_obj.record_request(success=True)
            
            logger.info(f"Successfully extracted text using key {key_obj.alias}. "
                       f"Chars: {len(extracted_text)}, Time: {processing_time:.2f}s")
            
            return extracted_text, key_obj.alias
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to extract text using key {key_obj.alias}: {error_msg}")
            
            # Record failed request
            key_obj.record_request(success=False, error_message=error_msg)
            
            # Check if we should retry with different key
            if "429" in error_msg or "quota" in error_msg.lower():
                logger.warning(f"Key {key_obj.alias} may be rate limited or out of quota")
            
            raise
    
    def _create_prompt(self, language_hint: str) -> str:
        """Create optimized prompt for Nepali OCR"""
        return f"""
        Extract all text from this Nepali document image with maximum accuracy.
        
        CRITICAL INSTRUCTIONS:
        1. Extract EXACT Nepali text including all Devanagari script characters
        2. Preserve original line breaks, spacing, and paragraph structure
        3. DO NOT translate, interpret, or modify the text
        4. If text is unclear or unreadable, mark as [UNREADABLE]
        5. Preserve tables, lists, and formatting indicators
        6. Include page numbers if present
        7. Handle mixed languages (Nepali/English) appropriately
        8. Output ONLY the extracted text, no explanations
        
        Document Language: {language_hint}
        Script: Devanagari
        
        Important Nepali characters to preserve:
        - Vowels: अ आ इ ई उ ऊ ऋ ॠ ऌ ॡ ए ऐ ओ औ
        - Consonants: क ख ग घ ङ च छ ज झ ञ ट ठ ड ढ ण त थ द ध न प फ ब भ म य र ल व श ष स ह
        - Vowel signs / Matras:  ि ी ु ू ृ ॄ ॢ ॣ े ै ो 
        - Special characters: ं ँ ः ्
        - Nasalization / visarga / halant modifiers: ् ं ँ ः
        - Consonant ligatures / conjuncts (examples): क्ष त्र ज्ञ
        
        Output format:
        [Start of extracted text]
        <exact text from document>
        [End of extracted text]
        """
    
    def validate_response(self, text: str) -> bool:
        """Validate OCR response quality"""
        if not text or len(text.strip()) < 10:
            return False
        
        # Check for Nepali characters (Devanagari Unicode range)
        nepali_chars = any('\u0900' <= char <= '\u097F' for char in text)
        
        if not nepali_chars:
            logger.warning("No Nepali characters detected in OCR output")
            # Still return True as some documents might have English content
        
        return True
    
    def get_current_key_info(self) -> Optional[Dict]:
        """Get information about current API key"""
        if self.current_key:
            return self.current_key.get_stats()
        return None