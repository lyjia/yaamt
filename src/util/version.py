import subprocess
import os
import re
from .const import VERSION_STRING

def get_version_from_git():
    """
    Retrieves the version string using git describe command.
    """
    try:
        # Get the project root directory (where .git is located)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Run git describe to get version string
        version = subprocess.check_output(
            ['git', 'describe', '--tags', '--dirty', '--always'],
            cwd=project_root,
            stderr=subprocess.STDOUT
        ).decode('utf-8').strip()
        
        # If the version doesn't start with a number (like v0.1.0),
        # it's likely just a commit hash, so format it as 0.0.1+hash
        if not re.match(r'^v?\d+\.\d+\.\d+', version):
            # Clean up the hash but preserve the dirty flag
            dirty_flag = "-dirty" if "dirty" in version else ""
            clean_hash = re.sub(r'[^a-zA-Z0-9]', '', version.replace("-dirty", ""))
            version = f"0.0.0+{clean_hash}{dirty_flag}"
        # If it starts with 'v', remove it to make it a valid version
        elif version.startswith('v'):
            version = version[1:]
            
        return version
    except subprocess.CalledProcessError as e:
        print(f"Error getting version from git: {e}")
        return "0.0.0"
    except Exception as e:
        print(f"Error getting version from git: {e}")
        return "0.0.0"

def get_version():
    """
    Returns the version string.
    First, it checks for a hardcoded version in const.VERSION_STRING.
    If not found, it falls back to getting the version from git.
    """
    if VERSION_STRING:
        return VERSION_STRING
    
    return get_version_from_git()

if __name__ == "__main__":
    print(get_version())