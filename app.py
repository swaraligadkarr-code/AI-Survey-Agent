
import os
import re
import json
import time
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from google import genai

# ---------------- CONFIGURATION ----------------

load_dotenv()

st.set_page_config(
    page_title="Survey Studio AI",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

DATA_DIR = Path("survey_data")
DATA_DIR.mkdir(exist_ok=True)

SURVEYS_FILE = DATA_DIR / "surveys.json"
RESPONSES_FILE = DATA_DIR / "responses.json"

api_key = os.getenv("GEMINI_API_KEY")


# ---------------- LOCAL STORAGE ----------------

def load_json(path):
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_json(path, data):
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


# ---------------- SESSION STATE ----------------

if "current_survey" not in st.session_state:
    st.session_state.current_survey = None

if "page" not in st.session_state:
    st.session_state.page = "Create Survey"


# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.title("📝 Survey Studio AI")
    st.caption("AI-powered survey workspace")
    st.divider()

    page = st.radio(
        "Navigation",
        [
            "Create Survey",
            "Edit Surveys",
            "Collect Responses",
            "Analytics",
            "Survey History"
        ],
        key="navigation"
    )

    st.session_state.page = page

    st.divider()
    st.caption("Powered by Google Gemini")


# ---------------- HELPER FUNCTIONS ----------------

def clean_text(text):
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    text = text.replace("**", "").replace("__", "")
    text = text.replace("`", "")
    text = re.sub(r"(?m)^\s*[-*_]{3,}\s*$", "", text)
    return text.strip()


def generate_survey(topic, purpose, number, question_type, audience):
    if not api_key:
        raise ValueError("Gemini API key not found. Check your .env file.")

    client = genai.Client(api_key=api_key)

    prompt = f"""
You are an expert survey designer.

Create exactly {number} survey questions.

Topic: {topic}
Purpose: {purpose or "Collect opinions about this topic"}
Target audience: {audience}
Question type: {question_type}

Requirements:
1. Use simple, clear, unbiased language.
2. Include a suitable title and short introduction.
3. Number every question.
4. Give four options for multiple-choice questions.
5. Use a 1–5 scale for rating questions.
6. Include Yes and No for binary questions.
7. Make open-ended questions answerable in writing.
8. Avoid unnecessary personal information.
9. Avoid repetitive questions.
10. Do not invent correct answers for opinion questions.
11. Match every question to the requested type.
12. Return a clean, readable survey.
"""

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt
            )
            if not response.text:
                raise ValueError("The AI returned an empty response.")
            return clean_text(response.text)

        except Exception as error:
            message = str(error)
            if ("503" in message or "UNAVAILABLE" in message) and attempt < 2:
                time.sleep(3 * (attempt + 1))
            else:
                raise


# ---------------- PAGE: CREATE SURVEY ----------------

if page == "Create Survey":
    st.title("Create a New Survey")
    st.write("Generate a custom questionnaire using AI.")

    with st.container(border=True):
        st.subheader("Survey Details")

        col1, col2 = st.columns(2)

        with col1:
            topic = st.text_input(
                "Survey topic *",
                placeholder="e.g. College canteen satisfaction"
            )

            audience = st.selectbox(
                "Target audience",
                [
                    "College students",
                    "School students",
                    "Teachers",
                    "General public",
                    "Employees"
                ]
            )

        with col2:
            number = st.slider("Number of questions", 5, 20, 10)

            question_type = st.selectbox(
                "Question type",
                [
                    "Mixed question types",
                    "Multiple choice",
                    "Rating scale",
                    "Yes/No",
                    "Open-ended"
                ]
            )

        purpose = st.text_area(
            "What do you want to learn?",
            placeholder="Describe the purpose of this survey..."
        )

        generate = st.button(
            "✨ Generate Survey",
            type="primary",
            use_container_width=True
        )

    if generate:
        if not topic.strip():
            st.warning("Please enter a survey topic.")
        else:
            try:
                with st.spinner("Creating your survey..."):
                    survey_text = generate_survey(
                        topic.strip(),
                        purpose.strip(),
                        number,
                        question_type,
                        audience
                    )

                survey_id = datetime.now().strftime("%Y%m%d%H%M%S%f")

                survey = {
                    "id": survey_id,
                    "title": topic.strip(),
                    "purpose": purpose.strip(),
                    "audience": audience,
                    "question_type": question_type,
                    "question_count": number,
                    "content": survey_text,
                    "created_at": datetime.now().isoformat()
                }

                st.session_state.current_survey = survey

                surveys = load_json(SURVEYS_FILE)
                surveys.append(survey)
                save_json(SURVEYS_FILE, surveys)

                st.success("Survey generated and saved locally!")

            except Exception as error:
                st.error("Unable to generate the survey.")
                st.caption(str(error))

    survey = st.session_state.current_survey

    if survey:
        st.divider()
        st.subheader("Survey Preview")
        st.markdown(survey["content"])

        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                "⬇️ Download TXT",
                data=survey["content"],
                file_name="survey.txt",
                mime="text/plain",
                use_container_width=True
            )

        with col2:
            pdf_placeholder = st.button(
                "📄 PDF export — coming next",
                disabled=True,
                use_container_width=True
            )


# ---------------- PAGE: EDIT SURVEYS ----------------

elif page == "Edit Surveys":
    st.title("Edit Surveys")
    st.info(
        "The next upgrade will add editable question fields, "
        "plus add and delete question controls."
    )

    surveys = load_json(SURVEYS_FILE)

    if surveys:
        options = {
            f'{s["title"]} — {s["created_at"][:10]} ({s["id"]})': s
            for s in surveys
        }
        selected_label = st.selectbox("Choose a saved survey", list(options))
        st.text_area(
            "Survey content",
            value=options[selected_label]["content"],
            height=300,
            disabled=True
        )
    else:
        st.info("Your saved surveys will appear here.")


# ---------------- PAGE: COLLECT RESPONSES ----------------

elif page == "Collect Responses":
    st.title("Collect Responses")
    st.info(
        "The next upgrade will add a respondent form and "
        "save answers locally."
    )


# ---------------- PAGE: ANALYTICS ----------------

elif page == "Analytics":
    st.title("Survey Analytics")
    surveys = load_json(SURVEYS_FILE)
    responses = load_json(RESPONSES_FILE)

    col1, col2, col3 = st.columns(3)
    col1.metric("Surveys created", len(surveys))
    col2.metric("Responses received", len(responses))
    col3.metric(
        "Average responses per survey",
        round(len(responses) / len(surveys), 1) if surveys else 0
    )

    st.info(
        "Question-level charts and response analysis will be added "
        "after response collection is implemented."
    )


# ---------------- PAGE: SURVEY HISTORY ----------------

elif page == "Survey History":
    st.title("Survey History")
    surveys = load_json(SURVEYS_FILE)

    if surveys:
        for survey in reversed(surveys):
            with st.expander(
                f'{survey["title"]} — {survey["created_at"][:10]}'
            ):
                st.write("Audience:", survey["audience"])
                st.write("Questions requested:", survey["question_count"])
                st.text(survey["content"])

                st.download_button(
                    "Download this survey",
                    data=survey["content"],
                    file_name=f'survey_{survey["id"]}.txt',
                    mime="text/plain",
                    key=f'download_{survey["id"]}'
                )
    else:
        st.info("No saved surveys yet. Create your first survey!")


# ---------------- FOOTER ----------------

st.divider()
st.caption("Survey Studio AI | Built with Python, Streamlit & Gemini")
