import json
import logging
import re
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

    def _parse_json(self, text: str) -> dict:
        # Strip markdown formatting
        text = text.replace('```json', '').replace('```', '')
        
        # Extract everything between the first '{' and the last '}'
        start = text.find('{')
        end = text.rfind('}')
        
        if start != -1 and end != -1:
            text = text[start:end+1]
            
        return json.loads(text)

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

    def generate_quiz_data(self, topic: str, agegroup: str) -> dict:
        q_prompt = (
            f"Generate a quiz about '{topic}' for the {agegroup} age group. "
            "You MUST return strictly valid JSON only. Do not include markdown formatting, conversational text, or trailing commas. "
            "Ensure any quotes inside the text are properly escaped. Use this exact schema:\n"
            '{"title": "Quiz Title", "description": "Quiz Description", "questions": [{"text": "Question text here", "explanation": "Explanation here"}]}'
        )
        q_res = self.get_llm_response(q_prompt)
        quiz_data = self._parse_json(q_res)

        for q in quiz_data.get("questions", []):
            a_prompt = (
                f"Question: '{q.get('text')}'. Provide exactly 4 answers (1 correct, 3 incorrect). "
                "You MUST return strictly valid JSON only. Do not include markdown formatting or conversational text. "
                "Ensure any quotes inside the text are properly escaped. Use this exact schema:\n"
                '{"answers": [{"text": "Answer text", "is_correct": true}, {"text": "Wrong answer", "is_correct": false}]}'
            )
            a_res = self.get_llm_response(a_prompt)
            a_data = self._parse_json(a_res)
            q["answers"] = a_data.get("answers", [])

        return quiz_data