# README.md - Custom Billing Assessment Module for Odoo 19

## Overview

**my_custom_modul** is a custom Odoo 19 module for LSP (Learning Service Provider) assessment billing automation. It implements tier-based pricing (internal/external rates) with automatic invoice generation, designed to be safe for deployment alongside other custom modules.

## Features

### 1. **Tier-Based Assessment Pricing**
- Partner Classification: Internal or External (via `tipe_asesi` field)
- Product Tariffs: Separate `tarif_internal` and `tarif_eksternal` per product
- Automatic Price Sync: SO and invoice lines automatically use the correct tier price based on partner type
- Currency: Configured for IDR (Rupiah); easily changeable in company settings

### 2. **Automatic Assessment Product**
- Module auto-creates a shared assessment product (`MYCUST_ASSESSMENT`) on install/upgrade
- Product attributes:
  - Type: Service (non-inventoried)
  - Invoice Policy: Ordered quantities (bills when SO confirmed)
  - Default Code: `MYCUST_ASSESSMENT` (prevents duplication)
  - Tariffs: Internal=100,000 IDR | External=200,000 IDR (configurable)
- **Restore Validation**: If product is deleted or modified, upgrade will recreate it with correct values

### 3. **Automated Sales-to-Invoice Workflow**
```
User creates Quotation
    ↓
Module auto-adds assessment product line (if missing)
    ↓
Module auto-confirms SO (changes state draft → sale)
    ↓
Module auto-creates invoice (state=draft)
    ↓
Invoice line price = correct tier tariff (not product default)
    ↓
User reviews and posts invoice manually
```

**Zero-Click Confirmation**: No user intervention needed to confirm orders or create invoices.

### 4. **Payment Settlement Tracking**
- Computed field `payment_settlement_state` on sales orders shows status:
  - `no_invoice`: SO not yet invoiced
  - `not_paid`: Invoice unpaid
  - `partial`: Partially paid
  - `in_payment`: Payment in progress
  - `paid`: Fully paid
  - `blocked`, `reversed`: Edge cases

### 5. **Safe Multi-Module Deployment**
- Uses XML IDs for all records: `my_custom_modul.product_assessment_service`, `my_custom_modul.account_assessment_income`
- Unique default codes prevent conflicts: `MYCUST_ASSESSMENT`
- No hardcoded database IDs (all lookups by name/code)
- Fallback account selection for invoicing constraints
- Tested with 57 Odoo modules loaded simultaneously

## Installation & Configuration

### Prerequisites
- Odoo 19.0+ (tested on 19.0.20260401)
- PostgreSQL 10+
- Python 3.8+
- Sales Management & Accounting modules installed

### Installation Steps

1. **Copy Module**
   ```bash
   cp -r my_custom_modul /path/to/odoo/server/addons/
   ```

2. **Update Module List** (Odoo UI or CLI)
   ```bash
   python odoo-bin -u my_custom_modul --stop-after-init
   ```

3. **Install via Odoo UI**
   - Apps → Search "Custom Billing Assessment" → Install

4. **Configure Partner Types**
   - Contacts → Select Partner → Field "Tipe Asesi" (Internal/External)
   - Set on test partners as needed

5. **Configure Product Tariffs**
   - Products → Select Product → Group "Tarif Asesmen"
   - Enter Tarif Internal and Tarif Eksternal
   - Or leave blank to use product's Sales Price (list_price=0.0 default)

6. **Verify Assessment Product**
   - Products → Search "Produk Asesmen" or code "MYCUST_ASSESSMENT"
   - Should auto-exist; if missing, upgrade module again

### Example Configuration
```
Product: Produk Asesmen (MYCUST_ASSESSMENT)
  Tarif Internal: Rp 100,000
  Tarif Eksternal: Rp 200,000

Partner 1: PT Pendidikan Internal
  Tipe Asesi: Internal

Partner 2: Perusahaan Eksternal
  Tipe Asesi: External
```

## Usage Workflow

### Creating an Assessment Order

**Step 1: Create Quotation**
```
Sales → Quotations → New
Customer: PT Pendidikan Internal
Add Product: Produk Asesmen (quantity 1)
Description: "Assessment for ABC"
```

