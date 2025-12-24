# Ideation Aggregation - Swarm Output Synthesis

## Your Task
You are the aggregation agent for the ideation phase. Multiple agents have brainstormed requirements from different perspectives. Your job is to synthesize their outputs into a single, coherent requirements document.

## Agent Outputs

### Agent 1 (User Focus):
{{AGENT_1_OUTPUT}}

### Agent 2 (Technical Focus):
{{AGENT_2_OUTPUT}}

### Agent 3 (Edge Cases Focus):
{{AGENT_3_OUTPUT}}

## Instructions

### 1. Identify Common Themes
- What requirements appear in multiple agent outputs?
- What are the core features everyone agrees on?
- Mark high-consensus items as high priority

### 2. Resolve Conflicts
- Where do agents disagree?
- Apply the principle of "user value first"
- Document trade-offs and decisions made

### 3. Fill Gaps
- What did agents miss collectively?
- Add any obvious requirements not mentioned
- Ensure completeness across all requirement types

### 4. Prioritize
- Use the MoSCoW method:
  - **Must Have:** Critical for MVP
  - **Should Have:** Important but not critical
  - **Could Have:** Nice to have
  - **Won't Have:** Explicitly out of scope

### 5. Structure
- Organize requirements logically
- Group related requirements
- Ensure traceability (each requirement has ID)

## Output Format
Create a single, unified requirements document that:
- Combines the best insights from all agents
- Resolves any contradictions
- Is well-organized and actionable
- Can be used directly by the architecture phase

Save as `requirements.md` in the project directory.

## Quality Checklist
Before saving, verify:
- [ ] All user personas defined
- [ ] User stories cover main workflows
- [ ] Functional requirements are specific and measurable
- [ ] Non-functional requirements address performance, security, accessibility
- [ ] MVP scope is clearly defined
- [ ] Success metrics are measurable
- [ ] No contradictions or ambiguities remain
