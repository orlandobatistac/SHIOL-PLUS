"""
Google Gemini AI Service for Lottery Ticket Processing
Replaces Google Vision API with Gemini Pro Vision for enhanced ticket number extraction.
"""

import os
import base64
import json
from typing import Dict, List, Optional, Any
from loguru import logger
import google.generativeai as genai


class GeminiService:
    """
    Google Gemini AI service for processing lottery ticket images.
    Uses Gemini Pro Vision model for intelligent text extraction.
    """

    def __init__(self):
        """Initialize the Gemini service with API configuration."""
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        # Configure Gemini AI
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash-lite')  # Use most cost-efficient model with vision
        
        # Define the prompt template for lottery ticket analysis
        self.prompt_template = """
Analyze this lottery ticket image. Extract ALL the lottery plays, numbers, and draw date information. 
This is a North Carolina Powerball ticket with up to 5 plays labeled A, B, C, D, E.

Each play has:
- 5 main numbers (between 1-69)  
- 1 Powerball number (between 1-26)

Also extract:
- Draw date (when the drawing will take place)

Return ONLY a valid JSON object with this structure:
{
  "draw_date": "YYYY-MM-DD" or null if not found,
  "plays": [
    {
      "jugada": "A", 
      "numeros": [2, 3, 15, 20, 22],
      "powerball": 7
    },
    {
      "jugada": "B",
      "numeros": [10, 15, 21, 48, 62], 
      "powerball": 4
    }
  ]
}

Look for date information like:
- "MON JUL28 25" (Monday July 28, 2025)
- "WED AUG03 25" (Wednesday August 3, 2025) 
- Any date format on the ticket

IMPORTANT:
- Return ONLY the JSON object, no other text
- Include ALL visible plays on the ticket
- Sort main numbers in ascending order
- Verify all numbers are within valid ranges (1-69 main, 1-26 Powerball)
- Extract draw date if visible (format as YYYY-MM-DD)
"""

        logger.info("Gemini service initialized successfully")

    def encode_image_to_base64(self, image_data: bytes) -> str:
        """
        Encode image bytes to base64 string.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Base64 encoded string
        """
        return base64.b64encode(image_data).decode('utf-8')

    def process_ticket_image(self, image_data: bytes) -> Dict[str, Any]:
        """
        Process a lottery ticket image using Gemini Pro Vision.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Dictionary with extraction results
        """
        try:
            logger.debug("Starting Gemini image processing")
            
            # Encode image to base64
            base64_image = self.encode_image_to_base64(image_data)
            
            # Prepare content for Gemini
            contents = [
                self.prompt_template,
                {
                    'mime_type': 'image/jpeg',
                    'data': base64_image
                }
            ]
            
            # Generate response from Gemini
            logger.debug("Sending request to Gemini API")
            response = self.model.generate_content(contents)
            
            if not response.text:
                logger.error("Empty response from Gemini API")
                return {
                    'success': False,
                    'error': 'No response from Gemini API',
                    'plays': [],
                    'extraction_method': 'gemini_vision'
                }
            
            logger.debug(f"Raw Gemini response: {response.text}")
            
            # Clean and parse JSON response
            json_text = response.text.strip()
            
            # Remove any markdown code blocks if present
            if json_text.startswith('```json'):
                json_text = json_text[7:]
            if json_text.startswith('```'):
                json_text = json_text[3:]
            if json_text.endswith('```'):
                json_text = json_text[:-3]
            
            json_text = json_text.strip()
            
            # Parse JSON
            try:
                response_data = json.loads(json_text)
                
                # Handle new format with draw_date and plays
                if isinstance(response_data, dict) and 'plays' in response_data:
                    plays_data = response_data['plays']
                    draw_date = response_data.get('draw_date')
                    logger.debug(f"Extracted draw date: {draw_date}")
                elif isinstance(response_data, list):
                    # Backward compatibility with old format
                    plays_data = response_data
                    draw_date = None
                    logger.debug("No draw date in response (old format)")
                else:
                    logger.error("Gemini response has invalid format")
                    return {
                        'success': False,
                        'error': 'Invalid JSON format: expected object with plays array or array',
                        'plays': [],
                        'extraction_method': 'gemini_vision'
                    }
                
                # Convert to internal format and validate
                processed_plays = self._process_and_validate_plays(plays_data)
                
                logger.info(f"Gemini successfully extracted {len(processed_plays)} plays")
                
                return {
                    'success': True,
                    'plays': processed_plays,
                    'draw_date': draw_date,
                    'total_plays': len(processed_plays),
                    'extraction_method': 'gemini_vision',
                    'raw_response': response.text
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Gemini JSON response: {e}")
                logger.error(f"Response text: {json_text}")
                return {
                    'success': False,
                    'error': f'JSON parsing failed: {str(e)}',
                    'plays': [],
                    'extraction_method': 'gemini_vision',
                    'raw_response': response.text
                }
                
        except Exception as e:
            logger.error(f"Gemini processing error: {str(e)}")
            return {
                'success': False,
                'error': f'Gemini API error: {str(e)}',
                'plays': [],
                'extraction_method': 'gemini_vision'
            }

    def _process_and_validate_plays(self, plays_data: List[Dict]) -> List[Dict]:
        """
        Process and validate plays from Gemini response.
        
        Args:
            plays_data: Raw plays data from Gemini
            
        Returns:
            List of validated play dictionaries
        """
        processed_plays = []
        
        for i, play in enumerate(plays_data):
            try:
                # Extract data
                jugada = play.get('jugada', f'Play{i+1}').upper()
                numeros = play.get('numeros', [])
                powerball = play.get('powerball')
                
                # Validate main numbers
                if not isinstance(numeros, list) or len(numeros) != 5:
                    logger.warning(f"Play {jugada}: Invalid main numbers count: {len(numeros)}")
                    continue
                
                # Convert to integers and validate range
                try:
                    main_numbers = [int(n) for n in numeros]
                    if any(n < 1 or n > 69 for n in main_numbers):
                        logger.warning(f"Play {jugada}: Main numbers out of range 1-69: {main_numbers}")
                        continue
                    
                    # Sort main numbers
                    main_numbers = sorted(main_numbers)
                    
                except (ValueError, TypeError):
                    logger.warning(f"Play {jugada}: Invalid main number format: {numeros}")
                    continue
                
                # Validate Powerball
                try:
                    powerball_num = int(powerball)
                    if powerball_num < 1 or powerball_num > 26:
                        logger.warning(f"Play {jugada}: Powerball out of range 1-26: {powerball_num}")
                        continue
                        
                except (ValueError, TypeError):
                    logger.warning(f"Play {jugada}: Invalid Powerball format: {powerball}")
                    continue
                
                # Create validated play
                processed_play = {
                    'line': jugada,
                    'main_numbers': main_numbers,
                    'powerball': powerball_num
                }
                
                processed_plays.append(processed_play)
                logger.debug(f"Validated play {jugada}: {main_numbers} PB:{powerball_num}")
                
            except Exception as e:
                logger.error(f"Error processing play {i}: {str(e)}")
                continue
        
        return processed_plays

    def test_connection(self) -> Dict[str, Any]:
        """
        Test Gemini API connection with a simple request.
        
        Returns:
            Dictionary with test results
        """
        try:
            # Simple text generation test
            model = genai.GenerativeModel('gemini-2.5-flash-lite')
            response = model.generate_content("Hello")
            
            if response.text:
                logger.info("Gemini API connection test successful")
                return {
                    'success': True,
                    'message': 'Gemini API connection working',
                    'model': 'gemini-2.5-flash-lite'
                }
            else:
                return {
                    'success': False,
                    'error': 'No response from Gemini API'
                }
                
        except Exception as e:
            logger.error(f"Gemini API connection test failed: {str(e)}")
            return {
                'success': False,
                'error': f'Connection test failed: {str(e)}'
            }


def create_gemini_service() -> GeminiService:
    """
    Create and configure a Gemini service instance.
    
    Returns:
        Configured GeminiService instance
    """
    try:
        return GeminiService()
    except Exception as e:
        logger.error(f"Failed to create Gemini service: {str(e)}")
        raise


# Test the service if run directly
if __name__ == "__main__":
    try:
        service = create_gemini_service()
        test_result = service.test_connection()
        print(json.dumps(test_result, indent=2))
    except Exception as e:
        print(f"Service creation failed: {e}")