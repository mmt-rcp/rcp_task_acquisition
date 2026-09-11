from __future__ import annotations  # noqa

import os

try:
    import git
except ModuleNotFoundError:
    git = None


DEFAULT_REMOTE_BRANCH = os.getenv("RCP_CHECK_REMOTE_BRANCH", "main")


def check_repo_up_to_date(
    repo_path,
    *,
    remote_name="origin",
    remote_branch=DEFAULT_REMOTE_BRANCH,
    m_git_not_found="git module not found (GitPython). Cannot check repo status",
    m_remote_branch_miss=r"The branch '{remote_branch}' does not exist on the remote tracking server.",
    m_detached="Repository is in a detached HEAD state. Cannot verify tracking branch.",
    m_diff_branch=r"Your local branch ({branch_name}) is not same than {remote_branch}.",
    m_up2date_but_dirty="The repository is up2date with remote but has local changes!",
    m_ahead="⚠️ Local is AHEAD of remote (You have unpushed commits).",
    m_behind="⚠️ Local is BEHIND remote (You need to pull changes).",
    m_diverged="🚨 Diverged! Both local and remote have unique, conflicting commits.",
) -> str | None:
    locs = dict(locals())
    del locs["repo_path"]  # keep as arg
    try:
        msg = _check_repo_up_to_date(repo_path, **locs)
    except Exception as err:  # noqa
        return f"Failed verify repo status: {err}"
    return msg


def _check_repo_up_to_date(
    repo_path,
    remote_name,
    remote_branch,
    m_git_not_found,
    m_remote_branch_miss,
    m_detached,
    m_diff_branch,
    m_up2date_but_dirty,
    m_ahead,
    m_behind,
    m_diverged,
) -> str | None:

    locs = locals()

    def ret_val(v):
        return v if not isinstance(v, str) else v.format(**locs)

    if git is None:
        return ret_val(m_git_not_found)

    # Initialize the repository object
    repo = git.Repo(repo_path)

    # 1. Ensure the repo isn't in a broken state and get the active branch name
    if repo.head.is_detached:
        return ret_val(m_detached)

    branch_name = repo.active_branch.name
    if branch_name != remote_branch:
        return ret_val(m_diff_branch)

    # 2. Fetch the latest references from the remote server
    # print("Fetching from remote...")
    origin = repo.remote(name=remote_name)
    origin.fetch()

    # 3. Get the latest commit hashes for local and remote
    local_commit = repo.head.commit
    try:
        remote_commit = origin.refs[remote_branch].commit
    except IndexError:
        return ret_val(m_remote_branch_miss)

    # 4. Compare the commits to determine the status
    if remote_commit == local_commit:
        if repo.is_dirty(untracked_files=True):
            return ret_val(m_up2date_but_dirty)
        else:
            # print("No changes found. Clean workspace.")
            return None

    # Determine the exact relationship
    # Is local ahead? (remote commit is an ancestor of local)
    is_ahead = repo.is_ancestor(remote_commit, local_commit)
    # Is local behind? (local commit is an ancestor of remote)
    is_behind = repo.is_ancestor(local_commit, remote_commit)

    if is_ahead and not is_behind:
        return ret_val(m_ahead)
    elif is_behind and not is_ahead:
        return ret_val(m_behind)
    else:
        return ret_val(m_diverged)
