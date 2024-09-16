import logging, traceback, os, sys, json, argparse, time
from logging_file import logger, upload_log_to_s3, time_formatting, update_timestamp_of_script_execution
from datetime import datetime
from pycrtsh import Crtsh
from collections import defaultdict
from database_configuration import AssetTable, asset_table_session
from email_conf import send_email, send_email_to_client

log_file_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file_name = f'{log_file_timestamp}_ssl_certificate_logfile.log'
log_file_path = f'/home/ubuntu/log_files/asset_logs/{log_file_name}'
S3_BUCKET = '20231103_application_data'
S3_LOG_KEY = f'app_log/asset_logs/{log_file_name}'

logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(log_file_path, mode="a+")
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)-10s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
logger.addHandler(file_handler)

parser = argparse.ArgumentParser()
parser.add_argument('domain', help='Domain name')
parser.add_argument('--log', action='store_true', help='Print log messages to the terminal')
parser.add_argument('--force_run', action='store_true', help='Force script execution even if data exists in the database')
parser.add_argument('--send_email', action='store_true', help='Send email after completion.')
parser.add_argument('--is_cronjob', action='store_true', help='Update cronjob log database.')
args = parser.parse_args()

if not args.domain:
    parser.error(f'You must provide domain name. Example <python3 {os.path.basename(__file__)} example.com>')
    sys.exit(1)

if args.log:
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)-10s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(stream_handler)

domain = args.domain
mail_to_client = False
start_time = datetime.now()

######################################################################################
## Script to get only one latest ssl certificate related to each domain / subdomain ##
######################################################################################

def check_data_existencein_db(domain):
    exists = asset_table_session.query(AssetTable).filter_by(domain=domain, discovered_by="pycrtsh").first()
    return exists is not None

def invoke_crt_module(domain, mail_to_client, start_time):
    try:
        start_ssl_block = time.time()
        logger.report(f"Start of SSL certificate block for {domain}.")

        c = Crtsh()
        crt_raw_output = c.search(domain)
        logger.info(f"Raw output: \n{crt_raw_output}")
        result = []
        latest_certs = defaultdict(lambda: {'logged_at': datetime(1970, 1, 1)})

        for item in crt_raw_output:
            names = item["name"].split("\n")
            logged_at = item["logged_at"]
            expiry_date = item["not_after"]

            if len(names) > 1:
                for name in names:
                    new_item = item.copy()
                    new_item["name"] = name
                    new_item["expiry_timestamp"] = expiry_date
                    result.append(new_item)
                    if logged_at > latest_certs[name]["logged_at"]:
                        latest_certs[name] = new_item
            else:
                result.append(item)
                if logged_at > latest_certs[item["name"]]["logged_at"]:
                    latest_certs[item["name"]] = item

        filtered_result = list(latest_certs.values())

        def custom_json_encoder(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

        final_results_in_json = json.dumps(filtered_result, default=custom_json_encoder, indent=4)

        data_for_name = json.loads(final_results_in_json)
        names = [entry["name"] for entry in data_for_name]
        crt_details = [(entry["name"], entry["not_after"]) for entry in data_for_name]

        for crt_detail in crt_details:
            value_type = 'SSL_Certificate'
            value_name = crt_detail[0]
            crt_expiry_date = crt_detail[1][:10]
            current_date = datetime.now()
            discovered_by_project = "pycrtsh"
            existing_asset = asset_table_session.query(AssetTable).filter_by(domain=domain, value_type=value_type, value_name=value_name).first()

            if existing_asset is None:
                crt_adding_query = AssetTable(
                    domain=domain,
                    value_type=value_type,
                    value_name=value_name,
                    expiry_date=crt_expiry_date,
                    discovered_date=current_date,
                    discovered_by=discovered_by_project
                )
                asset_table_session.merge(crt_adding_query)
                asset_table_session.commit()
                logger.info(f"Added asset '{value_name}' of '{domain}' to database.")
            else:
                old_date = existing_asset.expiry_date

                if existing_asset.expiry_date != crt_expiry_date:
                    existing_asset.expiry_date = crt_expiry_date
                    asset_table_session.commit()
                    logger.info(f"Updated expiary date of '{value_name}' of {domain} from '{old_date}' to '{crt_expiry_date}'.")
                else:
                    logger.info(f"Asset {value_name} of {domain} is already present in database.")

        end_ssl_block = time.time()
        ssl_block = end_ssl_block - start_ssl_block
        final_ssl_time = time_formatting(ssl_block)
        logger.report(f"End of SSL certificate block for {domain}, total time taken is {final_ssl_time}")

        if args.send_email:
            send_completion_email(domain, mail_to_client, final_ssl_time)
        if args.is_cronjob:
            end_time = datetime.now()
            todays_date = datetime.now().date()
            todays_count_query = asset_table_session.query(AssetTable).filter(AssetTable.discovered_date == todays_date, AssetTable.domain == domain, AssetTable.discovered_by == 'pycrtsh').count()
            log_description = f"SSL Certificate script discovered {todays_count_query} SSL Certificate."

        update_timestamp_of_script_execution(domain, 'asset_discovery')

    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)
        line_number = tb[0].lineno
        error_message = f"An error occurred in the '{os.path.basename(__file__)}' script at line {line_number} and the error is: {e}"
        logger.error(error_message)
        subject = f"ERROR - Asset - An error occured in '{os.path.basename(__file__)}' file."
        send_email(subject, error_message, importance=True)
        if args.is_cronjob:
            end_time = datetime.now()
            log_description = f"An error occured in SSL Certificate at line {line_number}."

