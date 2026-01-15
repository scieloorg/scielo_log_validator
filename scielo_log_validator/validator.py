# -*- coding: UTF-8 -*-
from argparse import ArgumentParser
from datetime import datetime

import os
import operator
import re

from ipaddress import ip_address

from scielo_log_validator import date_utils, exceptions, file_utils, values


# Minimum acceptable percentage of remote IPs to consider the log file valid
MIN_ACCEPTABLE_PERCENT_OF_REMOTE_IPS = float(os.environ.get('MIN_ACCEPTABLE_PERCENT_OF_REMOTE_IPS', '10'))

# Minimum number of sample lines to be considered in the content validation
MIN_NUMBER_OF_SAMPLE_LINES = int(os.environ.get('MIN_NUMBER_OF_SAMPLE_LINES', '1000'))

# Default message for the application
COMMAND_LINE_SCRIPT_MESSAGE = '''
SciELO Log Validator

This script is responsible for validating log usage records obtained from the SciELO Network Apache Servers.
A validation is composed of two main aspects as follows:
    1) Validation with regard to the file name
    2) Validation with regard to the file content
'''


def get_execution_mode(path):
    """
    Determines the execution mode based on the given path.

    Args:
        path (str): The path to check.

    Returns:
        str: 'validate-file' if the path is a file, 'validate-directory' if the path is a directory.

    Raises:
        FileNotFoundError: If the path does not exist.
    """
    if os.path.exists(path):
        if os.path.isfile(path):
            return 'validate-file'
        if os.path.isdir(path):
            return 'validate-directory'
    raise FileNotFoundError()


def get_ip_type(ip):
    """
    Determine the type of an IP address.
    Args:
        ip (str): The IP address to be evaluated.
    Returns:
        str: The type of the IP address, which can be one of the following:
            - 'remote': if the IP address is a global address.
            - 'local': if the IP address is private, loopback, or link-local.
            - 'unknown': if the IP address is invalid or its type cannot be determined.
    """

    try:
        ipa = ip_address(ip)
    except ValueError:
        return 'unknown'

    if ipa.is_global:
        return 'remote'
    elif ipa.is_private or ipa.is_loopback or ipa.is_link_local:
        return 'local'

    return 'unknown'


def get_year_month_day_hour_from_timestamp(timestamp):
    """
    Extracts the year, month, day, and hour from a timestamp.

    Args:
        timestamp:

    Returns
        tuple: A tuple containing the year (int), month (int), day (int), and hour (int).

    Example:
         >>> get_year_month_day_hour_from_timestamp("1755473648")
         (2025, 8, 17, 20)
    """
    if isinstance(timestamp, str):
        try:
            timestamp = int(timestamp)
        except ValueError:
            raise exceptions.InvalidTimestampContentError("Timestamp must be an integer or a string representing an integer")

    dt = datetime.fromtimestamp(timestamp)
    return dt.year, dt.month, dt.day, dt.hour


def get_year_month_day_hour_from_date_str(log_date):
    """
    Extracts the year, month, day, and hour from a log date string.

    Args:
        log_date (str): The log date string in the format 'dd/Mon/YYYY:HH:MM:SS [offset]'.

    Returns:
        tuple: A tuple containing the year (int), month (int), day (int), and hour (int).

    Example:
        >>> get_year_month_day_hour_from_date_str('12/Mar/2023:14:22:30 +0000')
        (2023, 3, 12, 14)
    """
    # Discard offset
    log_date = log_date.split(' ')[0]
    dt = datetime.strptime(log_date, '%d/%b/%Y:%H:%M:%S')
    return dt.year, dt.month, dt.day, dt.hour


def get_date_frequencies(results):
    """
    Gets the date frequencies from the content analysis results.

    Args:
        results (dict): The results dictionary containing the dates from the file content.

    Returns:
        dict: A dictionary where the keys are tuples (year, month, day) and the values are the frequencies of those dates.
    """
    file_content_dates = results.get('content', {}).get('summary', {}).get('datetimes', {})

    ymd_to_freq = {}
    for k, frequency in file_content_dates.items():
        year, month, day, _ = k
        if (year, month, day) not in ymd_to_freq:
            ymd_to_freq[(year, month, day)] = 0
        ymd_to_freq[(year, month, day)] += frequency

    return ymd_to_freq


