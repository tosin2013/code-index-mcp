"""
Unit tests for GitRepositoryManager.

Tests:
- URL parsing for GitHub, GitLab, Bitbucket, Gitea
- Authentication token injection
- Clone operations
- Pull operations
- Error handling
- GCS integration (mocked)

Run with:
    pytest tests/ingestion/test_git_manager.py -v
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest

from src.code_index_mcp.ingestion.git_manager import (
    GitManagerError,
    GitRepositoryInfo,
    GitRepositoryManager,
)


@pytest.fixture
def mock_gcs_client():
    """Mock Google Cloud Storage client."""
    with patch("src.code_index_mcp.ingestion.git_manager.storage") as mock_storage:
        # Mock Client
        mock_client = MagicMock()
        mock_storage.Client.return_value = mock_client

        # Mock bucket
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        # Mock blob
        mock_blob = MagicMock()
        mock_blob.exists.return_value = False
        mock_bucket.blob.return_value = mock_blob

        yield mock_client, mock_bucket, mock_blob


@pytest.fixture
def git_manager(mock_gcs_client):
    """Create GitRepositoryManager instance with mocked GCS."""
    mock_client, mock_bucket, _ = mock_gcs_client

    # Create temporary directory for local cache
    temp_dir = Path(tempfile.mkdtemp())

    manager = GitRepositoryManager(
        gcs_bucket="test-bucket", user_id="test-user", local_cache_dir=temp_dir
    )

    yield manager

    # Cleanup
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


class TestURLParsing:
    """Test Git URL parsing for various platforms."""

    def test_parse_github_https(self, git_manager):
        """Test parsing GitHub HTTPS URL."""
        repo_info = git_manager.parse_git_url("https://github.com/user/repo")

        assert repo_info.platform == "github"
        assert repo_info.host == "github.com"
        assert repo_info.owner == "user"
        assert repo_info.repo == "repo"
        assert repo_info.git_url == "https://github.com/user/repo.git"
        assert repo_info.clone_path == "github.com/user/repo.git"
        assert repo_info.worktree_path == "github.com/user/repo"

    def test_parse_github_https_with_git_extension(self, git_manager):
        """Test parsing GitHub HTTPS URL with .git extension."""
        repo_info = git_manager.parse_git_url("https://github.com/user/repo.git")

        assert repo_info.platform == "github"
        assert repo_info.owner == "user"
        assert repo_info.repo == "repo"

    def test_parse_github_ssh(self, git_manager):
        """Test parsing GitHub SSH URL."""
        repo_info = git_manager.parse_git_url("git@github.com:user/repo.git")

        assert repo_info.platform == "github"
        assert repo_info.host == "github.com"
        assert repo_info.owner == "user"
        assert repo_info.repo == "repo"

    def test_parse_gitlab_https(self, git_manager):
        """Test parsing GitLab HTTPS URL."""
        repo_info = git_manager.parse_git_url("https://gitlab.com/org/project")

        assert repo_info.platform == "gitlab"
        assert repo_info.host == "gitlab.com"
        assert repo_info.owner == "org"
        assert repo_info.repo == "project"
        assert repo_info.git_url == "https://gitlab.com/org/project.git"

    def test_parse_bitbucket_https(self, git_manager):
        """Test parsing Bitbucket HTTPS URL."""
        repo_info = git_manager.parse_git_url("https://bitbucket.org/team/service")

        assert repo_info.platform == "bitbucket"
        assert repo_info.host == "bitbucket.org"
        assert repo_info.owner == "team"
        assert repo_info.repo == "service"
        assert repo_info.git_url == "https://bitbucket.org/team/service.git"

    def test_parse_gitea_custom_domain(self, git_manager):
        """Test parsing Gitea URL with custom domain."""
        repo_info = git_manager.parse_git_url("https://gitea.example.com/user/repo")

        assert repo_info.platform == "gitea"
        assert repo_info.host == "gitea.example.com"
        assert repo_info.owner == "user"
        assert repo_info.repo == "repo"
        assert repo_info.git_url == "https://gitea.example.com/user/repo.git"
        assert repo_info.clone_path == "gitea.example.com/user/repo.git"

    def test_parse_gitea_with_git_extension(self, git_manager):
        """Test parsing Gitea URL with .git extension."""
        repo_info = git_manager.parse_git_url("https://git.company.com/dev/app.git")

        assert repo_info.platform == "gitea"
        assert repo_info.host == "git.company.com"
        assert repo_info.owner == "dev"
        assert repo_info.repo == "app"

    def test_parse_invalid_url(self, git_manager):
        """Test parsing invalid Git URL."""
        with pytest.raises(GitManagerError, match="Unable to parse Git URL"):
            git_manager.parse_git_url("not-a-valid-url")

    def test_parse_url_with_trailing_slash(self, git_manager):
        """Test parsing URL with trailing slash."""
        repo_info = git_manager.parse_git_url("https://github.com/user/repo/")

        assert repo_info.owner == "user"
        assert repo_info.repo == "repo"


class TestAuthToken:
    """Test authentication token injection."""

    def test_inject_auth_token(self, git_manager):
        """Test injecting auth token into URL."""
        original_url = "https://github.com/user/repo.git"
        token = "ghp_test_token_123"

        auth_url = git_manager._inject_auth_token(original_url, token)

        assert auth_url == "https://ghp_test_token_123@github.com/user/repo.git"

    def test_inject_auth_token_gitlab(self, git_manager):
        """Test injecting auth token for GitLab."""
        original_url = "https://gitlab.com/org/project.git"
        token = "glpat_test_123"

        auth_url = git_manager._inject_auth_token(original_url, token)

        assert auth_url == "https://glpat_test_123@gitlab.com/org/project.git"

    def test_inject_auth_token_gitea(self, git_manager):
        """Test injecting auth token for Gitea."""
        original_url = "https://gitea.example.com/user/repo.git"
        token = "gitea_token_456"

        auth_url = git_manager._inject_auth_token(original_url, token)

        assert auth_url == "https://gitea_token_456@gitea.example.com/user/repo.git"


class TestGCSOperations:
    """Test Cloud Storage operations."""

    def test_repo_exists_in_gcs_true(self, git_manager, mock_gcs_client):
        """Test checking if repository exists in GCS (exists)."""
        _, mock_bucket, mock_blob = mock_gcs_client
        mock_blob.exists.return_value = True

        repo_info = GitRepositoryInfo(
            host="github.com",
            owner="user",
            repo="test",
            platform="github",
            git_url="https://github.com/user/test.git",
            clone_path="github.com/user/test.git",
            worktree_path="github.com/user/test",
        )

        exists = git_manager._repo_exists_in_gcs(repo_info)

        assert exists is True
        mock_bucket.blob.assert_called_once_with("github.com/user/test.git/config")

    def test_repo_exists_in_gcs_false(self, git_manager, mock_gcs_client):
        """Test checking if repository exists in GCS (doesn't exist)."""
        _, mock_bucket, mock_blob = mock_gcs_client
        mock_blob.exists.return_value = False

        repo_info = GitRepositoryInfo(
            host="github.com",
            owner="user",
            repo="test",
            platform="github",
            git_url="https://github.com/user/test.git",
            clone_path="github.com/user/test.git",
            worktree_path="github.com/user/test",
        )

        exists = git_manager._repo_exists_in_gcs(repo_info)

        assert exists is False


class TestGitCommands:
    """Test Git command execution."""

    @patch("subprocess.run")
    def test_run_git_command_success(self, mock_run, git_manager):
        """Test successful git command execution."""
        mock_run.return_value = Mock(returncode=0, stdout="success output", stderr="")

        stdout, stderr = git_manager._run_git_command(["status"])

        assert stdout == "success output"
        assert stderr == ""
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["git", "status"]

    @patch("subprocess.run")
    def test_run_git_command_failure(self, mock_run, git_manager):
        """Test failed git command execution."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="fatal: not a git repository")

        with pytest.raises(GitManagerError, match="Git command failed"):
            git_manager._run_git_command(["status"])

    @patch("subprocess.run")
    def test_run_git_command_timeout(self, mock_run, git_manager):
        """Test git command timeout."""
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired(cmd=["git"], timeout=300)

        with pytest.raises(GitManagerError, match="timed out"):
            git_manager._run_git_command(["clone", "huge-repo"])


class TestCloneOperation:
    """Test repository cloning."""

    @pytest.mark.asyncio
    @patch("subprocess.run")
    @patch.object(GitRepositoryManager, "_upload_repo_to_gcs", new_callable=AsyncMock)
    async def test_clone_public_repo(self, mock_upload, mock_run, git_manager):
        """Test cloning a public repository."""
        # Mock git clone success
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        repo_info = GitRepositoryInfo(
            host="github.com",
            owner="user",
            repo="public-repo",
            platform="github",
            git_url="https://github.com/user/public-repo.git",
            clone_path="github.com/user/public-repo.git",
            worktree_path="github.com/user/public-repo",
        )

        local_path = await git_manager._clone_repo(repo_info, "main", None)

        # Verify git clone was called
        assert mock_run.called
        git_args = mock_run.call_args[0][0]
        assert "clone" in git_args
        assert "--depth" in git_args
        assert "1" in git_args
        assert "--branch" in git_args
        assert "main" in git_args

        # Verify upload to GCS was called
        mock_upload.assert_called_once()

        # Verify local path
        assert str(local_path).endswith("github.com/user/public-repo")

    @pytest.mark.asyncio
    @patch("subprocess.run")
    @patch.object(GitRepositoryManager, "_upload_repo_to_gcs", new_callable=AsyncMock)
    async def test_clone_private_repo_with_token(self, mock_upload, mock_run, git_manager):
        """Test cloning a private repository with auth token."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        repo_info = GitRepositoryInfo(
            host="github.com",
            owner="user",
            repo="private-repo",
            platform="github",
            git_url="https://github.com/user/private-repo.git",
            clone_path="github.com/user/private-repo.git",
            worktree_path="github.com/user/private-repo",
        )

        await git_manager._clone_repo(repo_info, "main", "ghp_token_123")

        # Verify URL has auth token
        git_args = mock_run.call_args[0][0]
        clone_url = git_args[-2]  # URL is second to last arg
        assert "ghp_token_123@github.com" in clone_url

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_clone_repo_not_found(self, mock_run, git_manager):
        """Test cloning a repository that doesn't exist."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="fatal: repository 'https://github.com/user/nonexistent.git/' not found",
        )

        repo_info = GitRepositoryInfo(
            host="github.com",
            owner="user",
            repo="nonexistent",
            platform="github",
            git_url="https://github.com/user/nonexistent.git",
            clone_path="github.com/user/nonexistent.git",
            worktree_path="github.com/user/nonexistent",
        )

        with pytest.raises(GitManagerError, match="not found or not accessible"):
            await git_manager._clone_repo(repo_info, "main", None)


class TestPullOperation:
    """Test pulling changes from repository."""

    @pytest.mark.asyncio
    @patch("subprocess.run")
    @patch.object(GitRepositoryManager, "_download_repo_from_gcs", new_callable=AsyncMock)
    @patch.object(GitRepositoryManager, "_upload_repo_to_gcs", new_callable=AsyncMock)
    async def test_pull_with_changes(self, mock_upload, mock_download, mock_run, git_manager):
        """Test pulling changes from repository."""

        # Mock git commands
        def git_side_effect(*args, **kwargs):
            cmd = args[0]
            if "rev-parse" in cmd:
                # Return different commits before/after pull
                if not hasattr(git_side_effect, "call_count"):
                    git_side_effect.call_count = 0
                git_side_effect.call_count += 1

                if git_side_effect.call_count == 1:
                    return Mock(returncode=0, stdout="abc123\n", stderr="")
                else:
                    return Mock(returncode=0, stdout="def456\n", stderr="")
            elif "diff" in cmd:
                return Mock(returncode=0, stdout="file1.py\nfile2.py\n", stderr="")
            else:
                return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = git_side_effect

        repo_info = GitRepositoryInfo(
            host="github.com",
            owner="user",
            repo="test-repo",
            platform="github",
            git_url="https://github.com/user/test-repo.git",
            clone_path="github.com/user/test-repo.git",
            worktree_path="github.com/user/test-repo",
        )

        # Create mock local repo directory
        local_path = git_manager.local_cache_dir / repo_info.worktree_path
        local_path.mkdir(parents=True, exist_ok=True)

        result_path, changed_files = await git_manager._pull_changes(repo_info, "main", None)

        # Verify changed files detected
        assert len(changed_files) == 2
        assert "file1.py" in changed_files
        assert "file2.py" in changed_files

        # Verify upload to GCS called (changes detected)
        mock_upload.assert_called_once()

    @pytest.mark.asyncio
    @patch("subprocess.run")
    @patch.object(GitRepositoryManager, "_download_repo_from_gcs", new_callable=AsyncMock)
    @patch.object(GitRepositoryManager, "_upload_repo_to_gcs", new_callable=AsyncMock)
    async def test_pull_no_changes(self, mock_upload, mock_download, mock_run, git_manager):
        """Test pulling when no changes exist."""

        # Mock git commands - same commit before/after
        def git_side_effect(*args, **kwargs):
            cmd = args[0]
            if "rev-parse" in cmd:
                return Mock(returncode=0, stdout="abc123\n", stderr="")
            else:
                return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = git_side_effect

        repo_info = GitRepositoryInfo(
            host="github.com",
            owner="user",
            repo="test-repo",
            platform="github",
            git_url="https://github.com/user/test-repo.git",
            clone_path="github.com/user/test-repo.git",
            worktree_path="github.com/user/test-repo",
        )

        # Create mock local repo directory
        local_path = git_manager.local_cache_dir / repo_info.worktree_path
        local_path.mkdir(parents=True, exist_ok=True)

        result_path, changed_files = await git_manager._pull_changes(repo_info, "main", None)

        # Verify no changes detected
        assert len(changed_files) == 0

        # Verify upload NOT called (no changes)
        mock_upload.assert_not_called()


class TestSyncRepository:
    """Test main sync_repository method."""

    @pytest.mark.asyncio
    @patch.object(GitRepositoryManager, "_clone_repo", new_callable=AsyncMock)
    @patch.object(GitRepositoryManager, "_repo_exists_in_gcs")
    async def test_sync_clone_new_repo(self, mock_exists, mock_clone, git_manager):
        """Test syncing a new repository (clone)."""
        mock_exists.return_value = False
        mock_clone.return_value = Path("/tmp/test-repo")

        result = await git_manager.sync_repository("https://github.com/user/new-repo", "main", None)

        assert result["sync_type"] == "clone"
        assert result["local_path"] == "/tmp/test-repo"
        assert result["changed_files"] is None
        assert result["repo_info"]["platform"] == "github"
        assert result["repo_info"]["owner"] == "user"
        assert result["repo_info"]["repo"] == "new-repo"

        mock_clone.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(GitRepositoryManager, "_pull_changes", new_callable=AsyncMock)
    @patch.object(GitRepositoryManager, "_repo_exists_in_gcs")
    async def test_sync_pull_existing_repo(self, mock_exists, mock_pull, git_manager):
        """Test syncing an existing repository (pull)."""
        mock_exists.return_value = True
        mock_pull.return_value = (Path("/tmp/test-repo"), ["file1.py", "file2.py"])

        result = await git_manager.sync_repository(
            "https://github.com/user/existing-repo", "main", None
        )

        assert result["sync_type"] == "pull"
        assert result["local_path"] == "/tmp/test-repo"
        assert result["changed_files"] == ["file1.py", "file2.py"]
        assert result["files_changed"] == 2
        assert result["repo_info"]["platform"] == "github"

        mock_pull.assert_called_once()


class TestCleanup:
    """Test cleanup operations."""

    def test_cleanup_specific_repo(self, git_manager):
        """Test cleaning up a specific repository."""
        # Create mock repository directory
        repo_info = git_manager.parse_git_url("https://github.com/user/test")
        local_path = git_manager.local_cache_dir / repo_info.worktree_path
        local_path.mkdir(parents=True, exist_ok=True)

        assert local_path.exists()

        git_manager.cleanup_local_cache("https://github.com/user/test")

        assert not local_path.exists()

    def test_cleanup_all_cache(self, git_manager):
        """Test cleaning up all cached repositories."""
        # Create some mock directories
        (git_manager.local_cache_dir / "test1").mkdir(parents=True, exist_ok=True)
        (git_manager.local_cache_dir / "test2").mkdir(parents=True, exist_ok=True)

        git_manager.cleanup_local_cache()

        # Cache dir should be empty but still exist
        assert git_manager.local_cache_dir.exists()
        assert len(list(git_manager.local_cache_dir.iterdir())) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
