"""Common test fixtures."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _use_temp_config(tmp_path):
    """Use a temporary config directory for all tests."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Write a minimal config.yml
    config_yml = config_dir / "config.yml"
    config_yml.write_text(
        """
app:
  name: argus-insight-usersync-test
  version: 0.1.0-test

logging:
  level: DEBUG
  dir: {log_dir}
  filename: usersync-test.log

sync:
  source: file
  min_uid: 1000
  min_gid: 1000

ranger:
  url: http://localhost:6080
  username: admin
  password: admin
  timeout: 10

file:
  users_path: ""
  groups_path: ""
  format: csv
""".format(log_dir=str(tmp_path / "logs"))
    )

    config_props = config_dir / "config.properties"
    config_props.write_text("")

    with patch.dict(os.environ, {"ARGUS_USERSYNC_CONFIG_DIR": str(config_dir)}):
        # Reimport to pick up the new config dir
        import importlib

        import app.core.config
        import app.core.config_loader

        importlib.reload(app.core.config_loader)
        importlib.reload(app.core.config)
        yield


@pytest.fixture
def sample_users_csv(tmp_path) -> Path:
    """Create a sample users CSV file."""
    csv_file = tmp_path / "users.csv"
    csv_file.write_text(
        "name,first_name,last_name,email,description,groups\n"
        'jdoe,John,Doe,jdoe@example.com,Developer,"dev,admin"\n'
        "jsmith,Jane,Smith,jsmith@example.com,Manager,dev\n"
        "bob,Bob,Builder,bob@example.com,Tester,qa\n"
    )
    return csv_file


@pytest.fixture
def sample_groups_csv(tmp_path) -> Path:
    """Create a sample groups CSV file."""
    csv_file = tmp_path / "groups.csv"
    csv_file.write_text(
        "name,description,members\n"
        'dev,Development team,"jdoe,jsmith"\n'
        "admin,Admin team,jdoe\n"
        "qa,QA team,bob\n"
    )
    return csv_file


@pytest.fixture
def sample_users_json(tmp_path) -> Path:
    """Create a sample users JSON file."""
    import json

    json_file = tmp_path / "users.json"
    data = [
        {
            "name": "jdoe",
            "first_name": "John",
            "last_name": "Doe",
            "email": "jdoe@example.com",
            "groups": ["dev", "admin"],
        },
        {
            "name": "jsmith",
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "jsmith@example.com",
            "groups": ["dev"],
        },
    ]
    json_file.write_text(json.dumps(data))
    return json_file


@pytest.fixture
def sample_groups_json(tmp_path) -> Path:
    """Create a sample groups JSON file."""
    import json

    json_file = tmp_path / "groups.json"
    data = [
        {"name": "dev", "description": "Development team", "members": ["jdoe", "jsmith"]},
        {"name": "admin", "description": "Admin team", "members": ["jdoe"]},
    ]
    json_file.write_text(json.dumps(data))
    return json_file
