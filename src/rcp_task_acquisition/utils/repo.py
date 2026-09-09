from __future__ import annotations  # noqa

try:
    import git
except ModuleNotFoundError:
    git = None


def check_repo_up_to_date(repo_path, remote_name="origin", remote_branch="main") -> str | None:
    try:
        return _check_repo_up_to_date(repo_path, remote_name, remote_branch)
    except Exception as err:  # noqa
        return f"Failed verify repo status: {err}"


def _check_repo_up_to_date(repo_path, remote_name="origin", remote_branch="main") -> str | None:
    if git is None:
        return "git module not found (GitPython). Cannot check repo status"

    # Initialize the repository object
    repo = git.Repo(repo_path)

    # 1. Ensure the repo isn't in a broken state and get the active branch name
    if repo.head.is_detached:
        return "Repository is in a detached HEAD state. Cannot verify tracking branch."

    branch_name = repo.active_branch.name
    if branch_name != remote_branch:
        return f"Your local branch ({branch_name}) is not same than {remote_branch}."

    # 2. Fetch the latest references from the remote server
    # print("Fetching from remote...")
    origin = repo.remote(name=remote_name)
    origin.fetch()

    # 3. Get the latest commit hashes for local and remote
    local_commit = repo.head.commit
    try:
        remote_commit = origin.refs[remote_branch].commit
    except IndexError:
        return f"The branch '{remote_branch}' does not exist on the remote tracking server."

    # 4. Compare the commits to determine the status
    if remote_commit == local_commit:
        if repo.is_dirty(untracked_files=True):
            return "The repository is up2date with remote but has local changes!"
        else:
            # print("No changes found. Clean workspace.")
            return None

    # Determine the exact relationship
    # Is local ahead? (remote commit is an ancestor of local)
    is_ahead = repo.is_ancestor(remote_commit, local_commit)
    # Is local behind? (local commit is an ancestor of remote)
    is_behind = repo.is_ancestor(local_commit, remote_commit)

    if is_ahead and not is_behind:
        return "⚠️ Local is AHEAD of remote (You have unpushed commits)."
    elif is_behind and not is_ahead:
        return "⚠️ Local is BEHIND remote (You need to pull changes)."
    else:
        return "🚨 Diverged! Both local and remote have unique, conflicting commits."
