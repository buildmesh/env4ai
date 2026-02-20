### Project Awareness & Context
- **Always read `docs/PLANNING.md`** at the start of a new conversation to understand the project's architecture, goals, style, and constraints.
- **Use consistent naming conventions, file structure, and architecture patterns** as described in `PLANNING.md`.

### Code Structure & Modularity
- **Never create a file longer than 500 lines of code.** If a file approaches this limit, refactor by splitting it into modules or helper files.
- **Organize code into clearly separated modules**, grouped by feature or responsibility.
- **Use clear, consistent imports** (prefer relative imports within packages).
- **Observe DRY (Don’t Repeat Yourself).** Before adding a new function/class, search the codebase for existing implementations that already solve the problem.
  - Prefer **reusing, extracting, or generalizing** existing code over creating near-duplicates.
  - Only allow intentional duplication when there is a **clear best-practice reason** (e.g., reducing coupling, avoiding leaky abstractions, preserving performance-critical hot paths, or keeping public APIs stable).
  - If duplication is chosen intentionally, add a brief comment explaining **why duplication is preferable** in that case.

### Testing & Reliability
- **Always create unit tests for new features** (functions, classes, routes, etc).
- **After updating any logic**, check whether existing unit tests need to be updated. If so, do it.
- When installing libraries for testing purposes, don't specify a version, and just allow the tool to install the latest.
- **Tests should live in a `/tests` folder** mirroring the main app structure.
  - Always *mock* calls to services like the DB and LLM so you aren’t interacting with anything “for real”.
  - Include at least:
    - 1 test for expected use
    - 1 edge case
    - 1 failure case

### Task Completion & Git Workflow
- When instructed to complete **a list of tasks**, follow a **strict sequential workflow**:
  1. Select **one task only**.
  2. Implement the task fully.
  3. Create **good, comprehensive tests** covering the task.
  4. Ensure **all tests (new and existing) pass**.
  5. Create a **git commit with a clear, meaningful commit message** describing the change.
  6. Only then proceed to the **next task**.

- **Never batch multiple tasks into a single commit** unless explicitly instructed.

- When a task **requires refactoring** for correctness, clarity, or maintainability:
  1. Perform the **refactor first**, without adding new features.
  2. Ensure **existing tests still pass** (update tests only if strictly necessary for the refactor).
  3. Create a **dedicated git commit** describing the refactor.
  4. Proceed with the original task using the refactored codebase.

### Style & Conventions
- **Use Python** as the primary language.
- **Follow Python style**, use type hints, and format with an industry-standard linter.
- **Use industry-standard libraries for data validation**.
- Write **docstrings for every function** using the industry-standard style.

### Documentation & Explainability
- **Update `README.md`** when new features are added, dependencies change, or setup steps are modified.
- **Comment non-obvious code** and ensure everything is understandable to a mid-level developer.
- When writing complex logic, **add an inline `// Reason:` comment** explaining the *why*, not just the *what*.

### File Editing Policy

When modifying files:

1. DO NOT use:
   - `cat <<EOF > file`
   - `cat > file`
   - python for file editing
   - whole-file rewrites unless explicitly requested

2. ALWAYS prefer:
   - `git apply` style patches
   - explicit line-by-line diffs

3. Every change MUST be reviewable as a diff:
   - show added lines with `+`
   - show removed lines with `-`
   - preserve unchanged context

4. If a file is new:
   - show the full contents inline
   - explain why the file is new

### AI Behavior Rules
- **Never assume missing context. Ask questions if uncertain.**
- **Never hallucinate libraries or functions** — only use known, verified Python packages.
- **Always confirm file paths and module names** exist before referencing them in code or tests.
- **Never delete or overwrite existing code** unless explicitly instructed to or if part of a task from `TASKS.md`.
- **Create features in a way that is intuitive for the user** unless specifically instructed otherwise
- **Create features that are aesthetically pleasing** unless specifically instructed otherwise
- **Follow UX best practices** unless specifically instructed otherwise

