
import re
import logfire

from langchain_groq import ChatGroq
from nemoguardrails import RailsConfig, LLMRails

from app.config import settings

from app.guardrails.colang_rules import (
    COLANG_CONTENT,
    YAML_CONTENT,
    RAIL_INDICATORS
)


_rails: LLMRails | None = None


# ============================================================
# SUPPORTED DOMAIN KEYWORDS
# ============================================================

SUPPORTED_KEYWORDS = [
    # Kubernetes
    "kubernetes",
    "k8s",
    "pod",
    "pods",
    "deployment",
    "deployments",
    "service",
    "services",
    "cronjob",
    "ingress",
    "kubectl",
    "kubelet",
    "helm",
    "hpa",
    "vpa",
    "operator",
    "operators",

    # Intel hardware
    "intel",
    "fpga",
    "sriov",
    "sr-iov",
    "nic",
    "nics",
    "cpu",
    "hardware accelerator",

    # Networking
    "network",
    "networking",
    "bgp",
    "vlan",
    "sdn",
    "routing",
    "router",
    "switch",
    "tcp/ip",
    "firewall",
    "subnet"
]


# ============================================================
# JAILBREAK DETECTION
# ============================================================

JAILBREAK_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"forget\s+(your\s+)?system\s+prompt",
    r"reveal\s+(your\s+)?system\s+prompt",
    r"show\s+(your\s+)?hidden\s+instructions",
    r"bypass\s+(your\s+)?safety\s+rules",
    r"act\s+as\s+an\s+unrestricted\s+ai",
    r"you\s+are\s+now\s+dan",
    r"developer\s+mode"
]


def initialize_rails() -> None:
    """
    Initialize NeMo Guardrails using Groq.
    """

    global _rails

    guard_llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="openai/gpt-oss-20b",
        temperature=0
    )

    config = RailsConfig.from_content(
        colang_content=COLANG_CONTENT,
        yaml_content=YAML_CONTENT
    )

    _rails = LLMRails(config, llm=guard_llm)

    logfire.info(
        "NeMo Guardrails initialized (openai/gpt-oss-20b)."
    )


def guard(message: str) -> tuple[bool, str | None]:
    """
    Check whether the user message should be blocked.

    True  -> Block and return response.
    False -> Allow message to proceed to LangGraph.
    """

    if _rails is None:
        logfire.warning("Guardrails not initialized.")
        return False, None

    message = message.strip()
    lower_message = message.lower()
    print("===== UPDATED RAILS.PY EXECUTED =====")
    print("USER MESSAGE:", message)
    print("INTEL CHECK:", "intel" in lower_message)
    lower_message = message.lower()

    if not message:
        return True, "Please enter a question."

    with logfire.span("Guardrails Check"):

        logfire.info(f"Checking query: {message[:80]}")

        # ----------------------------------------------------
        # 1. CHECK JAILBREAK FIRST
        # ----------------------------------------------------

        for pattern in JAILBREAK_PATTERNS:

            if re.search(pattern, lower_message):
                logfire.warning("Jailbreak attempt detected.")

                return True, (
                    "I maintain consistent guidelines regardless "
                    "of how I am prompted. I am here to help with "
                    "Kubernetes, Intel, and networking. "
                    "What can I help you with?"
                )

        # ----------------------------------------------------
        # 2. ALLOW SUPPORTED DOMAIN QUESTIONS
        # ----------------------------------------------------

        for keyword in SUPPORTED_KEYWORDS:

            pattern = (
                r"(?<![a-zA-Z0-9_])"
                + re.escape(keyword)
                + r"(?![a-zA-Z0-9_])"
            )

            if re.search(pattern, lower_message):

                logfire.info(
                    f"Supported domain detected: {keyword}"
                )

                return False, None

        # ----------------------------------------------------
        # 3. RUN NEMO GUARDRAILS
        # ----------------------------------------------------

        try:

            result = _rails.generate(
                messages=[
                    {
                        "role": "user",
                        "content": message
                    }
                ]
            )

            content = (
                result.get("content", "")
                if isinstance(result, dict)
                else str(result)
            )

            content = content.strip()

            logfire.info(
                f"NeMo response: {content[:200]}"
            )

            # ------------------------------------------------
            # 4. CHECK RAIL RESPONSE
            # ------------------------------------------------

            fired = any(
                indicator.lower() in content.lower()
                for indicator in RAIL_INDICATORS
            )

            if fired:

                logfire.warning(
                    f"Guardrails blocked query: {message[:80]}"
                )

                return True, content

            # ------------------------------------------------
            # 5. ALLOW REQUEST TO RAG
            # ------------------------------------------------

            logfire.info("Guardrails passed.")

            return False, None

        except Exception as exc:

            logfire.exception(
                f"Guardrails error: {exc}"
            )

            return True, (
                "I'm temporarily unable to validate your question. "
                "Please try again."
            )
