# Sync Dev Environment  
import sys, subprocess

def sync_env(path:str):
    """Install Packages From a Config File (pyproject.toml)"""
    try:
        # Update package manager
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'])

        # Install project dependencies
        
        build = open(path).read().split("dependencies = [")[1].split("]\n")[0].split(",")
        build = [i.strip().strip('"') for i in build]
        [subprocess.check_call([sys.executable, '-m', 'pip', 'install', package]) for package in build if len(package) > 0]
                
        # Install test dependencies
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', "pytest"])
    
    except Exception as e:
        err = f"Error : {e}"
        print(err)
        return False
    
    return True

if __name__ == "__main__":
    sync_env('pyproject.toml')