def get_probably_date(results):
    """
    Computes the most probable date from the content analysis results.

    Args:
        results (dict): The results dictionary containing the dates from the file content.

    Returns:
        datetime: The most probable date based on the frequency of occurrences.
        dict: An error message if the date cannot be determined.
    """
    ymd_to_freq = get_date_frequencies(results)

    try:
        # Sort the dates by frequency and get the most frequent one
        ymd, _ = sorted(ymd_to_freq.items(), key=operator.itemgetter(1)).pop()
        y, m, d = ymd
        return datetime(y, m, d)
    except ValueError:
        return {'error': 'Could not determine a probable date'}
    except IndexError:
        return {'error': 'Date dictionary is empty'}


def get_total_lines(path, buffer_size=2048):
    """
    Counts the number of lines in a file.

    Args:
        path (str): The path to the file.
        buffer_size (int, optional): The buffer size for reading the file. Defaults to 2048.

    Returns:
        int: The number of lines in the file.

    Raises:
        exceptions.TruncatedLogFileError: If the file is truncated.
        exceptions.InvalidLogFileMimeError: If the file has an invalid MIME type.
        exceptions.LogFileIsEmptyError: If the file is empty.
    """
    try:
        with file_utils.open_file(path=path, buffer_size=buffer_size) as fin:
            return sum(1 for _ in fin)
    except EOFError:
        raise exceptions.TruncatedLogFileError('Arquivo %s está truncado' % path)
    except exceptions.InvalidLogFileMimeError:
        raise exceptions.InvalidLogFileMimeError('Arquivo %s é inválido' % path)
    except exceptions.LogFileIsEmptyError:
        raise exceptions.LogFileIsEmptyError('Arquivo %s está vazio' % path)


def analyze_log_content(path, total_lines, sample_lines):
    """
    Analyzes a log file and provides a summary of its content.
    Args:
        path (str): The file path to the log file.
        total_lines (int): The total number of lines in the log file.
        sample_lines (int): The number of lines to sample for analysis.
    Returns:
        dict: A dictionary containing the following keys:
            - 'ips' (dict): A dictionary with counts of 'local' and 'remote' IP addresses.
            - 'datetimes' (dict): A dictionary with counts of occurrences of each datetime (year, month, day, hour).
            - 'invalid_lines' (int): The number of lines that could not be parsed.
            - 'total_lines' (int): The total number of lines in the log file.
    Raises:
        exceptions.LogFileIsEmptyError: If the log file is empty.
    """
    ips = {'local': 0, 'remote': 0, 'unknown': 0}
    datetimes = {}
    invalid_lines = 0

    try:
        eval_lines = set(range(0, total_lines + 1, int(total_lines/sample_lines)))
    except ZeroDivisionError:
        raise exceptions.LogFileIsEmptyError('Arquivo %s está vazio' % path)

    line_counter = 0

    with file_utils.open_file(path) as data:
        for line in data:
            try:
                decoded_line = line.decode().strip() if isinstance(line, bytes) else line.strip()
            except UnicodeDecodeError:
                decoded_line = line.decode('utf-8', errors='ignore').strip() if isinstance(line, bytes) else line.strip()
            line_counter += 1

            if line_counter in eval_lines:
                patterns = [
                    values.PATTERN_NCSA_EXTENDED_LOG_FORMAT,
                    values.PATTERN_NCSA_EXTENDED_LOG_FORMAT_DOMAIN,
                    values.PATTERN_NCSA_EXTENDED_LOG_FORMAT_WITH_IP_LIST,
                    values.PATTERN_NCSA_EXTENDED_LOG_FORMAT_DOMAIN_WITH_IP_LIST,
                    values.PATTERN_BUNNY,
                ]

                match = None
                ip_type = 'unknown'

                for pattern in patterns:
                    match = re.match(pattern, decoded_line)

                    # Match the pattern and extract the IP address
                    if match:
                        content = match.groupdict()
                        
                        ip_value = content.get('ip')
                        ip_type = get_ip_type(ip_value)

                        if ip_type != 'unknown':
                            break
                        else:
                            for i in content.get('ip_list', '').split(','):
                                ip_type = get_ip_type(i.strip())
                                if ip_type != 'unknown':
                                    break

                            if ip_type != 'unknown':
                                break

                ips[ip_type] += 1

                # Match the date pattern and extract the datetime
                if match:
                    content = match.groupdict()

                    matched_datetime = content.get('date', '')
                    matched_timestamp = content.get('timestamp', '')

                    try:
                        if matched_datetime:
                            year, month, day, hour = get_year_month_day_hour_from_date_str(matched_datetime)
                        elif matched_timestamp:
                            year, month, day, hour = get_year_month_day_hour_from_timestamp(matched_timestamp)

                        if (year, month, day, hour) not in datetimes:
                            datetimes[(year, month, day, hour)] = 0
                        datetimes[(year, month, day, hour)] += 1

                    except (ValueError, exceptions.InvalidTimestampContentError):
                        invalid_lines += 1

                else:
                    invalid_lines += 1

    return {
        'ips': ips,
        'datetimes': datetimes,
        'invalid_lines': invalid_lines,
        'total_lines': total_lines
    }


