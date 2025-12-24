# Architecture Aggregation - Swarm Output Synthesis

## Your Task
You are the aggregation agent for the architecture phase. Multiple agents have designed different aspects of the system. Synthesize their outputs into a single, coherent architecture document.

## Agent Outputs

### Agent 1 (System Design):
{{AGENT_1_OUTPUT}}

### Agent 2 (Data Models):
{{AGENT_2_OUTPUT}}

### Agent 3 (API Design):
{{AGENT_3_OUTPUT}}

## Instructions

### 1. Validate Consistency

Check for consistency across agent outputs:
- Do technology choices align?
- Do data models support the API design?
- Does the system design account for all entities?
- Are there naming inconsistencies?

### 2. Resolve Conflicts

Where agents made different choices:
- Evaluate trade-offs
- Choose the option that best serves requirements
- Document the decision and rationale

### 3. Fill Gaps

Ensure completeness:
- All entities have complete definitions
- All APIs have corresponding data models
- Security is addressed for all components
- Error handling is specified

### 4. Optimize

Look for optimization opportunities:
- Can any components be combined?
- Are there redundant layers?
- Is the architecture appropriately simple?

### 5. Create Unified Document

Merge all outputs into a single `architecture.md` with:
- Technology Stack (unified)
- System Architecture (one coherent diagram)
- Data Models (complete schema)
- API Specification (full endpoints)
- Directory Structure (agreed upon)
- Security Model (comprehensive)

## Output Format
Create the final `architecture.md` that:
- Is internally consistent
- Contains no contradictions
- Provides complete implementation guidance
- Can be used directly by task breakdown phase

## Quality Checklist
- [ ] All technology choices are justified
- [ ] System diagram shows all components
- [ ] All entities have complete schemas
- [ ] All relationships are defined
- [ ] API endpoints cover all use cases
- [ ] Security is addressed throughout
- [ ] Directory structure is practical
- [ ] No inconsistencies between sections
