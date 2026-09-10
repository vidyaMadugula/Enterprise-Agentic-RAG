# import logfire
# from langchain_groq import ChatGroq
# from nemoguardrails import RailsConfig, LLMRails

# from app.config import settings
# from app.guardrails.colang_rules import COLANG_CONTENT, YAML_CONTENT, RAIL_INDICATORS


# _rails: LLMRails | None = None


# def initialize_rails() -> None:
#     """
#     Build the NeMo LLMRails singleton at app startup.
#     Uses openai/gpt-oss-20b for fast intent classification —
#     the heavier llama-3.3-70b-versatile is reserved for the RAG pipeline.
#     """
#     global _rails

#     guard_llm = ChatGroq(
#         api_key=settings.GROQ_API_KEY,
#         model="openai/gpt-oss-20b",
#         temperature=0
#     )

#     config = RailsConfig.from_content(
#         colang_content=COLANG_CONTENT,
#         yaml_content=YAML_CONTENT
#     )

#     _rails = LLMRails(config, llm=guard_llm)
#     logfire.info("🛡️ NeMo Guardrails initialised (openai/gpt-oss-20b).")
    
    


# def guard(message: str) -> tuple[bool, str | None]:
#     """
#     Run a user message through the NeMo rails gate.

#     Returns:
#         (True,  rail_response) — a rail fired; return this response immediately,
#                                 skip the RAG pipeline entirely.
#         (False, None)          — message is clean; proceed to LangGraph.
#     """
#     if _rails is None:
#         logfire.warning("⚠️ Guardrails not initialised — skipping gate.")
#         return False, None

#     with logfire.span("🛡️ Guardrails Check"):
#         result = _rails.generate(messages=[{"role": "user", "content": message}])

#         # NeMo returns {'role': 'assistant', 'content': '...'} — extract text
#         content = result.get("content", "") if isinstance(result, dict) else str(result)

#         fired = any(indicator in content for indicator in RAIL_INDICATORS)

#         if fired:
#             logfire.info(f"🛡️ Guardrails fired | query='{message[:80]}'")
#             return True, content

#         logfire.info("✅ Guardrails passed.")
#         return False, None


# # ============================================================
# # NeMo Guardrails Gate
# # ============================================================
# #
# # NeMo is used ONLY as an input/security gate.
# #
# # Flow:
# #
# # User
# #   ↓
# # NeMo Guardrails
# #   ↓
# # BLOCK ─────────────→ Refusal
# #   │
# #   PASS
# #   ↓
# # LangGraph Planner
# #   ↓
# # RAG pipeline
# #
# # NeMo does NOT perform retrieval or answer generation.
# # ============================================================


import re
import logfire

from langchain_groq import ChatGroq
from nemoguardrails import RailsConfig, LLMRails

from app.config import settings
from app.guardrails.colang_rules import (
    COLANG_CONTENT,
    YAML_CONTENT,
    RAIL_INDICATORS,
)


_rails: LLMRails | None = None


# ============================================================
# FIXED REFUSAL MESSAGE
# ============================================================

REFUSAL_MESSAGE = (
    "I'm an Enterprise IT Assistant focused on Kubernetes, "
    "Intel hardware, and networking. I can't help with that — "
    "but ask me anything technical!"
)


# ============================================================
# INITIALIZE GUARDRAILS
# ============================================================

def initialize_rails() -> None:
    global _rails

    guard_llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="openai/gpt-oss-20b",
        temperature=0,
    )

    config = RailsConfig.from_content(
        colang_content=COLANG_CONTENT,
        yaml_content=YAML_CONTENT,
    )

    _rails = LLMRails(
        config,
        llm=guard_llm,
    )

    logfire.info(
        "🛡️ NeMo Guardrails initialised "
        "(openai/gpt-oss-20b)."
    )


# ============================================================
# REMOVE MODEL REASONING FROM RESPONSE
# ============================================================

def clean_guardrail_response(content: str) -> str:
    """
    Removes <think>...</think> blocks from the guardrail
    model response.
    """

    if not content:
        return ""

    # Remove reasoning blocks
    content = re.sub(
        r"<think>.*?</think>",
        "",
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )

    return content.strip()


# ============================================================
# GUARD
# ============================================================

def guard(message: str) -> tuple[bool, str | None]:

    if _rails is None:
        logfire.warning(
            "⚠️ Guardrails not initialised — skipping gate."
        )

        return False, None

    with logfire.span("🛡️ Guardrails Check"):

        try:

            result = _rails.generate(
                messages=[
                    {
                        "role": "user",
                        "content": message,
                    }
                ]
            )

            # ------------------------------------------------
            # Get generated content
            # ------------------------------------------------

            if isinstance(result, dict):
                content = result.get("content", "")
            else:
                content = str(result)

            content = clean_guardrail_response(content)

            # ------------------------------------------------
            # Check whether guardrail fired
            # ------------------------------------------------

            fired = any(
                indicator.lower() in content.lower()
                for indicator in RAIL_INDICATORS
            )

            # ------------------------------------------------
            # BLOCKED
            # ------------------------------------------------

            if fired:

                logfire.info(
                    f"🛡️ Guardrails fired | "
                    f"query='{message[:80]}'"
                )

                # IMPORTANT:
                # Do NOT return the LLM's reasoning.
                # Return only the fixed refusal message.
                return True, REFUSAL_MESSAGE

            # ------------------------------------------------
            # ALLOWED
            # ------------------------------------------------

            logfire.info(
                f"✅ Guardrails passed | "
                f"query='{message[:80]}'"
            )

            return False, None

        except Exception as e:

            logfire.error(
                f"❌ Guardrails check failed: {e}"
            )

            raise