#!/usr/bin/env python3
"""
Claims Processing UI
Streamlit frontend for the Claims Processing REST API
"""
import os
import httpx
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv("/workspaces/claims-processing-hack/.env")

# Page configuration
st.set_page_config(
    page_title="Claims Processing System",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1E3A8A; margin-bottom: 1rem; }
    .status-success { background-color: #D1FAE5; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #10B981; }
    .status-error { background-color: #FEE2E2; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #EF4444; }
</style>
""", unsafe_allow_html=True)

DEFAULT_API_URL = os.environ.get(
    "API_URL",
    os.environ.get("APIM_GATEWAY_URL", "http://localhost:8080")
)


def get_api_url() -> str:
    if "api_url" not in st.session_state:
        st.session_state.api_url = DEFAULT_API_URL
    return st.session_state.api_url


def get_bearer_token() -> str:
    if "bearer_token" not in st.session_state:
        st.session_state.bearer_token = os.environ.get(
            "APIM_BEARER_TOKEN",
            os.environ.get("BEARER_TOKEN", "")
        )
    return st.session_state.bearer_token


def build_headers(bearer_token: str = "") -> dict:
    headers = {}
    token = bearer_token.strip()
    if token:
        if not token.lower().startswith("bearer "):
            token = f"Bearer {token}"
        headers["Authorization"] = token

    return headers


def parse_response(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw_response": response.text}

    if response.is_error:
        error = payload.get("detail") if isinstance(payload, dict) else payload
        return {
            "success": False,
            "status": "error",
            "error": f"HTTP {response.status_code}: {error}",
            "response": payload,
        }

    if isinstance(payload, dict):
        return payload

    return {"success": True, "data": payload}


def check_health(api_url: str, bearer_token: str = "") -> dict:
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{api_url.rstrip('/')}/health",
                headers=build_headers(bearer_token),
            )
            return parse_response(response)
    except Exception as e:
        return {"status": "error", "success": False, "error": str(e)}


def process_claim(
    api_url: str,
    file_content: bytes,
    filename: str,
    bearer_token: str = "",
) -> dict:
    try:
        with httpx.Client(timeout=120.0) as client:
            files = {"file": (filename, file_content, "image/jpeg")}
            response = client.post(
                f"{api_url.rstrip('/')}/process-claim/upload",
                files=files,
                headers=build_headers(bearer_token),
            )
            return parse_response(response)
    except Exception as e:
        return {"success": False, "error": str(e)}


def display_results(data: dict):
    if not data:
        return

    if "vehicle_info" in data:
        st.subheader("🚗 Vehicle Information")
        v = data["vehicle_info"]
        cols = st.columns(4)
        cols[0].metric("Make", v.get("make", "N/A"))
        cols[1].metric("Model", v.get("model", "N/A"))
        cols[2].metric("Color", v.get("color", "N/A"))
        cols[3].metric("Year", v.get("year", "N/A"))

    if "damage_assessment" in data:
        st.subheader("💥 Damage Assessment")
        d = data["damage_assessment"]
        cols = st.columns(3)
        severity = d.get("severity", "N/A")
        icon = {"minor": "🟢", "moderate": "🟡", "severe": "🔴"}.get(str(severity).lower(), "⚪")
        cols[0].metric("Severity", f"{icon} {severity}")
        cost = d.get("estimated_cost", "N/A")
        cols[1].metric("Estimated Cost", f"${cost:,.2f}" if isinstance(cost, (int, float)) else cost)
        areas = d.get("affected_areas", [])
        cols[2].metric("Affected Areas", len(areas) if isinstance(areas, list) else "N/A")
        if areas:
            st.markdown("**Areas:** " + ", ".join(areas))

    if "incident_info" in data:
        st.subheader("📋 Incident Information")
        i = data["incident_info"]
        st.markdown(f"**Date:** {i.get('date', 'N/A')} | **Location:** {i.get('location', 'N/A')}")
        st.markdown(f"**Description:** {i.get('description', 'N/A')}")


def main():
    st.markdown('<p class="main-header">🚗 Insurance Claims Processing</p>', unsafe_allow_html=True)
    st.markdown("Upload claim images to extract structured data using AI")

    with st.sidebar:
        st.header("⚙️ Configuration")
        api_url = st.text_input("API URL", value=get_api_url())
        bearer_token = st.text_input("Bearer Token", value=get_bearer_token(), type="password")

        st.session_state.api_url = api_url
        st.session_state.bearer_token = bearer_token

        if st.button("🏥 Check Health", use_container_width=True):
            with st.spinner("Checking..."):
                result = check_health(api_url, bearer_token)
                if result.get("status") == "healthy":
                    st.success(f"✅ API Healthy\n\n{result.get('service', '')}")
                else:
                    st.error(f"❌ {result.get('error', 'Error')}")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.header("📤 Upload Claim")
        uploaded = st.file_uploader("Choose image", type=["jpg", "jpeg", "png"])
        process_btn = st.button("🚀 Process Claim", type="primary", use_container_width=True, disabled=not uploaded)

    with col2:
        if uploaded:
            st.image(uploaded, caption=uploaded.name, width=200)

    if process_btn and uploaded:
        st.divider()
        with st.spinner("🔄 Processing... (30-60 seconds)"):
            result = process_claim(
                st.session_state.api_url,
                uploaded.getvalue(),
                uploaded.name,
                st.session_state.bearer_token,
            )

        st.header("📋 Results")
        if result.get("success"):
            st.markdown('<div class="status-success">✅ Claim processed successfully!</div>', unsafe_allow_html=True)
            display_results(result.get("data", {}))
            with st.expander("🔍 Raw JSON"):
                st.json(result)
        else:
            st.markdown(f'<div class="status-error">❌ Error: {result.get("error", "Unknown")}</div>', unsafe_allow_html=True)
            if result.get("response"):
                with st.expander("🔍 Error Response"):
                    st.json(result["response"])


if __name__ == "__main__":
    main()
