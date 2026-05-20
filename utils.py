import datetime
import glob
import requests
import socket
import os
import functools
import logging
import logging.handlers


def _rotate_log_on_startup(log_path: str, keep: int = 10) -> None:
    """
    앱 시작 시 기존 로그 파일을 수정일 기반 이름으로 아카이브.

    wizconfig.log  →  wizconfig_2026-05-20.log
    같은 날 여러 번 실행 시: wizconfig_2026-05-20_1.log, _2.log …
    오래된 아카이브는 최근 keep개만 유지하고 나머지 삭제.
    """
    if not os.path.isfile(log_path):
        return
    mtime = os.path.getmtime(log_path)
    date_str = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
    base, ext = os.path.splitext(log_path)
    rotated = f"{base}_{date_str}{ext}"
    counter = 1
    while os.path.exists(rotated):
        rotated = f"{base}_{date_str}_{counter}{ext}"
        counter += 1
    try:
        os.rename(log_path, rotated)
    except OSError:
        return

    # 오래된 아카이브 정리
    archived = sorted(glob.glob(f"{base}_*{ext}"))
    for old in archived[:-keep]:
        try:
            os.remove(old)
        except OSError:
            pass


def get_logger(logger_name, path, filename):
    """
    - logger_name: unique name
    - path: base path
    - name: logger name
    Directory will be created with name.
    """
    # Config variables
    LOG_MAX_SIZE = 1024 * 1024 * 5
    LOG_FILE_CNT = 2          # 시작 시 로테이션하므로 세션 내 백업은 2개로 충분
    LOG_LEVEL = logging.INFO
    # LOG_LEVEL = logging.DEBUG

    LOG_DIR = os.path.join(path, f'.{filename}', 'logs')
    os.makedirs(LOG_DIR, exist_ok=True)

    log_path = os.path.join(LOG_DIR, f'{filename}.log')

    # 앱 시작 시 이전 로그 아카이브
    _rotate_log_on_startup(log_path)

    logger = logging.getLogger(logger_name)
    logger.setLevel(LOG_LEVEL)

    # log format
    if LOG_LEVEL == logging.DEBUG:
        fileformatter = logging.Formatter('[%(asctime)s|%(levelname)s|%(filename)s|(%(funcName)s)]-%(message)s')
    else:
        fileformatter = logging.Formatter('[%(asctime)s|%(levelname)s]-%(message)s')

    fileHandler = logging.handlers.RotatingFileHandler(log_path, maxBytes=LOG_MAX_SIZE, backupCount=LOG_FILE_CNT, encoding='utf-8')
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
                raise
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
