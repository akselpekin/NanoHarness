from helpers.startup import startup_checks
from core.harness import run

if __name__ == "__main__":
    print("Running checks...")
    startup_checks()
    print("Starting...")
    run()
