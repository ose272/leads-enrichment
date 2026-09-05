"""Groq LLM client wrapper for the Outreach Agent."""

from __future__ import annotations

import logging
import os
from typing import Optional

from groq import Groq

LOGGER = logging.getLogger("llm_client")


class LLMCallError(Exception):
    """Custom exception for LLM API call failures."""
    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(message)
        self.original_error = original_error


class GroqClient:
    """Wrapper for Groq API with error handling and retries."""
    
    def __init__(self, api_key: str = None, model: str = "llama-3.1-8b-instant"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        self.model = model
        self.client = Groq(api_key=self.api_key)
    
    def generate(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
        """Generate a response from the LLM with retry logic.
        
        Args:
            prompt: The prompt to send to the LLM
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            
        Returns:
            Generated text response
            
        Raises:
            LLMCallError: If the API call fails after retries
        """
        for attempt in range(2):  # Try once, retry once
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                if attempt == 0:
                    LOGGER.warning("Groq API call failed (attempt 1/2): %s. Retrying...", e)
                else:
                    LOGGER.error("Groq API call failed after 2 attempts: %s", e)
                    raise LLMCallError(f"Groq API call failed: {e}", original_error=e)
        
        # Should not reach here
        raise LLMCallError("Unexpected error in generate()")
