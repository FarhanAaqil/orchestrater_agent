import streamlit as st
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from orchestrator.master import handle
from voice.voice_handler import speak, listen

st.set_page_config(page_title="Aaqil", page_icon="🤖", layout="wide")

# ─── CSS ──────────────────────────────────────────────────────────
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {
    background: transparent;
    }

    /* White background everywhere */
    .stApp {
        background-color: white;
    }

    section[data-testid="stSidebar"] {
        background-color: white;
        border-right: 1px solid #e0e0e0;
    }

    /* Sticky chat input */
    .stChatInput {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        padding: 1rem 1.5rem;
        background: white;
        z-index: 999;
        border-top: 1px solid #e0e0e0;
    }

    .main {
        padding-bottom: 80px;
    }

    /* Sidebar buttons */
    .stButton > button {
        width: 100%;
        text-align: left;
        background: #f5f5f5;
        border: 1px solid #e0e0e0;
        color: #333;
        border-radius: 8px;
        padding: 6px 12px;
        font-size: 13px;
        margin-bottom: 3px;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: #eeeeff;
        border-color: #7777ff;
        color: #333;
    }

    /* Agent badge */
    .agent-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        margin-bottom: 4px;
        background: #f0f0ff;
        color: #5555aa;
    }

    h1 {
        font-size: 1.4rem !important;
    }
</style>
""", unsafe_allow_html=True)

# ─── Sidebar ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🤖 Aaqil")
    st.caption("Personal AI Chief of Staff")
    st.divider()

    st.markdown("**🧠 Agents**")
    agents = {
        "🎯 Orchestrator": "✅",
        "🐙 GitHub": "✅",
        "💼 LinkedIn": "✅",
        "🔍 Job/Internship": "✅",
        "📋 Project Manager": "✅",
        "🎓 Career": "✅",
        "📈 Growth": "✅",
        "📚 Research": "✅",
        "📧 Email": "✅",
        "🌅 Briefing": "✅",
    }
    for agent, status in agents.items():
        st.markdown(f"{status} {agent}")

    st.divider()

    voice_enabled = st.toggle("🎙️ Voice Response", value=False)

    if st.button("🎙️ Speak"):
        with st.spinner("Listening..."):
            spoken = listen()
        if spoken:
            st.session_state.pending_voice = spoken
        else:
            st.warning("Didn't catch that.")

    st.divider()
    st.markdown("**⚡ Quick Actions**")
    quick_actions = [
        ("🌅 Morning Briefing",      "generate morning briefing"),
        ("🔍 Find Internships",       "find machine learning internships on Internshala"),
        ("📋 Show Tasks",             "show all tasks"),
        ("📁 Show Projects",          "show all projects"),
        ("🎯 Show Goals",             "show goals"),
        ("📚 Show Papers",            "show papers"),
        ("📬 Email Dashboard",        "email dashboard"),
        ("📊 Content Dashboard",      "content dashboard"),
        ("💼 Career Dashboard",       "career dashboard"),
        ("🐙 GitHub Summary",         "show github profile summary"),
    ]
    for label, cmd in quick_actions:
        if st.button(label):
            st.session_state.pending_quick = cmd

# ─── Chat History Init ────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "pending_quick" not in st.session_state:
    st.session_state.pending_quick = None
if "pending_voice" not in st.session_state:
    st.session_state.pending_voice = None

# ─── Header ───────────────────────────────────────────────────────

# notification bell + approvals tab
from orchestrator.master import handle, get_pipeline
from scheduler.background import get_notifications, mark_all_read

# Notifications bell
pipeline = get_pipeline()
notifications = get_notifications()
unread = [n for n in notifications if not n["read"]]

col1, col2 = st.columns([8, 1])
with col1:
    st.markdown("## 🤖 Aaqil")
    st.caption("Chief of Staff • Background scheduler active")
with col2:
    if unread:
        if st.button(f"🔔 {len(unread)}"):
            st.session_state.show_notifications = True
            mark_all_read()
    else:
        st.button("🔔")

# Notifications panel
if st.session_state.get("show_notifications"):
    with st.expander("📬 Notifications", expanded=True):
        for n in notifications[-10:][::-1]:
            st.write(f"**{n['time']}** — {n['message']}")
        if st.button("Close"):
            st.session_state.show_notifications = False

# Tabs
tab1, tab2, tab3 = st.tabs(["💬 Chat", "📋 Approvals", "📊 Dashboard"])

with tab2:
    approvals = pipeline.get_pending_approvals()
    if not approvals:
        st.info("No pending approvals.")
    for a in approvals:
        with st.expander(f"[{a['id']}] {a['title']} — {a['type'].upper()}"):
            st.text_area("Content", a["content"], height=200, key=f"approval_{a['id']}")
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"✅ Approve", key=f"approve_{a['id']}"):
                    result = pipeline.approve(a["id"])
                    st.success(result)
                    st.rerun()
            with col2:
                if st.button(f"❌ Reject", key=f"reject_{a['id']}"):
                    result = pipeline.reject(a["id"])
                    st.error(result)
                    st.rerun()


# ─── Chat Messages ────────────────────────────────────────────────
agent_emoji = {
    "github": "🐙", "linkedin": "💼", "job": "🔍",
    "project_manager": "📋", "career": "🎓", "growth": "📈",
    "research": "📚", "email": "📧", "briefing": "🌅",
    "orchestrator": "🤖"
}

if not st.session_state.history:
    st.markdown("""
    <div style='text-align:center; padding: 3rem 0; color: #555;'>
        <div style='font-size: 3rem'>🤖</div>
        <div style='font-size: 1.1rem; margin-top: 1rem;'>Aaqil is ready.</div>
        <div style='font-size: 0.85rem; margin-top: 0.5rem;'>Type a command or pick a quick action from the sidebar.</div>
    </div>
    """, unsafe_allow_html=True)

for chat in st.session_state.history:
    with st.chat_message("user"):
        st.write(chat["user"])
    with st.chat_message("assistant"):
        emoji = agent_emoji.get(chat["agent"], "🤖")
        st.markdown(f'<div class="agent-badge">{emoji} {chat["agent"].upper()} AGENT</div>', unsafe_allow_html=True)
        st.write(chat["response"])

# ─── Process Pending (Quick Action / Voice) ───────────────────────
pending = st.session_state.pending_quick or st.session_state.pending_voice

if pending:
    st.session_state.pending_quick = None
    st.session_state.pending_voice = None
    with st.spinner("Aaqil thinking..."):
        result = handle(pending)
    if voice_enabled:
        speak(result["response"][:500])
    st.session_state.history.append({
        "user": pending,
        "agent": result["agent"],
        "response": result["response"]
    })
    st.rerun()

# ─── Chat Input (Sticky Bottom) ───────────────────────────────────
user_input = st.chat_input("Message Aaqil...")

if user_input:
    with st.spinner("Aaqil thinking..."):
        result = handle(user_input)
    if voice_enabled:
        speak(result["response"][:500])
    st.session_state.history.append({
        "user": user_input,
        "agent": result["agent"],
        "response": result["response"]
    })
    st.rerun()