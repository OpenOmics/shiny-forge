#!/usr/bin/env python3
"""
posit.py - Module for deploying Shiny applications to Posit Connect

This module provides functionality to deploy Shiny applications to Posit Connect
servers using the rsconnect-python library.
"""
import json
import os
import sys
from typing import Optional, Dict, Any
from rsconnect.api import RSConnectServer
from rsconnect.actions import deploy_app
from src.config import bcolors


def validate_posit_config(config: Dict[str, Any]) -> None:
    """
    Validate that the Posit configuration has all required fields.
    
    Args:
        config: Dictionary containing Posit configuration
        
    Raises:
        ValueError: If required fields are missing
    """
    required_fields = ['username', 'api_key', 'server', 'app_dir']
    missing_fields = [field for field in required_fields if field not in config or not config[field]]
    
    if missing_fields:
        raise ValueError(
            f"Missing required configuration fields: {', '.join(missing_fields)}\n"
            f"Required fields: {', '.join(required_fields)}"
        )
    
    # Validate app_dir exists
    if not os.path.exists(config['app_dir']):
        raise ValueError(f"Application directory does not exist: {config['app_dir']}")
    
    if not os.path.isdir(config['app_dir']):
        raise ValueError(f"Application path is not a directory: {config['app_dir']}")


def load_posit_config(config_file: str) -> Dict[str, Any]:
    """
    Load Posit configuration from a JSON file.
    
    Args:
        config_file: Path to JSON configuration file
        
    Returns:
        Dictionary containing Posit configuration
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config file is not valid JSON
    """
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    return config


def create_posit_config(
    username: Optional[str] = None,
    api_key: Optional[str] = None,
    server: Optional[str] = None,
    app_dir: Optional[str] = None,
    config_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a Posit configuration from either direct arguments or a config file.
    
    Args:
        username: Posit Connect username
        api_key: Posit Connect API key
        server: Posit Connect server URL
        app_dir: Path to Shiny application directory
        config_file: Path to JSON configuration file (overrides other args)
        
    Returns:
        Dictionary containing Posit configuration
        
    Raises:
        ValueError: If neither config_file nor required arguments are provided
    """
    if config_file:
        config = load_posit_config(config_file)
        # Allow command-line args to override config file values
        if username:
            config['username'] = username
        if api_key:
            config['api_key'] = api_key
        if server:
            config['server'] = server
        if app_dir:
            config['app_dir'] = app_dir
    else:
        config = {
            'username': username,
            'api_key': api_key,
            'server': server,
            'app_dir': app_dir
        }
    
    validate_posit_config(config)
    return config


def deploy_to_posit(
    username: str,
    api_key: str,
    server: str,
    app_dir: str,
    app_name: Optional[str] = None,
    title: Optional[str] = None,
    **kwargs
) -> None:
    """
    Deploy a Shiny application to Posit Connect.
    
    Args:
        username: Posit Connect username
        api_key: Posit Connect API key
        server: Posit Connect server URL (e.g., https://connect.example.com)
        app_dir: Path to Shiny application directory
        app_name: Optional name for the application (defaults to directory name)
        title: Optional title for the application
        **kwargs: Additional arguments to pass to rsconnect deploy_app
        
    Raises:
        Exception: If deployment fails
    """
    # Normalize server URL
    if not server.startswith('http://') and not server.startswith('https://'):
        server = f'https://{server}'
    
    # Default app_name to directory name if not provided
    if not app_name:
        app_name = os.path.basename(os.path.abspath(app_dir))
    
    print(f"{bcolors.OKBLUE}Deploying Shiny application to Posit Connect...{bcolors.ENDC}")
    print(f"  Server: {server}")
    print(f"  App Name: {app_name}")
    print(f"  App Directory: {app_dir}")
    
    try:
        # Create RSConnect server connection
        connect_server = RSConnectServer(url=server, api_key=api_key)
        
        print(f"{bcolors.OKBLUE}Connected to Posit Connect server{bcolors.ENDC}")
        
        # Deploy the application using rsconnect deploy_app
        deploy_app(
            connect_server=connect_server,
            path=app_dir,
            name=app_name,
            title=title or app_name,
            verbose=True,
            **kwargs
        )
        
        print(f"{bcolors.OKGREEN}✅ Successfully deployed '{app_name}' to Posit Connect!{bcolors.ENDC}")
        print(f"{bcolors.OKGREEN}Access your application at: {server}/connect/#/apps{bcolors.ENDC}")
            
    except Exception as e:
        print(f"{bcolors.FAIL}❌ Error deploying to Posit Connect: {str(e)}{bcolors.ENDC}")
        raise


def posit_deploy_handler(
    username: Optional[str] = None,
    api_key: Optional[str] = None,
    server: Optional[str] = None,
    app_dir: Optional[str] = None,
    config_file: Optional[str] = None,
    app_name: Optional[str] = None,
    title: Optional[str] = None
) -> None:
    """
    Handler function for the posit deploy command.
    
    This function orchestrates the deployment process by:
    1. Creating/loading configuration
    2. Validating inputs
    3. Calling the deployment function
    
    Args:
        username: Posit Connect username
        api_key: Posit Connect API key
        server: Posit Connect server URL
        app_dir: Path to Shiny application directory
        config_file: Path to JSON configuration file
        app_name: Optional name for the application
        title: Optional title for the application
    """
    try:
        # Create configuration from provided arguments
        config = create_posit_config(
            username=username,
            api_key=api_key,
            server=server,
            app_dir=app_dir,
            config_file=config_file
        )
        
        # Deploy to Posit Connect
        deploy_to_posit(
            username=config['username'],
            api_key=config['api_key'],
            server=config['server'],
            app_dir=config['app_dir'],
            app_name=app_name,
            title=title
        )
        
    except Exception as e:
        print(f"{bcolors.FAIL}Error: {str(e)}{bcolors.ENDC}", file=sys.stderr)
        sys.exit(1)
