"""Tests for configuration management."""

import pytest
import tempfile
from pathlib import Path
from devops_cli.config.settings import (
    get_default_config,
    load_config,
    save_config,
)


class TestConfig:
    """Test configuration functions."""

    def test_get_default_config(self):
        """Test default configuration."""
        config = get_default_config()

        assert "github" in config
        assert "servers" in config
        assert "services" in config
        assert "logs" in config
        assert "environments" in config
        assert "ci" in config

    def test_default_environments(self):
        """Test default environment configuration."""
        config = get_default_config()
        envs = config["environments"]

        assert "dev" in envs
        assert "staging" in envs
        assert "prod" in envs

        assert envs["dev"]["branch"] == "develop"
        assert envs["prod"]["auto_deploy"] is False

    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"

            test_config = {
                "github": {"token": "test-token"},
                "servers": {"test-server": {"host": "test.com"}},
            }

            # Save
            config_path.parent.mkdir(parents=True, exist_ok=True)
            import yaml
            with open(config_path, "w") as f:
                yaml.dump(test_config, f)

            # Load
            with open(config_path) as f:
                loaded = yaml.safe_load(f)

            assert loaded["github"]["token"] == "test-token"
            assert loaded["servers"]["test-server"]["host"] == "test.com"
