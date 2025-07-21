import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from .utils import print_error, print_info
from ..config.constants import CONFIG_FILE

class ConfigManager:
    """Manages project configuration file operations"""
    
    def __init__(self, config_file: str = CONFIG_FILE):
        self.config_file = Path(config_file)
        self.config_data: Optional[Dict[str, Any]] = None
    
    def config_exists(self) -> bool:
        """Check if configuration file exists"""
        return self.config_file.exists()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            if not self.config_exists():
                raise FileNotFoundError(f"Configuration file {self.config_file} not found")
            
            with open(self.config_file, 'r') as f:
                self.config_data = json.load(f)
            
            return self.config_data
            
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON in configuration file: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to load configuration: {str(e)}")
    
    def save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration to file"""
        try:
            self.config_data = config
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2, sort_keys=True)
            
            print_info(f"Configuration saved to {self.config_file}")
            
        except Exception as e:
            raise Exception(f"Failed to save configuration: {str(e)}")
    
    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update specific configuration values"""
        if not self.config_data:
            self.config_data = self.load_config()
        
        def deep_update(original: dict, updates: dict) -> dict:
            """Recursively update nested dictionaries"""
            for key, value in updates.items():
                if isinstance(value, dict) and key in original and isinstance(original[key], dict):
                    deep_update(original[key], value)
                else:
                    original[key] = value
            return original
        
        deep_update(self.config_data, updates)
        self.save_config(self.config_data)
    
    def get_config_value(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'aws.region')"""
        if not self.config_data:
            self.config_data = self.load_config()
        
        keys = key_path.split('.')
        value = self.config_data
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
