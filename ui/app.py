import os
import streamlit as st
import requests
import time
import uuid
import logfire
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

env_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".env")
)

load_dotenv(dotenv_path=env_path)


# ============================================================
# INITIALIZE LOGFIRE
# ============================================================

try:
    token = os.getenv("LOGFIRE_TOKEN")

    if token:
        logfire.configure(token=token)
        LOGFIRE_STATUS = "Connected & Tracing"
    else:
        LOGFIRE_STATUS = "Disabled (No Token)"

except Exception as e:
    print(f"Logfire Init Error in UI: {e}")
    LOGFIRE_STATUS = "Disabled"


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Enterprise Agentic RAG",
    page_icon="🤖",
    layout="wide",
)


# ============================================================
# AVATARS
# ============================================================

AI_AVATAR = "🤖"
USER_AVATAR = "👤"


# ============================================================
# SESSION MANAGEMENT
# ============================================================

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

    logfire.info(
        f"✨ New User Session Created: "
        f"{st.session_state.session_id}"
    )


if "messages" not in st.session_state:
    st.session_state.messages = []


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("🧠 Agent OS")

    st.markdown("---")

    st.success(
        f"Logfire: {LOGFIRE_STATUS}"
    )

    st.info(
        f"Memory ID: "
        f"{st.session_state.session_id[:8]}"
    )

    if st.button(
        "🗑️ Clear History & Memory",
        width="stretch",
        type="primary",
    ):

        logfire.warning(
            "🗑️ Memory Wipe Triggered for session: "
            f"{st.session_state.session_id}"
        )

        st.session_state.messages = []

        st.session_state.session_id = str(
            uuid.uuid4()
        )

        st.rerun()


# ============================================================
# MAIN CHAT
# ============================================================

st.title("🤖 Enterprise Agentic Assistant")


# ============================================================
# DISPLAY CHAT HISTORY
# ============================================================

for message in st.session_state.messages:

    avatar = (
        AI_AVATAR
        if message["role"] == "assistant"
        else USER_AVATAR
    )

    with st.chat_message(
        message["role"],
        avatar=avatar,
    ):
        st.markdown(message["content"])


# ============================================================
# CHAT INPUT
# ============================================================

if prompt := st.chat_input(
    "Ask about your documentation..."
):

    # ========================================================
    # START USER INTERACTION TRACE
    # ========================================================

    with logfire.span(
        "💬 User Chat Interaction",
        user_query=prompt,
        session_id=st.session_state.session_id,
    ):

        # ----------------------------------------------------
        # STORE USER MESSAGE
        # ----------------------------------------------------

        st.session_state.messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        with st.chat_message(
            "user",
            avatar=USER_AVATAR,
        ):
            st.markdown(prompt)


        # ====================================================
        # ASSISTANT RESPONSE
        # ====================================================

        with st.chat_message(
            "assistant",
            avatar=AI_AVATAR,
        ):

            with st.status(
                "🔍 Agent is thinking...",
                expanded=True,
            ) as status:

                try:

                    # ========================================
                    # CALL BACKEND
                    # ========================================

                    with logfire.span(
                        "📡 Calling RAG Backend"
                    ):

                        base_url = os.getenv(
                            "BACKEND_URL",
                            "https://enterprise-agentic-rag-caq0.onrender.com",
                        ).rstrip("/")

                        url = f"{base_url}/query"

                        payload = {
                            "q": prompt,
                            "thread_id": (
                                st.session_state.session_id
                            ),
                        }

                        response = requests.post(
                            url,
                            json=payload,
                            timeout=60,
                        )


                        # ====================================
                        # BACKEND ERROR
                        # ====================================

                        if response.status_code != 200:

                            st.error(
                                f"Backend returned "
                                f"{response.status_code}: "
                                f"{response.text}"
                            )

                            st.stop()


                        data = response.json()


                    # ========================================
                    # GET BACKEND STATUS
                    # ========================================

                    backend_status = data.get(
                        "status",
                        "",
                    )


                    # ========================================
                    # GET THOUGHT PROCESS
                    # ========================================

                    steps = data.get(
                        "thought_process",
                        [],
                    )


                    for step in steps:

                        st.write(
                            f"⚙️ {step}"
                        )


                    # ==================================================
                    # GUARDRAILS BLOCKED
                    # ==================================================

                    if (
                        backend_status
                        == "Blocked by guardrails."
                    ):

                        status.update(
                            label="🛡️ Blocked by Guardrails",
                            state="complete",
                            expanded=False,
                        )


                    # ==================================================
                    # NORMAL RAG ANSWER
                    # ==================================================

                    elif backend_status != "error":

                        status.update(
                            label="✅ Answer Synthesized",
                            state="complete",
                            expanded=False,
                        )


                    # ==================================================
                    # BACKEND ERROR
                    # ==================================================

                    else:

                        status.update(
                            label="❌ Backend Error",
                            state="error",
                            expanded=False,
                        )


                    # ========================================
                    # SHOW SOURCES
                    # ========================================

                    sources = data.get(
                        "sources",
                        [],
                    )


                    # Only show sources when
                    # actual retrieval happened.

                    if (
                        sources
                        and backend_status
                        != "Blocked by guardrails."
                    ):

                        with st.expander(
                            "📄 View Retrieved Context (Sources)"
                        ):

                            for i, source in enumerate(
                                sources
                            ):

                                # --------------------------------
                                # Safety conversion
                                # --------------------------------

                                source_text = str(
                                    source
                                )

                                preview = (
                                    source_text[:100]
                                    .replace("\n", " ")
                                    + "..."
                                )


                                with st.expander(
                                    f"Chunk {i + 1}: "
                                    f"{preview}"
                                ):

                                    st.info(
                                        source_text
                                    )


                # ====================================================
                # EXCEPTION HANDLING
                # ====================================================

                except Exception as e:

                    logfire.error(
                        f"❌ UI-Backend Connection Failed: {e}"
                    )

                    status.update(
                        label="❌ Connection Failed",
                        state="error",
                    )

                    st.error(
                        f"Backend connection failed: {e}"
                    )

                    st.stop()


            # ====================================================
            # FINAL ANSWER
            # ====================================================

            answer_placeholder = st.empty()

            full_answer = data.get(
                "answer",
                "No response.",
            )


            # ====================================================
            # STREAMING EFFECT
            # ====================================================

            curr_text = ""

            for char in full_answer:

                curr_text += char

                answer_placeholder.markdown(
                    curr_text + "▌"
                )

                time.sleep(0.005)


            answer_placeholder.markdown(
                full_answer
            )


            # ====================================================
            # STORE ASSISTANT MESSAGE
            # ====================================================

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": full_answer,
                }
            )


            logfire.info(
                "✅ Chat cycle completed successfully."
            )