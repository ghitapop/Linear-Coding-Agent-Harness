"""Aggregator for combining swarm agent outputs."""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from orchestrator.swarm_controller import AgentStatus, SwarmAgentResult, SwarmResult


class AggregationStrategy(str, Enum):
    """Strategy for aggregating swarm outputs."""

    CONCATENATE = "concatenate"  # Simple concatenation with headers
    MERGE = "merge"  # Merge similar sections
    SYNTHESIZE = "synthesize"  # AI-powered synthesis into unified output
    VOTE = "vote"  # Voting for discrete choices
    BEST_OF = "best_of"  # Select best output based on criteria


@dataclass
class AggregationResult:
    """Result of aggregating swarm outputs."""

    content: str
    strategy_used: AggregationStrategy
    source_count: int
    metadata: dict[str, Any] = field(default_factory=dict)

    # Optional breakdown by section
    sections: dict[str, str] = field(default_factory=dict)


class Aggregator(ABC):
    """Abstract base class for swarm output aggregation."""

    @abstractmethod
    async def aggregate(
        self,
        swarm_result: SwarmResult,
        context: Optional[dict[str, Any]] = None,
    ) -> AggregationResult:
        """Aggregate swarm outputs into a single result.

        Args:
            swarm_result: Result from swarm execution.
            context: Optional context for aggregation.

        Returns:
            AggregationResult with combined output.
        """
        pass


class ConcatenateAggregator(Aggregator):
    """Simple aggregator that concatenates outputs with headers.

    Best for: Initial brainstorming where all perspectives are valuable.
    """

    def __init__(
        self,
        separator: str = "\n\n---\n\n",
        include_role_headers: bool = True,
    ) -> None:
        """Initialize the concatenate aggregator.

        Args:
            separator: Separator between agent outputs.
            include_role_headers: Whether to include role headers.
        """
        self._separator = separator
        self._include_role_headers = include_role_headers

    async def aggregate(
        self,
        swarm_result: SwarmResult,
        context: Optional[dict[str, Any]] = None,
    ) -> AggregationResult:
        """Concatenate all successful outputs.

        Args:
            swarm_result: Result from swarm execution.
            context: Optional context (unused in this strategy).

        Returns:
            AggregationResult with concatenated output.
        """
        parts: list[str] = []
        sections: dict[str, str] = {}

        for result in swarm_result.agent_results:
            if result.status != AgentStatus.COMPLETED or not result.output:
                continue

            if self._include_role_headers:
                role_display = result.role.replace("_", " ").title()
                header = f"## {role_display} Analysis\n\n"
                part = header + result.output
            else:
                part = result.output

            parts.append(part)
            sections[result.role] = result.output

        content = self._separator.join(parts)

        return AggregationResult(
            content=content,
            strategy_used=AggregationStrategy.CONCATENATE,
            source_count=len(parts),
            sections=sections,
            metadata={
                "total_agents": len(swarm_result.agent_results),
                "successful_agents": swarm_result.success_count,
            },
        )


