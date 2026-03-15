import os

from dotenv import load_dotenv

_ = load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "groq")


def get_completion(prompt: str) -> str:
    if PROVIDER == "groq":
        return _groq(prompt)
    elif PROVIDER == "gemini":
        return _gemini(prompt)
    elif PROVIDER == "anthropic":
        return _anthropic(prompt)
    else:
        raise ValueError(f"Unknown provider: {PROVIDER}")


def _groq(prompt: str) -> str:
    from groq import Groq

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content


def _gemini(prompt: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    return response.text


def _anthropic(prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
