## Working agreement

How work moves through the Project Relay board. Kanban practice: make policies explicit.

## Board columns
| Column | Meaning | WIP limit |
|---|---|---|
| Backlog | Ideas and stories not yet ready | - |
| Ready | Meets the Definition of Ready; next to pull | - |
| In Progress | Being built | 2 |
| Testing | Tests and acceptance criteria being checked | 2 |
| Done | Meets the Definition of Done | - |

Blocked work keeps it own column and gets the `blocked` label, with a comment saying why.

## Pull policy
- Only pull new work when In Progress is under its limit.
- Pull from Ready in priority order: Must -> Should -> Could, then by milestone.
- Finish (move to Done) before starting something new where possible.

## Definition of Ready
- [ ] Written as a user story (As a... I want... so that...)
- [ ] Acceptance criteria listed
- [ ] MoSCoW, Epic, Size, Work Type and Milestone set

## Definition of Done
- [ ] Acceptance criteria met
- [ ] Tests written and passing in CI
- [ ] No lint errors
- [ ] Merged through a pull request that closes the issue
- [ ] Deployed to the live environment
- [ ] Diary updated if anything notable happened 

## Commit messages
Conventional Commits: `type(scope): summary`
Types: feat, fix, docs, test, refactor, chore, ci, build
Reference the issue in the footer: `Closes #12`

## Versioning
Semantic versioning. 0.x during development; v1.0.0 once app is released
Versions are tracked as GitHub Milestones
