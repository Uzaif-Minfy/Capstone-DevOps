"""Configuration constants for the deploy tool"""

# AWS Configuration
DEFAULT_AWS_PROFILE = "Uzaif"
DEFAULT_AWS_REGION = "ap-south-1"
INFRASTRUCTURE_BUCKET = "minfy-uzaif-capstone-deployments"

# File Configuration
CONFIG_FILE = ".deploy-config.json"
TEMP_DIR_PREFIX = "deploy-tool-"

# Supported Frameworks
SUPPORTED_FRAMEWORKS = ["react", "vite", "next"]

# Framework Detection Patterns
FRAMEWORK_DETECTION = {
    "react": {
        "files": ["package.json"],
        "dependencies": ["react", "react-scripts"],
        "build_dir": "build",
        "build_command": "npm run build"
    },
    "vite": {
        "files": ["package.json", "vite.config.js", "vite.config.ts"],
        "dependencies": ["vite"],
        "build_dir": "dist",
        "build_command": "npm run build"
    },
    "next": {
        "files": ["package.json", "next.config.js"],
        "dependencies": ["next"],
        "build_dir": ".next",
        "build_command": "npm run build"
    }
}

# Docker Configuration
DOCKER_NODE_IMAGE = "node:18-alpine"
DOCKER_BUILD_TIMEOUT = 600  # 10 minutes