def validate_ip_distribution(results):
    """
    Validates the distribution of remote and local IPs in the given results.

    This function checks the percentage of remote and local IPs relative to the total number of lines.
    It returns True if the percentage of remote IPs is higher than the percentage of local IPs or if
    the percentage of remote IPs exceeds a predefined minimum acceptable percentage.

    Args:
        results (dict): A dictionary containing the results with the following structure:
            {
                'content': {
                    'summary': {
                        'ips': {
                            'remote': int,
                            'local': int
                        },
                        'total_lines': int
                    }
                }
            }

    Returns:
        bool: True if the distribution of IPs is valid, False otherwise.
    """
    remote_ips = results.get('content', {}).get('summary', {}).get('ips', {}).get('remote', 0)
    local_ips = results.get('content', {}).get('summary', {}).get('ips', {}).get('local', 0)
    total_lines = results.get('content', {}).get('summary', {}).get('total_lines', 0)

    # If there are no lines with detected IPs or the validation was not executed
    if (remote_ips == 0 and local_ips == 0) or total_lines == 0:
        return False

    # Compute the percentage of remote IPs relative to the total number of lines
    percent_remote_ips = float(remote_ips) / float(total_lines) * 100

    # Compute the percentage of local IPs relative to the total number of lines
    percent_local_ips = float(local_ips) / float(total_lines) * 100

    # The file is valid if there is a higher percentage of remote IPs
    if percent_remote_ips > percent_local_ips:
        return True

    # The file is valid if there is a minimum percentage of remote IPs
    if percent_remote_ips > MIN_ACCEPTABLE_PERCENT_OF_REMOTE_IPS:
        return True

    return False


def validate_date_consistency(results, days_delta=5):
    """
    Validates the consistency of dates from the file path and content to determine if they are significantly different.

    Args:
        results (dict): The results dictionary containing the file path date and content dates.
        days_delta (int): The number of days to determine the threshold for significant difference.

    Returns:
        bool: True if the dates are not significantly different, False otherwise.
    """
    # Ensure that the days delta is positive
    if days_delta < 0:
        days_delta = 5

    file_path_date = results.get('path', {}).get('date', '')
    file_content_dates = results.get('content', {}).get('summary', {}).get('datetimes', {})
    probably_date = results.get('probably_date')

    # If there is no content or the validation was not executed
    if not file_path_date or not file_content_dates:
        return False

    # The file is invalid if it is not possible to obtain a date from the file name
    try:
        file_date_object = datetime.strptime(file_path_date, '%Y-%m-%d')
    except ValueError:
        return False

    # If the probable date of the file is significantly earlier than the date indicated in the file name
    if date_utils.date_is_significantly_earlier(probably_date, file_date_object, days_delta):
        return False

    # If the probable date of the file is significantly later than the date indicated in the file name
    if date_utils.date_is_significantly_later(probably_date, file_date_object, days_delta):
        return False

    return True


def validate_path_name(path):
    """
    Validates the file path by extracting various attributes.

    Args:
        path (str): The file path to be validated.

    Returns:
        dict: A dictionary containing the extracted attributes from the file path.
    """
    results = {}

    # List of functions to extract attributes from the file path
    for func_impl, func_name in [
        (file_utils.extract_date_from_path, 'date'),
        (file_utils.extract_collection_from_path, 'collection'),
        (file_utils.has_paperboy_format, 'paperboy'),
        (file_utils.extract_mime_from_path, 'mimetype'),
        (file_utils.extract_file_extension_from_path, 'extension'),
    ]:
        try:
            results[func_name] = func_impl(path)
        except Exception as e:
            results[func_name] = {'error': str(e)}

    return results


