# Use Cases

Reference list of Project Relay's use cases. Each user story links to the use case it delivers using the ID below.

Actions **User** (any-signed in user) is generalised by **Administrator**, **Project Manager** and **Technician**. Anything linked to the User is available to all three roles. 

## Shared and Administration

| ID | Use Case | Actor | Relationship | Issues |
|---|---|---|---|---|
| UC01 | Sign In | User | - | [#5](https://github.com/daniela-tio/project-relay/issues/5) Sign in, [#6](https://github.com/daniela-tio/project-relay/issues/6) Account Lockout |
| UC02 | View Dashboard | User | - | [#32](https://github.com/daniela-tio/project-relay/issues/32) PM and Admin Dashboard, [#33](https://github.com/daniela-tio/project-relay/issues/33) Technician Dashboard |
| UC03 | Search Projects | User | - | [#34](https://github.com/daniela-tio/project-relay/issues/34) Search Projects |
| UC04 | View Portfolio | User | - | [#17](https://github.com/daniela-tio/project-relay/issues/17) View portfolio, [#21](https://github.com/daniela-tio/project-relay/issues/21) View project |
| UC05 | View My Projects | User | - | [#28](https://github.com/daniela-tio/project-relay/issues/28) My projects |
| UC06 | Manage Users | Administrator | Extended by UC07 | [#10](https://github.com/daniela-tio/project-relay/issues/10) Manage users |
| UC07 | Unlock Account | Administrator | «extend» UC06 | [#10](https://github.com/daniela-tio/project-relay/issues/10) Manage users, [#6](https://github.com/daniela-tio/project-relay/issues/6) Account lockout |
| UC08 | Manage Trusts, Schools | Administrator | Extended by UC09 | [#15](https://github.com/daniela-tio/project-relay/issues/15) Manage trusts and schools |
| UC09 | Merge School Records | Administrator | «extend» UC08 | [#16](https://github.com/daniela-tio/project-relay/issues/16) Merge school records |
| UC10 | Import GIAS Data | Administrator | «include» UC11 | [#14](https://github.com/daniela-tio/project-relay/issues/14) Import GIAS data |
| UC11 | Validate CSV | Administrator | Included by UC10 | [#14](https://github.com/daniela-tio/project-relay/issues/14) Import GIAS data |
| UC12 | View System Log | Administrator | - | [#13](https://github.com/daniela-tio/project-relay/issues/13) View system log |


## Project Management

| ID | Use case | Actor | Relationship | Issues |
|---|---|---|---|---|
| UC13 | Manage templates | Project Manager | – | [#30](https://github.com/daniela-tio/project-relay/issues/30) Manage templates |
| UC14 | Create project | Project Manager | Extended by UC15 | [#18](https://github.com/daniela-tio/project-relay/issues/18) Create project, #20 Assign project team |
| UC15 | Create from template | Project Manager | «extend» UC14 | [#31](https://github.com/daniela-tio/project-relay/issues/31) Create project from template |
| UC16 | Plan milestones, tasks | Project Manager | – | [#19](https://github.com/daniela-tio/project-relay/issues/19) Plan milestones and tasks, [#23](https://github.com/daniela-tio/project-relay/issues/23) Bank holiday date warning, [#24](https://github.com/daniela-tio/project-relay/issues/24) Dates needed flag |
| UC17 | View my tasks | Project Manager, Technician | – | [#27](https://github.com/daniela-tio/project-relay/issues/27) View my tasks |
| UC18 | Update task | Project Manager, Technician | – | [#26](https://github.com/daniela-tio/project-relay/issues/26) Update task, [#29](https://github.com/daniela-tio/project-relay/issues/29) Task drawer |
| UC19 | Move Kanban card | Project Manager, Technician | – | [#25](https://github.com/daniela-tio/project-relay/issues/25) Kanban board |
| UC20 | Build report | Project Manager | «include» UC21 | [#35](https://github.com/daniela-tio/project-relay/issues/35) Build report, [#36](https://github.com/daniela-tio/project-relay/issues/36) Saved reports |
| UC21 | Export file | Project Manager | Included by UC20 | [#35](https://github.com/daniela-tio/project-relay/issues/35) Build report |
| UC22 | Close project | Project Manager | «include» UC23 | [#37](https://github.com/daniela-tio/project-relay/issues/37) Close project |
| UC23 | Record sign-off | Project Manager | Included by UC22 | [#37](https://github.com/daniela-tio/project-relay/issues/37) Close project |


