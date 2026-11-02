import pytest
from app.security import safe_relative_path, publishable_files

def test_rejects_parent_traversal():
    with pytest.raises(ValueError):
        safe_relative_path("../secret.txt")

def test_rejects_env_file():
    with pytest.raises(ValueError):
        safe_relative_path(".env")

def test_publish_filter():
    result = publishable_files({"main.py": "print('ok')", ".env": "SECRET=x",
                                "node_modules/pkg/a.js": "bad"})
    assert list(result) == ["main.py"]
