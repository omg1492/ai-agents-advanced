---
applyTo: '**'
---
- Use docstrings as main way to document functionality. Make sure to revise it every time you change its code. 
- Comments only for things that are not obvious and worth extra documentation. Avoid adding comments about progress of work, about steps done or special comments for various code scanners..
- Prefer `simplicity` and readability
- If you encounter any potential to simplify and refactor code during working on something else, this is encouraged, but report this to user and offer user what and why you suggest to change beyond user original request.
- As you implement code, update `docs/ImplementationLog.md` with your progress and technical and architecture decisions
- Document common errors and pitfalls you encountered and had to fix in `docs/CommonErrors.md`, but only after I have confirmed issues are resolved and you have a solution. Make sure to read this file if you encounter any issues in code.
- When facing any issues, refer to `docs/CommonErrors.md` to see if you can find a solution. Search internet to gather more insights. 
- Continuously build short instructions how to run and test the project in `README.md` of particular service or component
- Avoid big files, split code if it makes sense
- When troubleshooting complex issue you can try to run simplified scripts to investigate issue and learn from it, but follow this rules:
    1. First try to do this in command line. Remember you execute typically in PowerShell so make sure to use proper string manipulations and escaping for this shell.
    2. Before you run something make sure you are in correct folder
    3. Often we use .env to set environmental variables and you should leverage this in your scripts by loading it
    4. When script fails multiple times and it is too complex, only that it is OK to create separate testing file and execute it. Make sure to clean it up afterwards. Each file must start with adhoc_test prefix so it is easy to identify it later for cleanup.
    5. When writing tests scripts think whether this might be useful to be added into unit or integration tests. If you think so, ask user for confirmation to do this.
- Do not proactively write any helper scripts outside of application code (eg. deployment or configuration script), only if asked to do so. If you think some helper script is needed, ask first.
- If in doubts or before doing major decision that changes the architecture or design, ask me first.
- Main language for this project is `Python`. Use `uv` to manage Python virtual environments and packages. Always work with `pyproject.toml` (not requirements.txt) and run apps with `uv run` command.
- Frontend framework for this project is `React` and UI is based on `assistant-ui` library.