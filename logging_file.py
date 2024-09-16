import logging
import boto3
from botocore.exceptions import NoCredentialsError, ClientError

# Define the new log level
REPORT = 25  # You can choose any integer value not used by other levels

# Add the new log level to the logging module
logging.addLevelName(REPORT, 'REPORT')

# Create a custom logger
logger = logging.getLogger(__name__)

# Create a custom log function for the new level
def report(self, message, *args, **kwargs):
    if self.isEnabledFor(REPORT):
        self._log(REPORT, message, args, **kwargs)

# Add the custom log function to the logger
logging.Logger.report = report

def upload_log_to_s3(log_file_path, s3_bucket, s3_log_key):
    try:
        s3_client = boto3.client('s3')
        s3_client.upload_file(log_file_path, s3_bucket, s3_log_key)
        logger.info(f"Successfully uploaded {log_file_path} to s3://{s3_bucket}/{s3_log_key}")
    except FileNotFoundError:
        logger.error(f"Log file not found: {log_file_path}")
    except NoCredentialsError:
        logger.error("AWS credentials not available")
    except ClientError as e:
        logger.error(f"Error occurred while uploading to S3: {e}")
