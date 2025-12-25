# Fix: Enable Full Pipeline (Planning Phases)

**Date**: 2025-12-25
**Status**: Completed

## Problem

When running `python main.py`, the planning agents (ideation, architecture, task_breakdown) were not processing the user's idea. Only `initialize` and `implement` phases were running.

**Expected flow:**
```
User's Idea → Ideation Agent → Architecture Agent → Task Breakdown → Initialize → Implement
```

**Actual flow (before fix):**
```
User's Idea → Initialize (copies generic app_spec.txt) → Implement
```

## Root Cause

In `main.py:255`, `create_default_runner()` was called without the `include_planning_phases=True` parameter:

```python
# Before:
runner = create_default_runner(project_dir)
```

The `create_default_runner()` function (in `phase_runner.py:439-513`) has:
- `include_planning_phases` parameter that defaults to `False`
- When `True`: runs ideation → architecture → task_breakdown → initialize → implement
- When `False`: runs only initialize → implement

## Fix Applied

### Change 1: Enable planning phases in main.py

**File:** `main.py` line 255

```python
# After:
runner = create_default_runner(project_dir, include_planning_phases=True)
```

### Change 2: Fix idea extraction in ideation phase

**File:** `phases/ideation.py` line 82

The idea is passed as a dict `{"idea": "..."}` from `main.py:280`, but the code was doing `str(input_data)` which produced `"{'idea': '...'}"`.

```python
# Before:
prompt = prompt_template.replace("{{IDEA}}", str(input_data))

# After:
if isinstance(input_data, dict):
    idea_text = input_data.get("idea", str(input_data))
else:
    idea_text = str(input_data)
prompt = prompt_template.replace("{{IDEA}}", idea_text)
```

### Change 3: Output to PRPs/plans subdirectory

Updated all phase output paths to use `{project_dir}/PRPs/plans/` instead of `{project_dir}/`.

**Writes (output files):**

| File | Change |
|------|--------|
| `phases/ideation.py:124-127` | Write to `PRPs/plans/requirements.md` |
| `phases/architecture.py:119-122` | Write to `PRPs/plans/architecture.md` |
| `phases/task_breakdown.py:116-119` | Write to `PRPs/plans/tasks.md` |

**Reads (helper methods):**

| File | Method | Change |
|------|--------|--------|
| `phases/architecture.py:158-159` | `_extract_requirements()` | Read from `PRPs/plans/requirements.md` |
| `phases/task_breakdown.py:162-163` | `_extract_architecture()` | Read from `PRPs/plans/architecture.md` |
| `phases/task_breakdown.py:182-183` | `_extract_requirements()` | Read from `PRPs/plans/requirements.md` |

## Files Modified

| File | Lines Changed | Description |
|------|---------------|-------------|
| `main.py` | 255 | Added `include_planning_phases=True` |
| `phases/ideation.py` | 81-88, 124-128 | Fixed idea extraction, updated output path |
| `phases/architecture.py` | 119-123, 158-159 | Updated write/read paths |
| `phases/task_breakdown.py` | 116-120, 162-163, 182-183 | Updated write/read paths |

## Expected Behavior After Fix

1. User enters idea: "Build a task management app"
2. **Ideation phase** - Agent analyzes idea, produces `PRPs/plans/requirements.md`
3. **Architecture phase** - Agent reads requirements, produces `PRPs/plans/architecture.md`
4. **Task Breakdown phase** - Creates actionable tasks, produces `PRPs/plans/tasks.md`
5. **Initialize phase** - Creates Linear issues from tasks
6. **Implement phase** - Implements each task

## Verification

Run `python main.py` and verify:
1. Ideation phase runs and produces `{project_dir}/PRPs/plans/requirements.md`
2. Architecture phase runs and produces `{project_dir}/PRPs/plans/architecture.md`
3. Task breakdown runs and produces `{project_dir}/PRPs/plans/tasks.md`
4. Initialize phase creates Linear issues based on tasks

## Notes

- `app_spec.txt` copying in `InitializePhase` was left unchanged as it's used by `autonomous_agent_demo.py` (the original two-agent implementation)
- The planning phases will produce `requirements.md` which downstream phases will use instead
