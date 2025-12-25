"""
Claude SDK Client Configuration
===============================

Functions for creating and configuring the Claude Agent SDK client.
"""

import json
import os
from pathlib import Path

from claude_code_sdk import ClaudeCodeOptions, ClaudeSDKClient
from claude_code_sdk.types import HookMatcher

from security import bash_security_hook


# Puppeteer MCP tools for browser automation
PUPPETEER_TOOLS = [
    "mcp__puppeteer__puppeteer_navigate",
    "mcp__puppeteer__puppeteer_screenshot",
    "mcp__puppeteer__puppeteer_click",
    "mcp__puppeteer__puppeteer_fill",
    "mcp__puppeteer__puppeteer_select",
    "mcp__puppeteer__puppeteer_hover",
    "mcp__puppeteer__puppeteer_evaluate",
]

# Linear MCP tools for project management
# Official Linear MCP server at mcp.linear.app
LINEAR_TOOLS = [
    # Team & Project discovery
    "mcp__linear__list_teams",
    "mcp__linear__get_team",
    "mcp__linear__list_projects",
    "mcp__linear__get_project",
    "mcp__linear__create_project",
    "mcp__linear__update_project",
    # Issue management
    "mcp__linear__list_issues",
    "mcp__linear__get_issue",
    "mcp__linear__create_issue",
    "mcp__linear__update_issue",
    "mcp__linear__list_my_issues",
    # Comments
    "mcp__linear__list_comments",
    "mcp__linear__create_comment",
    # Workflow
    "mcp__linear__list_issue_statuses",
    "mcp__linear__get_issue_status",
    "mcp__linear__list_issue_labels",
    # Users
    "mcp__linear__list_users",
    "mcp__linear__get_user",
]

# Built-in tools
BUILTIN_TOOLS = [
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Bash",
]


def setup_project_settings(project_dir: Path, verbose: bool = True) -> Path:
    """
    Set up project security settings file. Called ONCE by orchestrator before spawning agents.

    Args:
        project_dir: Directory for the project
        verbose: If True, print setup messages

    Returns:
        Path to the settings file

    This function is idempotent - it will only create the settings file if it doesn't exist.
    """
    # Ensure project directory exists
    project_dir.mkdir(parents=True, exist_ok=True)

    settings_file = project_dir / ".claude_settings.json"

    # Only create if it doesn't exist (idempotent)
    if settings_file.exists():
        if verbose:
            print(f"Using existing security settings at {settings_file}")
        return settings_file

    # Create comprehensive security settings
    # Note: Using relative paths ("./**") restricts access to project directory
    # since cwd is set to project_dir
    security_settings = {
        "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True},
        "permissions": {
            "defaultMode": "acceptEdits",  # Auto-approve edits within allowed directories
            "allow": [
                # Allow all file operations within the project directory
                "Read(./**)",
                "Write(./**)",
                "Edit(./**)",
                "Glob(./**)",
                "Grep(./**)",
                # Bash permission granted here, but actual commands are validated
                # by the bash_security_hook (see security.py for allowed commands)
                "Bash(*)",
                # Allow Puppeteer MCP tools for browser automation
                *PUPPETEER_TOOLS,
                # Allow Linear MCP tools for project management
                *LINEAR_TOOLS,
            ],
        },
    }

    # Write settings to file
    with open(settings_file, "w") as f:
        json.dump(security_settings, f, indent=2)

    if verbose:
        print(f"Created security settings at {settings_file}")
        print("   - Sandbox enabled (OS-level bash isolation)")
        print(f"   - Filesystem restricted to: {project_dir.resolve()}")
        print("   - Bash commands restricted to allowlist (see security.py)")
        print("   - MCP servers: puppeteer (browser automation), linear (project management)")
        print()

    return settings_file


def create_client(project_dir: Path, model: str, verbose: bool = True) -> ClaudeSDKClient:
    """
    Create a Claude Agent SDK client using existing project settings.

    Args:
        project_dir: Directory for the project (must have .claude_settings.json)
        model: Claude model to use
        verbose: If True, print status messages

    Returns:
        Configured ClaudeSDKClient

    Note: Call setup_project_settings() first to create the settings file.
    If settings don't exist, they will be created automatically for backwards compatibility.

    Security layers (defense in depth):
    1. Sandbox - OS-level bash command isolation prevents filesystem escape
    2. Permissions - File operations restricted to project_dir only
    3. Security hooks - Bash commands validated against an allowlist
       (see security.py for ALLOWED_COMMANDS)
    """
    api_key = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if not api_key:
        raise ValueError(
            "CLAUDE_CODE_OAUTH_TOKEN environment variable not set.\n"
            "Run 'claude setup-token after installing the Claude Code CLI."
        )

    linear_api_key = os.environ.get("LINEAR_API_KEY")
    if not linear_api_key:
        raise ValueError(
            "LINEAR_API_KEY environment variable not set.\n"
            "Get your API key from: https://linear.app/YOUR-TEAM/settings/api"
        )

    # Ensure settings exist (backwards compatibility - orchestrator should call setup_project_settings first)
    settings_file = project_dir / ".claude_settings.json"
    if not settings_file.exists():
        settings_file = setup_project_settings(project_dir, verbose=verbose)

    return ClaudeSDKClient(
        options=ClaudeCodeOptions(
            model=model,
            system_prompt="You are an expert full-stack developer building a production-quality web application. You use Linear for project management and tracking all your work.",
            allowed_tools=[
                *BUILTIN_TOOLS,
                *PUPPETEER_TOOLS,
                *LINEAR_TOOLS,
            ],
            mcp_servers={
                "puppeteer": {"command": "npx", "args": ["puppeteer-mcp-server"]},
                # Linear MCP with Streamable HTTP transport (recommended over SSE)
                # See: https://linear.app/docs/mcp
                "linear": {
                    "type": "http",
                    "url": "https://mcp.linear.app/mcp",
                    "headers": {
                        "Authorization": f"Bearer {linear_api_key}"
                    }
                }
            },
            hooks={
                "PreToolUse": [
                    HookMatcher(matcher="Bash", hooks=[bash_security_hook]),
                ],
            },
            max_turns=1000,
            cwd=str(project_dir.resolve()),
            settings=str(settings_file.resolve()),  # Use absolute path
        )
    )
