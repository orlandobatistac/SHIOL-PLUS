"""
Image preprocessing module for lottery ticket OCR enhancement.
Optimized for North Carolina Powerball ticket format.
"""

import numpy as np
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import io
from typing import Tuple, List, Optional
from loguru import logger


class ImagePreprocessor:
    """Advanced image preprocessing for lottery ticket OCR optimization."""
    
    def __init__(self):
        """Initialize the image preprocessor."""
        self.debug_mode = False
        logger.info("Image preprocessor initialized")
    
    def enhance_ticket_image(self, image_data: bytes, 
                           methods: Optional[List[str]] = None) -> List[Tuple[bytes, str, float]]:
        """
        Apply multiple enhancement methods to optimize OCR performance.
        
        Args:
            image_data: Raw image bytes
            methods: List of enhancement methods to apply
            
        Returns:
            List of (enhanced_image_bytes, method_name, confidence_score) tuples
        """
        try:
            if methods is None:
                methods = ['contrast_enhance', 'sharpen_text', 'binarize', 'resize_optimal', 'denoise']
            
            # Load original image
            original_pil = Image.open(io.BytesIO(image_data))
            logger.info(f"Original image size: {original_pil.size}, mode: {original_pil.mode}")
            
            enhanced_images = []
            
            # Always include original as baseline
            original_bytes = self._pil_to_bytes(original_pil)
            enhanced_images.append((original_bytes, 'original', 1.0))
            
            # Apply each enhancement method
            for method in methods:
                try:
                    if method == 'contrast_enhance':
                        enhanced = self._enhance_contrast(original_pil)
                        enhanced_images.append((self._pil_to_bytes(enhanced), method, 0.9))
                    
                    elif method == 'sharpen_text':
                        enhanced = self._sharpen_for_text(original_pil)
                        enhanced_images.append((self._pil_to_bytes(enhanced), method, 0.85))
                    
                    elif method == 'binarize':
                        enhanced = self._apply_binarization(original_pil)
                        enhanced_images.append((self._pil_to_bytes(enhanced), method, 0.8))
                    
                    elif method == 'resize_optimal':
                        enhanced = self._resize_for_ocr(original_pil)
                        enhanced_images.append((self._pil_to_bytes(enhanced), method, 0.75))
                    
                    elif method == 'denoise':
                        enhanced = self._reduce_noise(original_pil)
                        enhanced_images.append((self._pil_to_bytes(enhanced), method, 0.7))
                    
                    elif method == 'perspective_correct':
                        enhanced = self._correct_perspective_pil(original_pil)
                        if enhanced:
                            enhanced_images.append((self._pil_to_bytes(enhanced), method, 0.9))
                    
                except Exception as e:
                    logger.warning(f"Enhancement method '{method}' failed: {e}")
                    continue
            
            logger.info(f"Generated {len(enhanced_images)} enhanced versions")
            return enhanced_images
            
        except Exception as e:
            logger.error(f"Image enhancement failed: {e}")
            # Return original as fallback
            return [(image_data, 'original_fallback', 1.0)]
    
    def _enhance_contrast(self, image: Image.Image) -> Image.Image:
        """Enhance contrast for better text visibility."""
        try:
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Apply contrast enhancement
            enhancer = ImageEnhance.Contrast(image)
            enhanced = enhancer.enhance(1.5)  # Increase contrast by 50%
            
            # Apply brightness adjustment
            brightness_enhancer = ImageEnhance.Brightness(enhanced)
            enhanced = brightness_enhancer.enhance(1.1)  # Slight brightness increase
            
            logger.debug("Applied contrast enhancement")
            return enhanced
            
        except Exception as e:
            logger.error(f"Contrast enhancement failed: {e}")
            return image
    
    def _sharpen_for_text(self, image: Image.Image) -> Image.Image:
        """Apply sharpening filter optimized for text."""
        try:
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Apply unsharp mask filter
            enhanced = image.filter(ImageFilter.UnsharpMask(
                radius=1.0,    # Small radius for text
                percent=120,   # Strong sharpening
                threshold=1    # Low threshold to affect most pixels
            ))
            
            # Apply additional sharpness enhancement
            sharpness_enhancer = ImageEnhance.Sharpness(enhanced)
            enhanced = sharpness_enhancer.enhance(1.3)
            
            logger.debug("Applied text sharpening")
            return enhanced
            
        except Exception as e:
            logger.error(f"Text sharpening failed: {e}")
            return image
    
    def _apply_binarization(self, image: Image.Image) -> Image.Image:
        """Apply adaptive binarization for text extraction."""
        try:
            # Convert to grayscale first
            if image.mode != 'L':
                gray_image = image.convert('L')
            else:
                gray_image = image.copy()
            
            # Convert PIL to OpenCV for advanced processing
            cv_image = np.array(gray_image)
            
            # Apply adaptive thresholding
            binary = cv2.adaptiveThreshold(
                cv_image,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11,  # Block size
                2    # C constant
            )
            
            # Convert back to PIL
            enhanced = Image.fromarray(binary)
            
            logger.debug("Applied adaptive binarization")
            return enhanced
            
        except Exception as e:
            logger.error(f"Binarization failed: {e}")
            return image
    
    def _resize_for_ocr(self, image: Image.Image) -> Image.Image:
        """Resize image to optimal dimensions for OCR."""
        try:
            width, height = image.size
            
            # Target dimensions for optimal OCR (empirically determined)
            target_width = 1200
            
            # Calculate optimal height maintaining aspect ratio
            aspect_ratio = height / width
            target_height = int(target_width * aspect_ratio)
            
            # Only resize if image is significantly different from target
            if abs(width - target_width) > 200:
                enhanced = image.resize(
                    (target_width, target_height), 
                    Image.Resampling.LANCZOS
                )
                logger.debug(f"Resized from {width}x{height} to {target_width}x{target_height}")
            else:
                enhanced = image.copy()
                logger.debug("Image size already optimal, no resize needed")
            
            return enhanced
            
        except Exception as e:
            logger.error(f"OCR resizing failed: {e}")
            return image
    
    def _reduce_noise(self, image: Image.Image) -> Image.Image:
        """Apply noise reduction for cleaner OCR."""
        try:
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert to OpenCV format
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Apply Non-local Means Denoising
            denoised = cv2.fastNlMeansDenoisingColored(
                cv_image,
                None,
                h=10,          # Filter strength
                hColor=10,     # Filter strength for color
                templateWindowSize=7,
                searchWindowSize=21
            )
            
            # Convert back to PIL
            enhanced = Image.fromarray(cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB))
            
            logger.debug("Applied noise reduction")
            return enhanced
            
        except Exception as e:
            logger.error(f"Noise reduction failed: {e}")
            return image
    
    def _correct_perspective_pil(self, image: Image.Image) -> Optional[Image.Image]:
        """Attempt basic perspective correction using PIL."""
        try:
            # For now, return None as perspective correction is complex
            # This could be implemented with more sophisticated edge detection
            logger.debug("Perspective correction skipped (not implemented)")
            return None
            
        except Exception as e:
            logger.error(f"Perspective correction failed: {e}")
            return None
    
    def _pil_to_bytes(self, image: Image.Image) -> bytes:
        """Convert PIL Image to bytes."""
        try:
            buffer = io.BytesIO()
            # Save as JPEG with high quality
            image.save(buffer, format='JPEG', quality=95, optimize=True)
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"PIL to bytes conversion failed: {e}")
            # Fallback: try PNG format
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            return buffer.getvalue()
    
    def get_optimal_enhancement_methods(self, image_type: str = 'lottery_ticket') -> List[str]:
        """
        Get optimal enhancement methods for specific image types.
        
        Args:
            image_type: Type of image being processed
            
        Returns:
            List of recommended enhancement methods
        """
        if image_type == 'lottery_ticket':
            return ['contrast_enhance', 'sharpen_text', 'resize_optimal', 'denoise']
        elif image_type == 'document':
            return ['binarize', 'contrast_enhance', 'resize_optimal']
        else:
            return ['contrast_enhance', 'sharpen_text', 'resize_optimal']