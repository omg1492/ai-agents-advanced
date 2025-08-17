Scripts

This folder contains developer utility scripts. More will be added over time.

First script: cherry_pick.py

Automates cherry-picking the latest commit from main/master into all lesson branches:
- Lxx-teacher, Lxx-student-starter, Lxx-student-end

What it does (briefly)
- Shows the latest main commit and changed files, asks to continue
- Finds lesson branches (local + remote) by pattern
- Cherry-picks into each branch, aborts on conflict, prints a summary
- Does not push changes

Usage
- Prerequisites: git installed and a clean working tree
- From the repo root (recommended):

```powershell
uv run python .\scripts\cherry_pick.py
```
