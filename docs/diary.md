# Development Diary

One entry per working session. Keep it short: what happened, what worked, what didn't, what changed. 

## Template
(Only use what is required for entry)

## DATE · TITLE · NAME
**Done:** TEXT
**Decided:** TEXT
**Worked / didn't:** TEXT
**Reflection:** TEXT

## 9 Oct 2026 · Idea brainstorming (Written up on 17 Oct) · Dan A
**Done:** Read the assignment brief. Explored app ideas linked to project role within MSP.
**Decided:** A tool to allow the projects team to track on-going work.
**Reflection:** Other proposed ideas already had tools in place. Conversations regarding the idea of the product had already been initiated by myself with designs for features already in progress. 

## 16-17 Oct 2026 · Repo and board setup (Written up on 17 Oct) · Dan A
**Done:** Created GitHub repo, issue templates, labels, Kanban board (5 columns, WIP limits), custom fields, milestones v0.1.0-v1.0.0, automations and saved views.
**Decided:** Conventional Commits with semantic versioning instead of release labels.
**Reflection:** Discussions with internal development team on best practices was extremely helpful. Walkthrough of existing internal GitHub repo structure provided basis for the setup of labels, automation and commit style.   

## 17-18 Oct 2026 · Process Docs and v0.1.0 backlog · Dan A
**Done:** Added working agreement (board policies, Definitions of Ready and Done), PR template and Chore issue template. Created v0.1.0 foundations backlog, 3 chores and 7 stories with acceptance criteria. 
**Decided:** Acceptance criteria for the initial backlog items. UMLs, use case and diagrams are TBC. Demo data will be created and used until app is ready to go into production
**Reflection:** Continuing discussions with internal development team to create working agreements and complete the setup of the repo, including initial backlog items proved very helpful. 

## 19-20 Oct 2026 · Scope review · Dan A
**Done:** Completed review of all features and split them into what's achievable in the current timescale and what can be deferred to later updates.  
**Decided:** SSO, Halo ITSM integration, customer portal and team utilisation all deferred. Reports will be available via a filter based report builder. Sign-off recorded by PM and e-sign off deferred. 
**Reflection:** Moving more complex features to future updates makes the initial release a lot more achievable. MoSCoW helped to decide the priority of each feature. 

## 22-23 Oct 2026 · Initial backlog setup · Dan A
**Done:** Created issues for initial set of chores and user stories to populate the backlog. Created use case document and linked each issue to its related use case. 
**Decided:** Architecture will be modular monolith, split into Django apps. Account lockout will be 15 minutes per username and IP.
**Reflection:** After investigating splitting the services up and identifying the costs involved meant a modular monolith made sense for the current scale of the app but will allow for separation at a later date.
