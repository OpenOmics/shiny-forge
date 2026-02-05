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


def detect_shiny_app_type(app_dir: str) -> str:
    """
    Detect the type of Shiny application in the directory.
    
    Args:
        app_dir: Path to Shiny application directory
        
    Returns:
        String indicating app type: 'app.R', 'ui.R+server.R', 'python', or 'unknown'
        
    Raises:
        ValueError: If no valid Shiny application structure is found
    """
    app_r_path = os.path.join(app_dir, 'app.R')
    ui_r_path = os.path.join(app_dir, 'ui.R')
    server_r_path = os.path.join(app_dir, 'server.R')
    app_py_path = os.path.join(app_dir, 'app.py')
    
    # Check for single-file R Shiny app (app.R)
    if os.path.isfile(app_r_path):
        return 'app.R'
    
    # Check for old-style R Shiny app (ui.R + server.R)
    if os.path.isfile(ui_r_path) and os.path.isfile(server_r_path):
        return 'ui.R+server.R'
    
    # Check for Python Shiny app
    if os.path.isfile(app_py_path):
        return 'python'
    
    # No valid Shiny app structure found
    raise ValueError(
        f"No valid Shiny application structure found in {app_dir}\n"
        f"Expected one of:\n"
        f"  - app.R (single-file R Shiny)\n"
        f"  - ui.R + server.R (old-style R Shiny)\n"
        f"  - app.py (Python Shiny)"
    )


def get_app_files_summary(app_dir: str, app_type: str) -> str:
    """
    Get a summary of files in the Shiny app directory.
    
    Args:
        app_dir: Path to Shiny application directory
        app_type: Detected application type
        
    Returns:
        String summary of key files
    """
    files_info = []
    
    # List key files based on app type
    if app_type == 'app.R':
        key_files = ['app.R', 'DESCRIPTION', 'renv.lock', '.Rprofile']
    elif app_type == 'ui.R+server.R':
        key_files = ['ui.R', 'server.R', 'global.R', 'DESCRIPTION', 'renv.lock', '.Rprofile']
    elif app_type == 'python':
        key_files = ['app.py', 'requirements.txt', 'Pipfile', 'pyproject.toml']
    else:
        key_files = []
    
    for filename in key_files:
        filepath = os.path.join(app_dir, filename)
        if os.path.isfile(filepath):
            size = os.path.getsize(filepath)
            files_info.append(f"    ✓ {filename} ({size} bytes)")
        elif filename in ['app.R', 'ui.R', 'server.R', 'app.py']:
            # These are required files
            files_info.append(f"    ✗ {filename} (missing)")
    
    return '\n'.join(files_info) if files_info else '    (no key files detected)'


