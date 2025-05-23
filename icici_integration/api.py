import frappe
import pandas as pd
import os
from datetime import datetime
import re
from frappe.utils.file_manager import save_file
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
import json
import xlwt
from frappe.utils.password import get_decrypted_password
import paramiko
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from .email_utils import EmailSender
import xlwt
from frappe import _




@frappe.whitelist(allow_guest=True)
def vulnerable_api(user_input=None):
   
    if not user_input:
        user_input = frappe.local.form_dict.get('user_input')
    query = f"SELECT name FROM `tabUser` WHERE email = '{user_input}'"
    result = frappe.db.sql(query)
    return [r[0] for r in result]



# @frappe.whitelist(allow_guest=True)
# def vulnerable_api(user_input):
    
#     query = f"SELECT name FROM `tabUser` WHERE email = '{user_input}'"
#     result = frappe.db.sql(query)
#     return [r[0] for r in result]




@frappe.whitelist()
def generate_excel_for_folder(payment_order_id=None):


    filters = {"docstatus": 1}  
    if payment_order_id:
        payment_order_id = payment_order_id
        
        filters["name"] = payment_order_id  
    data = frappe.get_all(
        "Payment Order",
        filters= filters,
        fields=["name", "company_bank_account"]  
    )

    for i in data:
       
        i["debit_ac_no"] = ""
        if i.get("company_bank_account"):
            bank_acc_details = frappe.db.get_value(
                "Bank Account", i["company_bank_account"], ["bank_account_no"], as_dict=True
            )
            i["debit_ac_no"] = bank_acc_details.get("bank_account_no", "") if bank_acc_details else ""

        line_items = frappe.get_all(
            "Payment Order Summary",
            filters={"parent": i["name"]},
            fields=["name", "payment_date", "amount", "mode_of_transfer", "bank_account", "party", "account", "custom_remarks"]
        )

        for item in line_items:
            item["payment_order_id"] = i["name"]  
            item["payment_summary_id"] = item["name"]
            item["debit_ac_no"] = i["debit_ac_no"]  



            
            if item.get("bank_account"):
                bank_details = frappe.db.get_value(
                    "Bank Account", item["bank_account"], ["bank_account_no", "account_name", "ifsc"], as_dict=True
                )
                if bank_details:
                    item["beneficiary_ac_no"] = bank_details.get("bank_account_no", "")
                    item["beneficiary_name"] = bank_details.get("account_name", "")
                    item["ifs"] = bank_details.get("ifsc", "")

           
            if item.get("party"):
                supplier_details = frappe.db.get_value(
                    "Supplier", item["party"], ["email_id", "primary_address"], as_dict=True
                )
                if supplier_details:
                    item["beneficiary_email_id"] = supplier_details.get("email_id", "")
                    
                    raw_address = supplier_details.get("primary_address", "")
                    clean_address = BeautifulSoup(raw_address, "html.parser").get_text().strip().replace("\n", " ") if raw_address else ""
                    item["beneficiary_address_1"] = clean_address

            
            if item.get("account"):
                account_details = frappe.db.get_value(
                    "Account", item["account"], ["company"], as_dict=True
                )
                if account_details:
                    company_name = account_details.get("company", "")
                    
                    if company_name:
                        company_details = frappe.db.get_value(
                            "Company", company_name, ["custom_registered_address"], as_dict=True
                        )
                        if company_details:
                            address_id = company_details.get("custom_registered_address")
                            
                            if address_id:
                                address_details = frappe.db.get_value(
                                    "Address", address_id, ["address_line1", "address_line2", "city", "state", "country", "pincode"], as_dict=True
                                )
                                if address_details:
                                    combined_address = " ".join([
                                        address_details.get("address_line1", ""),
                                        address_details.get("address_line2", ""),
                                        address_details.get("city", ""),
                                        address_details.get("state", ""),
                                        address_details.get("country", ""),
                                        address_details.get("pincode", "")
                                    ])
                                    item["addd_details_1"] = combined_address.strip()

           
            item["Payable Location"] = ""
            item["Print Location"] = ""
            item["Bene Mobile No."] = ""
            item["Bene add2"] = ""
            item["Bene add3"] = ""
            item["Bene add4"] = ""
            item["Add Details 2"] = ""
            item["Add Details 3"] = ""
            item["Add Details 4"] = ""
            item["Add Details 5"] = ""
            

        i["line_items"] = line_items  

    return generate(data, payment_order_id)

