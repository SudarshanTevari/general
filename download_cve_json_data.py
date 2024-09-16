import os
import requests
import subprocess
import logging
import traceback
import argparse
from logging_file import logger, upload_log_to_s3
from datetime import datetime

log_file_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file_name = f'{log_file_timestamp}_download_cve_json_files.log'
log_file_path = f'/home/ubuntu/log_files/download_cve_json_script_log/{log_file_name}'

log_dir = os.path.dirname(log_file_path)
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

S3_BUCKET = '20231103-application-data'
S3_LOG_KEY = f'app_log/download_cve_json_script_log/{log_file_name}'

logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(log_file_path, mode="a+")
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)-10s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
logger.addHandler(file_handler)

parser = argparse.ArgumentParser()
parser.add_argument('--log', action='store_true', help='Print log messages to the terminal.')
parser.add_argument('--csv', action='store_true', help='Read data from json and create csv file of CVEs.')
args = parser.parse_args()

if args.log:
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)-10s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(stream_handler)

# Define URLs and paths
base_url = "https://nvd.nist.gov/feeds/json/cve/1.1/nvdcve-1.1-{year}.json.gz"
file_path_template = "/home/ubuntu/log_files/cve_json_files/nvdcve-1.1-{year}.json"

years = range(2002, 2025)

urls = [base_url.format(year=year) for year in years]
cve_json_file_path_list = [file_path_template.format(year=year) for year in years]

download_path = '/home/ubuntu/log_files/cve_json_files'
script_path = '/home/ubuntu/python_app'
python_script = 'cve_json_to_db.py'

def remove_existing_files(path, filenames):
    for filename in filenames:
        gz_file_path = os.path.join(path, filename)
        if os.path.exists(gz_file_path):
            try:
                os.remove(gz_file_path)
                logger.info(f"Removed existing file {filename}.")
            except Exception as e:
                logger.error(f"Error removing file {filename}: {e}")

        decompressed_filename = filename.replace('.gz', '')
        decompressed_file_path = os.path.join(path, decompressed_filename)
        if os.path.exists(decompressed_file_path):
            try:
                os.remove(decompressed_file_path)
                logger.info(f"Removed existing decompressed file {decompressed_filename}.")
            except Exception as e:
                logger.error(f"Error removing decompressed file {decompressed_filename}: {e}")

def check_and_download(url, path):
    try:
        response = requests.head(url, timeout=30)
        if response.status_code == 200:
            logger.info(f"URL {url} is reachable.")
            filename = url.split('/')[-1]
            file_path = os.path.join(path, filename)
            remove_existing_files(path, [filename])
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            logger.info(f"Downloaded {filename} successfully.")
            return file_path
        else:
            logger.critical(f"URL {url} is not reachable. Status code: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error checking or downloading {url}: {e}")
        return None

def decompress_file(file_path):
    try:
        logger.info(f"Decompressing {file_path}...")
        subprocess.run(['gunzip', file_path], check=True)
        logger.info(f"Decompressed {file_path}.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error decompressing {file_path}: {e}")

def run_python_script():
    try:
        logger.info(f"Running Python script '{python_script}' in backend.")
        script_command = ['python3', os.path.join(script_path, python_script), '--from_json']
        subprocess.Popen(script_command)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running Python script: {e}")

try:
    os.makedirs(download_path, exist_ok=True)
    for url in urls:
        file_path = check_and_download(url, download_path)
        if file_path:
            decompress_file(file_path)

    # run_python_script()

except Exception as main_exception:
    tb = traceback.extract_tb(main_exception.__traceback__)
    line_number = tb[0].lineno
    logger.error(f"An unexpected error occurred at line '{line_number}': {main_exception}")

finally:
    upload_log_to_s3(log_file_path, S3_BUCKET, S3_LOG_KEY)
