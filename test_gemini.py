import os
from getpass import getpass
from google import genai

# Get your Gemini API key securely
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    api_key = getpass("Paste your Gemini API key: ")

if not api_key:
    print("Error: API key is missing.")
else:
    try:
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents="Explain the Idea Enhancer project in 3 simple sentences."
        )

        print("\nGemini API is working!")
        print("\nResponse:")
        print(response.text)

    except Exception as e:
        print("\nGemini API error:")
        print(e)