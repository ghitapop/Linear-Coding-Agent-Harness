# Testing Phase - Comprehensive Testing

## Your Task
Run comprehensive tests on the implemented application. Execute {{TEST_TYPES}} tests.

## Project Directory
{{PROJECT_DIR}}

## Instructions

### 1. Discover Testing Setup

First, understand the testing environment:
- Find test configuration files (jest.config.js, pytest.ini, vitest.config.ts, etc.)
- Identify the testing framework used
- Locate existing test files
- Check for test scripts in package.json / pyproject.toml

### 2. Run Unit Tests

Execute all unit tests:

**For JavaScript/TypeScript:**
```bash
npm test
# or
npx jest
# or
npx vitest
```

**For Python:**
```bash
pytest
# or
python -m pytest
```

Document:
- Total tests found
- Passed/failed/skipped counts
- Any failures with full error messages

### 3. Run Integration Tests

If integration tests exist:
- Test API endpoints
- Test database operations
- Test service interactions
- Test external integrations (mocked)

### 4. Run E2E Tests

Use Puppeteer for browser-based testing:

**Critical User Flows to Test:**
1. Homepage loads correctly
2. User registration flow
3. User login flow
4. Main feature workflows
5. Error states display properly

**For each flow:**
- Navigate to the page
- Interact with elements
- Take screenshots
- Verify expected outcomes

### 5. Validate Acceptance Criteria

Review `tasks.md` and `requirements.md`:
- For each completed task, verify acceptance criteria
- Document which criteria pass/fail
- Note any untested criteria

### 6. Check Code Coverage

If coverage is configured:
- Run tests with coverage
- Report coverage percentage
- Identify uncovered code paths

### 7. Performance Baseline

Quick performance checks:
- Page load times
- API response times
- Memory usage (if measurable)

## Output Format

Save as `test_report.md`:

```markdown
# Test Report

**Generated:** [timestamp]
**Project:** {{PROJECT_DIR}}

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Tests | X |
| Passed | Y ✓ |
| Failed | Z ✗ |
| Skipped | W |
| Coverage | XX% |

### Overall Status: [PASS/FAIL]

---

## Unit Tests

### Summary
- **Framework:** [jest/pytest/vitest]
- **Tests Run:** X
- **Passed:** Y
- **Failed:** Z

### Failures
[If any failures, list each with:]

#### Failure 1: [test name]
**File:** path/to/test.ts
**Error:**
```
[error message]
```
**Likely Cause:** [analysis]

---

## Integration Tests

### API Endpoints Tested

| Endpoint | Method | Status | Response Time |
|----------|--------|--------|---------------|
| /api/users | GET | ✓ 200 | 45ms |
| /api/users | POST | ✓ 201 | 120ms |

### Database Tests
- [ ] Connection established
- [ ] Queries execute correctly
- [ ] Transactions work

---

## E2E Tests (Puppeteer)

### Test: Homepage Load
**Status:** ✓ PASS
**Screenshot:** [Attached or base64]
**Checks:**
- [x] Page loads within 3s
- [x] Header visible
- [x] Navigation works

### Test: User Registration
**Status:** ✗ FAIL
**Screenshot:** [Attached]
**Error:** Submit button not found
**Steps Taken:**
1. Navigated to /register
2. Filled form fields
3. Attempted to click submit
4. ERROR: Element not found

---

## Acceptance Criteria Validation

### TASK-001: Project Setup
- [x] Project initialized
- [x] Git repository ready
- [x] Dependencies installed

### TASK-015: User Authentication
- [x] Login works
- [ ] **FAIL:** Password reset not implemented
- [x] Session persists

---

## Code Coverage

| Category | Coverage |
|----------|----------|
| Statements | 75% |
| Branches | 68% |
| Functions | 82% |
| Lines | 76% |

### Uncovered Areas
- `src/utils/error-handler.ts` (0%)
- `src/api/webhooks.ts` (15%)

---

## Recommendations

### Critical (Must Fix)
1. [Issue description and fix suggestion]

### High Priority
1. [Issue description]

### Improvements
1. [Suggested improvement]

---

## Appendix: Screenshots

[E2E test screenshots]
```

## Important

- Run ALL tests, not just a sample
- Document exact error messages for failures
- Take screenshots for E2E tests
- If tests don't exist, note this and recommend creating them
- Be thorough - this report determines if we can deploy
