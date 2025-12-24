"""Configuration loader for YAML files."""

import os
from pathlib import Path
from typing import Any

import yaml

from config.schema import OrchestratorConfig, ProjectConfig


def load_config(config_path: Path) -> OrchestratorConfig:
    """Load orchestrator configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Parsed OrchestratorConfig object.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        yaml.YAMLError: If the YAML is invalid.
        pydantic.ValidationError: If the config doesn't match the schema.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    return load_config_from_dict(raw_config)


def load_config_from_dict(config_dict: dict[str, Any]) -> OrchestratorConfig:
    """Load orchestrator configuration from a dictionary.

    This function also handles environment variable substitution
    for sensitive values like API keys and database URLs.

    Args:
        config_dict: Configuration dictionary.

    Returns:
        Parsed OrchestratorConfig object.
    """
    # Substitute environment variables
    config_dict = _substitute_env_vars(config_dict)

    # Handle database_url at root level
    if "database_url" not in config_dict:
        config_dict["database_url"] = os.environ.get("DATABASE_URL")

    # Handle backend-specific env vars
    if "backend" in config_dict:
        backend = config_dict["backend"]
        if "database_url" not in backend or backend["database_url"] is None:
            backend["database_url"] = os.environ.get("DATABASE_URL")
        if "linear_api_key" not in backend or backend["linear_api_key"] is None:
            backend["linear_api_key"] = os.environ.get("LINEAR_API_KEY")

    # Handle agent-specific env vars
    if "agent" not in config_dict:
        config_dict["agent"] = {}
    agent = config_dict["agent"]

    # AGENT_MODEL env var
    if "model" not in agent or agent["model"] is None:
        env_model = os.environ.get("AGENT_MODEL")
        if env_model:
            agent["model"] = env_model

    # MAX_SESSIONS env var
    if "max_sessions" not in agent or agent["max_sessions"] is None:
        env_max_sessions = os.environ.get("MAX_SESSIONS")
        if env_max_sessions:
            try:
                agent["max_sessions"] = int(env_max_sessions)
            except ValueError:
                pass  # Ignore invalid values, use default

    return OrchestratorConfig.model_validate(config_dict)


def _substitute_env_vars(obj: Any) -> Any:
    """Recursively substitute environment variables in config values.

    Supports ${VAR_NAME} and ${VAR_NAME:-default} syntax.

    Args:
        obj: Configuration object (dict, list, or scalar).

    Returns:
        Object with environment variables substituted.
    """
    if isinstance(obj, dict):
        return {k: _substitute_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_env_vars(item) for item in obj]
    elif isinstance(obj, str):
        return _expand_env_string(obj)
    return obj


def _expand_env_string(value: str) -> str:
    """Expand environment variables in a string.

    Supports:
    - ${VAR_NAME} - Required variable
    - ${VAR_NAME:-default} - Variable with default

    Args:
        value: String potentially containing env var references.

    Returns:
        String with env vars expanded.
    """
    import re

    pattern = r"\$\{([^}:]+)(?::-([^}]*))?\}"

    def replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default = match.group(2)
        env_value = os.environ.get(var_name)
        if env_value is not None:
            return env_value
        if default is not None:
            return default
        return match.group(0)  # Keep original if no value and no default

    return re.sub(pattern, replace, value)


def create_default_config(project_name: str, project_dir: Path) -> OrchestratorConfig:
    """Create a default configuration for a new project.

    Args:
        project_name: Name of the project.
        project_dir: Directory for the project.

    Returns:
        Default OrchestratorConfig object.
    """
    return OrchestratorConfig(
        project=ProjectConfig(
            name=project_name,
            directory=project_dir,
        )
    )


def save_config(config: OrchestratorConfig, config_path: Path) -> None:
    """Save orchestrator configuration to a YAML file.

    Args:
        config: Configuration to save.
        config_path: Path to save the configuration to.
    """
    # Convert to dict, excluding None values and defaults where appropriate
    config_dict = config.model_dump(
        mode="json",
        exclude_none=True,
    )

    # Convert Path objects to strings
    config_dict = _paths_to_strings(config_dict)

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)


def _paths_to_strings(obj: Any) -> Any:
    """Convert Path objects to strings for YAML serialization."""
    if isinstance(obj, dict):
        return {k: _paths_to_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_paths_to_strings(item) for item in obj]
    elif isinstance(obj, Path):
        return str(obj)
    return obj
