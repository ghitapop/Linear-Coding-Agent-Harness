"""
Prompt Loading Utilities
========================

Functions for loading prompt templates from the prompts directory.
Supports both flat prompts (e.g., coding_prompt.md) and
phase-specific prompts (e.g., ideation/brainstorm.md).
"""

import shutil
from pathlib import Path
from typing import Optional


PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory.

    Args:
        name: The prompt name (without .md extension).

    Returns:
        The prompt content.

    Raises:
        FileNotFoundError: If the prompt file doesn't exist.
    """
    prompt_path = PROMPTS_DIR / f"{name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")
    return prompt_path.read_text()


def load_phase_prompt(phase: str, prompt_name: str) -> str:
    """Load a phase-specific prompt template.

    Args:
        phase: The phase name (e.g., 'ideation', 'architecture').
        prompt_name: The prompt name within the phase (e.g., 'brainstorm').

    Returns:
        The prompt content.

    Raises:
        FileNotFoundError: If the prompt file doesn't exist.

    Example:
        >>> load_phase_prompt('ideation', 'brainstorm')
        # Loads prompts/ideation/brainstorm.md
    """
    prompt_path = PROMPTS_DIR / phase / f"{prompt_name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Phase prompt not found: {prompt_path}")
    return prompt_path.read_text()


def get_phase_prompts(phase: str) -> list[str]:
    """Get all prompt names available for a phase.

    Args:
        phase: The phase name.

    Returns:
        List of prompt names (without .md extension).
    """
    phase_dir = PROMPTS_DIR / phase
    if not phase_dir.exists() or not phase_dir.is_dir():
        return []
    return [p.stem for p in phase_dir.glob("*.md")]


def list_phases_with_prompts() -> dict[str, list[str]]:
    """List all phases and their available prompts.

    Returns:
        Dict mapping phase names to lists of prompt names.
    """
    phases = {}
    for path in PROMPTS_DIR.iterdir():
        if path.is_dir() and not path.name.startswith("_"):
            prompts = [p.stem for p in path.glob("*.md")]
            if prompts:
                phases[path.name] = prompts
    return phases


def get_initializer_prompt() -> str:
    """Load the initializer prompt."""
    return load_prompt("initializer_prompt")


def get_coding_prompt() -> str:
    """Load the coding agent prompt."""
    return load_prompt("coding_prompt")


def copy_spec_to_project(project_dir: Path) -> None:
    """Copy the app spec file into the project directory for the agent to read."""
    spec_source = PROMPTS_DIR / "app_spec.txt"
    spec_dest = project_dir / "app_spec.txt"
    if not spec_dest.exists():
        shutil.copy(spec_source, spec_dest)
        print("Copied app_spec.txt to project directory")


def render_prompt(
    template: str,
    variables: Optional[dict[str, str]] = None,
) -> str:
    """Render a prompt template with variable substitution.

    Uses {{VARIABLE}} syntax for placeholders.

    Args:
        template: The prompt template string.
        variables: Dict of variable names to values.

    Returns:
        The rendered prompt with variables substituted.

    Example:
        >>> render_prompt("Hello {{NAME}}!", {"NAME": "World"})
        "Hello World!"
    """
    if not variables:
        return template

    result = template
    for key, value in variables.items():
        placeholder = "{{" + key + "}}"
        result = result.replace(placeholder, str(value))

    return result


def load_and_render_phase_prompt(
    phase: str,
    prompt_name: str,
    variables: Optional[dict[str, str]] = None,
) -> str:
    """Load a phase prompt and render it with variables.

    Convenience function combining load_phase_prompt and render_prompt.

    Args:
        phase: The phase name.
        prompt_name: The prompt name within the phase.
        variables: Dict of variable names to values.

    Returns:
        The rendered prompt.

    Example:
        >>> load_and_render_phase_prompt(
        ...     'ideation', 'brainstorm',
        ...     {'IDEA': 'Build a todo app'}
        ... )
    """
    template = load_phase_prompt(phase, prompt_name)
    return render_prompt(template, variables)