def generate(data, payment_order_id=None):
    doc = frappe.get_single("Email Configuration")
    smtp_server = doc.smtp_server
    username = doc.username
    port = doc.port
    password = get_decrypted_password(
        doctype='Email Configuration',
        name='Email Configuration',
        fieldname='password'
    )


    email = frappe.db.get_value("User", frappe.session.user, "email")

    email_sender = EmailSender(smtp_server, port, username, password)
    


    field_mapping = {
        "payment_order_id": "Payment Order ID",
        "payment_summary_id": "Payment Summary ID",
        "debit_ac_no": "Debit Ac No",
        "beneficiary_ac_no": "Beneficiary Ac No",
        "beneficiary_name": "Beneficiary Name",
        "amount": "Amount",
        "mode_of_transfer": "Pay Mode",
        "payment_date": "Date",
        "ifs": "IFS Code",
        "Payable Location": "Payable Location",
        "Print Location": "Print Location",
        "Bene Mobile No.": "Bene Mobile No.",
        "beneficiary_email_id": "Bene Email ID",
        "beneficiary_address_1": "Bene add1",
        "Bene add2": "Bene add2",
        "Bene add3": "Bene add3",
        "Bene add4": "Bene add4",
        "addd_details_1": "Add Details 1",
        "Add Details 2": "Add Details 2",
        "Add Details 3": "Add Details 3",
        "Add Details 4": "Add Details 4",
        "Add Details 5": "Add Details 5",
        "custom_remarks": "Remarks",
    }

    headers = list(field_mapping.values())
    wb = xlwt.Workbook()
    ws = wb.add_sheet("Sheet1")

  
    for col, header in enumerate(headers):
        ws.write(0, col, header)

    rows = []
    for record in data:
        for item in record.get("line_items", []):
            row = {field_mapping.get(k, k): v for k, v in item.items()}
            rows.append(row)

    
    for row_idx, row_data in enumerate(rows, start=1):
        for col_idx, header in enumerate(headers):
            value = row_data.get(header)
            if header == "Date" and value:
                try:
                    
                    value = datetime.strptime(value, "%Y-%m-%d").strftime("%d-%m-%Y")
                except:
                    pass
            ws.write(row_idx, col_idx, str(value) if value is not None else "")

    #filename = record["name"] + "-" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".xls"
    filename = record["name"] + ".xls"
    file_path = f"/home/subodhbarche/Desktop/new_jfs/frappe-bench/sites/jfs_new/public/files/{filename}"

    wb.save(file_path)

    frappe.db.set_value("Payment Order", record["name"], "custom_generated_file", f"/files/{filename}")
    frappe.db.commit()
    frappe.logger().info(f"Updated custom_generated_file: /files/{filename}")
    frappe.publish_realtime("refresh_payment_order", {"docname": record["name"]})


    #********File upload start*********************


    doc = frappe.get_single("Snorkal Configuration")
    ip_address = doc.ip_address
    username = doc.username
    password = get_decrypted_password(
        doctype='Snorkal Configuration',
        name='Snorkal Configuration',
        fieldname='password'
    )

    if not all([ip_address, username, password]):
        frappe.throw("SFTP configuration is incomplete. Please ensure the IP address, username, and password are correctly set in Snorkal Configuration.")

    file_name = os.path.basename(file_path)
    #remote_path = os.path.join("/home/snorkal/inBound", file_name)
    remote_path = os.path.join("/blkprodfile/subodh",file_name)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(hostname=ip_address, username=username, password=password)
        sftp = ssh.open_sftp()
        sftp.put(file_path, remote_path)
        sftp.close()
        ssh.close()
        frappe.logger().info(f"SFTP upload successful: {remote_path}")
        subject = "SFTP Upload Successful"
        body = """
            Dear User,

            Your file has been successfully uploaded to the SFTP server.

            No issues were encountered during the process.

            If you have any further queries or need assistance, feel free to contact the IT support team.

            Regards,  
            IT Support Team
            """
        email_sender.send_email(email, subject, body)
        # email_sender.send_email(email, "SFTP upload successful", "File Uploaded successfully")

    except paramiko.AuthenticationException:
        subject = "SFTP Authentication Failed - Invalid Credentials"
        body = """
            Dear User,

            This is to inform you that the authentication attempt to the SFTP server has failed due to invalid credentials.

            Please verify that the username and password you have provided are correct.

            If the issue persists, kindly reach out to the system administrator or support team for assistance.

            Regards,  
            IT Support Team
            """
        email_sender.send_email(email, subject, body)
        # email_sender.send_email(email, "SFTP Authentication Failed. Invalid username or password.", "Authentication failed while connecting to the SFTP server. Please verify the username and password.")

        frappe.logger().error("SFTP authentication failed. Invalid username or password.")
        frappe.throw("Authentication failed while connecting to the SFTP server. Please verify the username and password.")

    except paramiko.SSHException as e:
        frappe.logger().error(f"SSH connection error: {e}")
        email_sender.send_email(email, "SSH error occurred", "An SSH error occurred while trying to connect to the SFTP server. Please check the server status and network connection.")
        frappe.throw("An SSH error occurred while trying to connect to the SFTP server. Please check the server status and network connection.")

    except FileNotFoundError as e:
        frappe.logger().error(f"File not found: {e}")
        email_sender.send_email(email, "File not found", "The specified file was not found. Please verify that the file path is correct.")
        frappe.throw("The specified file was not found. Please verify that the file path is correct.")

    except Exception as e:
        frappe.logger().error(f"Unexpected error during SFTP upload: {e}")
        email_sender.send_email(email, "Unexpected error occurred", "An unexpected error occurred during the SFTP upload. Please check the logs for more details")
        frappe.throw("An unexpected error occurred during the SFTP upload. Please check the logs for more details.")






