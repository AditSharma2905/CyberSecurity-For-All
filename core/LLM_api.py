from groq import Groq
from google import genai
from google.genai import types
    
SYSTEM_PROMT =  "You are a friendly cybersecurity tutor for ages <15 to >50." \
                "Help with cybersecurity tasks. Provide accurate info & suggestions. " \
                "Short, informative answers with clear headings. Easy for teens/adults/elders." \
                "Include relevant resources, fun facts. Suggest other topics."

class LLM_API():
    def __init__(self) -> None:
        self.groq_client = Groq()
        self.gemini_client = genai.Client()
        self.providers = [self._get_groq_response, self._get_gemini_reponse]


    def get_llm_response(self, prompt: str) -> str:
        """
        Args:
            prompt: The input text.
        Returns:
            The generated response.
        Raises:
            ConnectionError: If both primary and fallback APIs fail.
            ValueError: If the prompt is empty.
        """

        if not prompt.strip():
            raise ValueError("The given prompt was empty")

        for provider in self.providers:
            try:
                return provider(prompt)
            except Exception as e:
                print(f"Error with {provider.__name__}: {e}")
 
        raise ConnectionError("Both LLMs did not respond")


    def _get_groq_response(self, prompt: str) -> str:
        """
        Args:
            prompt: The input text.

        Returns:
            The generated response.

        Raises:
            ConnectionError: If both primary and fallback APIs fail.
            ValueError: If the prompt is empty.
        """

        response = self.groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMT
                    },
                {
                    "role": "user",
                    "content": prompt,
                    }
                ],
            model="llama-3.1-8b-instant"
            )

        if response.choices[0].message.content is None:
            raise ValueError("Gemini response was None")
        
        return response.choices[0].message.content


    def _get_gemini_reponse(self, prompt: str) -> str:
        """
        Args:
            prompt: The input text.

        Returns:
            The generated response.

        Raises:
            ConnectionError: If both primary and fallback APIs fail.
            ValueError: If the prompt is empty.
        """ 

        response = self.gemini_client.models.generate_content(
            model="gemini-3-flash-preview",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMT),
            contents=prompt)

        if response.text is None:
            raise ValueError("Gemini response was None")  

        return response.text