import requests
import socket
import os
import functools
import logging
import logging.handlers


def get_logger(logger_name, path, filename):
    """
    - logger_name: unique name
    - path: base path
    - name: logger name
    Directory will be created with name.
    """
    # Config variables
    LOG_MAX_SIZE = 1024 * 1024 * 5
    LOG_FILE_CNT = 5
    LOG_LEVEL = logging.INFO
    # LOG_LEVEL = logging.DEBUG

    LOG_DIR = os.path.join(path, f'.{filename}')
    if not os.path.isdir(LOG_DIR):
        os.mkdir(LOG_DIR)

    log_path = os.path.join(LOG_DIR, f'{filename}.log')

    logger = logging.getLogger(logger_name)
    logger.setLevel(LOG_LEVEL)

    logging.handlers.RotatingFileHandler(log_path, maxBytes=LOG_MAX_SIZE, backupCount=LOG_FILE_CNT)

    # log format
    if LOG_LEVEL == logging.INFO:
        fileformatter = logging.Formatter('[%(asctime)s|%(levelname)s]-%(message)s')
    elif LOG_LEVEL == logging.DEBUG:
        fileformatter = logging.Formatter('[%(asctime)s|%(levelname)s|%(filename)s|(%(funcName)s)]-%(message)s')

    fileHandler = logging.FileHandler(log_path, encoding='utf-8')
    fileHandler.setFormatter(fileformatter)

    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(fileformatter)

    # log handler
    logger.addHandler(fileHandler)
    logger.addHandler(streamHandler)

    return logger


logger = get_logger('wizconfig', os.path.expanduser('~'), 'wizconfig')


def funclog(logger):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # logger.debug(f"{func.__name__} called.")
            logger.debug(f"{func.__qualname__.split('.')[0]} {func.__name__} called.")
            try:
                result = func(*args, **kwargs)
                # logger.debug(f"Function {func.__name__} completed.")
                logger.debug(f"{func.__qualname__.split('.')[0]} {func.__name__} completed.")
                return result
            except Exception as e:
                logger.error(f"Error in {func.__qualname__.split('.')[0]} {func.__name__}: {e}")
        return wrapper
    return decorator


def socket_exception_handler(logger):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (socket.error, ConnectionResetError, BrokenPipeError, OSError) as e:
                logger.error(f"Error in {func.__qualname__.split('.')[0]} {func.__name__}: {e}")
        return wrapper
    return decorator


def get_latest_release_version(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/tags"
    response = requests.get(url)
    if response.status_code == 200:
        tags = response.json()
        if tags:
            latest_tag = tags[0]['name']
            return latest_tag
    print("Failed to get the latest release version.")
    return None


if __name__ == "__main__":
    # 최신 버전 확인
    owner = "Wiznet"
    repo = "WIZnet-S2E-Tool-GUI"
    latest_release = get_latest_release_version(owner, repo)
    print(f"The latest release version of {repo} is: {latest_release}")
