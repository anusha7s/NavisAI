# Contributing to NavisAI

First off, thank you for considering contributing to NavisAI! It's people like you that make NavisAI a great tool.

## Where do I go from here?

If you've noticed a bug or have a feature request, make sure to check our [Issues](../../issues) section to see if someone else in the community has already created a ticket. If not, go ahead and make one!

## Fork & create a branch

If this is something you think you can fix, then fork NavisAI and create a branch with a descriptive name.

A good branch name would be (where issue #325 is the ticket you're working on):

```sh
git checkout -b 325-add-support-for-new-action
```

## Setup the Development Environment
Please refer to the `README.md` for steps on running the FastAPI server and Chrome Extension locally.

## Try to follow the style guidelines
- Python: Follow PEP 8 guidelines. Black is recommended for formatting. We use FastAPI, SlowAPI and SQLAlchemy.
- JavaScript: Stick to standard JavaScript styles currently in use. Add comments above complex background logic.
- Extension Manifest: Currently configured for Manifest V3. No legacy V2 upgrades please.

## Testing
Always make sure to add corresponding tests in the `backend/` folder whenever you introduce new API endpoints or core logic. Run tests using `pytest` before submitting a Pull Request.

## Open a Pull Request
When you've finished, open a PR with a clear title and description against the `main` branch. 
We'll review it and merge!
