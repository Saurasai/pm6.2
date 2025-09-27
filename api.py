import asyncio
import re
import streamlit as st
import google.genai as genai
from dotenv import load_dotenv
import os
import logging
import nest_asyncio

logger = logging.getLogger(__name__)

# Apply nest_asyncio for Streamlit compatibility
nest_asyncio.apply()

# Configure Gemini API
import streamlit as st
import logging

logger = logging.getLogger(__name__)

API_KEY = None

try:
    # Access Gemini API key from Streamlit secrets
    API_KEY = st.secrets.get("GEMINI_API_KEY")

    if not API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in Streamlit secrets")

    genai.api_key = API_KEY
    logger.info("Gemini API configured successfully")

except Exception as e:
    logger.error(f"API Key configuration error: {e}")
    st.error(f"API Key configuration error: {e}")
    raise

# Initialize model
try:
    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    logger.info("Gemini model initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Gemini model: {e}")
    st.error(f"Failed to initialize Gemini model: {e}")
    raise

async def generate_single_prompt(prompt: str) -> str:
    logger.info("Generating content with Gemini API")
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: model.generate_content(prompt))
        logger.debug("Content generated successfully")
        return response.text
    except Exception as e:
        logger.error(f"Error generating content from Gemini API: {e}")
        st.error(f"Error generating content from Gemini API: {e}")
        return ""

def split_numbered_drafts(text: str) -> list[str]:
    logger.info("Splitting generated drafts")
    try:
        pattern = r"(?:^|\n)(\d[\.\)]\s.*?)(?=\n\d[\.\)]\s|$)"
        matches = re.findall(pattern, text, re.DOTALL)
        if len(matches) < 3:
            parts = re.split(r"\n\d[\.\)]\s", text)
            drafts = [p.strip() for p in parts if p.strip()]
            logger.debug(f"Split into {len(drafts)} drafts (fallback method)")
            return drafts if len(drafts) >= 3 else [text.strip()]
        logger.debug(f"Split into {len(matches)} drafts")
        return [m.strip() for m in matches]
    except Exception as e:
        logger.error(f"Error parsing generated drafts: {e}")
        st.error(f"Error parsing generated drafts: {e}")
        return [text.strip()]

async def generate_platform_drafts(platform: str, vars: dict, prompt_templates: dict) -> list[str]:
    logger.info(f"Generating drafts for platform: {platform}")
    try:
        template = prompt_templates[platform]
        prompt = template.format(**vars)
        txt = await generate_single_prompt(prompt)
        drafts = split_numbered_drafts(txt)
        logger.debug(f"Generated {len(drafts)} drafts for {platform}")
        return drafts[:3]
    except Exception as e:
        logger.error(f"Error generating drafts for {platform}: {e}")
        st.error(f"Error generating drafts for {platform}: {e}")

        return []



