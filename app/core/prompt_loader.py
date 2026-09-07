import logging
import yaml
from functools import lru_cache
from pathlib import Path
from typing import Optional
from datetime import datetime

from langchain_core.prompts import (
    SystemMessagePromptTemplate, 
    HumanMessagePromptTemplate,
    ChatPromptTemplate, 
    MessagesPlaceholder
)

logger = logging.getLogger(__name__)




class PromptManager:
    def __init__(self):
        self.PROMPTS_DIR = Path(__file__).parent.parent / "ai" / "prompts"

    @lru_cache(maxsize=1)
    def load_core_config(self) -> dict:
        path = self.PROMPTS_DIR / "core.yaml"
        with open(path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        logger.debug("Core config loaded | path=%s", path)
        return config


    @staticmethod
    def _get_runtime_context() -> dict:
        """
        Generates runtime context variables dynamically.
        Injects current date, year, and time.
        """
        now = datetime.now()
        return {
            "date": now.strftime("%B %d, %Y"),  # e.g., "May 26, 2026"
            "year": str(now.year),               # e.g., "2026"
            "time": now.strftime("%H:%M:%S"),   # e.g., "15:31:50"
        }

    def _get_core_vars(self, config: dict) -> dict:
        """
        Flattens nested YAML into Template-injectable variables.
        Lists are converted to newline-separated strings.
        Includes runtime context (date, year, time).
        """
        def _fmt(value) -> str:
            if isinstance(value, list):
                return "\n".join(f"- {item}" for item in value)
            return str(value).strip()

        core_vars = {
            "product_name":      config["identity"]["name"],
            "company":           config["identity"]["company"],
            "version":           config["identity"]["version"],
            "description":       _fmt(config["identity"]["description"]),
            "security_hard_limits": _fmt(config["security"]["hard_limits"]),
            "jailbreak_policy":  _fmt(config["security"]["jailbreak_policy"]),
            "data_policy":       _fmt(config["security"]["data_policy"]),
            "format":            config["output"]["format"],
            "language":          config["output"]["language"],
            "output_rules":      _fmt(config["output"]["rules"]),
            "reasoning_policy":  _fmt(config["reasoning"]["policy"]),
        }
        
        # Inject runtime context
        core_vars.update(self._get_runtime_context())
        
        return core_vars

    @lru_cache(maxsize=128)
    def _load_raw(self, path: Path) -> str:
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        content = path.read_text(encoding="utf-8").strip()
        logger.debug("Prompt file loaded | path=%s | chars=%d", path, len(content))
        return content


    def load_agent_system_prompt(
        self,
        agent_name: str, 
        include_history: bool = True,
        **runtime_static_variables: Optional[str | list[str]]) -> ChatPromptTemplate:
        """
        Builds the complete system prompt for an agent.

        Assembly order:
        1. Load core.yaml — static identity, security, tone, output rules
        2. Load base/system_shell.md — XML structure template
        3. Load agents/{agent_name}.md — agent-specific behavior
        4. Inject all variables into shell

        Usage:
            load_agent_system_prompt("researcher", user_query="What is X?")
            load_agent_system_prompt("writer", critic_feedback="Section 2 lacks sources")
            load_agent_system_prompt("supervisor")
        """
        core_vars = self._get_core_vars(self.load_core_config())

        shell_path = self.PROMPTS_DIR / "templates" / "system_shell.md"
        shell_raw = self._load_raw(shell_path)

        # 3. Agent-specific prompt
        agent_path = self.PROMPTS_DIR / "agents" / f"{agent_name}.md"
        agent_prompt_raw = self._load_raw(agent_path)

        # Escape literal curly braces inside the agent prompt so that Python's
        # str.format() and LangChain's template parser don't treat JSON examples
        # (e.g. {"mode": "artifact"}) as template variables.
        #
        # We only do this when the agent prompt contains no intentional single-brace
        # LangChain template variables (i.e., patterns like {word} that are NOT
        # already doubled as {{word}}).  Agent prompts that legitimately use
        # {user_input}, {workflow_plan}, {research_findings}, etc. as template
        # variables must remain untouched.
        import re as _re
        _single_brace_vars = _re.findall(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})", agent_prompt_raw)
        if _single_brace_vars:
            # Prompt has real template variables — leave braces as-is.
            agent_prompt_for_shell = agent_prompt_raw
        else:
            # Prompt is static (JSON examples use {{ already or bare {).
            # Escape ALL braces so Python str.format() and LangChain don't
            # misinterpret them.  After shell.format() the {{ become { for LangChain,
            # which then renders them as literal { in the final message.
            agent_prompt_for_shell = agent_prompt_raw.replace("{", "{{").replace("}", "}}")

        full_system_content = shell_raw.format(
            **core_vars,
            agent_prompt=agent_prompt_for_shell
        )

        messages = [
            SystemMessagePromptTemplate.from_template(full_system_content)
        ]
        if include_history:
            messages.append(
                MessagesPlaceholder(variable_name="history", optional=True)
            )
        messages.append(
            HumanMessagePromptTemplate.from_template("{user_input}")
        )

        template = ChatPromptTemplate.from_messages(messages)

        logger.debug("System prompt assembled | agent=%s", agent_name)
        return template


    def load_tool_description(self, tool_name: str) -> str:
        """
        Loads tool description for use in llm.bind_tools().
        Tool descriptions are never combined with the shell —
        they go directly into the tool definition.
        """
        path = self.PROMPTS_DIR / "tools" / f"{tool_name}.md"
        return self._load_raw(path)