class MergeAggregator(Aggregator):
    """Aggregator that merges similar sections from different outputs.

    Best for: Architecture documents where different agents cover
    different aspects that should be combined into one cohesive document.
    """

    # Standard section headers to merge
    DEFAULT_SECTIONS = [
        "overview",
        "components",
        "data model",
        "api",
        "security",
        "performance",
        "deployment",
        "testing",
    ]

    def __init__(
        self,
        sections: Optional[list[str]] = None,
    ) -> None:
        """Initialize the merge aggregator.

        Args:
            sections: Section headers to look for and merge.
        """
        self._sections = sections or self.DEFAULT_SECTIONS

    async def aggregate(
        self,
        swarm_result: SwarmResult,
        context: Optional[dict[str, Any]] = None,
    ) -> AggregationResult:
        """Merge outputs by section.

        Args:
            swarm_result: Result from swarm execution.
            context: Optional context.

        Returns:
            AggregationResult with merged output.
        """
        # Collect content from all agents
        all_content: list[str] = []
        for result in swarm_result.agent_results:
            if result.status == AgentStatus.COMPLETED and result.output:
                all_content.append(result.output)

        if not all_content:
            return AggregationResult(
                content="",
                strategy_used=AggregationStrategy.MERGE,
                source_count=0,
            )

        # Extract sections from each output
        extracted_sections: dict[str, list[str]] = {s: [] for s in self._sections}
        other_content: list[str] = []

        for content in all_content:
            found_sections = self._extract_sections(content)
            for section, text in found_sections.items():
                if section in extracted_sections:
                    extracted_sections[section].append(text)
                else:
                    other_content.append(text)

        # Merge sections
        merged_parts: list[str] = []
        result_sections: dict[str, str] = {}

        for section in self._sections:
            section_contents = extracted_sections.get(section, [])
            if section_contents:
                section_title = section.title()
                merged = f"## {section_title}\n\n"
                merged += "\n\n".join(section_contents)
                merged_parts.append(merged)
                result_sections[section] = merged

        # Add any other content
        if other_content:
            merged_parts.append("## Additional Notes\n\n" + "\n\n".join(other_content))

        content = "\n\n---\n\n".join(merged_parts)

        return AggregationResult(
            content=content,
            strategy_used=AggregationStrategy.MERGE,
            source_count=len(all_content),
            sections=result_sections,
            metadata={
                "sections_found": list(result_sections.keys()),
                "total_agents": len(swarm_result.agent_results),
            },
        )

    def _extract_sections(self, content: str) -> dict[str, str]:
        """Extract sections from markdown content.

        Args:
            content: Markdown content.

        Returns:
            Dict mapping section names to content.
        """
        sections: dict[str, str] = {}
        lines = content.split("\n")
        current_section: Optional[str] = None
        current_content: list[str] = []

        for line in lines:
            # Check if this is a header
            if line.startswith("#"):
                # Save previous section
                if current_section and current_content:
                    sections[current_section] = "\n".join(current_content).strip()

                # Start new section
                header_text = line.lstrip("#").strip().lower()
                current_section = None
                for section in self._sections:
                    if section in header_text:
                        current_section = section
                        break
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_section and current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections


class SynthesizeAggregator(Aggregator):
    """Aggregator that uses AI to synthesize outputs into a unified document.

    Best for: Final documents where a cohesive, well-structured output is needed.
    """

    def __init__(
        self,
        model: str = "claude-opus-4-5-20251101",
        synthesis_prompt: Optional[str] = None,
    ) -> None:
        """Initialize the synthesize aggregator.

        Args:
            model: Model to use for synthesis.
            synthesis_prompt: Custom synthesis prompt template.
        """
        self._model = model
        self._synthesis_prompt = synthesis_prompt or self._default_prompt()

    def _default_prompt(self) -> str:
        """Get default synthesis prompt."""
        return """# Synthesis Task

You are a technical writer synthesizing multiple analysis documents into one cohesive document.

## Source Documents

{documents}

## Instructions

1. Read all source documents carefully
2. Identify common themes, agreements, and unique insights
3. Resolve any contradictions by choosing the most well-reasoned approach
4. Create a single, well-structured document that incorporates the best from all sources
5. Maintain technical accuracy and completeness
6. Use clear section headers and organize logically

## Output Format

Create a comprehensive Markdown document that synthesizes all the inputs into a cohesive whole.
Do not simply concatenate - truly synthesize and integrate the information.
"""

    async def aggregate(
        self,
        swarm_result: SwarmResult,
        context: Optional[dict[str, Any]] = None,
    ) -> AggregationResult:
        """Synthesize outputs using AI.

        Args:
            swarm_result: Result from swarm execution.
            context: Optional context with project_dir.

        Returns:
            AggregationResult with synthesized output.
        """
        from client import create_client

        # Collect successful outputs
        documents: list[str] = []
        for i, result in enumerate(swarm_result.agent_results, 1):
            if result.status == AgentStatus.COMPLETED and result.output:
                role_display = result.role.replace("_", " ").title()
                documents.append(f"### Document {i}: {role_display}\n\n{result.output}")

        if not documents:
            return AggregationResult(
                content="",
                strategy_used=AggregationStrategy.SYNTHESIZE,
                source_count=0,
            )

        # Build synthesis prompt
        documents_text = "\n\n---\n\n".join(documents)
        prompt = self._synthesis_prompt.format(documents=documents_text)

        # Get project directory from context
        project_dir = Path(context.get("project_dir", ".")) if context else Path(".")

        # Run synthesis agent
        try:
            client = create_client(project_dir, self._model)

            async with client:
                await client.query(prompt)

                response_text = ""
                async for msg in client.receive_response():
                    msg_type = type(msg).__name__
                    if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                        for block in msg.content:
                            if hasattr(block, "text"):
                                response_text += block.text

            return AggregationResult(
                content=response_text,
                strategy_used=AggregationStrategy.SYNTHESIZE,
                source_count=len(documents),
                metadata={
                    "model": self._model,
                    "total_agents": len(swarm_result.agent_results),
                    "successful_agents": swarm_result.success_count,
                },
            )

        except Exception as e:
            # Fallback to concatenation on error
            fallback = ConcatenateAggregator()
            result = await fallback.aggregate(swarm_result, context)
            result.metadata["synthesis_error"] = str(e)
            result.metadata["fallback_used"] = True
            return result


