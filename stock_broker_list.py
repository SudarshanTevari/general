import csv

# Read data from the file
with open("stock_broker_raw_list.txt", "r") as file:
    lines = file.readlines()

# Define the columns for the CSV file
columns = ["Name", "E-mail", "Trade Name", "Registration No.", "Telephone", "Address", "Exchange Name", "Validity"]

# Initialize variables
data = []
current_entry = {}

# Process each line
for line in lines:
    line = line.strip()

    if line.startswith("Name"):
        # Start of a new entry
        if current_entry and current_entry.get("E-mail"):
            trade_name_from_email = current_entry["E-mail"].split("@")[0].capitalize()
            current_entry["Trade Name"] = trade_name_from_email
            data.append(current_entry)
        current_entry = {"Name": line.replace("Name", "").strip()}
    else:
        # Check the starting characters to determine the field
        if line.startswith("Registration No."):
            current_entry["Registration No."] = line[len("Registration No."):].strip()
        elif line.startswith("E-mail"):
            email = line[len("E-mail"):].lower().strip()
            if email and email not in [entry.get("E-mail", "") for entry in data]:
                current_entry["E-mail"] = email
        elif line.startswith("Telephone"):
            current_entry["Telephone"] = line[len("Telephone"):].strip()
        elif line.startswith("Address"):
            current_entry["Address"] = line[len("Address"):].strip()
        elif line.startswith("Trade Name"):
            current_entry["Trade Name"] = line[len("Trade Name"):].strip()
        elif line.startswith("Exchange Name"):
            current_entry["Exchange Name"] = line[len("Exchange Name"):].strip()
        elif line.startswith("Validity"):
            current_entry["Validity"] = line[len("Validity"):].strip()

if current_entry and current_entry.get("E-mail"):
    trade_name_from_email = current_entry["E-mail"].split("@")[0].capitalize()
    current_entry["Trade Name"] = trade_name_from_email
    data.append(current_entry)

with open("stock_broker_list.csv", "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=columns)
    
    writer.writeheader()
    
    writer.writerows(data)
