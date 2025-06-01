# Contributing to Open Source: Can You Use Your Fork's Master Branch?

You asked: "If I want to contribute to an open source project can I fork the open source repository, and put my changes in the forked repo master and then with my commits try to upstream to the original GitHub repo?"

Here's a direct answer:

While it is technically *possible* to make changes in the `master` (or `main`) branch of your forked repository and then attempt to create a pull request from it to the original upstream repository, **this is strongly discouraged and is NOT the recommended or standard practice for contributing to open source projects.**

**Why you should avoid committing your changes directly to your fork's `master` branch for upstream contributions:**

1.  **Synchronization Headaches:** Your fork's `master` branch is meant to be a clean reflection of the upstream project's `master` branch. If you add your own commits to it, it diverges. This makes it difficult to pull in new updates from the upstream project without creating messy merge conflicts and a confusing history.
2.  **Difficulty Managing Multiple Contributions:** If you work on several unrelated changes and commit them all to your `master` branch, you cannot create separate, focused pull requests for each change. Your pull request would bundle everything together, making it hard to review and less likely to be accepted.
3.  **Complicated and "Noisy" Pull Requests:** Pull requests created from a `master` branch that contains your custom commits (and potentially merge commits from trying to stay in sync) are often large, include a mix of unrelated changes, and are harder for project maintainers to review and integrate.

**The Recommended Best Practice (The Fork-and-Branch Workflow):**

1.  **Fork** the original repository to your GitHub account.
2.  **Clone** your fork to your local machine.
3.  **Create a new, descriptively named branch** from your fork's `master` branch for your specific changes (e.g., `git checkout -b feature-new-login` or `fix-documentation-typo`). **Do not make your changes on your `master` branch.**
4.  Make your commits on this **new branch**. Keep the changes focused on a single feature or bug fix.
5.  Push this new branch to your fork on GitHub (e.g., `git push origin feature-new-login`).
6.  **Create a Pull Request** from this **new branch** in your fork to the appropriate branch (usually `main` or `master`) in the original upstream repository.

This workflow keeps your contributions organized, your fork's `master` branch clean for easy synchronization with the upstream project, and makes the review process much smoother for everyone involved. Always check the project's `CONTRIBUTING.md` file for any specific guidelines they might have.