@frappe.whitelist()
def send_email(payment_order_id=None):  
    #smtp_server = "smtp.office365.com"
    smtp_server= "email.cloverinfotech.com"
    smtp_port = 587
    smtp_user = "adnan.shaikh@cloverinfotech.com"
    smtp_password = "Clover@10"

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = "subodh.barche@cloverinfotech.com"
    msg["Subject"] = f"Test Email"

    body = f"This is a test email for Payment Order"
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(msg["From"], msg["To"], msg.as_string())
            return f"Email sent successfully to {msg['To']}"
    except Exception as e:
        frappe.throw(f"Failed to send email: {e}")





# @frappe.whitelist()
# def send_email():
        
#         smtp_server = "smtp.office365.com"
#         smtp_port = 587
#         smtp_user = "subodh.barche@cloverinfotech.com"
#         smtp_password = "54321#clover"

#         msg = MIMEMultipart()
#         msg["From"] = "subodh.barche@cloverinfotech.com"
#         msg["To"] = "rahul.pawar@cloverinfotech.com"
#         msg["Subject"] = "Test"

#         body = "This is a test email."
#         msg.attach(MIMEText(body, "plain"))

#         try:
#             with smtplib.SMTP(smtp_server, smtp_port) as server:
#                 server.starttls()
#                 server.login(smtp_user, smtp_password)
#                 server.sendmail(from_address, to_address, msg.as_string())
#                 print("Email sent successfully!")
#         except Exception as e:
#             print(f"Failed to send email: {e}")



 