def get_proxy_config() -> Dict[str, Optional[str]]:
    """
    Detect proxy configuration from environment variables.
    
    Checks for http_proxy, https_proxy, HTTP_PROXY, and HTTPS_PROXY
    environment variables (case-insensitive).
    
    Returns:
        Dictionary with 'http' and 'https' proxy URLs, or None if not set
    """
    # Check environment variables (case-insensitive)
    http_proxy = os.environ.get('http_proxy') or os.environ.get('HTTP_PROXY')
    https_proxy = os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')
    
    return {
        'http': http_proxy,
        'https': https_proxy
    }


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
    
    Supports:
    - Single-file R Shiny apps (app.R)
    - Old-style R Shiny apps (ui.R + server.R)
    - Python Shiny apps (app.py)
    
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
    
    # Detect and log proxy configuration
    proxy_config = get_proxy_config()
    if proxy_config['http'] or proxy_config['https']:
        print(f"{bcolors.OKBLUE}Proxy configuration detected:{bcolors.ENDC}")
        if proxy_config['http']:
            print(f"  HTTP Proxy: {proxy_config['http']}")
        if proxy_config['https']:
            print(f"  HTTPS Proxy: {proxy_config['https']}")
        print(f"{bcolors.OKBLUE}rsconnect-python will use these proxy settings{bcolors.ENDC}")
    else:
        print(f"{bcolors.OKBLUE}No proxy configuration detected (http_proxy/https_proxy not set){bcolors.ENDC}")
    
    # Detect application type
    try:
        app_type = detect_shiny_app_type(app_dir)
        print(f"{bcolors.OKBLUE}Detected Shiny application type: {app_type}{bcolors.ENDC}")
        
        # Display files summary
        files_summary = get_app_files_summary(app_dir, app_type)
        print(f"{bcolors.OKBLUE}Application files:{bcolors.ENDC}")
        print(files_summary)
        
    except ValueError as e:
        print(f"{bcolors.FAIL}❌ {str(e)}{bcolors.ENDC}")
        raise
    
    # Set entry point based on application type
    entrypoint = None
    app_mode = None
    
    if app_type == 'app.R':
        entrypoint = 'app.R'
        app_mode = 'shiny'
        print(f"{bcolors.OKBLUE}Using single-file R Shiny entry point: app.R{bcolors.ENDC}")
    elif app_type == 'ui.R+server.R':
        # For old-style Shiny apps, use server.R as entry point
        entrypoint = 'server.R'
        app_mode = 'shiny'
        print(f"{bcolors.OKBLUE}Using old-style R Shiny with entry point: server.R{bcolors.ENDC}")
    elif app_type == 'python':
        entrypoint = 'app.py'
        app_mode = 'python-shiny'
        print(f"{bcolors.OKBLUE}Using Python Shiny entry point: app.py{bcolors.ENDC}")
    
    print(f"{bcolors.OKBLUE}Deploying Shiny application to Posit Connect...{bcolors.ENDC}")
    print(f"  Server: {server}")
    print(f"  App Name: {app_name}")
    print(f"  App Directory: {app_dir}")
    print(f"  Entry Point: {entrypoint}")
    
    try:
        # Create RSConnect server connection
        connect_server = RSConnectServer(url=server, api_key=api_key)
        
        print(f"{bcolors.OKBLUE}Connected to Posit Connect server{bcolors.ENDC}")
        
        # Ensure app_dir is absolute path
        abs_app_dir = os.path.abspath(app_dir)
        
        # Prepare deployment arguments
        # When using connect_server, don't pass 'server' or 'name' separately
        deploy_kwargs = {
            'connect_server': connect_server,
            'directory': abs_app_dir,
            'title': title or app_name,
        }
        
        # Add entry_point only if specified (not for ui.R+server.R auto-detect)
        if entrypoint:
            deploy_kwargs['entry_point'] = entrypoint  # Note: underscore not camelCase
        
        # Add app_mode if specified
        if app_mode:
            deploy_kwargs['app_mode'] = app_mode
        
        # Merge with any additional kwargs (but don't override our core params)
        for key, value in kwargs.items():
            if key not in deploy_kwargs:
                deploy_kwargs[key] = value
        
        # Debug: show what we're passing to deploy_app
        print(f"{bcolors.OKBLUE}Deployment parameters:{bcolors.ENDC}")
        print(f"  directory: {deploy_kwargs.get('directory')}")
        print(f"  entry_point: {deploy_kwargs.get('entry_point')}")
        print(f"  app_mode: {deploy_kwargs.get('app_mode')}")
        
        # Deploy the application using rsconnect deploy_app
        deploy_app(**deploy_kwargs)
        
        print(f"{bcolors.OKGREEN}✅ Successfully deployed '{title or app_name}' to Posit Connect!{bcolors.ENDC}")
        print(f"{bcolors.OKGREEN}Access your application at: {server}/connect/#/apps{bcolors.ENDC}")
            
    except Exception as e:
        error_msg = str(e)
        print(f"{bcolors.FAIL}❌ Error deploying to Posit Connect: {error_msg}{bcolors.ENDC}")
        
        # Provide helpful hints for common proxy errors
        if "Tunnel connection failed" in error_msg or "503" in error_msg:
            print(f"\n{bcolors.WARNING}Proxy Troubleshooting:{bcolors.ENDC}")
            print(f"  • The proxy server rejected the HTTPS tunnel connection")
            print(f"  • Check if {server} is allowed through the proxy")
            print(f"  • Verify proxy firewall rules allow CONNECT method")
            print(f"  • Consider proxy authentication if required")
            print(f"  • Try connecting directly without proxy (unset http_proxy/https_proxy)")
        elif "Connection" in error_msg or "timeout" in error_msg.lower():
            print(f"\n{bcolors.WARNING}Connection Troubleshooting:{bcolors.ENDC}")
            print(f"  • Verify server URL is correct: {server}")
            print(f"  • Check network connectivity to Posit Connect server")
            print(f"  • Verify API key is valid and not expired")
        
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
