import subprocess
import os
import re

def generate_version_file():
    """
    Generates a version file using git describe command.
    The version is written to src/VERSION file.
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
            version = f"0.0.1+{clean_hash}{dirty_flag}"
        # If it starts with 'v', remove it to make it a valid version
        elif version.startswith('v'):
            version = version[1:]
            
        # Define the path to VERSION file
        version_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'VERSION')
        
        # Write version to file
        with open(version_file_path, 'w') as f:
            f.write(version)
            
        return version
    except subprocess.CalledProcessError as e:
        print(f"Error getting version from git: {e}")
        return "0.0.0"
    except Exception as e:
        print(f"Error generating version file: {e}")
        return "0.0.0"

def get_version():
    """
    Reads the version string from the VERSION file.
    Returns the version string or '0.0.0' if the file doesn't exist.
    """
    try:
        # Define the path to VERSION file
        version_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'VERSION')
        
        # Read version from file
        with open(version_file_path, 'r') as f:
            version = f.read().strip()
            
        return version
    except FileNotFoundError:
        print(f"Version file not found at {version_file_path}")
        return "0.0.0"
    except Exception as e:
        print(f"Error reading version file: {e}")
        return "0.0.0"

if __name__ == "__main__":
    generate_version_file()