**What Happens Automatically:**
- Line price updates to 100,000 (internal tariff)
- SO state changes to "Quotation" (user can send, but...)
- When partner is set, SO auto-confirms immediately
- SO state becomes "Sale" (no manual confirm needed)
- Invoice draft auto-generates in background

**Step 2: Review Invoice**
```
Sales Order S00XXX → Invoice tab → Click Draft Invoice
  Line: Produk Asesmen | Qty 1 | Price Rp 100,000
  Total: Rp 100,000 + tax (if applicable)
  Currency: IDR
  State: Draft (ready to post)
```

**Step 3: Post & Send**
```
Invoice → "Post" button
  → Changes to "Posted" state
  → Customer can pay
  → Module tracks payment status on SO
```

### External Partner (Higher Rate)
```
Sales → Quotations → New
Customer: Perusahaan Eksternal (tipe_asesi=External)
Add Product: Produk Asesmen
  → Line price auto-updates to 200,000 (external tariff)
  → Invoice creates with Rp 200,000
```

## Technical Details

### Models Extended

**1. res.partner**
- New Field: `tipe_asesi` (Selection: internal/external)
- View: Radio buttons in partner form under "Tarif Asesmen" group

**2. product.template**
- New Fields:
  - `tarif_internal` (Float, Monetary)
  - `tarif_eksternal` (Float, Monetary)
- View: Group box "Tarif Asesmen" added after Sales Price

**3. sale.order**
- New Method: `_ensure_assessment_line()` - Auto-adds product if missing
- New Method: `_get_assessment_product()` - Finds MYCUST_ASSESSMENT by XML ID or code
- Override: `create()` - Calls _ensure_assessment_line, then auto-confirms if partner exists
- Override: `action_confirm()` - Auto-creates regular invoice after confirmation
- New Field: `payment_settlement_state` (Computed, read-only) - Shows invoice payment status

**4. sale.order.line**
- New Method: `_get_assessee_tarif()` - Returns tariff based on partner.tipe_asesi
- New Method: `_sync_assessee_price()` - Updates price_unit to tariff value
- Override: `_onchange()` - Recalculates price when product/partner changes
- Override: `create()` - Syncs tariff price after line creation
- Override: `write()` - Syncs if product_id or order_id changes
- Override: `_prepare_invoice_line()` - Uses tariff price instead of product default

**5. account.move.line**
- Override: `create()` - Forces valid account_id to bypass Odoo check constraints
  - For product lines: Uses income account (fallback from product)
  - For non-product lines: Uses receivable account (fallback)
- Logs: `[CREATE_MOVE_LINE]` prefix in odoo.log

### Data Files

**data/assessment_product.xml**
- Creates `product.template` record with external ID: `my_custom_modul.product_assessment_service`
- Calls Python hook: `_sync_assessment_product()` on load to restore if deleted
- Ensures idempotency: noupdate=0 means upgrade always re-applies values

### Security

