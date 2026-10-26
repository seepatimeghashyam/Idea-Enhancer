def build_idea_enhancement_prompt(
    student_idea,
    similar_projects,
    research_papers
):
    prompt = f"""
You are an academic project idea enhancement assistant.

STUDENT'S PROJECT IDEA:
{student_idea}

SIMILAR EXISTING PROJECTS:
{similar_projects}

RETRIEVED RESEARCH PAPERS:
{research_papers}

YOUR TASK:
1. Explain the student's project idea in simple language.
2. Compare it with the existing projects provided.
3. Identify overlapping features and explain the differences.
4. Suggest three practical ways to improve the idea.
5. Explain the technologies that could be useful and why.
6. Use research papers as supporting evidence when relevant.
7. If the evidence is insufficient, clearly say so.

IMPORTANT RULES:
- Use only the supplied project records and research papers as evidence.
- Never invent project records, paper titles, authors, or links.
- Do not claim an idea is completely unique based on limited search results.
- Clearly distinguish evidence from your own recommendations.
- Keep the explanation clear and suitable for engineering students.

FORMAT YOUR RESPONSE:
1. Idea Explanation
2. Similarities with Existing Projects
3. Important Differences
4. Three Improvement Suggestions
5. Recommended Technologies
6. Research Evidence
7. Limitations
"""
    return prompt


if __name__ == "__main__":
    idea = "AI-based plant disease detection"

    projects = [
        {
            "title": "Plant Disease Detection Using CNN",
            "technologies": "Python, CNN, TensorFlow"
        }
    ]

    papers = [
        {
            "title": "Example research paper",
            "url": "https://example.org/paper"
        }
    ]

    result = build_idea_enhancement_prompt(
        idea,
        projects,
        papers
    )

    print(result)
    import os
from google import genai


def generate_idea_enhancement(prompt):
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return "Error: Gemini API key is missing."

    try:
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        return response.text

    except Exception as e:
        return f"Gemini error: {e}"