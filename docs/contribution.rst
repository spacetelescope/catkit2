Contributions
=============

Contribution guidelines and process instructions for the ``catkit2`` package. 

Guidelines
---------
* Keep your scope as small as possible. PRs with a smaller scope are faster to
  contribute, and easier to review and test. Try to subdivide a goal into
  several bite-size pieces. 
* Use issues when starting to go out of scope: they help you keep track of
  problems that can be adressed with future PRs. The minimum viable PR is code
  that works, does not crash, and does not crash existing code. 
* Avoid sneaking in changes or scope creep; if you need to change something
  that feels unrelated it is better to open a new PR, even if it is a very
  (very) short one. 
* If your review process is dragging and feels slow, it is likely your PR is too
  large in scope. 
* Be specific when cross-linking issues/PRs in their descriptions. For example,
  if your changes are inspired by previous code reviews, link the comment that
  this resulted from for better context/easier paper trails. 

Process
-------
1. Open an issue on GitHub. Describe the nature of the problem, use tags, and
   assign yourself or others. 
2. Make a new branch off of the current develop. Use branch names like ``bugfix/nature_of_bug`` or
   ``feature/nature_of_feature``. 
3. Open a **Draft** pull request as soon as possible, even if your work seems far
   away from being merged. This allows us to comunicate through comments on the
   PR in a way that is permanent and visible to everyone and allows us to
   inspect code changes with diffs. 
   a) Link your PR to the issue in Step 1, e.g. write ``Fixes #188`` in the PR
   description to link it to Issue 188. 
   b) Write a detailed descript in the PR. This helps define the scope of the
   PR, gives reviewers and idea what to expect, and helps with testing. Update
   as necessary as the PR evolves. 
   c) Assign yourself and others working on the PR, and add labels as
   applicable. The assignee is responsible for finishing the PR. If you cannot
   finish this work, find and assign someone else who can complete it. 
4. Complete all work before marking a PR as "ready to review": rebase, run the
   testing, fix any errors, **update and write documentation**, and write unit
   tests where necessary. 
5. Rebase your branch regularly if your development takes a while. If you need
   help with rebasing please reach out. 
6. Request at least one review and iterate with the reviewer on your PR. If you 
   don't know who to ask for a review, please reach out. 
7. Answer all review comments and implement requested changes. Make it clear
   which comments you are leaving for later PRs, and create a new issue for
   every comment left untouched. Let the reviewer know what changes you made for
   each comment and please reach out if you don't understand a comment. Ask for
   a re-review from the reviewer once you are done. **Do not mark reviewer
   comments on your PR as resolved; this is the duty of the reviewer.** 
8. Once the PR is approved, it can be merged by anyone, but it never hurts to
   double-check it is ready to be merged before you click the button. 