class VoteAggregator(Aggregator):
    """Aggregator that uses voting for discrete choices.

    Best for: Architecture decisions where agents choose between options.
    """

    def __init__(
        self,
        choices_key: str = "recommendation",
        require_majority: bool = False,
    ) -> None:
        """Initialize the vote aggregator.

        Args:
            choices_key: Key in output JSON containing the choice.
            require_majority: Whether to require majority for decision.
        """
        self._choices_key = choices_key
        self._require_majority = require_majority

    async def aggregate(
        self,
        swarm_result: SwarmResult,
        context: Optional[dict[str, Any]] = None,
    ) -> AggregationResult:
        """Aggregate by voting on choices.

        Args:
            swarm_result: Result from swarm execution.
            context: Optional context.

        Returns:
            AggregationResult with voting results.
        """
        votes: dict[str, int] = {}
        reasonings: dict[str, list[str]] = {}

        for result in swarm_result.agent_results:
            if result.status != AgentStatus.COMPLETED or not result.output:
                continue

            # Try to extract choice from output
            choice, reasoning = self._extract_choice(result.output)
            if choice:
                votes[choice] = votes.get(choice, 0) + 1
                if reasoning:
                    if choice not in reasonings:
                        reasonings[choice] = []
                    reasonings[choice].append(reasoning)

        if not votes:
            return AggregationResult(
                content="No votes could be extracted from agent outputs.",
                strategy_used=AggregationStrategy.VOTE,
                source_count=0,
            )

        # Determine winner
        total_votes = sum(votes.values())
        winner = max(votes.keys(), key=lambda k: votes[k])
        winner_votes = votes[winner]

        if self._require_majority and winner_votes <= total_votes / 2:
            winner = None

        # Build result content
        content_parts = ["# Voting Results\n"]
        content_parts.append(f"Total votes: {total_votes}\n")

        for choice, count in sorted(votes.items(), key=lambda x: -x[1]):
            percentage = (count / total_votes) * 100
            marker = " (SELECTED)" if choice == winner else ""
            content_parts.append(f"- **{choice}**: {count} votes ({percentage:.1f}%){marker}")

        if winner and winner in reasonings:
            content_parts.append(f"\n## Reasoning for {winner}\n")
            for i, reason in enumerate(reasonings[winner], 1):
                content_parts.append(f"\n### Perspective {i}\n{reason}")

        return AggregationResult(
            content="\n".join(content_parts),
            strategy_used=AggregationStrategy.VOTE,
            source_count=total_votes,
            metadata={
                "votes": votes,
                "winner": winner,
                "winner_votes": winner_votes,
                "total_votes": total_votes,
            },
        )

    def _extract_choice(self, output: str) -> tuple[Optional[str], Optional[str]]:
        """Extract choice and reasoning from output.

        Args:
            output: Agent output text.

        Returns:
            Tuple of (choice, reasoning) or (None, None).
        """
        # Try JSON parsing first
        try:
            data = json.loads(output)
            choice = data.get(self._choices_key)
            reasoning = data.get("reasoning")
            return choice, reasoning
        except json.JSONDecodeError:
            pass

        # Try to find choice in text
        # Look for patterns like "Recommendation: X" or "I recommend X"
        lines = output.lower().split("\n")
        for line in lines:
            if "recommend" in line:
                # Extract the recommendation
                parts = line.split(":")
                if len(parts) > 1:
                    return parts[1].strip(), None
        return None, None


