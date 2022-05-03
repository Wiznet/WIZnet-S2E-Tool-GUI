import os
import logging
import logging.handlers


def getLogger(path, name):
    """
    - path: base path
    - name: logger name
    Directory will be created with name.
    """
    # Config variables
    LOG_MAX_SIZE = 1024 * 1024 * 5
    LOG_FILE_CNT = 5
    LOG_LEVEL = logging.INFO

    LOG_DIR = os.path.join(path, f'.{name}')
    if not os.path.isdir(LOG_DIR):
        os.mkdir(LOG_DIR)

    log_path = os.path.join(LOG_DIR, f'{name}.log')

    logger = logging.getLogger(log_path)
    logger.setLevel(LOG_LEVEL)

    logging.handlers.RotatingFileHandler(log_path, maxBytes=LOG_MAX_SIZE, backupCount=LOG_FILE_CNT)

    # log format
    if LOG_LEVEL == logging.INFO:
        fileformatter = logging.Formatter(
            '[%(asctime)s|%(levelname)s]-%(message)s')
    elif LOG_LEVEL == logging.DEBUG:
        fileformatter = logging.Formatter(
            '[%(asctime)s|%(levelname)s|%(filename)s|(%(funcName)s)]-%(message)s')

    fileHandler = logging.FileHandler(log_path, encoding='utf-8')
    streamHandler = logging.StreamHandler()

    fileHandler.setFormatter(fileformatter)
    streamHandler.setFormatter(fileformatter)

    # log handler
    logger.addHandler(fileHandler)
    logger.addHandler(streamHandler)

    return logger


if __name__ == "__main__":
    # 기준 경로, 이름
    logger = getLogger(os.path.expanduser('~'), 'wizconfig')