def send_completion_email(domain, mail_to_client, final_ssl_time):
    todays_date = datetime.now().date()
    ssl_list = ""

    new_ssl_discovered_count = asset_table_session.query(AssetTable).filter(AssetTable.domain == domain, AssetTable.discovered_by == 'pycrtsh', AssetTable.discovered_date == todays_date).count()

    if new_ssl_discovered_count == 0:
        discovered_ssl_statement = "No new SSL certificates discovered."
    else:
        mail_to_client = True
        new_ssl_discovered = asset_table_session.query(AssetTable).filter(AssetTable.domain == domain, AssetTable.discovered_by == 'pycrtsh', AssetTable.discovered_date == todays_date).all()
        for item in new_ssl_discovered:
            ssl_list += f"Asset Type: {item.value_type}<br>"
            ssl_list += f"Asset Name: {item.value_name}<br>"
            ssl_list += f"Discovered Date: {item.discovered_date}<br>"
            ssl_list += "<br>"

        discovered_ssl_statement = f"Total time taken is {final_ssl_time} and new SSL certificates discovered are: {new_ssl_discovered_count}<br><br>{ssl_list}"

    subject = f"INFO - Asset - SSL certificates script sucessfully executed for '{domain}'"
    body_content = f'''
    <p>{discovered_ssl_statement}</p>

    <br><br><br>
    <p>Thank you.</p>
    '''
    send_email(subject, body_content, importance=False)
    logger.info("Update mail sent.")

    if mail_to_client:
        client_msg_subject = "New SSL Certificate discovered!."
        client_msg_body = f"We have discovered {new_ssl_discovered_count} new ssl certificate/s.<br><br>{ssl_list}"
        send_email_to_client(domain, client_msg_subject, client_msg_body)
        logger.info("Mail sent to clients email.")

try:
    if not args.force_run and check_data_existencein_db(domain):
        logger.info(f"SSL Certificate data for {domain} already exists in the database. Skipping {os.path.basename(__file__)} execution.")
    else:
        invoke_crt_module(domain, mail_to_client, start_time)

except Exception as main_exception:
    tb = traceback.extract_tb(main_exception.__traceback__)
    line_number = tb[0].lineno
    logger.error(f"An unexpected error occurred at line '{line_number}': {main_exception}")

finally:
    upload_log_to_s3(log_file_path, S3_BUCKET, S3_LOG_KEY)
