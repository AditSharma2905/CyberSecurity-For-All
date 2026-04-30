import logging

from google import genai
from google.genai import types
from groq import Groq

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a friendly cybersecurity tutor for ages <15 to >50. "
    "Help with cybersecurity tasks. Provide accurate info & suggestions. "
    "Short, informative answers with clear headings. Easy for teens/adults/elders. "
    "Include relevant resources, fun facts. Suggest other topics."
)

class LLMAPI:
    def __init__(self) -> None:
        self.groq_client = Groq()
        self.gemini_client = genai.Client()
        self.providers = [self._get_groq_response, self._get_gemini_response]

    def get_llm_response(self, prompt: str) -> str:
        if not prompt.strip():
            raise ValueError("The given prompt was empty")

        for provider in self.providers:
            try:
                return provider(prompt)
            except Exception as e:
                logger.error(f"Error with {provider.__name__}: {e}")

        raise ConnectionError("All LLM providers failed to respond")

    def _get_groq_response(self, prompt: str) -> str:
        response = self.groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Groq response content was None")
        return content

    def _get_gemini_response(self, prompt: str) -> str:
        response = self.gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            contents=prompt,
        )
        if response.text is None:
            raise ValueError("Gemini response text was None")
        return response.text
