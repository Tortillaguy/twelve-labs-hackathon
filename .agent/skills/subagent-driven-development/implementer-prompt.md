# Implementer Prompt Template

Use this template when dispatching a subagent to implement a specific subtask.

**Purpose:** Get code written according to a specific plan or requirement.

```yaml
Task tool (general-purpose):
  description: "Implement [Description of Subtask]"
  prompt: |
    You are an expert software engineer. Your task is to implement the following:

    ## The Goal

    [Insert clear, concise goal here]

    ## Detailed Requirements

    [Insert specific requirements here]

    ## Context/Constraints

    - Files involved: [List files]
    - Project standards: [Briefly describe or link]
    - Performance/Safety constraints: [If any]

    ## Expected Outcome

    Your primary deliverable is the implemented code. Please provide a brief report 
    of what you did, which files were modified, and any instructions needed for verification.
```
