# IVR Tree Discovery — Onsite Project

> From: Spencer Small via Underdog.io
> Date: Wed, Mar 11, 2026 at 11:09 AM

Build a system that calls into IVR (Interactive Voice Response) phone trees using the Bland AI API, discovers their menu structure, and visualizes the tree in realtime as discovery progresses.

---

## Setup

- Sign up at [app.bland.ai](https://app.bland.ai) and grab an API key from **Dashboard → Settings**. API docs: [docs.bland.ai](https://docs.bland.ai)
- You may use any AI provider (Anthropic, OpenAI, etc.) for transcript analysis.
- You own the system design — choose any language, framework, or data store.
- AI coding tools are fine, but be ready to explain your code.

---

## Requirements

### Discovery

- Given a target phone number, explore its IVR menu structure and produce a tree of prompts and options.
- Define a data model for the tree: nodes, edges, call metadata.
- Handle edge cases: timeouts, silence, dead ends, repeated menus.
- The system should explore efficiently — both in terms of API usage and wall-clock time.

### Frontend

- A UI that accepts a phone number and kicks off discovery.
- The tree should render and update in realtime as new branches are discovered — don't wait for the full run to complete.
- Clicking a node should show its details (prompt text, options found, call transcript, cost).
- Show a lightweight progress/status indicator for the overall run.

### Nice to Have

- Select a node in the tree and trigger re-discovery of that subtree from the UI.
- Visual distinction between completed, in-progress, and failed nodes.
- Running cost total for the discovery session.

---

## Testing

- Tests that validate core logic without making real API calls.
- At minimum cover: transcript parsing, tree construction, failure handling.

---

## Deliverables

1. Working system (backend + frontend) that can discover at least 2 levels of an IVR tree with realtime visualization.
2. Brief design notes covering your data model, discovery approach, and how you handle realtime updates.
3. A sample discovered tree from a public IVR ([tollfreenumber.org](https://tollfreenumber.org) has numbers to test).

---

## Evaluation Criteria

- System design and separation of concerns
- Realtime update approach (backend → frontend)
- UI clarity and usability
- Resilience and failure handling
- Test coverage
- API efficiency
- Code clarity

---

## Time Guide (~4 hours)


| Block                          | Time        |
| ------------------------------ | ----------- |
| Whiteboard + questions         | 0:00 – 0:15 |
| API plumbing + basic call flow | 0:15 – 0:45 |
| Discovery engine + data model  | 0:45 – 1:45 |
| Frontend + realtime updates    | 1:45 – 3:00 |
| Polish, tests, demo prep       | 3:00 – 4:00 |


