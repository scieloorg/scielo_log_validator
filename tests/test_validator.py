import datetime
import gzip
import tempfile
import unittest
from unittest import mock

from scielo_log_validator import exceptions, validator


class TestValidator(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
        self.log_directory_wi = 'tests/fixtures/logs/scielo.wi/'
        self.log_file_br_1 = 'tests/fixtures/logs/scielo.scl/2022-03-05_scielo-br.log.gz'
        self.log_file_cl_1_default_pattern = 'tests/fixtures/logs/scielo.cl/2024-05-15_scielo.cl.log.gz'
        self.log_file_cl_2_list_pattern = 'tests/fixtures/logs/scielo.cl/2024-09-15_scielo.cl.log.gz'
        self.log_file_cl_3_ipv6_pattern = 'tests/fixtures/logs/scielo.cl/2024-12-10_scielo.cl.log.gz'
        self.log_file_wi_1_invalid_content = 'tests/fixtures/logs/scielo.wi/2024-02-20_caribbean.scielo.org.1.log.gz'
        self.log_file_wi_2_invalid_file_name = 'tests/fixtures/logs/scielo.wi/invalid_file_name.log.gz'
        self.log_file_br_bunny = 'tests/fixtures/logs/bunnynet/2025/2025-08-17_scielo-br.log'

    def test_get_execution_mode_is_file(self):
        exec_mode = validator.get_execution_mode(self.log_file_wi_1_invalid_content)
        self.assertEqual(exec_mode, 'validate-file')

    def test_get_execution_mode_is_directory(self):
        exec_mode = validator.get_execution_mode(self.log_directory_wi)
        self.assertEqual(exec_mode, 'validate-directory')

    def test_get_execution_mode_is_invalid(self):
        path_to_non_existing_file = '/path/to/nothing'
        with self.assertRaises(FileNotFoundError):
            validator.get_execution_mode(path_to_non_existing_file)

    def test_extract_year_month_day_hour(self):
        timestamp = '12/Mar/2023:14:22:30 +0000'
        y, m, d, h = validator.get_year_month_day_hour_from_date_str(timestamp)
        self.assertEqual((y, m, d, h), (2023, 3, 12, 14))

    def test_extract_year_month_day_hour_from_timestamp_str(self):
        timestamp = '1755473648'
        y, m, d, h = validator.get_year_month_day_hour_from_timestamp(timestamp)
        self.assertEqual((y, m, d, h), (2025, 8, 17, 20))

    def test_extract_year_month_day_hour_from_timestamp_empty_str(self):
        timestamp = ""
        with self.assertRaises(exceptions.InvalidTimestampContentError):
            validator.get_year_month_day_hour_from_timestamp(timestamp)

    def test_extract_year_month_day_hour_from_timestamp_int(self):
        timestamp = 1755473648
        y, m, d, h = validator.get_year_month_day_hour_from_timestamp(timestamp)
        self.assertEqual((y, m, d, h), (2025, 8, 17, 20))

    def test_extract_year_month_day_hour_from_millisecond_timestamp(self):
        timestamp = '1785887999998'
        y, m, d, h = validator.get_year_month_day_hour_from_timestamp(timestamp)
        self.assertEqual((y, m, d, h), (2026, 8, 4, 20))

    def test_count_lines(self):
        obtained_nlines = validator.get_total_lines(self.log_file_wi_1_invalid_content)
        expected_nlines = 7160
        self.assertEqual(obtained_nlines, expected_nlines)

    def test_validate_ip_distribution_is_true(self):
        results = {
            'content': {
                'summary': {
                    'ips': {'remote': 5, 'local': 3},
                    'total_lines': 10
                }
            }
        }
        self.assertTrue(validator.validate_ip_distribution(results))

    def test_validate_ip_distribution_is_false(self):
        results = {
            'content': {
                'summary': {
                    'ips': {'remote': 0, 'local': 3},
                    'total_lines': 8
                }
            }
        }
        self.assertFalse(validator.validate_ip_distribution(results))

    def test_validate_ip_distribution_is_false_9_percent_remote(self):
        results = {
            'content': {
                'summary': {
                    'ips': {'remote': 9, 'local': 91},
                    'total_lines': 100
                }
            }
        }
        self.assertFalse(validator.validate_ip_distribution(results, 10))

    def test_validate_ip_distribution_is_true_11_percent_remote(self):
        results = {
            'content': {
                'summary': {
                    'ips': {'remote': 11, 'local': 89},
                    'total_lines': 100
                }
            }
        }
        self.assertTrue(validator.validate_ip_distribution(results, 10))

    def test_validate_date_consistency_is_true(self):
        results = {
            'path': {'date': '2023-01-01'},
            'content': {'summary': {'datetimes': {(2023, 1, 1, 0): 1}}},
            'probably_date': validator.datetime(2023, 1, 1)
        }
        self.assertTrue(validator.validate_date_consistency(results))

    def test_validate_date_consistency_is_false(self):
        results = {
            'path': {'date': '2023-01-01'},
            'content': {'summary': {'datetimes': {(2023, 10, 30, 0): 1}}},
            'probably_date': validator.datetime(2023, 10, 30)
        }
        self.assertFalse(validator.validate_date_consistency(results))

    def test_validate_path(self):
        path = self.log_file_wi_2_invalid_file_name
        results = validator.validate_path_name(path)
        self.assertIn('date', results)
        self.assertIn('paperboy', results)
        self.assertIn('mimetype', results)
        self.assertIn('extension', results)

    def test_validate_content(self):
        results = validator.validate_content(self.log_file_wi_1_invalid_content)
        self.assertIn('summary', results)

    def test_analyze_log_content_accepts_long_classic_url(self):
        long_unused_parameter = '%C3' * 2048
        line = (
            '8.8.8.8 - - [23/Jan/2026:00:00:00 -0600] '
            '"GET /scielo.php?lng=es&nrm='
            f'{long_unused_parameter}'
            '&pid=S0043-31442017000600634&script=sci_arttext&tlng=es '
            'HTTP/1.0" 200 123 "-" "Mozilla/5.0"\n'
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = f'{temp_dir}/2026-01-23_scielo.mx.log.gz'
            with gzip.open(path, 'wt') as output:
                output.write(line)

            result = validator.analyze_log_content(path, 1, 1)

        self.assertEqual(result['invalid_lines'], 0)
        self.assertEqual(result['ips']['remote'], 1)
        self.assertEqual(result['datetimes'], {(2026, 1, 23, 0): 1})

    def test_validate_content_reports_corrupted_gzip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = f'{temp_dir}/2026-09-04_scielo.pe.log.gz'
            compressed = bytearray(gzip.compress(b'valid line\n'))
            compressed[-1] ^= 0xff
            with open(path, 'wb') as output:
                output.write(compressed)

            results = validator.validate_content(path)

        self.assertEqual(results['error']['code'], 'file_read_error')
        self.assertEqual(results['error']['kind'], 'corrupted')
        self.assertIn('corrupted', results['error']['message'])

    def test_validate_content_reports_truncated_gzip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = f'{temp_dir}/2026-09-04_scielo.pe.log.gz'
            compressed = gzip.compress(b'valid line\n')
            with open(path, 'wb') as output:
                output.write(compressed[:-8])

            results = validator.validate_content(path)

        self.assertEqual(results['error']['code'], 'file_read_error')
        self.assertEqual(results['error']['kind'], 'truncated')

    def test_validate_content_reports_io_error(self):
        with mock.patch.object(
            validator.file_utils,
            'open_file',
            side_effect=PermissionError('permission denied'),
        ):
            results = validator.validate_content('/tmp/2026-09-04_scielo.pe.log.gz')

        self.assertEqual(results['error']['code'], 'file_read_error')
        self.assertEqual(results['error']['kind'], 'io')

    def test_error_suffix_does_not_determine_validation_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = f'{temp_dir}/2026-09-04-error_scielo.pe.log.gz'
            with gzip.open(path, 'wt') as output:
                output.write('request failed\n')

            results = validator.pipeline_validate(path, sample_size=1)

        self.assertNotIn('error', results['content'])
        self.assertFalse(results['is_valid']['all'])

    def test_pipeline_validate_successfully_runs(self):
        obtained_results = validator.pipeline_validate(self.log_file_wi_1_invalid_content)
        expected_results = {
            'mode': {
                'path_validation': True,
                'content_validation': True,
            },
            'path': {
                'date': '2024-02-20', 
                'paperboy': True, 
                'mimetype': 'application/gzip', 
                'extension': '.gz'
            }, 
            'content': {
                'summary': {
                    'datetimes': {
                        (2024, 2, 21, 0): 22, 
                        (2024, 2, 21, 1): 34, 
                        (2024, 2, 21, 2): 21, 
                        (2024, 2, 21, 3): 35, 
                        (2024, 2, 21, 4): 29, 
                        (2024, 2, 21, 5): 22, 
                        (2024, 2, 21, 6): 29, 
                        (2024, 2, 21, 7): 43, 
                        (2024, 2, 21, 8): 29, 
                        (2024, 2, 21, 9): 30, 
                        (2024, 2, 21, 10): 35, 
                        (2024, 2, 21, 11): 25, 
                        (2024, 2, 21, 12): 27, 
                        (2024, 2, 21, 13): 31, 
                        (2024, 2, 21, 14): 31, 
                        (2024, 2, 21, 15): 29, 
                        (2024, 2, 21, 16): 23, 
                        (2024, 2, 21, 17): 24, 
                        (2024, 2, 21, 18): 29, 
                        (2024, 2, 21, 19): 28, 
                        (2024, 2, 21, 20): 37, 
                        (2024, 2, 21, 21): 33, 
                        (2024, 2, 21, 22): 33, 
                        (2024, 2, 21, 23): 37,
                    },
                    'ips': {'local': 701, 'remote': 15, 'unknown': 0}, 
                    'invalid_lines': 0,
                    'total_lines': 7160,
                }
            }, 
            'is_valid': {
                'ips': False, 'dates': True, 'all': False}, 
                'probably_date': datetime.datetime(2024, 2, 21, 0, 0)
            }
        self.assertDictEqual(obtained_results, expected_results)
        self.assertFalse(obtained_results['is_valid']['all'])

    def test_pipeline_validate_only_path(self):
        obtained_results = validator.pipeline_validate(
            path=self.log_file_wi_1_invalid_content, 
            apply_path_validation=True, 
            apply_content_validation=False
        )

        expected_results = {
            'mode': {
                'path_validation': True,
                'content_validation': False,
            },
            'path': {
                'date': '2024-02-20', 

                'paperboy': True, 
                'mimetype': 'application/gzip', 
                'extension': '.gz'
            }, 
        }
        self.assertDictEqual(obtained_results, expected_results)

    def test_pipeline_validate_only_content(self):
        obtained_results = validator.pipeline_validate(
            path=self.log_file_wi_1_invalid_content, 
            apply_path_validation=False, 
            apply_content_validation=True
        )

        expected_results = {
            'mode': {
                'path_validation': False,
                'content_validation': True,
            },
            'is_valid': {'ips': False, 'dates': False, 'all': False}, 
            'probably_date': datetime.datetime(2024, 2, 21, 0, 0),
            'content': {
                'summary': {
                    'datetimes': {
                        (2024, 2, 21, 0): 22, 
                        (2024, 2, 21, 1): 34, 
                        (2024, 2, 21, 2): 21, 
                        (2024, 2, 21, 3): 35, 
                        (2024, 2, 21, 4): 29, 
                        (2024, 2, 21, 5): 22, 
                        (2024, 2, 21, 6): 29, 
                        (2024, 2, 21, 7): 43, 
                        (2024, 2, 21, 8): 29, 
                        (2024, 2, 21, 9): 30, 
                        (2024, 2, 21, 10): 35, 
                        (2024, 2, 21, 11): 25, 
                        (2024, 2, 21, 12): 27, 
                        (2024, 2, 21, 13): 31, 
                        (2024, 2, 21, 14): 31, 
                        (2024, 2, 21, 15): 29, 
                        (2024, 2, 21, 16): 23, 
                        (2024, 2, 21, 17): 24, 
                        (2024, 2, 21, 18): 29, 
                        (2024, 2, 21, 19): 28, 
                        (2024, 2, 21, 20): 37, 
                        (2024, 2, 21, 21): 33, 
                        (2024, 2, 21, 22): 33, 
                        (2024, 2, 21, 23): 37,
                    },
                    'ips': {'local': 701, 'remote': 15, 'unknown': 0}, 
                    'invalid_lines': 0,
                    'total_lines': 7160,
                }
            }, 
        }
        self.assertDictEqual(obtained_results, expected_results)
        self.assertFalse(obtained_results['is_valid']['all'])

    def test_pipeline_validate_with_sample_size_zero(self):
        obtained_results = validator.pipeline_validate(self.log_file_br_1, sample_size=0)
        self.assertTrue(obtained_results['is_valid']['all'])

    def test_pipeline_validate_with_sample_size_greater_than_one(self):
        obtained_results = validator.pipeline_validate(self.log_file_wi_1_invalid_content, sample_size=100)
        self.assertTrue(obtained_results['is_valid']['dates'])

    def test_get_date_frequencies(self):
        results = {
            'content': {
                'summary': {
                    'datetimes': {(2023, 1, 1, 0): 1, (2023, 1, 1, 1): 2}
                }
            }
        }
        frequencies = validator.get_date_frequencies(results)
        self.assertEqual(frequencies, {(2023, 1, 1): 3})

    def test_compute_probably_date(self):
        results = {
            'content': {
                'summary': {
                    'datetimes': {(2023, 1, 1, 0): 1, (2023, 1, 1, 1): 2}
                }
            }
        }
        self.assertEqual(validator.get_probably_date(results), validator.datetime(2023, 1, 1))

    def test_line_with_default_pattern(self):
        results = validator.pipeline_validate(
            path=self.log_file_cl_1_default_pattern,
            apply_path_validation=True,
            apply_content_validation=True,
        )

        expected = {
            'mode': {
                'path_validation': True,
                'content_validation': True,
            },
            'path': {
                'date': '2024-05-15',
                'paperboy': True,
                'mimetype': 'application/gzip',
                'extension': '.gz'
            },
            'content': {
                'summary': {
                    'ips': {'local': 0, 'remote': 100, 'unknown': 0},
                    'datetimes': {
                        (2024, 5, 15, 0): 30,
                        (2024, 5, 16, 0): 70
                    },
                    'invalid_lines': 0,
                    'total_lines': 100
                }
            },
            'is_valid': {
                'ips': True,
                'dates': True,
                'all': True
            },
            'probably_date': datetime.datetime(2024, 5, 16, 0, 0)
        }

        self.assertDictEqual(results, expected)

    def test_line_with_list_pattern(self):
        results = validator.pipeline_validate(
            sample_size=1,
            path=self.log_file_cl_2_list_pattern,
            apply_path_validation=True,
            apply_content_validation=True,
        )
        expected = {
            'mode': {
                'path_validation': True,
                'content_validation': True,
            },
            'path': {
                'date': '2024-09-15',
                'paperboy': True,
                'mimetype': 'application/gzip',
                'extension': '.gz'
            },
            'content': {
                'summary': {
                    'ips': {'local': 0, 'remote': 95, 'unknown': 6},
                    'datetimes': {
                        (2024, 9, 15, 0): 71,
                        (2024, 9, 16, 0): 24
                    },
                    'invalid_lines': 6,
                    'total_lines': 101
                }
            },
            'is_valid': {
                'ips': True,
                'dates': True,
                'all': True
            },
            'probably_date': datetime.datetime(2024, 9, 15, 0, 0)
        }

        self.assertDictEqual(results, expected)
    
    def test_line_with_ipv6_pattern(self):
        results = validator.pipeline_validate(
            sample_size=1,
            path=self.log_file_cl_3_ipv6_pattern,
            apply_path_validation=True,
            apply_content_validation=True,
        )
        expected = {
            'mode': {
                'path_validation': True,
                'content_validation': True,
            },
            'path': {
                'date': '2024-12-10',
                'paperboy': True,
                'mimetype': 'application/gzip',
                'extension': '.gz'
            },
            'content': {
                'summary': {
                    'ips': {'local': 0, 'remote': 29, 'unknown': 2},
                    'datetimes': {
                        (2024, 12, 10, 0): 19,
                        (2024, 12, 11, 0): 10
                    },
                    'invalid_lines': 2,
                    'total_lines': 31
                }
            },
            'is_valid': {
                'ips': True,
                'dates': True,
                'all': True
            },
            'probably_date': datetime.datetime(2024, 12, 10, 0, 0)
        }

        self.assertDictEqual(results, expected)

    def test_line_with_bunny_pattern(self):
        results = validator.pipeline_validate(
            sample_size=1,
            path=self.log_file_br_bunny,
            apply_path_validation=True,
            apply_content_validation=True,
        )
        expected = {
            'mode': {
                'path_validation': True,
                'content_validation': True,
            },
            'path': {
                'date': '2025-08-17',

                'paperboy': False,
                'mimetype': 'text/plain',
                'extension': '.log'
            },
            'content': {
                'summary': {
                    'ips': {'local': 0, 'remote': 149, 'unknown': 1},
                    'datetimes': {
                        (2025, 8, 16, 20): 10,
                        (2025, 8, 16, 23): 19,
                        (2025, 8, 17, 0): 29,
                        (2025, 8, 17, 1): 58,
                        (2025, 8, 17, 2): 3,
                        (2025, 8, 17, 3): 17,
                        (2025, 8, 17, 4): 3,
                        (2025, 8, 17, 5): 1,
                        (2025, 8, 17, 19): 2,
                        (2025, 8, 17, 20): 7,
                    },
                    'invalid_lines': 1,
                    'total_lines': 150
                }
            },
            'is_valid': {
                'ips': True,
                'dates': True,
                'all': True
            },
            'probably_date': datetime.datetime(2025, 8, 17, 0, 0)
        }

        self.assertDictEqual(results, expected)

    def test_bunny_cache_status_variants_are_valid_content(self):
        for cache_status in ('REVALIDATED', '-'):
            with self.subTest(cache_status=cache_status):
                with tempfile.TemporaryDirectory() as temp_dir:
                    path = f'{temp_dir}/2025-09-10_scielo-br.log.gz'
                    with gzip.open(path, 'wt') as output:
                        output.write(
                            f'{cache_status}|200|1757548786|5432|4339610|'
                            '186.225.0.1|-|https://www.scielo.br/j/neco/a/test/|'
                            'BR|Mozilla/5.0|8dbbeef65a64c5235f863868a7c94d70|BR\n'
                        )

                    results = validator.analyze_log_content(
                        path,
                        total_lines=1,
                        sample_lines=1,
                    )

                self.assertEqual(results['invalid_lines'], 0)
                self.assertEqual(results['ips']['remote'], 1)

    def test_line_with_bucketed_bunny_timestamp(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = f'{temp_dir}/2025-08-17_scielo-br.log.gz'
            with gzip.open(path, 'wt') as fout:
                fout.write(
                    'HIT|200|1766620|5615808|4384504|20.90.7.0|-|'
                    'https://books.scielo.org/id/3yrrb/pdf/benchimol-9788575412350.pdf|FR|'
                    'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; '
                    'ChatGPT-User/1.0; +https://openai.com/bot|'
                    'ee24594ec72285fab56eb85c792c56c0|GB\n'
                )

            results = validator.pipeline_validate(
                sample_size=1,
                path=path,
                apply_path_validation=True,
                apply_content_validation=True,
            )

        self.assertEqual(results['path']['date'], '2025-08-17')
        self.assertEqual(results['path']['extension'], '.gz')
        self.assertEqual(results['content']['summary']['ips'], {'local': 0, 'remote': 1, 'unknown': 0})
        self.assertEqual(results['content']['summary']['invalid_lines'], 0)
        self.assertEqual(results['content']['summary']['datetimes'], {(2025, 12, 24, 20): 1})
        self.assertEqual(results['probably_date'].date(), datetime.date(2025, 12, 24))
        self.assertTrue(results['is_valid']['ips'])

    def test_line_with_millisecond_bunny_timestamp(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = f'{temp_dir}/2026-08-04_scielo-br.log.gz'
            with gzip.open(path, 'wt') as fout:
                fout.write(
                    'HIT|200|1785887999998|5432|4339610|186.225.0.1|-|'
                    'https://www.scielo.br/j/neco/a/test/|IQ2|'
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/151.0.0.0 Safari/537.36|'
                    '8dbbeef65a64c5235f863868a7c94d70|US\n'
                )

            results = validator.pipeline_validate(
                sample_size=1,
                path=path,
                apply_path_validation=True,
                apply_content_validation=True,
            )

        self.assertEqual(results['path']['date'], '2026-08-04')
        self.assertEqual(results['content']['summary']['invalid_lines'], 0)
        self.assertEqual(
            results['content']['summary']['datetimes'],
            {(2026, 8, 4, 20): 1},
        )
        self.assertTrue(results['is_valid']['all'])

    def test_get_probably_date_returns_most_frequent(self):
        results = {
            'content': {
                'summary': {
                    'datetimes': {
                        (2023, 3, 12, 14): 10,
                        (2023, 3, 13, 10): 5,
                        (2023, 3, 11, 8): 2,
                    }
                }
            }
        }
        result = validator.get_probably_date(results)
        self.assertIsInstance(result, datetime.datetime)
        self.assertEqual(result.year, 2023)
        self.assertEqual(result.month, 3)
        self.assertEqual(result.day, 12)

    def test_get_probably_date_empty_dict(self):
        results = {'content': {'summary': {'datetimes': {}}}}
        result = validator.get_probably_date(results)
        self.assertIsInstance(result, dict)
        self.assertIn('error', result)
        self.assertEqual(result['error'], 'Date dictionary is empty')
