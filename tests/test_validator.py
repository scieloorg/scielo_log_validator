import datetime
import unittest

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
        self.assertFalse(validator.validate_ip_distribution(results))

    def test_validate_ip_distribution_is_true_11_percent_remote(self):
        results = {
            'content': {
                'summary': {
                    'ips': {'remote': 11, 'local': 89},
                    'total_lines': 100
                }
            }
        }
        self.assertTrue(validator.validate_ip_distribution(results))

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
        self.assertIn('collection', results)
        self.assertIn('paperboy', results)
        self.assertIn('mimetype', results)
        self.assertIn('extension', results)

    def test_validate_content(self):
        results = validator.validate_content(self.log_file_wi_1_invalid_content)
        self.assertIn('summary', results)

    def test_pipeline_validate_successfully_runs(self):
        obtained_results = validator.pipeline_validate(self.log_file_wi_1_invalid_content)
        expected_results = {
            'mode': {
                'path_validation': True,
                'content_validation': True,
            },
            'path': {
                'date': '2024-02-20', 
                'collection': 'wid', 
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
                'collection': 'wid', 
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

    def test_pipeline_validate_with_directory(self):
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
                'collection': 'chl',
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
                'collection': 'chl',
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
                'collection': 'chl',
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
                'collection': 'scl',
                'paperboy': False,
                'mimetype': 'text/plain',
                'extension': '.log'
            },
            'content': {
                'summary': {
                    'ips': {'local': 0, 'remote': 145, 'unknown': 5},
                    'datetimes': {
                        (2025, 8, 16, 20): 10,
                        (2025, 8, 16, 23): 19,
                        (2025, 8, 17, 0): 25,
                        (2025, 8, 17, 1): 58,
                        (2025, 8, 17, 2): 3,
                        (2025, 8, 17, 3): 17,
                        (2025, 8, 17, 4): 3,
                        (2025, 8, 17, 5): 1,
                        (2025, 8, 17, 19): 2,
                        (2025, 8, 17, 20): 7,
                    },
                    'invalid_lines': 5,
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