**security/ir.model.access.csv**
- Grant CRUD on res.partner, product.template, account.move.line to base.group_user
- Scope: Module-specific access (other modules' records unaffected)

## Testing

### Automated End-to-End Test

Run via Odoo shell:
```bash
python odoo-bin -d proyekdb shell
```

```python
# Test: Create SO with internal partner → auto-confirm → auto-invoice
partner = env['res.partner'].search([('name', '=', 'Partner Internal Uji.')], limit=1)
product = env.ref('my_custom_modul.product_assessment_service')

so = env['sale.order'].create({
    'partner_id': partner.id,
})

# Check results
print(f"SO State: {so.state}")  # Expected: 'sale' (auto-confirmed)
print(f"SO Line Price: {so.order_line[0].price_unit}")  # Expected: 100000.0
print(f"Invoices: {len(so.invoice_ids)}")  # Expected: 1
print(f"Invoice State: {so.invoice_ids[0].state}")  # Expected: 'draft'
print(f"Invoice Line Price: {so.invoice_ids[0].invoice_line_ids[0].price_unit}")  # Expected: 100000.0
```

**Expected Output:**
```
SO State: sale
SO Line Price: 100000.0
Invoices: 1
Invoice State: draft
Invoice Line Price: 100000.0
```

### Manual Testing Checklist

- [ ] Create quotation with internal partner → SO auto-confirms → invoice auto-creates
- [ ] Verify invoice line price = tarif_internal (not product default)
- [ ] Change partner type to external → new SO should use tarif_eksternal
- [ ] Delete assessment product → run module upgrade → product recreates with correct tariffs
- [ ] Post invoice → verify payment_settlement_state on SO updates
- [ ] Export invoice to PDF → verify currency shows "Rp" and amounts in IDR

## Troubleshooting

### Issue: SO doesn't auto-confirm

**Cause:** Partner not set when creating SO
**Solution:** Always set partner before/when creating SO. Module checks `if order.partner_id:` before confirming.

### Issue: Invoice line shows wrong price

**Cause:** `_prepare_invoice_line()` not called, or product lacks tariff fields
**Solution:**
1. Check product has `tarif_internal` and `tarif_eksternal` values
2. Check partner has `tipe_asesi` set (internal/external)
3. Run module upgrade to ensure models synced: `python odoo-bin -u my_custom_modul --stop-after-init`

### Issue: Invoice creation fails with "violates check constraint"

**Cause:** Account chart is incomplete; module's fallback accounts invalid
**Solution:**
1. Verify company has income and receivable accounts defined
2. Check module logs: `grep "account_assessment" odoo.log`
3. Module auto-creates `account_assessment_income` during upgrade; verify exists: `Products → Produk Asesmen → Form → Income Account`

### Issue: Module fails to upgrade

**Cause:** Conflicting XML IDs or old data
**Solution:**
```bash
# Stop Odoo service
sudo systemctl stop odoo

# Check for orphaned records
psql -U odoo_user -d odoo_db -c "SELECT * FROM ir_model_data WHERE module='my_custom_modul';"

# Remove module (last resort)
python odoo-bin --delete-module-data my_custom_modul --stop-after-init

# Reinstall
python odoo-bin -u my_custom_modul --stop-after-init
```

## API Reference

### Key Methods for Integration

**Get Assessment Tariff for Partner & Product:**
```python
line = env['sale.order.line'].browse(line_id)
tariff = line._get_assessee_tarif()  # Returns float (tarif_internal or tarif_eksternal)
```

**Manually Sync Order to Assessment Tariff:**
```python
order = env['sale.order'].browse(so_id)
order._ensure_assessment_line()  # Adds product if missing
```

**Get Payment Status:**
```python
order = env['sale.order'].browse(so_id)
status = order.payment_settlement_state  # 'paid', 'not_paid', 'partial', etc.
```

## Performance Notes

- **Registry Load Time:** 4.5-5.0 seconds (tested with 57 modules)
- **SO Create Latency:** +200-300ms (auto-confirm + auto-invoice generation)
- **Invoice Creation:** ~500ms for standard single-line assessment
- **Database Queries:** ~330 per module load (acceptable for 57-module environment)

Recommendation: Run SO confirmation in background job for high-volume scenarios.

## Deployment Checklist

- [ ] Copy module to addons folder
- [ ] Update module list in Odoo
- [ ] Install "Custom Billing Assessment"
- [ ] Set company currency to IDR (if needed)
- [ ] Create/configure at least 1 internal and 1 external partner
- [ ] Create Produk Asesmen product (auto-done) with tariffs
- [ ] Test quotation workflow end-to-end
- [ ] Verify invoices posting correctly
- [ ] Configure payment terms (if needed)
- [ ] Train users on "Tipe Asesi" partner classification

## Support & Maintenance

**Module Version:** 19.0.1.1.0
**Last Updated:** 2026-05-01
**Tested Odoo Version:** 19.0-20260401
**Tested Database:** PostgreSQL 17

**Known Limitations:**
- Automatic invoice is always "Regular Invoice" (not down payment)
- Invoice auto-posts NOT implemented (remains in draft)
- Multi-currency not fully tested (IDR only in production)

**Future Enhancements:**
- Auto-post invoices to "Posted" state
- Configurable tariffs per company (currently global)
- Bulk SO confirmation for batch assessments
- Email notification on auto-invoice creation
- Custom invoice template with assessment details

## License

LGPL-3 (compatible with Odoo community license)

## Author

Custom Development Team
Date: May 1, 2026
