from gzip import GzipFile

import bz2
import magic
import os
import re

from scielo_log_validator import exceptions, values, date_utils


# Define the default handlers for different MIME types
DEFAULT_MIME_HANDLERS = {
    'application/gzip': GzipFile,
    'application/x-gzip': GzipFile,
    'application/x-bzip2': bz2.open,
    'application/text': open,
    'text/plain': open,
    'application/x-empty': None
}


def open_file(path, mime_handlers=DEFAULT_MIME_HANDLERS, buffer_size=2048):
    """
    Opens a file and returns its content based on its MIME type.

    Args:
        path (str): The path to the file to be opened.
        mime_handlers (dict, optional): A dictionary mapping MIME types to handler functions. 
                                        Defaults to DEFAULT_MIME_HANDLERS.

    Raises:
        exceptions.InvalidLogFileMimeError: If the file's MIME type is not supported.
        exceptions.LogFileIsEmptyError: If the file is empty.

    Returns:
        object: The content of the file as processed by the appropriate handler function.
    """
    file_mime = extract_mime_from_path(path, buffer_size)

    if file_mime not in mime_handlers:
        raise exceptions.InvalidLogFileMimeError('File %s is invalid' % path)

    if file_mime == 'application/x-empty':
        raise exceptions.LogFileIsEmptyError('File %s is empty' % path)

    if file_mime in ('application/gzip', 'application/x-gzip'):
        open_mode = 'rb'
    else:
        open_mode = 'r'
    
    return mime_handlers[file_mime](path, open_mode)


def extract_mime_from_path(path, buffer_size=2048):
    """
    Determines the MIME type of a file based on its content.

    Args:
        path (str): The file path to read and determine the MIME type.
        buffer_size (int, optional): The number of bytes to read from the file for MIME type detection. Defaults to 2048.

    Returns:
        str: The MIME type of the file.

    Raises:
        FileNotFoundError: If the file at the given path does not exist.
        IOError: If there is an error reading the file.
    """
    mime = magic.Magic(mime=True)
    with open(path, 'rb') as fin:
        magic_code = mime.from_buffer(fin.read(buffer_size))
        return magic_code


def extract_collection_from_path(path, collection_identifiers=None):
    """
    Extracts the collection identifier from the given file path.

    This function iterates over a dictionary of collection file name identifiers
    and checks if any of these identifiers are present in the provided file path.
    If a match is found, the corresponding collection ID is returned.

    Args:
        path (str): The file path to be checked for collection identifiers.
        collection_identifiers (dict, optional): A dictionary where keys are file name identifiers 
                                                 and values are collection IDs. 
                                                 If not provided, defaults to values.COLLECTION_FILE_NAME_IDENTIFIERS.

    Returns:
        str: The collection identifier if found in the file path, otherwise None.
    """
    if collection_identifiers is None:
        collection_identifiers = values.COLLECTION_FILE_NAME_IDENTIFIERS

    for file_identifier, collection_id in collection_identifiers.items():
        if file_identifier in path:
            return collection_id
    return None


def extract_file_extension_from_path(path):
    """
    Extracts the file extension from a given file path.

    Args:
        path (str): The file path from which to extract the extension.

    Returns:
        str: The file extension, including the leading dot (e.g., '.txt').

    Raises:
        LogFileExtensionUndetectable: If the file extension cannot be determined.
    """
    file = os.path.basename(path)
    _, extension = os.path.splitext(file)
    if extension:
        return extension
    raise exceptions.LogFileExtensionUndetectableError('Could not extract extension from %s' % path)


def extract_date_from_path(path):
    """
    Extracts a date from a file name based on predefined patterns.

    Args:
        path (str): The file path from which to extract the date.

    Returns:
        str: The extracted date in a cleaned format if a pattern matches, otherwise None.

    Raises:
        None
    """
    _, tail = os.path.split(path)
    for pattern in [values.PATTERN_Y_M_D, values.PATTERN_YMD]:
        match = re.search(pattern, tail)
        if match:
            return date_utils.clean_date(match.group())


def has_paperboy_format(path):
    """
    Checks if the given file path has a filename that matches the Paperboy format.

    Args:
        path (str): The file path to check.

    Returns:
        bool: True if the filename matches the Paperboy format, False otherwise.
    """
    _, tail = os.path.split(path)
    if re.match(values.PATTERN_PAPERBOY, tail):
        return True
    return False
