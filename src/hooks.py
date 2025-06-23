#!/usr/bin/env python3
import logging
import shutil
from google.cloud import storage
from contextlib import contextmanager
from typing import Generator, Optional, Callable, Any
from pathlib import Path


class ExceptionHook:
    """
    Context manager for handling exceptions with automatic cleanup of temporary directories and Google Cloud buckets
    """
    
    def __init__(self, 
                 handler: Optional[Callable] = None,
                 suppress: bool = False,
                 log_errors: bool = True,
                 cleanup_on_exception: bool = True):
        """
        Initialize the ExceptionHook
        
        Args:
            handler: Custom exception handler function
            suppress: Whether to suppress exceptions after handling
            log_errors: Whether to log exceptions
            cleanup_on_exception: Whether to perform cleanup when exceptions occur
        """
        self.handler = handler
        self.suppress = suppress
        self.log_errors = log_errors
        self.cleanup_on_exception = cleanup_on_exception
        self.exception = None
        self.temp_dir = None
        self.google_bucket_name = None
        self.google_project_id = None
    
    def __enter__(self):
        return self
    
    @staticmethod
    def delete_gcs_bucket(project_id: str, bucket_name: str) -> None:
        """
        Delete a GCS bucket and all its contents.
        
        Args:
            project_id: Google Cloud Project ID
            bucket_name: Name of the bucket to delete
        """
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.get_bucket(bucket_name)
        blobs = list(bucket.list_blobs())
        for blob in blobs: blob.delete()
        bucket.delete()
        return
        
    def set_cleanup_resources(self, temp_dir: Optional[str] = None, 
                             google_bucket_name: Optional[str] = None,
                             google_project_id: Optional[str] = None):
        """
        Set resources to be cleaned up when context exits
        
        Args:
            temp_dir: Path to temporary directory to clean up
            google_bucket_name: Name of Google Cloud Storage bucket to delete
            google_project_id: Google Cloud project ID
        """
        # Handle temporary directory setup
        if temp_dir:
            self.temp_dir = Path(temp_dir)
            logging.info(f"Set temporary directory for cleanup: {self.temp_dir}")
            
        # Handle Google Cloud Storage setup
        if google_bucket_name:
            self.google_bucket_name = google_bucket_name
            self.google_project_id = google_project_id
            logging.info(f"Set Google Cloud bucket for cleanup: {google_bucket_name}")
    
    def __exit__(self, exc_type, exc_value, traceback):
        exception_occurred = exc_type is not None
        
        # Handle exception if one occurred
        if exception_occurred:
            self.exception = exc_value
            
            if self.log_errors:
                logging.error(f"Exception caught: {exc_type.__name__}: {exc_value}")
            
            if self.handler:
                try:
                    self.handler(exc_type, exc_value, traceback)
                except Exception as handler_error:
                    logging.error(f"Error in exception handler: {handler_error}")
            
            # Perform cleanup if exception occurred and cleanup_on_exception is True
            if self.cleanup_on_exception:
                logging.info("Performing cleanup due to exception...")
                self._cleanup()
            
            # Always rethrow the exception after cleanup (unless suppress is True)
            if not self.suppress:
                return False  # Let the exception propagate
        
        # Always perform cleanup on normal exit (no exception)
        if not exception_occurred:
            logging.info("Performing cleanup on normal exit...")
            self._cleanup()
        
        # Return True to suppress the exception, False to let it propagate
        return self.suppress if exception_occurred else False
    
    def _cleanup(self):
        """Perform cleanup of temporary directory and Google Cloud bucket"""
        
        # Clean up temporary directory
        if self.temp_dir and self.temp_dir.exists():
            try:
                logging.info(f"Cleaning up temporary directory: {self.temp_dir}")
                shutil.rmtree(self.temp_dir)
                logging.info("Temporary directory cleaned up successfully")
            except Exception as e:
                logging.error(f"Failed to clean up temporary directory {self.temp_dir}: {e}")
        
        # Clean up Google Cloud bucket
        if self.google_bucket_name and self.google_project_id:
            try:
                logging.info(f"Deleting Google Cloud bucket: {self.google_bucket_name}")
                self.delete_gcs_bucket(self.google_project_id, self.google_bucket_name)
                logging.info(f"Google Cloud bucket {self.google_bucket_name} deleted successfully")
            except Exception as e:
                logging.error(f"Failed to clean up Google Cloud bucket {self.google_bucket_name}: {e}")

@contextmanager
def handle_exceptions_with_cleanup(
    handler : Any = None, 
    suppress : bool = False,
    cleanup_on_exception : bool = True) -> Generator[ExceptionHook, None, None]:
    """
    Context manager function for exception handling with automatic cleanup
    
    Args:
        handler: Custom exception handler function
        suppress: Whether to suppress exceptions after handling
        cleanup_on_exception: Whether to perform cleanup when exceptions occur
    """
    hook = ExceptionHook(
        handler=handler,
        suppress=suppress,
        cleanup_on_exception=cleanup_on_exception
    )
    
    try:
        yield hook
    finally:
        # Cleanup is handled in __exit__, but we ensure it happens
        pass