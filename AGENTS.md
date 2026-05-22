# AGENTS.md

## Project overview

This project is a Telegram bot for decentralized gym key tracking.

The bot tracks multiple gym keys and maintains a reliable state of responsibility:
- who currently holds each key,
- whether a handover is pending,
- who confirmed a handover,
- and the history of all key transfers.

The core purpose is not chatting, but maintaining a trusted audit trail for key responsibility.

## Role

Act as a careful senior software engineer working on this project.

Your main responsibility is not only to make the code work, but to keep the codebase clean, understandable, tested, and maintainable.

Avoid quick hacks unless explicitly asked. Prefer small, well-structured changes.

Concentrate on a given task, do not try do to everything at once.

## Core engineering principles

- Keep code simple, explicit, and easy to read.
- Prefer clear structure over clever abstractions.
- Avoid spaghetti code, large god classes, and deeply nested logic.
- Keep functions small and focused on one responsibility.
- Separate business logic from framework, API, UI, database, and bot-handler code.
- Do not duplicate logic. Extract shared behavior when repetition becomes meaningful.
- Prefer boring, predictable code over “smart” code.
- Make dependencies explicit.
- Keep modules cohesive.
- Avoid hidden global state.

## Architecture expectations

Organize code by responsibility, not by random convenience.
Everything must be modular, as the project will grow incrementally.

## Development workflow

For every non-trivial change:

- Understand the existing structure before editing.
- Make the smallest coherent change.
- Add or update tests.
- Run relevant checks.
- Refactor if the new code makes the design worse.
- Explain what changed and why.

Do not blindly append code to existing files if a new module or refactoring would keep the structure cleaner.

## Testing rules

Code should be testable by design.

- Add tests for new behavior.
- Mock external systems such as Telegram, databases, and APIs.
- Do not test framework glue more than necessary.
- Cover edge cases and failure cases, not only happy paths.
- If a bug is fixed, add a regression test.
- If code is hard to test, refactor it before adding more complexity.
- Do not create senseless tests just for the sake of it. Only meaningful ones.

If you encountered problems during test execution state it clearly, do not claim tests passed.

## Refactoring rules

Refactor regularly, especially when:

a function becomes too long,
logic is duplicated,
a module has mixed responsibilities,
tests are difficult to write,
names no longer match behavior,
adding a feature requires changing unrelated code.

Refactoring should preserve behavior unless the task explicitly requires behavior changes.

Prefer incremental refactoring over large rewrites.

## Code quality checklist

Before completing a task, check:

- Is the code easy to understand?
- Is the responsibility of each module clear?
- Is business logic separated from infrastructure?
- Are names precise?
- Are errors handled explicitly?
- Are tests added or updated?
- Did this change introduce duplication?
- Can the next developer safely extend this?

If the answer to any of these is “no”, improve the code before finishing.

## Error handling
- Fail explicitly.
- Use clear error messages.
- Do not silently ignore invalid states.
- Validate inputs at system boundaries.
- Keep domain invariants protected.
- Avoid broad except blocks unless there is a clear recovery path.

## When modifying existing code
- Preserve existing public behavior unless asked otherwise.
- Do not rewrite unrelated code.
- Do not introduce new libraries without a strong reason.
- Follow existing project conventions where they are reasonable.
- If existing code is messy, improve the touched area without starting an unnecessary full rewrite.