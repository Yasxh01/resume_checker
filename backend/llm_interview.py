import os
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Attempt to import and initialize the Gemini client
_gemini_available = False

try:
    from google import genai
    api_key = os.getenv("GEMINI_API_KEY", "")
    if api_key:
        _client = genai.Client(api_key=api_key)
        _gemini_available = True
        logger.info("LLM Interview: Gemini client initialized successfully. ✓")
    else:
        logger.warning(
            "LLM Interview: GEMINI_API_KEY not found in environment. "
            "Will use fallback generic questions."
        )
except ImportError:
    logger.warning("LLM Interview: google-genai package not installed. Using fallback.")


async def generate_interview_questions(
    candidate_name: str,
    matched_skills: list,
    missing_skills: list,
    jd_text: str,
    api_key: str = ""
) -> dict:
    """
    Generates 3 personalized technical interview questions.
    """
    
    matched_str = ", ".join(matched_skills) if matched_skills else "None explicitly matched"
    missing_str = ", ".join(missing_skills) if missing_skills else "None"

    # ----------------------------------------------------------
    # ATTEMPT LLM GENERATION
    # ----------------------------------------------------------
    use_gemini = False
    client = None
    try:
        from google import genai
        final_key = api_key if api_key else os.getenv("GEMINI_API_KEY", "")
        if final_key:
            client = genai.Client(api_key=final_key)
            use_gemini = True
            if api_key:
                logger.info("LLM Interview: Using provided dynamic API Key.")
    except ImportError:
        logger.warning("LLM Interview: Failed to import google-genai.")
    except Exception as e:
        logger.warning(f"LLM Interview: Failed to configure dynamic key: {e}")

    if use_gemini:
        try:
            prompt = f"""You are a senior technical interviewer. Generate exactly 3 technical interview questions for {candidate_name} based on their profile.

JOB DESCRIPTION:
{jd_text}

CANDIDATE: {candidate_name}
MATCHED SKILLS: {matched_str}
MISSING SKILLS: {missing_str}

REQUIREMENTS:
1. Question 1 must deeply test one of their MATCHED SKILLS to verify their expertise.
2. Question 2 must evaluate how they would handle a scenario requiring one of their MISSING SKILLS.
3. Question 3 must be a situational/architecture question tying their background to the Job Description.

FORMAT REQUIREMENTS:
Return valid JSON matching this exact structure:
{{
  "questions": [
    {{
      "type": "Matched Skill Deep-Dive",
      "question": "The actual question text...",
      "rationale": "Why you are asking this..."
    }}
  ]
}}
Do NOT wrap the JSON in markdown code blocks. Just output raw JSON.
"""
            response = await client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            response_text = response.text.strip()
            
            # Clean up markdown if the LLM adds it anyway
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            data = json.loads(response_text)
            logger.info(f"LLM Interview: Generated for {candidate_name}")

            return {
                "source": "llm",
                "questions": data.get("questions", [])
            }

        except Exception as e:
            logger.warning(f"LLM Interview: API call failed — {e}. Using rule-based fallback.")

    # ----------------------------------------------------------
    # FALLBACK GENERATION
    # ----------------------------------------------------------
    q1_skill = matched_skills[0] if matched_skills else "your technical stack"
    q2_skill = missing_skills[0] if missing_skills else "a completely new technology"
    
    fallback_questions = [
        {
            "type": "Matched Skill Deep-Dive",
            "question": f"Can you describe the most complex project where you utilized {q1_skill}? What were the key technical challenges you faced?",
            "rationale": f"To verify their claimed proficiency in {q1_skill}."
        },
        {
            "type": "Adaptability & Missing Skills",
            "question": f"This role heavily involves {q2_skill}, which isn't prominent on your resume. How would you approach learning and implementing this on the job?",
            "rationale": f"To assess their ability to bridge the gap in {q2_skill}."
        },
        {
            "type": "Situational Fit",
            "question": "Based on the job description, we need someone who can scale systems efficiently. Describe a time you optimized a slow system.",
            "rationale": "To evaluate their practical problem-solving skills relative to the role."
        }
    ]

    return {
        "source": "fallback",
        "questions": fallback_questions
    }
