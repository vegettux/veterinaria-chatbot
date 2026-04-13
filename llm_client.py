import os
from typing import Optional

from groq import Groq


DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


def get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY no está configurada.")
    return Groq(api_key=api_key)


def get_groq_model() -> str:
    return os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)


def generar_respuesta_llm(prompt: str, system_prompt: Optional[str] = None) -> str:
    client = get_groq_client()
    model = get_groq_model()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
    )
    return completion.choices[0].message.content or ""
