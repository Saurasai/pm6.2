import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import logging
import re
import asyncio
import pyperclip
from api import generate_platform_drafts
from config import PROMPT_TEMPLATES
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
API_BASE = os.getenv("API_BASE", "http://localhost:8000/api")  # Default to localhost if not set

logger = logging.getLogger(__name__)

# Config
PLATFORMS = ["bluesky", "facebook", "gmb", "instagram", "linkedin", "pinterest", "reddit", "snapchat", "telegram", "tiktok", "threads", "twitter", "youtube"]
TONE_OPTIONS = ["Professional", "Casual", "Excited"]
st.set_page_config(page_title="🌟 Post Muse Dashboard", layout="wide", initial_sidebar_state="expanded")

# Social media platform URLs for opening after draft generation
PLATFORM_URLS = {
    "twitter": "https://twitter.com",
    "linkedin": "https://www.linkedin.com",
    "instagram": "https://www.instagram.com"
}

def clean_draft_content(draft: str) -> str:
    """Remove numbering (e.g., '1. ', '2. ') from the start of draft content."""
    return re.sub(r'^\d+\.\s*', '', draft.strip(), count=1)

def get_user_info(api_key: str) -> dict:
    """Fetch user info to determine admin status."""
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        with st.spinner("🔄 Fetching user info..."):
            response = requests.get(f"{API_BASE}/user", headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to fetch user info: {response.text}")
            st.warning("⚠️ Could not fetch user info. Defaulting to non-admin.")
            return {"is_admin": False}
    except Exception as e:
        logger.error(f"Error fetching user info: {str(e)}")
        st.warning(f"⚠️ Error fetching user info: {str(e)}")
        return {"is_admin": False}

async def simulate_progress(progress_bar):
    """Simulate progress bar animation."""
    for i in range(100):
        progress_bar.progress(i + 1)
        await asyncio.sleep(0.02)

def login():
    st.subheader("🔐 Welcome to Post Muse")
    with st.container(border=True):
        st.markdown("### 🎉 Login or Register")
        auth_option = st.selectbox("Choose an action", ["Login", "Register"], key="auth_option")
        
        with st.form(key="auth_form"):
            if auth_option == "Login":
                email = st.text_input("📧 Email", placeholder="Enter your email", key="login_email")
                password = st.text_input("🔒 Password", type="password", placeholder="Enter your password", key="login_pass")
                submit_button = st.form_submit_button("🚀 Login", type="primary")
                if submit_button:
                    with st.spinner("🔄 Logging in..."):
                        try:
                            response = requests.post(f"{API_BASE}/login", json={"email": email.lower(), "password": password}, timeout=5)
                            if response.status_code == 200:
                                st.session_state.user = {"email": email.lower(), "api_key": response.json()["api_key"]}
                                st.success("🎉 Logged in successfully!")
                                st.balloons()
                                logger.info(f"Login successful for {email}")
                                st.rerun()
                            else:
                                st.error(f"❌ Login failed: {response.json().get('detail', 'Unknown error')}")
                                logger.warning(f"Login failed for {email}: {response.text}")
                        except requests.ConnectionError:
                            st.error(f"❌ Failed to connect to the server. Ensure the API server is running at {API_BASE}.")
                            logger.error(f"Connection error for {email}: Server not reachable")
                        except requests.Timeout:
                            st.error("❌ Request timed out. Check your network or server status.")
                            logger.error(f"Timeout error for {email}")
                        except Exception as e:
                            st.error(f"❌ Login error: {str(e)}")
                            logger.error(f"Login error for {email}: {str(e)}")
            else:
                email = st.text_input("📧 Email", placeholder="Enter your email", key="reg_email")
                password = st.text_input("🔒 Password", type="password", placeholder="Enter your password", key="reg_pass")
                confirm_password = st.text_input("🔒 Confirm Password", type="password", placeholder="Confirm your password", key="reg_pass2")
                is_admin = st.checkbox("🛡️ Register as Admin", key="reg_is_admin")
                admin_secret = st.text_input("🔑 Admin Secret (required for admin)", type="password", placeholder="Enter admin secret for admin privileges", key="reg_admin_secret") if is_admin else None
                submit_button = st.form_submit_button("🌟 Register", type="primary")
                if submit_button:
                    if password != confirm_password:
                        st.error("❌ Passwords do not match")
                        logger.warning("Password mismatch during registration")
                        return
                    with st.spinner("🔄 Registering..."):
                        try:
                            payload = {
                                "email": email.lower(),
                                "password": password,
                                "confirm_password": confirm_password,
                                "tier": "free",
                                "is_admin": is_admin,
                                "admin_secret": admin_secret if is_admin else None
                            }
                            response = requests.post(f"{API_BASE}/user", json=payload, timeout=5)
                            if response.status_code == 200:
                                st.session_state.user = {"email": email.lower(), "api_key": response.json()["api_key"]}
                                st.success(f"🎉 Registered successfully! API Key: {response.json()['api_key']}")
                                st.balloons()
                                logger.info(f"Registered user: {email}, is_admin: {is_admin}")
                                st.rerun()
                            else:
                                st.error(f"❌ Registration failed: {response.json().get('detail', 'Unknown error')}")
                                logger.warning(f"Registration failed for {email}: {response.text}")
                        except requests.ConnectionError:
                            st.error(f"❌ Failed to connect to the server. Ensure the API server is running at {API_BASE}.")
                            logger.error(f"Connection error for {email}: Server not reachable")
                        except requests.Timeout:
                            st.error("❌ Request timed out. Check your network or server status.")
                            logger.error(f"Timeout error for {email}")
                        except Exception as e:
                            st.error(f"❌ Registration error: {str(e)}")
                            logger.error(f"Registration error for {email}: {str(e)}")

if "user" not in st.session_state:
    with st.container(border=True):
        login()
    st.stop()

# Sidebar: User Info and Logout
with st.sidebar:
    st.header("👤 User Profile")
    with st.container(border=True):
        st.markdown(f"**Email**: {st.session_state.user.get('email', 'Unknown')}")
        st.markdown(f"**Tier**: {get_user_info(st.session_state.user.get('api_key', '')).get('tier', 'Free')}")
        if get_user_info(st.session_state.user.get('api_key', '')).get('is_admin', False):
            st.markdown("**Status**: 🛡️ Admin")
        else:
            st.markdown("**Status**: 🌟 User")
        if st.button("🚪 Logout", type="primary", key="logout"):
            st.session_state.clear()
            st.success("🎉 Logged out successfully!")
            st.snow()
            logger.info(f"User {st.session_state.get('user', {}).get('email', 'unknown')} logged out")
            st.rerun()

# Main Title
st.title("🌟 Post Muse: Craft Your Social Media Magic")
st.markdown("Unleash your creativity with vibrant, platform-ready posts! 🚀")

# Determine if user is admin
api_key = st.session_state.user.get("api_key", "")
if not api_key:
    st.error("❌ No API key found. Please log in again.")
    logger.error("No API key in session state")
    st.stop()
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
user_info = get_user_info(api_key)
is_admin = user_info.get("is_admin", False)

# Tabs
tab1, tab2, tab3 = st.tabs(["📝 Create Post", "💾 Saved Drafts", "⚙️ Settings"])

with tab1:
    st.subheader("📝 Create Your Post")
    with st.container(border=True):
        st.markdown("### 🌈 Input Your Ideas")
        col1, col2 = st.columns([1, 1], gap="medium")
        with col1:
            topic = st.text_input("🧠 Topic / Product / Feature", placeholder="e.g. Smart AI Writing Tool", key="topic")
            hashtags = st.text_input("🐦 Hashtags", placeholder="e.g. #AI #Productivity", key="hashtags")
        with col2:
            insight = st.text_area("💼 Insight / Story", placeholder="Share a professional insight…", height=100, key="insight")
            tone = st.selectbox("🎨 Tone", TONE_OPTIONS, index=1, key="tone")
        
        if st.button("🚀 Generate Drafts", key="generate_drafts", type="primary") and topic.strip():
            with st.spinner("🌟 Generating your drafts..."):
                progress_bar = st.progress(0)
                try:
                    asyncio.run(simulate_progress(progress_bar))  # Run async progress simulation
                    draft_platforms = ["twitter", "linkedin", "instagram"]  # Twitter drafts for all users
                    tasks = [generate_platform_drafts(p, {
                        "topic": topic,
                        "hashtags": hashtags,
                        "insight": insight,
                        "tone": tone
                    }, PROMPT_TEMPLATES) for p in draft_platforms]
                    results = asyncio.run(asyncio.gather(*tasks))
                    st.session_state.drafts = {p: [clean_draft_content(d) for d in d] for p, d in zip(draft_platforms, results)}
                    st.success("🎉 Drafts generated! Review them below.")
                    st.balloons()
                    logger.info("Drafts generated successfully")
                except Exception as e:
                    st.error(f"❌ Generation failed: {str(e)}")
                    logger.error(f"Draft generation failed: {str(e)}")
                progress_bar.empty()

    st.markdown("---")
    with st.container(border=True):
        st.markdown("### 📬 Your Drafts")
        draft_platforms = ["twitter", "linkedin", "instagram"]
        tabs = st.tabs([f"🐦 Twitter" if p == "twitter" else f"💼 LinkedIn" if p == "linkedin" else f"📸 Instagram" for p in draft_platforms])
        for tab, platform in zip(tabs, draft_platforms):
            with tab:
                drafts = st.session_state.get("drafts", {}).get(platform, [])
                if not drafts:
                    st.info(f"ℹ️ No drafts for {platform.capitalize()}. Generate some above! 😊")
                else:
                    st.markdown(f"[Open {platform.capitalize()}]({PLATFORM_URLS.get(platform, '#')}) 🌐")
                    for i, draft in enumerate(drafts, 1):
                        with st.expander(f"Draft {i} for {platform.capitalize()}", expanded=True):
                            draft_key = f"{platform}_{i}_edit"
                            edited_draft = st.text_area(f"✍️ Edit Draft {i}", value=draft, key=draft_key, height=100)
                            if edited_draft != draft:
                                st.session_state.drafts[platform][i-1] = edited_draft
                                st.info(f"✨ Draft {i} updated for {platform.capitalize()}!")
                                logger.debug(f"Draft {i} edited for {platform}")
                            col1, col2, col3 = st.columns([0.7, 0.15, 0.15])
                            with col1:
                                st.markdown(f"**Content:** {edited_draft}")
                            with col2:
                                if st.button("📋 Copy", key=f"{platform}_{i}_copy"):
                                    try:
                                        pyperclip.copy(edited_draft)
                                        st.success(f"🎉 Copied draft {i} to clipboard!")
                                        st.balloons()
                                        logger.debug(f"Draft {i} copied for {platform}")
                                    except Exception as e:
                                        st.error(f"❌ Failed to copy to clipboard: {str(e)}")
                                        logger.error(f"Clipboard copy failed for {platform}: {str(e)}")
                            with col3:
                                if st.button("💾 Save Draft", key=f"{platform}_{i}_save"):
                                    payload = {"content": clean_draft_content(edited_draft), "platform": platform}
                                    with st.spinner(f"🔄 Saving draft to {platform.capitalize()}..."):
                                        try:
                                            response = requests.post(f"{API_BASE}/draft", json=payload, headers=headers, timeout=5)
                                            if response.status_code == 200:
                                                st.success(f"🎉 Draft {i} saved for {platform.capitalize()}!")
                                                st.snow()
                                                logger.info(f"Draft saved for {platform} by {st.session_state.user['email']}")
                                            else:
                                                st.error(f"❌ Failed to save draft: {response.json().get('detail', 'Unknown error')}")
                                                logger.warning(f"Draft save failed for {platform}: {response.text}")
                                        except requests.ConnectionError:
                                            st.error("❌ Failed to connect to the server. Ensure the API server is running.")
                                            logger.error(f"Connection error for {platform} draft save")
                                        except requests.Timeout:
                                            st.error("❌ Request timed out. Check your network or server status.")
                                            logger.error(f"Timeout error for {platform} draft save")
                                        except Exception as e:
                                            st.error(f"❌ Failed to save draft: {str(e)}")
                                            logger.error(f"Draft save failed for {platform}: {str(e)}")
                            # Show Post button only for non-Twitter platforms or for admins on Twitter
                            if platform != "twitter" or is_admin:
                                if st.button(f"📤 Post to {platform.capitalize()}", key=f"{platform}_{i}_post", type="primary"):
                                    cleaned_draft = clean_draft_content(edited_draft)
                                    payload = {"post": cleaned_draft, "platforms": [platform]}
                                    with st.spinner(f"📬 Posting to {platform.capitalize()}..."):
                                        try:
                                            response = requests.post(f"{API_BASE}/post", json=payload, headers=headers, timeout=5)
                                            if response.status_code == 200:
                                                post_ids = response.json()["postIds"]
                                                for p in post_ids:
                                                    if p["platform"] == platform and p["status"] == "success":
                                                        st.success(f"🎉 Posted to {platform.capitalize()}! [View]({p['postUrl']})")
                                                        st.balloons()
                                                        logger.info(f"Posted to {platform} for {st.session_state.user['email']}, ID: {p['id']}")
                                                    else:
                                                        st.error(f"❌ Failed to post to {platform.capitalize()}: {p.get('error', 'Unknown error')}")
                                                        logger.warning(f"Post failed to {platform}: {p.get('error', 'Unknown error')}")
                                            else:
                                                st.error(f"❌ Error: {response.json().get('detail', 'Unknown error')}")
                                                logger.warning(f"Post request failed: {response.text}")
                                        except requests.ConnectionError:
                                            st.error("❌ Failed to connect to the server. Ensure the API server is running.")
                                            logger.error(f"Connection error for {platform} post")
                                        except requests.Timeout:
                                            st.error("❌ Request timed out. Check your network or server status.")
                                            logger.error(f"Timeout error for {platform} post")
                                        except Exception as e:
                                            st.error(f"❌ Failed to post: {str(e)}")
                                            logger.error(f"Post failed for {platform}: {str(e)}")
                            else:
                                st.info("ℹ️ Posting to Twitter is admin-only. Save or copy your draft instead! 😊")

with tab2:
    st.subheader("💾 Your Saved Drafts")
    with st.container(border=True):
        if st.button("🔄 Load Saved Drafts", key="load_drafts", type="primary"):
            with st.spinner("🔄 Loading your drafts..."):
                progress_bar = st.progress(0)
                try:
                    asyncio.run(simulate_progress(progress_bar))  # Run async progress simulation
                    response = requests.get(f"{API_BASE}/drafts", headers=headers, timeout=5)
                    if response.status_code == 200:
                        df = pd.DataFrame(response.json())
                        if df.empty:
                            st.info("ℹ️ No saved drafts found. Create some in the 'Create Post' tab! 😊")
                        else:
                            st.dataframe(df[["platform", "content", "created_at"]], use_container_width=True)
                            st.success("🎉 Drafts loaded successfully!")
                            st.balloons()
                        logger.info("Drafts loaded successfully")
                    else:
                        st.error(f"❌ Error: {response.json().get('detail', 'Unknown error')}")
                        logger.warning(f"Draft fetch failed: {response.text}")
                except requests.ConnectionError:
                    st.error("❌ Failed to connect to the server. Ensure the API server is running.")
                    logger.error("Connection error for drafts")
                except requests.Timeout:
                    st.error("❌ Request timed out. Check your network or server status.")
                    logger.error(f"Timeout error for drafts")
                except Exception as e:
                    st.error(f"❌ Error fetching drafts: {str(e)}")
                    logger.error(f"Draft fetch failed: {str(e)}")
                progress_bar.empty()

with tab3:
    st.subheader("⚙️ Settings")
    with st.container(border=True):
        st.markdown("### 🛠️ Account Settings")
        tier = st.selectbox("🌟 Upgrade Tier", ["Free", "Premium", "Business"], key="tier_select")
        if st.button("🚀 Update Tier", key="update_tier", type="primary"):
            st.success(f"🎉 Upgraded to {tier}!")  # Mock
            st.balloons()
            logger.info(f"User {st.session_state.user['email']} requested tier upgrade to {tier}")