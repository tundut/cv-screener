import json
import sys
from decimal import Decimal
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.bedrock import evaluate_cv
from backend.config import load_settings
from backend.history import get_user_id, list_evaluations, save_evaluation
from backend.pdf_extractor import extract_text_from_pdf


st.set_page_config(page_title="CV Screener", page_icon="📄", layout="wide", initial_sidebar_state="expanded")
settings = load_settings()

st.markdown(
    """
    <style>
    :root { --ink: #152a3a; --muted: #60707d; --teal: #087f8c; --orange: #e46d3c; --paper: #f5f7f4; }
    .stApp { background: var(--paper); }
    [data-testid="stHeader"] { background: rgba(245,247,244,.86); }
    [data-testid="stSidebar"] { background: #152a3a; }
    [data-testid="stSidebar"] * { color: #edf4f1; }
    [data-testid="stSidebar"] .stCaption { color: #b8cbc9 !important; }
    [data-testid="stSidebar"] button,
    [data-testid="stSidebar"] button * { color: #edf4f1 !important; }
    [data-testid="stAppViewContainer"] h1,
    [data-testid="stAppViewContainer"] h2,
    [data-testid="stAppViewContainer"] h3,
    [data-testid="stAppViewContainer"] p,
    [data-testid="stAppViewContainer"] label,
    [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] { color: var(--ink); }
    [data-testid="stAppViewContainer"] .stCaption,
    [data-testid="stAppViewContainer"] [data-testid="stCaptionContainer"] { color: var(--muted); }
    [data-testid="stAppViewContainer"] [data-baseweb="tab-list"] button,
    [data-testid="stAppViewContainer"] [data-baseweb="tab-list"] button * { color: var(--muted) !important; }
    [data-testid="stAppViewContainer"] [data-baseweb="tab-list"] button[aria-selected="true"],
    [data-testid="stAppViewContainer"] [data-baseweb="tab-list"] button[aria-selected="true"] * { color: var(--orange) !important; }
    [data-testid="stAppViewContainer"] [data-testid="stExpander"] summary,
    [data-testid="stAppViewContainer"] [data-testid="stExpander"] summary * { color: #edf4f1 !important; }
    [data-testid="stAppViewContainer"] .stDownloadButton button { color: #edf4f1 !important; background: var(--ink); }
    [data-testid="stAppViewContainer"] .stButton button[kind="primary"] { color: white !important; background: var(--orange); }
    .brand { padding: .6rem 0 2rem; }
    .brand-mark { color: #f5a66f; font-size: 2rem; font-weight: 800; letter-spacing: .02em; }
    .brand-copy { color: #b8cbc9; font-size: .85rem; line-height: 1.45; }
    .eyebrow { color: var(--orange); font-size: .75rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }
    .hero-title { color: var(--ink); font-size: 2.45rem; font-weight: 800; letter-spacing: -.04em; line-height: 1.05; margin: .25rem 0 .6rem; }
    .hero-copy { color: var(--muted); font-size: 1rem; margin-bottom: 1.4rem; }
    .step-label { color: var(--ink); font-size: .8rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
    .result-score { color: var(--teal); font-size: 3.4rem; font-weight: 800; line-height: 1; }
    .result-name { color: var(--ink); font-size: 1.55rem; font-weight: 750; margin-top: .4rem; }
    div[data-testid="stFileUploader"] { background: white; border: 1px dashed #9bb9b5; border-radius: 8px; padding: .4rem; }
    .status-good { color: #1f9d72; font-weight: 700; }
    .status-warn { color: #f5a66f; font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True,
)


def clear_session() -> None:
    for key in ("evaluation", "cv_text", "job_description"):
        st.session_state.pop(key, None)


def render_list(items: list[str], empty_message: str) -> None:
    if items:
        for item in items:
            st.markdown(f"- {item}")
    else:
        st.caption(empty_message)


def json_default(value: object) -> object:
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def render_evaluation(result: dict) -> None:
    st.markdown("## Evaluation snapshot")
    score = max(0, min(100, float(result.get("fit_score", 0))))
    score_col, summary_col, export_col = st.columns([.8, 1.65, .75], gap="large")
    with score_col:
        st.markdown(f'<div class="result-score">{score:.0f}<span style="font-size:1.3rem"> / 100</span></div>', unsafe_allow_html=True)
        st.caption("Estimated role fit")
    with summary_col:
        st.markdown(f'<div class="result-name">{result.get("candidate_name", "Candidate")}</div>', unsafe_allow_html=True)
        st.write(result.get("summary", "No summary returned."))
    with export_col:
        st.download_button("Download JSON", json.dumps(result, indent=2, default=json_default), file_name="cv-evaluation.json", mime="application/json", use_container_width=True)

    st.progress(score / 100, text=f"Fit score  ·  {score:.0f}%")
    strengths_col, gaps_col = st.columns(2, gap="large")
    with strengths_col:
        st.markdown("### Strong matches")
        render_list(result.get("strengths", []), "No strengths were returned.")
    with gaps_col:
        st.markdown("### Gaps to review")
        render_list(result.get("gaps", []), "No gaps were returned.")


def render_login() -> None:
    st.markdown('<div class="eyebrow">Private candidate workspace</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-title">Sign in to your CV workspace.</div>', unsafe_allow_html=True)
    st.markdown("Your evaluations are linked to your Cognito account and are only visible to you.")
    st.button("Sign in with Amazon Cognito  →", type="primary", on_click=st.login, args=("cognito",))
    st.info("Cognito login is not configured yet. Add the [auth.cognito] OIDC settings described in README.txt to enable it.")


def is_logged_in() -> bool:
    return bool(getattr(st.user, "is_logged_in", False))


with st.sidebar:
    st.markdown('<div class="brand"><div class="brand-mark">CV / SCREEN</div><div class="brand-copy">Candidate intelligence for focused, evidence-based hiring.</div></div>', unsafe_allow_html=True)
    st.markdown("### Workspace")
    st.caption(f"Region  ·  `{settings.aws_region}`")
    st.caption(f"Model  ·  `{settings.bedrock_model_id or 'not configured'}`")
    if settings.bedrock_model_id:
        st.markdown('<p class="status-good">● Bedrock configured</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="status-warn">● Bedrock needs setup</p>', unsafe_allow_html=True)


if not is_logged_in():
    render_login()
    st.stop()

user_id = get_user_id(st.user)
user_email = getattr(st.user, "email", None)
with st.sidebar:
    st.divider()
    st.caption(f"Signed in as `{user_email}`")
    if st.button("Sign out", use_container_width=True):
        st.logout()
    if st.button("Clear current session", use_container_width=True):
        clear_session()
        st.rerun()

st.markdown('<div class="eyebrow">Candidate review workspace</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">Find the signal in every CV.</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-copy">Upload one resume and compare it with a role brief. Your evaluation history stays attached to this account.</div>', unsafe_allow_html=True)

history_tab, evaluate_tab = st.tabs(["Evaluation history", "New evaluation"])
with history_tab:
    st.markdown("### Your previous evaluations")
    try:
        evaluations = list_evaluations(settings, user_id)
    except Exception as error:
        evaluations = []
        st.error(f"Could not load evaluation history: {error}")
    if not evaluations:
        st.caption("No saved evaluations yet. Complete your first evaluation in the New evaluation tab.")
    for evaluation in evaluations:
        label = f"{evaluation.get('candidate_name', 'Candidate')}  ·  {evaluation.get('fit_score', 0)}/100  ·  {evaluation.get('created_at', '')}"
        with st.expander(label):
            render_evaluation(evaluation)

with evaluate_tab:
    if "job_description" not in st.session_state:
        st.session_state.job_description = ""

    input_col, preview_col = st.columns([1.05, 0.95], gap="large")
    with input_col:
        st.markdown('<div class="step-label">01  ·  Resume</div>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Drop a PDF resume here", type=["pdf"], label_visibility="collapsed")
        cv_text = ""
        if uploaded_file:
            try:
                cv_text = extract_text_from_pdf(uploaded_file.getvalue())
                st.session_state.cv_text = cv_text
                st.success(f"{uploaded_file.name}  ·  {len(cv_text):,} characters extracted")
            except Exception as error:
                st.error(f"Could not read this PDF: {error}")
        elif st.session_state.get("cv_text"):
            cv_text = st.session_state.cv_text

    with preview_col:
        st.markdown('<div class="step-label">02  ·  Role brief</div>', unsafe_allow_html=True)
        st.text_area("Role brief", height=184, key="job_description", label_visibility="collapsed", placeholder="Paste the responsibilities, must-have skills, and experience for this role...")
        st.caption("Tip: include must-have skills and measurable expectations for a more useful comparison.")

    st.divider()
    action_col, info_col = st.columns([1, 3])
    with action_col:
        ready = bool(cv_text and st.session_state.job_description.strip())
        evaluate_clicked = st.button("Evaluate candidate  →", type="primary", use_container_width=True, disabled=not ready)
    with info_col:
        st.caption("Ready to evaluate. The request uses Amazon Bedrock and may consume account quota." if ready else "Add a PDF and role brief to unlock evaluation.")

    if evaluate_clicked:
        with st.spinner("Reading the profile against the role brief..."):
            try:
                result = evaluate_cv(cv_text, st.session_state.job_description, settings)
                result["job_description"] = st.session_state.job_description
                save_evaluation(settings, user_id, result)
                st.session_state.evaluation = result
                st.success("Evaluation saved to your account history.")
            except Exception as error:
                st.error(str(error))
                if not settings.bedrock_model_id:
                    st.info("Configure BEDROCK_MODEL_ID and AWS credentials in .env before using cloud evaluation.")

    if result := st.session_state.get("evaluation"):
        render_evaluation(result)
        with st.expander("View extracted evidence"):
            st.text(st.session_state.get("cv_text", ""))