def validate_content(path, sample_size=0.1, buffer_size=2048, min_lines=MIN_NUMBER_OF_SAMPLE_LINES):
    """
    Validates the content of a log file by analyzing a sample of its lines.

    Args:
        path (str): The file path to the log file.
        sample_size (float): The fraction of lines to sample for analysis (default is 0.1).

    Returns:
        dict: A dictionary containing the summary of the content analysis.

    Raises:
        exceptions.TruncatedLogFileError: If the log file is truncated.
        exceptions.InvalidLogFileMimeError: If the log file has an invalid MIME type.
        exceptions.LogFileIsEmptyError: If the log file is empty.
    """
    # Ensure that the sample size is within the valid range
    if sample_size > 1.0 or sample_size < 0.001:
        sample_size = 1.0

    try:
        total_lines = get_total_lines(path=path, buffer_size=buffer_size)
        if total_lines <= min_lines:
            sample_size = 1.0
        sample_lines = int(total_lines * sample_size)
        return {'summary': analyze_log_content(path, total_lines, sample_lines)}
    except exceptions.TruncatedLogFileError:
        return {'summary': {'total_lines': {'error': 'File is truncated'},}}
    except exceptions.InvalidLogFileMimeError:
        return {'summary': {'total_lines': {'error': 'File is invalid'},}}
    except exceptions.LogFileIsEmptyError:
        return {'summary': {'total_lines': {'error': 'File is empty'},}}


def pipeline_validate(path, sample_size=0.1, buffer_size=2048, days_delta=5, apply_path_validation=True, apply_content_validation=True):
    """
    Validates a log file by applying various validation checks.
    
    Args:
        path (str): The file path to the log file to be validated.
        sample_size (float, optional): The percentage of the log file to sample for content validation. Defaults to 0.1.
        buffer_size (int, optional): The buffer size for file type checking. Defaults to 2048.
        days_delta (int, optional): The number of days to determine the threshold for significant date difference. Defaults to 5.
        apply_path_validation (bool, optional): Whether to apply path validation. Defaults to True.
        apply_content_validation (bool, optional): Whether to apply content validation. Defaults to True.
    
    Returns:
        dict: A dictionary containing the results of the validation checks. The keys include:
            - 'path': The result of the path validation (if applied).
            - 'content': The result of the content validation (if applied).
            - 'is_valid': A dictionary containing:
                - 'ips': The result of the IP distribution validation.
                - 'dates': The result of the date consistency validation.
                - 'all': A boolean indicating if both IP and date validations passed.
            - 'probably_date': The probable date extracted from the log file.
    """
    results = {'mode': {'path_validation': apply_path_validation, 'content_validation': apply_content_validation}}

    if apply_path_validation:
        results['path'] = validate_path_name(path)
    
    if apply_content_validation:
        results['content'] = validate_content(path=path, sample_size=sample_size, buffer_size=buffer_size)
        results['is_valid'] = {'ips': validate_ip_distribution(results)}
        results['probably_date'] = get_probably_date(results)
        results['is_valid'].update({'dates': validate_date_consistency(results, days_delta=days_delta)})
        results['is_valid'].update({'all': results['is_valid']['ips'] and results['is_valid']['dates']})

    return results


def main():
    parser = ArgumentParser()

    parser.add_argument('-p', '--path', help='File or directory to be checked', required=True)
    parser.add_argument('-s', '--sample_size', help='Sample size to be checked (must be between 0 and 1)', default=0.1, type=float)
    parser.add_argument('-b', '--buffer_size', help='Buffer size for file type checking', default=2048, type=int)
    parser.add_argument('-d', '--days_delta', help='Number of days to determine the threshold for significant date difference', default=5, type=int)
    parser.add_argument('--no_path_validation', help='Deactivate path validation', action='store_false', dest='apply_path_validation', default=True)
    parser.add_argument('--no_content_validation', help='Deactivate content validation', action='store_false', dest='apply_content_validation', default=True)

    params = parser.parse_args()

    # Determine the execution mode based on the provided path
    execution_mode = get_execution_mode(params.path)

    print(COMMAND_LINE_SCRIPT_MESSAGE)
    from pprint import pprint

    if execution_mode == 'validate-file':
        # Validate a single file
        results = pipeline_validate(
            path=params.path, 
            sample_size=params.sample_size,
            buffer_size=params.buffer_size,
            days_delta=params.days_delta,
            apply_path_validation=params.apply_path_validation,
            apply_content_validation=params.apply_content_validation)
        print(params.path)
        pprint(results)

    elif execution_mode == 'validate-directory':
        # Validate all files in a directory
        for root, _, files in os.walk(params.path):
            for file in files:
                file_path = os.path.join(root, file)
                results = pipeline_validate(
                    path=file_path, 
                    sample_size=params.sample_size,
                    buffer_size=params.buffer_size,
                    days_delta=params.days_delta,
                    apply_path_validation=params.apply_path_validation,
                    apply_content_validation=params.apply_content_validation)
                print(file_path)
                pprint(results)
