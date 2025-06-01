# Upstreaming Changes with Pull Requests

After developing a feature or fixing a bug in a dedicated branch within your fork, the next step is to propose these changes to be merged into the original (upstream) project. This is almost universally done using a mechanism called a **Pull Request** (PR) or, in some platforms like GitLab, a **Merge Request** (MR).

## Pull Requests: The Standard for Proposing Changes

Pull Requests are the cornerstone of collaborative development in the fork-and-branch workflow. They serve as a formal proposal to integrate the changes you've made in your fork into the codebase of the upstream repository.

**Key characteristics of proposing changes via Pull Requests:**

1.  **From Your Fork's Branch to Upstream's Branch:**
    *   A pull request is typically initiated from a specific **feature branch** (e.g., `my-cool-feature`, `fix-login-bug`) in your forked repository. It's crucial that these changes are isolated in their own branch and not on your fork's `master` or `main` branch.
    *   The target of the pull request is a designated branch in the **upstream repository**. This is often the `main` or `master` branch, but larger projects might use other integration branches like `develop`, `staging`, or specific release branches. The project's contribution guidelines will usually specify the correct target branch.

2.  **A Request, Not a Command:**
    *   As the name suggests, a "pull request" is a *request* for the upstream project maintainers to "pull" your changes into their repository. You don't directly merge your code into the upstream project; you ask the maintainers to do so.
    *   This provides a crucial control point for the project maintainers to ensure the quality, consistency, and appropriateness of new contributions.

3.  **Clear Documentation of Changes:**
    *   When creating a pull request, you typically provide a title and a description. This is an opportunity to clearly explain:
        *   What problem your changes solve or what feature they add.
        *   How you've implemented the solution.
        *   Any relevant context, such as links to issue trackers.
    *   The pull request also inherently shows the `diff` (the exact lines of code added, removed, or modified), allowing for precise review.

## The Review Process

Once a pull request is submitted, it typically undergoes a review process before being merged (or rejected):

1.  **Automated Checks:** Many projects integrate automated checks that run on every new pull request. These can include:
    *   **Linters and Code Style Checks:** Ensuring the code adheres to the project's formatting standards.
    *   **Unit Tests and Integration Tests:** Verifying that the changes work as expected and don't break existing functionality.
    *   **Build Processes:** Confirming that the project still builds correctly with the new changes.
    If any of these checks fail, the PR will usually be marked, and the contributor is expected to fix the issues.

2.  **Human Review:**
    *   Project maintainers and other contributors will review the code changes. They look for:
        *   Correctness and effectiveness of the solution.
        *   Potential bugs or edge cases.
        *   Adherence to project architecture and best practices.
        *   Clarity and maintainability of the code.
        *   Security implications.
    *   Reviewers can ask questions, request modifications, or suggest improvements directly on the pull request platform (e.g., GitHub, GitLab).

3.  **Discussion and Iteration:**
    *   The pull request becomes a space for discussion between the contributor and the reviewers.
    *   The contributor may need to make further commits to their feature branch to address feedback, pushing those new commits to their fork. The pull request automatically updates to reflect these new changes. This iterative process continues until the reviewers are satisfied.

4.  **Merging or Closing:**
    *   If the pull request is approved and passes all checks, a project maintainer with the necessary permissions will merge the changes from the feature branch into the target upstream branch.
    *   If the changes are not suitable, or if the contributor doesn't address feedback, the pull request might be closed without merging.

The pull request process, including the review stage, is fundamental to maintaining the health and quality of a collaborative software project. It ensures that multiple eyes vet changes and that contributions align with the project's goals and standards.
