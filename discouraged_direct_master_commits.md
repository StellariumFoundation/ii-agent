# Why Committing Directly to a Fork's Master Branch is Discouraged for Upstream Contributions

When contributing to an upstream project using the fork-and-branch workflow, it's a strongly recommended best practice to **avoid committing your changes directly to the `master` (or `main`) branch of your fork**. Instead, you should always create separate feature branches for your work.

Committing directly to your fork's `master` branch can lead to several significant problems, making it harder to manage your contributions and collaborate effectively:

1.  **Difficulty Synchronizing with Upstream `master`:**
    *   The primary purpose of your fork's `master` branch should be to mirror the state of the upstream repository's `master` branch. This allows you to easily pull in the latest changes from the original project to keep your fork up-to-date.
    *   If you commit your own changes directly to your fork's `master`, this branch will diverge from the upstream `master`. When you then try to pull upstream changes, you'll often face merge conflicts that can be complicated to resolve. Your `master` branch becomes a mix of upstream code and your personal changes, making it messy and hard to track the true "original" state.
    *   A clean `master` branch in your fork acts as a stable base from which you can create new feature branches, knowing they are starting from the latest upstream code.

2.  **Complications Managing Multiple, Unrelated Changes:**
    *   If you're working on several different features or bug fixes, committing them all to the `master` branch intertwines them.
    *   Imagine you're working on `feature-A` and `bugfix-B`. If both sets of commits are on `master`, you cannot selectively create a pull request for just `feature-A`. The pull request will inevitably include commits for `bugfix-B` as well, even if it's not ready or relevant to `feature-A`.
    *   Feature branches allow you to isolate each set of changes. You can have a branch for `feature-A`, another for `bugfix-B`, and switch between them as needed. Each piece of work remains independent until it's ready to be proposed for merging.

3.  **Large and Hard-to-Review Pull Requests:**
    *   When you create a pull request (PR) to the upstream repository, it's typically based on comparing a branch from your fork with the upstream's target branch (usually `master`).
    *   If your fork's `master` branch contains many of your own commits (potentially mixed with merge commits from trying to sync with upstream), a PR created from this `master` branch will include all those divergent changes.
    *   This makes the PR very large, difficult for project maintainers to review, and increases the chances of introducing unintended changes or bugs. Reviewers prefer focused PRs that address a single concern (one feature, one bug fix).
    *   If your `master` has diverged significantly, you might even be forced to submit a PR that includes changes you didn't intend to, or you might struggle to rebase your work cleanly.

**The Recommended Approach:**

1.  Keep your fork's `master` branch clean and synchronized with the upstream `master` branch. Use it as a reference, not a development branch.
2.  For any new piece of work (feature, bug fix, experiment), create a new, descriptively named branch from your up-to-date `master` branch (e.g., `git checkout -b feature-user-profile` from `master`).
3.  Make all your commits for that specific piece of work on this feature branch.
4.  When ready, push this feature branch to your remote fork (e.g., `git push origin feature-user-profile`).
5.  Create a pull request from this feature branch to the upstream repository's `master` branch. This PR will contain only the relevant, focused commits for that specific feature.

By following this discipline, you ensure a smoother contribution process, easier synchronization with the upstream project, and more manageable, reviewable pull requests. This benefits both you as a contributor and the maintainers of the upstream project.
