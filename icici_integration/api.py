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
    
    field_mapping = {
        "payment_order_id": "Payment Order ID",  # Pehli column
        "payment_summary_id": "Payment Summary ID",  # Dusri column
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

    rows = []
    for record in data:
        for item in record.get("line_items", []):
            row = {field_mapping.get(k, k): v for k, v in item.items()}
            rows.append(row)

    df = pd.DataFrame(rows, columns=headers)

    filename = record["name"]+"-"+ datetime.now().strftime("%Y%m%d_%H%M%S") + ".xlsx"
    file_path = f"/home/subodhbarche/Desktop/new_jfs/frappe-bench/sites/jfs_new/public/files/{filename}"

    df.to_excel(file_path, index=False)
    
    frappe.db.set_value("Payment Order", record["name"], "custom_generated_file", f"/files/{filename}")
    frappe.db.commit()

    updated_value = frappe.db.get_value("Payment Order", record["name"], "custom_generated_file")
    frappe.logger().info(f"Updated custom_generated_file: {updated_value}")  

 
    frappe.publish_realtime("refresh_payment_order", {"docname": record["name"]})

    
    return {"file_path": file_path, "file_name": filename}





 