class BestOfAggregator(Aggregator):
    """Aggregator that selects the best output based on criteria.

    Best for: Selecting the highest quality output when only one is needed.
    """

    def __init__(
        self,
        criteria: Optional[list[str]] = None,
        model: str = "claude-opus-4-5-20251101",
    ) -> None:
        """Initialize the best-of aggregator.

        Args:
            criteria: Criteria for evaluation.
            model: Model to use for evaluation.
        """
        self._criteria = criteria or [
            "completeness",
            "technical accuracy",
            "clarity",
            "actionability",
        ]
        self._model = model

    async def aggregate(
        self,
        swarm_result: SwarmResult,
        context: Optional[dict[str, Any]] = None,
    ) -> AggregationResult:
        """Select the best output.

        Args:
            swarm_result: Result from swarm execution.
            context: Optional context with project_dir.

        Returns:
            AggregationResult with best output.
        """
        successful = [
            r for r in swarm_result.agent_results
            if r.status == AgentStatus.COMPLETED and r.output
        ]

        if not successful:
            return AggregationResult(
                content="",
                strategy_used=AggregationStrategy.BEST_OF,
                source_count=0,
            )

        if len(successful) == 1:
            return AggregationResult(
                content=successful[0].output or "",
                strategy_used=AggregationStrategy.BEST_OF,
                source_count=1,
                metadata={"selected_role": successful[0].role},
            )

        # For simplicity, select based on output length and structure
        # (A more sophisticated version would use AI evaluation)
        best = max(successful, key=lambda r: self._score_output(r.output or ""))

        return AggregationResult(
            content=best.output or "",
            strategy_used=AggregationStrategy.BEST_OF,
            source_count=len(successful),
            metadata={
                "selected_role": best.role,
                "candidates": len(successful),
            },
        )

    def _score_output(self, output: str) -> float:
        """Score an output based on heuristics.

        Args:
            output: The output to score.

        Returns:
            Score value (higher is better).
        """
        score = 0.0

        # Length (reasonable length is good)
        length = len(output)
        if 1000 < length < 10000:
            score += 30
        elif 500 < length < 20000:
            score += 20

        # Structure (headers indicate organization)
        header_count = output.count("##")
        score += min(header_count * 5, 25)

        # Lists (indicate detailed content)
        list_items = output.count("\n- ") + output.count("\n* ")
        score += min(list_items * 2, 20)

        # Code blocks (technical depth)
        code_blocks = output.count("```")
        score += min(code_blocks * 5, 15)

        # Complete sentences (coherence)
        sentences = output.count(". ")
        score += min(sentences, 10)

        return score


def create_aggregator(strategy: AggregationStrategy, **kwargs: Any) -> Aggregator:
    """Factory function to create an aggregator.

    Args:
        strategy: Aggregation strategy to use.
        **kwargs: Additional arguments for the aggregator.

    Returns:
        Aggregator instance.
    """
    aggregators = {
        AggregationStrategy.CONCATENATE: ConcatenateAggregator,
        AggregationStrategy.MERGE: MergeAggregator,
        AggregationStrategy.SYNTHESIZE: SynthesizeAggregator,
        AggregationStrategy.VOTE: VoteAggregator,
        AggregationStrategy.BEST_OF: BestOfAggregator,
    }

    aggregator_class = aggregators.get(strategy)
    if not aggregator_class:
        raise ValueError(f"Unknown aggregation strategy: {strategy}")

    return aggregator_class(**kwargs)
