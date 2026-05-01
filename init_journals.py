#!/usr/bin/env python3
"""
Script to initialize sales and general journals via Odoo XML-RPC API
Run this after Odoo is running
"""

import xmlrpc.client as xmlrpc

# Odoo connection details
ODOO_URL = "http://localhost:8069"
DB_NAME = "proyekdb"
USERNAME = "admin"
PASSWORD = "admin"

# Connect to Odoo
common = xmlrpc.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
models = xmlrpc.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')

print("[*] Authenticating...")
uid = common.authenticate(DB_NAME, USERNAME, PASSWORD, {})
if not uid:
    print("[ERROR] Authentication failed!")
    exit(1)

print(f"[+] Authenticated as user ID: {uid}")

# Create Sales Journal
print("[*] Creating Sales Journal...")
try:
    journal_data = {
        'name': 'Customer Invoices',
        'code': 'INV',
        'type': 'sale',
        'company_id': 1,
        'active': True,
    }
    sales_journal_id = models.execute_kw(DB_NAME, uid, PASSWORD, 'account.journal', 'create', [journal_data])
    print(f"[+] Sales Journal created: ID {sales_journal_id}")
except Exception as e:
    print(f"[ERROR] Failed to create sales journal: {e}")

# List journals
print("\n[*] Listing journals...")
try:
    journals = models.execute_kw(DB_NAME, uid, PASSWORD, 'account.journal', 'search_read', 
                                  [['company_id', '=', 1]], {'fields': ['id', 'name', 'code', 'type']})
    for j in journals:
        print(f"  - {j['name']} ({j['code']}) - Type: {j['type']}")
except Exception as e:
    print(f"[ERROR] Failed to list journals: {e}")

print("[+] Done!")
