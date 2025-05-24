import logging
import os
import sys
from . import config # Import config from the same package (utils)

# Removed old DATA_DIR and LOG_FILE_NAME comments as they are replaced by config

def setup_logger(name='app_logger', 
                 log_file_dir=None, # Default to None, will use config.LOG_DATA_DIR
                 log_file_name=None, # Default to None, will use config.APP_LOG_FILE
                 level=None, # Default to None, will use config.LOG_LEVEL
                 log_format=None # Default to None, will use config.LOG_FORMAT
                 ):
    """
    Configures and returns a logger that logs to both console and a file.
    Defaults are sourced from config.py.
    """
    # Resolve defaults from config
    resolved_log_file_dir = log_file_dir if log_file_dir is not None else config.LOG_DATA_DIR
    resolved_log_file_name = log_file_name if log_file_name is not None else config.APP_LOG_FILE
    resolved_level = level if level is not None else config.LOG_LEVEL
    resolved_formatter_str = log_format if log_format is not None else config.LOG_FORMAT

    # Ensure the log directory exists. config.LOG_DATA_DIR is absolute.
    os.makedirs(resolved_log_file_dir, exist_ok=True)
    log_file_path = os.path.join(resolved_log_file_dir, resolved_log_file_name)

    logger = logging.getLogger(name)
    logger.setLevel(resolved_level)

    if logger.hasHandlers():
        return logger

    formatter = logging.Formatter(resolved_formatter_str)

    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(resolved_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(resolved_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Print is safer for this initial meta-log, as logger might not be fully ready.
    print(f"Logger '{name}' configured by setup_logger. Level: {resolved_level}. File: {log_file_path}")
    return logger

if __name__ == '__main__':
    # Example usage, now relying on config.py for defaults
    print(f"Testing logger setup. Default log file dir: {config.LOG_DATA_DIR}")
    print(f"Default app log file name: {config.APP_LOG_FILE}")
    print(f"Default log level: {config.LOG_LEVEL}")

    # Test with all defaults (name 'app_logger', file 'data/app.log')
    default_logger = setup_logger() # Uses name 'app_logger'
    default_logger.debug("This is a debug message (default_logger) - should not appear if default level is INFO.")
    default_logger.info("This is an info message (default_logger).")

    # Test overriding some parameters, e.g., name and specific log file
    # It will still use config.LOG_DATA_DIR unless log_file_dir is also overridden.
    # This test logger will write to a file like data/custom_test_logger.log
    custom_logger_name = 'custom_test'
    custom_log_file = 'custom_test_logger.log'
    print(f"Setting up custom logger: {custom_logger_name} to file {os.path.join(config.LOG_DATA_DIR, custom_log_file)}")
    
    custom_logger = setup_logger(name=custom_logger_name, 
                                 log_file_name=custom_log_file, 
                                 level=logging.DEBUG) # Override level
    custom_logger.debug("This is a DEBUG message from custom_logger (should appear).")
    custom_logger.info("This is an INFO message from custom_logger.")

    print(f"Test finished. Check console output and log files in '{config.LOG_DATA_DIR}'")
    print(f"Files should include: {config.APP_LOG_FILE} (for default_logger) and {custom_log_file} (for custom_logger).") 